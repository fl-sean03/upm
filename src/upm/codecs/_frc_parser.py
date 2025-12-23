"""Internal parsing helpers for MSI `.frc` codec.

Private module for parsing logic; public API is in `msi_frc.py`.
"""
from __future__ import annotations

import re
from typing import Any

from upm.core.tables import TABLE_COLUMN_ORDER

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


# ----------------------------
# Line-level helpers
# ----------------------------


def _strip_inline_comment(s: str) -> str:
    # Treat ';' as comment leader if present (common in some FF formats).
    # Keep conservative: if not present, return as-is.
    if ";" in s:
        return s.split(";", 1)[0].rstrip()
    return s.rstrip()


def _is_ignorable_line(line: str) -> bool:
    s = line.strip()
    # Many MSI/CVFF assets include ">" prose lines inside sections.
    return (not s) or s.startswith("!") or s.startswith(";") or s.startswith("#") or s.startswith(">")


# ----------------------------
# Section parsers
# ----------------------------


def _parse_atom_types(lines: list[str]) -> list[dict[str, Any]]:
    """Parse `#atom_types` section rows.

    Accepts both:
    - Minimal rows: `atom_type element mass_amu [notes...]`
    - CVFF/MSI asset-style rows with leading columns:
        `ver ref atom_type mass_amu element [connections...] [comment...]`

    Robustness:
    - If the line begins with two "metadata" tokens (ver, ref) and then contains
      (atom_type, mass, element), we parse that layout.
    - Otherwise we fall back to the minimal layout.
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        toks = line.split()
        if not toks:
            continue

        atom_type: str
        element: str | None
        mass: float | None
        notes: str | None

        # Asset-style: ver ref type mass element ...
        if len(toks) >= 5:
            try:
                float(toks[0])  # ver
                int(float(toks[1]))  # ref (often integer-like)
                float(toks[3])  # mass
            except Exception:
                pass
            else:
                atom_type = toks[2]
                mass = float(toks[3])
                element = toks[4]
                notes = " ".join(toks[5:]) if len(toks) >= 6 else None
                rows.append(
                    {
                        "atom_type": atom_type,
                        "element": element,
                        "mass_amu": mass,
                        "vdw_style": "lj_ab_12_6",
                        "lj_a": None,
                        "lj_b": None,
                        "notes": notes,
                    }
                )
                continue

        # Minimal: type element mass ...
        atom_type = toks[0]
        element = toks[1] if len(toks) >= 2 else None
        try:
            mass = float(toks[2]) if len(toks) >= 3 else None
        except Exception:
            # Keep tolerant: if mass is malformed, treat as missing and keep remaining as notes.
            mass = None
        notes = " ".join(toks[3:]) if len(toks) >= 4 else None

        rows.append(
            {
                "atom_type": atom_type,
                "element": element,
                "mass_amu": mass,
                "vdw_style": "lj_ab_12_6",
                "lj_a": None,
                "lj_b": None,
                "notes": notes,
            }
        )
    return rows


def _parse_quadratic_bond(lines: list[str], *, source_default: str | None) -> list[dict[str, Any]]:
    """Parse `#quadratic_bond` section rows.

    Accepts both:
    - Minimal rows: `t1 t2 k r0 [source...]`
    - Asset-style rows with leading columns (eg `ver ref t1 t2 r0 k2`)

    Robustness:
    - We locate the last *adjacent* pair of float-like tokens.
    - The two tokens immediately before that pair are interpreted as `(t1,t2)`.
    - The float ordering is inferred via a simple heuristic:
        - if first<=10 and second>10 => (r0,k)
        - if first>10 and second<=10 => (k,r0)
        - otherwise default to minimal ordering (k,r0) for backwards compatibility
    - If a header suffix is present (eg `#quadratic_bond cvff_auto`), it becomes the
      default row `source`.
    - If no header suffix exists, any trailing tokens after the numeric pair become `source`.
    """
    rows: list[dict[str, Any]] = []

    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue

        toks = line.split()
        if len(toks) < 4:
            raise ValueError(
                f"#quadratic_bond: expected at least 4 columns (t1 t2 k r0) "
                f"or asset-style (ver ref t1 t2 r0 k2), got: {raw!r}"
            )

        # Find the last two *adjacent* float-like tokens.
        a_i: int | None = None
        b_i: int | None = None
        for i in range(len(toks) - 2, -1, -1):
            try:
                float(toks[i])
                float(toks[i + 1])
            except Exception:
                continue
            a_i = i
            b_i = i + 1
            break

        if a_i is None or b_i is None:
            raise ValueError(f"#quadratic_bond: could not find trailing numeric pair in row: {raw!r}")

        if a_i < 2:
            raise ValueError(f"#quadratic_bond: not enough tokens before numeric pair to extract (t1,t2): {raw!r}")

        t1, t2 = toks[a_i - 2], toks[a_i - 1]
        a = float(toks[a_i])
        b = float(toks[b_i])

        # Heuristic to map (a,b) to (k,r0) vs (r0,k).
        # Typical ranges: r0 ~ 0.9-3.5, k ~ O(100)+
        if a <= 10.0 and b > 10.0:
            r0, k = a, b
        elif a > 10.0 and b <= 10.0:
            k, r0 = a, b
        else:
            # Ambiguous; keep minimal ordering for compatibility with existing tests.
            k, r0 = a, b

        source = source_default
        if source is None:
            tail = " ".join(toks[b_i + 1 :]).strip()
            source = tail if tail else None

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

    Accepts both:
    - Minimal rows: `atom_type lj_a lj_b`
    - Asset-style rows with leading columns (eg `ver ref atom_type lj_a lj_b`)
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
            raise ValueError(f"#nonbond(12-6): expected at least 3 columns (atom_type lj_a lj_b), got: {raw!r}")

        # Locate the last two *adjacent* float-like tokens; interpret them as (a,b).
        a_i: int | None = None
        b_i: int | None = None
        for i in range(len(toks) - 2, -1, -1):
            try:
                float(toks[i])
                float(toks[i + 1])
            except Exception:
                continue
            a_i = i
            b_i = i + 1
            break

        if a_i is None or b_i is None:
            raise ValueError(f"#nonbond(12-6): could not find trailing numeric (A,B) pair in row: {raw!r}")
        if a_i < 1:
            raise ValueError(f"#nonbond(12-6): not enough tokens before (A,B) to extract atom_type: {raw!r}")

        at = toks[a_i - 1]
        a = float(toks[a_i])
        b = float(toks[b_i])
        out[at] = (a, b)

    if not saw_type:
        raise ValueError("#nonbond(12-6): missing required directive '@type A-B'")
    if not saw_comb:
        raise ValueError("#nonbond(12-6): missing required directive '@combination geometric'")

    return out


def _parse_bond_increments(lines: list[str]) -> list[dict[str, Any]]:
    """Parse #bond_increments section rows.
    
    Format: ver ref t1 t2 delta_ij delta_ji
    Example: 3.6  32  cdc  cdo  -0.03000  0.03000
    
    Robustness:
    - We locate the last two *adjacent* float-like tokens as (delta_ij, delta_ji).
    - The two tokens immediately before that pair are interpreted as (t1, t2).
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        toks = line.split()
        if len(toks) < 4:
            continue
        
        # Find last two adjacent floats
        di_i: int | None = None
        dj_i: int | None = None
        for i in range(len(toks) - 2, -1, -1):
            try:
                float(toks[i])
                float(toks[i + 1])
            except Exception:
                continue
            di_i = i
            dj_i = i + 1
            break
        
        if di_i is None or di_i < 2:
            continue
            
        t1, t2 = toks[di_i - 2], toks[di_i - 1]
        delta_ij = float(toks[di_i])
        delta_ji = float(toks[dj_i])
        
        rows.append({
            "t1": t1,
            "t2": t2,
            "delta_ij": delta_ij,
            "delta_ji": delta_ji,
        })
    return rows


