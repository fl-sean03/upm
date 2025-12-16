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

import re
from pathlib import Path
from typing import Any

from upm.core.tables import TABLE_COLUMN_ORDER, normalize_tables
from upm.core.validate import validate_tables

# Raw sections are stored as ordered dict entries:
#   {"header": str, "body": list[str]}
# This preserves encounter order and supports duplicate headers.

# ----------------------------
# Public API
# ----------------------------


def parse_frc_text(text: str) -> tuple[dict[str, "Any"], list[dict[str, Any]]]:
    """Parse MSI `.frc` text into canonical UPM tables + raw/unknown section blobs.

    Returns:
        (tables, unknown_sections)

    Where:
        - `tables` are canonicalized + sorted deterministically.
        - `unknown_sections` is an ordered list of raw sections:
          `{"header": str, "body": list[str]}` (see module docstring).

    Notes:
        - Returned tables are normalized (canonicalized dtypes + sorting).
        - Returned tables are validated via `validate_tables()` (v0.1 strict).
    """
    if not isinstance(text, str):
        raise TypeError(f"parse_frc_text: expected str, got {type(text).__name__}")

    sections, unknown_sections = _split_sections(text)

    atom_types_rows: list[dict[str, Any]] = []
    bonds_rows: list[dict[str, Any]] = []
    angles_rows: list[dict[str, Any]] = []

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
            bonds_rows.extend(_parse_quadratic_bond(body_lines))
        elif header_key == "#quadratic_angle":
            angles_rows.extend(_parse_quadratic_angle(body_lines, source_default=header_suffix))
        elif header_key == "#nonbond(12-6)":
            nb = _parse_nonbond_12_6(body_lines)
            # merge; last one wins deterministically by file order
            nonbond_params.update(nb)
        else:
            # Unknown/unsupported section: preserve in encounter order, body-only.
            unknown_sections.append({"header": header_raw, "body": list(body_lines)})

    tables = _build_tables(atom_types_rows, bonds_rows, angles_rows, nonbond_params)

    # Normalize + validate for deterministic downstream behavior.
    tables_norm = normalize_tables(tables)
    validate_tables(tables_norm)
    return tables_norm, unknown_sections


def read_frc(path: str | Path) -> tuple[dict[str, "Any"], list[dict[str, Any]]]:
    """Read an MSI `.frc` file from disk and parse."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_frc_text(text)


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
    """
    if mode not in {"full", "minimal"}:
        raise ValueError("write_frc: mode must be 'full' or 'minimal'")

    # Normalize for stable ordering/column layout, but validate only the tables we emit.
    # (Callers may supply a subset table set for "minimal export".)
    norm_tables = normalize_tables(tables)

    lines: list[str] = []

    # If requested, emit the original preamble lines (text before the first real `#...`
    # section header) before any supported sections.
    raw_sections = _coerce_unknown_sections(unknown_sections) if include_raw else []
    for item in raw_sections:
        if item.get("header") == "#preamble":
            lines.extend([str(x) for x in item.get("body", [])])

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


# ----------------------------
# Parsing helpers
# ----------------------------


_SECTION_HEADER_RE = re.compile(r"^\s*#")


def _split_sections(text: str) -> tuple[list[tuple[str, list[str]]], list[dict[str, Any]]]:
    """Split `.frc` text into (header, body_lines) blocks.

    Returns:
        (sections, unknown_sections_seed)

    Notes:
        - `sections` includes *only* lines that are inside a `#...` section.
        - Text before the first section is preserved as a synthetic raw section
          with `header="#preamble"` for lossless roundtrips.
    """
    lines = text.splitlines()

    sections: list[tuple[str, list[str]]] = []
    unknown: list[dict[str, Any]] = []

    current_header: str | None = None
    current_body: list[str] = []

    preamble: list[str] = []
    i = 0
    while i < len(lines) and not _SECTION_HEADER_RE.match(lines[i]):
        preamble.append(lines[i])
        i += 1
    if preamble:
        unknown.append({"header": "#preamble", "body": preamble})

    for line in lines[i:]:
        if _SECTION_HEADER_RE.match(line):
            # flush previous
            if current_header is not None:
                sections.append((current_header, current_body))
            current_header = line  # exact header line (no newline)
            current_body = []
        else:
            if current_header is None:
                # Shouldn't happen due to preamble handling, but keep safe.
                if unknown and unknown[0].get("header") == "#preamble":
                    unknown[0]["body"].append(line)
                else:
                    unknown.insert(0, {"header": "#preamble", "body": [line]})
            else:
                current_body.append(line)

    if current_header is not None:
        sections.append((current_header, current_body))

    return sections, unknown


