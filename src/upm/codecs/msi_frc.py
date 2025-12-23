"""MSI `.frc` codec (import + export) for UPM v0.1.1.

Supported parse/export subset (v0.1.1):
- `#atom_types`
- `#quadratic_bond`
- `#quadratic_angle`
- `#nonbond(12-6)` with:
  - `@type A-B`
  - `@combination geometric`

Everything else is preserved losslessly (as raw text lines) as an **ordered**
list of raw sections, suitable for deterministic roundtrips:

- each entry is `{"header": "<exact header line>", "body": ["<line>", ...]}`
- `header` is the exact section header line including leading `#` (no trailing newline)
- `body` contains body lines only (exclude the header), each stored exactly as in file
  (no trailing newline)
- text before the first real `#...` section is preserved as a synthetic section
  with `header="#preamble"`.

Export writes supported sections first (in a fixed order). Raw/unknown sections
are **omitted by default** and are included only when `include_raw=True`; when
included they are emitted in preserved encounter order (deterministic).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from upm.core.tables import normalize_tables
from upm.core.validate import validate_tables

# Import internal helpers from private modules
from upm.codecs._frc_parser import (
    _build_tables,
    _coerce_unknown_sections,
    _parse_atom_types,
    _parse_bond_increments,
    _parse_nonbond_12_6,
    _parse_quadratic_angle,
    _parse_quadratic_bond,
    _split_sections,
)
from upm.codecs._frc_writer import (
    _format_atom_types_section,
    _format_nonbond_12_6_section_from_atom_types,
    _format_quadratic_angle_section,
    _format_quadratic_bond_section,
    _require_df,
)


# ----------------------------
# Public API
# ----------------------------


def parse_frc_text(
    text: str,
    *,
    validate: bool = True,
) -> tuple[dict[str, "Any"], list[dict[str, Any]]]:
    """Parse MSI `.frc` text into canonical UPM tables + raw/unknown section blobs.

    Args:
        text: The raw FRC file content as a string.
        validate: If True (default), validate tables after parsing. Set to False
            to parse files with duplicate entries or other validation issues.

    Returns:
        (tables, unknown_sections)

    Where:
        - `tables` are canonicalized + sorted deterministically.
        - `unknown_sections` is an ordered list of raw sections:
          `{"header": str, "body": list[str]}` (see module docstring).

    Notes:
        - Returned tables are normalized (canonicalized dtypes + sorting).
        - When validate=True (default), tables are validated via `validate_tables()` (v0.1 strict).
    """
    if not isinstance(text, str):
        raise TypeError(f"parse_frc_text: expected str, got {type(text).__name__}")

    sections, unknown_sections = _split_sections(text)

    atom_types_rows: list[dict[str, Any]] = []
    bonds_rows: list[dict[str, Any]] = []
    angles_rows: list[dict[str, Any]] = []
    bond_increments_rows: list[dict[str, Any]] = []

    # nonbond map: atom_type -> (lj_a, lj_b)
    nonbond_params: dict[str, tuple[float, float]] = {}

    for header_raw, body_lines in sections:
        # Section header may contain extra tokens (eg "#quadratic_angle cvff_auto").
        header_tokens = header_raw.strip().split()
        header_key = header_tokens[0].lower() if header_tokens else ""
        header_suffix = " ".join(header_tokens[1:]).strip() if len(header_tokens) > 1 else None
        if header_suffix == "":
            header_suffix = None

        if header_key == "#atom_types":
            atom_types_rows.extend(_parse_atom_types(body_lines))
        elif header_key == "#quadratic_bond":
            bonds_rows.extend(_parse_quadratic_bond(body_lines, source_default=header_suffix))
        elif header_key == "#quadratic_angle":
            angles_rows.extend(_parse_quadratic_angle(body_lines, source_default=header_suffix))
        elif header_key == "#nonbond(12-6)":
            nb = _parse_nonbond_12_6(body_lines)
            # merge; last one wins deterministically by file order
            nonbond_params.update(nb)
        elif header_key == "#bond_increments":
            bond_increments_rows.extend(_parse_bond_increments(body_lines))
        else:
            # Unknown/unsupported section: preserve in encounter order, body-only.
            unknown_sections.append({"header": header_raw, "body": list(body_lines)})

    tables = _build_tables(
        atom_types_rows, bonds_rows, angles_rows, nonbond_params,
        bond_increments_rows=bond_increments_rows if bond_increments_rows else None,
    )

    # Normalize for deterministic downstream behavior.
    tables_norm = normalize_tables(tables)
    
    # Validate only if requested (default True for backwards compatibility).
    if validate:
        validate_tables(tables_norm)
    
    return tables_norm, unknown_sections


def read_frc(
    path: str | Path,
    *,
    validate: bool = True,
) -> tuple[dict[str, "Any"], list[dict[str, Any]]]:
    """Read an MSI `.frc` file from disk and parse.
    
    Args:
        path: Path to the .frc file.
        validate: If True (default), validate tables after parsing. Set to False
            to parse files with duplicate entries or other validation issues.
    
    Returns:
        (tables, unknown_sections) tuple.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_frc_text(text, validate=validate)