# ----------------------------
# Table building
# ----------------------------


def _build_tables(
    atom_types_rows: list[dict[str, Any]],
    bonds_rows: list[dict[str, Any]],
    angles_rows: list[dict[str, Any]],
    nonbond_params: dict[str, tuple[float, float]],
    bond_increments_rows: list[dict[str, Any]] | None = None,
) -> dict[str, "Any"]:
    import pandas as pd

    if not atom_types_rows:
        # v0.1 requires atom_types table
        raise ValueError("parse_frc_text: missing required #atom_types section (no rows parsed)")

    atom_df = pd.DataFrame(atom_types_rows)

    # Apply nonbond params to atom_df.
    #
    # CVFF/MSI assets do not necessarily provide A/B params for every declared atom type.
    # Keep tolerant: fill when present, otherwise leave as None.
    lj_a_vals: list[Any] = []
    lj_b_vals: list[Any] = []
    for at in atom_df["atom_type"].tolist():
        if at in nonbond_params:
            a, b = nonbond_params[at]
            lj_a_vals.append(a)
            lj_b_vals.append(b)
        else:
            lj_a_vals.append(None)
            lj_b_vals.append(None)

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

    if bond_increments_rows:
        bi_df = pd.DataFrame(bond_increments_rows)
        # bond_increments has columns: t1, t2, delta_ij, delta_ji
        # No TABLE_COLUMN_ORDER for bond_increments, use as-is
        tables["bond_increments"] = bi_df

    return tables