def _coerce_unknown_sections(obj: Any | None) -> list[dict[str, Any]]:
    """Coerce raw sections input into canonical ordered list form.

    Accepts:
      - None -> []
      - list[{"header": str, "body": list[str]}] (canonical)
      - legacy dict[str, list[str]] (converted deterministically by sorted header)

    Raises:
        TypeError/ValueError for invalid shapes.
    """
    if obj is None:
        return []
    if isinstance(obj, dict):
        # Legacy mapping format: deterministic by sorted header.
        out: list[dict[str, Any]] = []
        for h in sorted(obj.keys()):
            body = obj[h]
            if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
                raise ValueError("unknown_sections: expected dict[str, list[str]] (legacy format)")
            out.append({"header": str(h), "body": list(body)})
        return out
    if isinstance(obj, list):
        out2: list[dict[str, Any]] = []
        for i, item in enumerate(obj):
            if not isinstance(item, dict):
                raise ValueError(f"unknown_sections[{i}]: expected object with 'header' and 'body'")
            if "header" not in item or "body" not in item:
                raise ValueError(f"unknown_sections[{i}]: missing 'header' or 'body'")
            header = item["header"]
            body = item["body"]
            if not isinstance(header, str):
                raise ValueError(f"unknown_sections[{i}].header: expected str")
            if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
                raise ValueError(f"unknown_sections[{i}].body: expected list[str]")
            out2.append({"header": header, "body": list(body)})
        return out2
    raise TypeError(f"unknown_sections: expected list or dict, got {type(obj).__name__}")


def _strip_inline_comment(s: str) -> str:
    # Treat ';' as comment leader if present (common in some FF formats).
    # Keep conservative: if not present, return as-is.
    if ";" in s:
        return s.split(";", 1)[0].rstrip()
    return s.rstrip()


def _is_ignorable_line(line: str) -> bool:
    s = line.strip()
    return (not s) or s.startswith("!") or s.startswith(";") or s.startswith("#")