# Minimal FRC header required by msi2lmp.exe
_MINIMAL_FRC_PREAMBLE = """\
!BIOSYM forcefield          1

#version cvff.frc	1.0	01-Jan-00

#define cvff

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
 1.0   1    atom_types				cvff
 1.0   1    quadratic_bond			cvff
 1.0   1    quadratic_angle			cvff
 1.0   1    nonbond(12-6)			cvff
"""


def write_frc(
    path: str | Path,
    *,
    tables: dict[str, "Any"],
    unknown_sections: Any | None = None,
    include_raw: bool = False,
    mode: str = "full",
) -> None:
    """Write an MSI `.frc` file.

    v0.1.1 behavior:
    - `mode` is accepted for API stability, but `full` and `minimal` behave the same:
      write whatever rows exist in the provided tables (resolver logic is out of scope).
    - raw/unknown sections are **omitted by default**. If `include_raw=True`, they are
      appended in deterministic encounter order (as stored).
    - A minimal BIOSYM header is ALWAYS emitted if no preamble is provided, as
      msi2lmp.exe requires the `!BIOSYM forcefield 1` line and `#define cvff` block.
    """
    if mode not in {"full", "minimal"}:
        raise ValueError("write_frc: mode must be 'full' or 'minimal'")

    # Normalize for stable ordering/column layout, but validate only the tables we emit.
    # (Callers may supply a subset table set for "minimal export".)
    norm_tables = normalize_tables(tables)

    lines: list[str] = []

    # Check if we have a preamble in the raw sections
    raw_sections = _coerce_unknown_sections(unknown_sections) if include_raw else []
    has_preamble = False
    for item in raw_sections:
        if item.get("header") == "#preamble":
            preamble_body = item.get("body", [])
            if preamble_body:
                lines.extend([str(x) for x in preamble_body])
                has_preamble = True
            break
    
    # If no preamble was found, emit a minimal FRC header
    # This is required for msi2lmp.exe compatibility
    if not has_preamble:
        lines.extend(_MINIMAL_FRC_PREAMBLE.strip().split("\n"))
        lines.append("")  # Blank line after preamble

    # ---- supported sections (fixed order) ----
    if "atom_types" in norm_tables and norm_tables["atom_types"] is not None:
        df = _require_df(norm_tables["atom_types"], table="atom_types")
        lines.extend(_format_atom_types_section(df))

    if "bonds" in norm_tables and norm_tables["bonds"] is not None:
        df = _require_df(norm_tables["bonds"], table="bonds")
        lines.extend(_format_quadratic_bond_section(df))

    if "angles" in norm_tables and norm_tables["angles"] is not None:
        df = _require_df(norm_tables["angles"], table="angles")
        lines.extend(_format_quadratic_angle_section(df))

    # For v0.1 export, we emit nonbond parameters from atom_types (lj_a/lj_b).
    if "atom_types" in norm_tables and norm_tables["atom_types"] is not None:
        df = _require_df(norm_tables["atom_types"], table="atom_types")
        lines.extend(_format_nonbond_12_6_section_from_atom_types(df))

    # ---- raw/unknown sections (encounter order; only if requested) ----
    # We already emitted the preamble body (header "#preamble") above; skip it here.
    if include_raw:
        for item in raw_sections:
            if item.get("header") == "#preamble":
                continue
            header = item["header"]
            body = item["body"]
            lines.append(str(header))
            lines.extend([str(x) for x in body])

    # Ensure file ends with newline. Use newline="" to prevent newline translation.
    out_text = "\n".join(lines) + "\n"
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write(out_text)