def _parse_atom_types(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        toks = line.split()
        if len(toks) < 1:
            continue

        atom_type = toks[0]
        element = toks[1] if len(toks) >= 2 else None
        mass = float(toks[2]) if len(toks) >= 3 else None
        notes = " ".join(toks[3:]) if len(toks) >= 4 else None

        rows.append(
            {
                "atom_type": atom_type,
                "element": element,
                "mass_amu": mass,
                # vdw_style/lj_a/lj_b populated later from nonbond section
                "vdw_style": "lj_ab_12_6",
                "lj_a": None,
                "lj_b": None,
                "notes": notes,
            }
        )
    return rows


def _parse_quadratic_bond(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        toks = line.split()
        if len(toks) < 4:
            raise ValueError(f"#quadratic_bond: expected at least 4 columns (t1 t2 k r0), got: {raw!r}")

        t1, t2 = toks[0], toks[1]
        k = float(toks[2])
        r0 = float(toks[3])
        source = " ".join(toks[4:]) if len(toks) > 4 else None

        rows.append(
            {
                "t1": t1,
                "t2": t2,
                "style": "quadratic",
                "k": k,
                "r0": r0,
                "source": source,
            }
        )
    return rows


def _parse_quadratic_angle(lines: list[str], *, source_default: str | None) -> list[dict[str, Any]]:
    """Parse `#quadratic_angle` section rows.

    Accepts both:
    - Minimal rows: `t1 t2 t3 theta0_deg k`
    - Asset-style rows with leading columns (eg `ver ref t1 t2 t3 theta0 k`)

    Robustness:
    - We locate the last *adjacent* pair of float-like tokens as `(theta0_deg, k)`.
    - The three tokens immediately before `theta0_deg` are interpreted as `(t1,t2,t3)`.
    - If a header suffix is present (eg `#quadratic_angle cvff_auto`), it becomes the
      default row `source`.
    - If no header suffix exists, any trailing tokens after `k` become `source`.
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue

        toks = line.split()
        if len(toks) < 5:
            raise ValueError(f"#quadratic_angle: expected at least 5 columns (t1 t2 t3 theta0 k), got: {raw!r}")

        # Find the last two *adjacent* float-like tokens: theta0_deg then k.
        theta0_i: int | None = None
        k_i: int | None = None
        for i in range(len(toks) - 2, -1, -1):
            try:
                float(toks[i])
                float(toks[i + 1])
            except Exception:
                continue
            theta0_i = i
            k_i = i + 1
            break

        if theta0_i is None or k_i is None:
            raise ValueError(f"#quadratic_angle: could not find trailing numeric theta0/k in row: {raw!r}")

        if theta0_i < 3:
            raise ValueError(f"#quadratic_angle: not enough tokens before theta0 to extract (t1,t2,t3): {raw!r}")

        t1, t2, t3 = toks[theta0_i - 3], toks[theta0_i - 2], toks[theta0_i - 1]
        theta0 = float(toks[theta0_i])
        k = float(toks[k_i])

        # Source policy:
        # - prefer section-level suffix
        # - else allow per-row trailing text after k
        source = source_default
        if source is None:
            tail = " ".join(toks[k_i + 1 :]).strip()
            source = tail if tail else None

        rows.append(
            {
                "t1": t1,
                "t2": t2,
                "t3": t3,
                "style": "quadratic",
                "k": k,
                "theta0_deg": theta0,
                "source": source,
            }
        )

    return rows


_TYPE_AB_RE = re.compile(r"@type\s+a-b\b", flags=re.IGNORECASE)
_COMB_GEOM_RE = re.compile(r"@combination\s+geometric\b", flags=re.IGNORECASE)


def _parse_nonbond_12_6(lines: list[str]) -> dict[str, tuple[float, float]]:
    """Parse `#nonbond(12-6)`.

    Supported directives:
    - `@type A-B`
    - `@combination geometric`

    Parameter lines expected: `atom_type lj_a lj_b`
    """
    saw_type = False
    saw_comb = False
    out: dict[str, tuple[float, float]] = {}

    for raw in lines:
        if _is_ignorable_line(raw):
            continue

        s = _strip_inline_comment(raw)
        if not s.strip():
            continue

        if s.lstrip().startswith("@"):
            if _TYPE_AB_RE.search(s):
                saw_type = True
                continue
            if _COMB_GEOM_RE.search(s):
                saw_comb = True
                continue
            raise ValueError(f"#nonbond(12-6): unsupported directive line: {raw!r}")

        toks = s.split()
        if len(toks) < 3:
            raise ValueError(f"#nonbond(12-6): expected 3 columns (atom_type lj_a lj_b), got: {raw!r}")

        at = toks[0]
        a = float(toks[1])
        b = float(toks[2])
        out[at] = (a, b)

    if not saw_type:
        raise ValueError("#nonbond(12-6): missing required directive '@type A-B'")
    if not saw_comb:
        raise ValueError("#nonbond(12-6): missing required directive '@combination geometric'")

    return out


def _build_tables(
    atom_types_rows: list[dict[str, Any]],
    bonds_rows: list[dict[str, Any]],
    angles_rows: list[dict[str, Any]],
    nonbond_params: dict[str, tuple[float, float]],
) -> dict[str, "Any"]:
    import pandas as pd

    if not atom_types_rows:
        # v0.1 requires atom_types table
        raise ValueError("parse_frc_text: missing required #atom_types section (no rows parsed)")

    atom_df = pd.DataFrame(atom_types_rows)

    # Apply nonbond params to atom_df
    # Every atom type must end up with lj_a/lj_b populated due to strict validator.
    lj_a_vals: list[Any] = []
    lj_b_vals: list[Any] = []
    for at in atom_df["atom_type"].tolist():
        if at not in nonbond_params:
            raise ValueError(f"parse_frc_text: missing nonbond(12-6) A/B parameters for atom_type {at!r}")
        a, b = nonbond_params[at]
        lj_a_vals.append(a)
        lj_b_vals.append(b)

    atom_df["vdw_style"] = "lj_ab_12_6"
    atom_df["lj_a"] = lj_a_vals
    atom_df["lj_b"] = lj_b_vals

    # Ensure schema columns exist even if parser didn't include them.
    atom_df = atom_df.loc[:, TABLE_COLUMN_ORDER["atom_types"]]

    tables: dict[str, Any] = {"atom_types": atom_df}

    if bonds_rows:
        bonds_df = pd.DataFrame(bonds_rows)
        # Ensure schema columns exist
        bonds_df = bonds_df.loc[:, TABLE_COLUMN_ORDER["bonds"]]
        tables["bonds"] = bonds_df

    if angles_rows:
        angles_df = pd.DataFrame(angles_rows)
        angles_df = angles_df.loc[:, TABLE_COLUMN_ORDER["angles"]]
        tables["angles"] = angles_df

    return tables


# ----------------------------
# Export helpers
# ----------------------------


def _require_df(obj: Any, *, table: str) -> "Any":
    import pandas as pd

    if not isinstance(obj, pd.DataFrame):
        raise TypeError(f"{table}: expected pandas.DataFrame, got {type(obj).__name__}")
    return obj


def _fmt_float(x: Any) -> str:
    # Stable, compact formatting for frc text (locked in tests).
    return ("%.8g" % float(x)).rstrip()


def _format_atom_types_section(df: Any) -> list[str]:
    # Emit the section header exactly as MSI expects.
    lines: list[str] = ["#atom_types"]
    # Deterministic order already guaranteed by normalization.
    for _, row in df.iterrows():
        atom_type = str(row["atom_type"])
        element = row["element"]
        mass = row["mass_amu"]
        notes = row["notes"]

        parts = [atom_type]
        if element is not None and str(element) != "<NA>":
            parts.append(str(element))
        if mass is not None and str(mass) != "<NA>":
            parts.append(_fmt_float(mass))
        if notes is not None and str(notes) != "<NA>":
            parts.append(str(notes))
        lines.append("  " + " ".join(parts))
    return lines


def _format_quadratic_bond_section(df: Any) -> list[str]:
    lines: list[str] = ["#quadratic_bond"]
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        k = _fmt_float(row["k"])
        r0 = _fmt_float(row["r0"])
        source = row["source"]

        parts = [t1, t2, k, r0]
        if source is not None and str(source) != "<NA>":
            parts.append(str(source))
        lines.append("  " + " ".join(parts))
    return lines


def _format_quadratic_angle_section(df: Any) -> list[str]:
    # Determine a uniform source suffix (if any) to attach to the header.
    src_series = df["source"].astype("string").str.strip()
    present = [str(x) for x in src_series.dropna().tolist() if str(x) != "<NA>"]
    unique = sorted(set(present))
    header = "#quadratic_angle"
    header_suffix = unique[0] if len(unique) == 1 and unique[0] else None
    if header_suffix is not None:
        header = f"{header} {header_suffix}"

    lines: list[str] = [header]

    # Emit minimal 5-column rows deterministically. If header suffix is not used,
    # preserve per-row `source` as trailing tokens when present.
    use_header_source = header_suffix is not None
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        t3 = str(row["t3"])
        theta0 = _fmt_float(row["theta0_deg"])
        k = _fmt_float(row["k"])
        parts = [t1, t2, t3, theta0, k]

        if not use_header_source:
            source = row["source"]
            if source is not None and str(source) != "<NA>":
                parts.append(str(source))

        lines.append("  " + " ".join(parts))

    return lines


def _format_nonbond_12_6_section_from_atom_types(df: Any) -> list[str]:
    lines: list[str] = ["#nonbond(12-6)", "  @type A-B", "  @combination geometric"]
    for _, row in df.iterrows():
        at = str(row["atom_type"])
        a = _fmt_float(row["lj_a"])
        b = _fmt_float(row["lj_b"])
        lines.append(f"  {at} {a} {b}")
    return lines