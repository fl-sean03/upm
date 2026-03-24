"""Internal parsing helpers for CHARMM .prm codec.

Parses CHARMM/NAMD parameter files into UPM canonical tables.
Section format follows CHARMM X-PLOR conventions.

Private module; public API is in `charmm_prm.py`.
"""
from __future__ import annotations

from typing import Any


def _strip_comment(line: str) -> str:
    """Strip inline ! comment from a line."""
    idx = line.find("!")
    if idx >= 0:
        return line[:idx].rstrip()
    return line.rstrip()


def _is_ignorable(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("!") or s.startswith("*")


def _split_prm_sections(text: str) -> dict[str, list[str]]:
    """Split .prm text into {section_name: body_lines}.

    Title lines (starting with *) are stored under key 'TITLE'.
    NONBONDED header options are stored in sections['NONBONDED_HEADER'].
    """
    lines = text.splitlines()
    sections: dict[str, list[str]] = {"TITLE": []}
    current: str | None = "TITLE"
    section_keywords = {
        "BONDS", "ANGLES", "DIHEDRALS", "IMPROPER", "IMPROPERS",
        "CMAP", "NONBONDED", "NBFIX", "HBOND", "END",
    }

    for line in lines:
        stripped = line.strip()
        first_word = stripped.split()[0].upper() if stripped.split() else ""

        if stripped.startswith("*"):
            sections.setdefault("TITLE", []).append(line)
            continue

        if first_word in section_keywords:
            current = first_word
            if current == "IMPROPERS":
                current = "IMPROPER"
            sections.setdefault(current, [])
            # NONBONDED header may have options on same/next line
            if current == "NONBONDED":
                sections.setdefault("NONBONDED_HEADER", []).append(stripped)
            continue

        # Continuation line for NONBONDED header (starts with cutnb, etc.)
        if current == "NONBONDED" and stripped and not _is_ignorable(line):
            lower = stripped.lower()
            if lower.startswith("cutnb") or lower.startswith("wmin"):
                sections.setdefault("NONBONDED_HEADER", []).append(stripped)
                continue

        if current is not None and current != "TITLE":
            sections.setdefault(current, []).append(line)

    return sections


# =============================================================================
# Section Parsers
# =============================================================================


def _parse_bonds(lines: list[str]) -> list[dict[str, Any]]:
    """Parse BONDS section: t1 t2 Kb b0 [! comment]."""
    rows = []
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 4:
            continue
        try:
            k = float(toks[2])
            r0 = float(toks[3])
        except ValueError:
            continue
        rows.append({
            "t1": toks[0], "t2": toks[1],
            "style": "quadratic", "k": k, "r0": r0,
            "source": None,
        })
    return rows


def _parse_angles(lines: list[str]) -> list[dict[str, Any]]:
    """Parse ANGLES section: t1 t2 t3 Ktheta theta0 [Kub S0] [! comment]."""
    rows = []
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 5:
            continue
        try:
            k = float(toks[3])
            theta0 = float(toks[4])
        except ValueError:
            continue
        rows.append({
            "t1": toks[0], "t2": toks[1], "t3": toks[2],
            "style": "quadratic", "k": k, "theta0_deg": theta0,
            "source": None,
        })
    return rows


def _parse_dihedrals(lines: list[str]) -> list[dict[str, Any]]:
    """Parse DIHEDRALS section: t1 t2 t3 t4 Kchi n delta [! comment].

    Multiple entries per type quad are allowed (different multiplicities).
    """
    rows = []
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 7:
            continue
        try:
            kphi = float(toks[4])
            n = int(toks[5])
            phi0 = float(toks[6])
        except ValueError:
            continue
        rows.append({
            "t1": toks[0], "t2": toks[1], "t3": toks[2], "t4": toks[3],
            "style": "torsion_1", "kphi": kphi, "n": n, "phi0": phi0,
            "source": None,
        })
    return rows


def _parse_improper(lines: list[str]) -> list[dict[str, Any]]:
    """Parse IMPROPER section: t1 t2 t3 t4 Kpsi ignored psi0 [! comment]."""
    rows = []
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 7:
            continue
        try:
            kchi = float(toks[4])
            # toks[5] is ignored (placeholder)
            chi0 = float(toks[6])
        except ValueError:
            continue
        rows.append({
            "t1": toks[0], "t2": toks[1], "t3": toks[2], "t4": toks[3],
            "style": "out_of_plane", "kchi": kchi,
            "n": 0,  # harmonic improper (n=0 convention)
            "chi0": chi0,
            "source": None,
        })
    return rows


def _charmm_eps_rmin_to_lj_ab(neg_eps: float, rmin_half: float) -> tuple[float, float]:
    """Convert CHARMM nonbond params to LJ A/B coefficients.

    CHARMM: V = eps * [(Rmin/r)^12 - 2*(Rmin/r)^6]
    Standard: V = A/r^12 - B/r^6

    So: A = eps * Rmin^12, B = 2 * eps * Rmin^6

    CHARMM .prm stores -epsilon (negative) and Rmin/2.
    """
    eps = abs(neg_eps)
    rmin = 2.0 * abs(rmin_half)
    rmin6 = rmin ** 6
    a = eps * rmin6 * rmin6
    b = 2.0 * eps * rmin6
    return a, b


def _lj_ab_to_charmm_eps_rmin(lj_a: float, lj_b: float) -> tuple[float, float]:
    """Convert LJ A/B to CHARMM -epsilon and Rmin/2.

    Returns (-epsilon, Rmin/2).
    """
    if lj_b == 0.0 or lj_a == 0.0:
        return (0.0, 0.0)
    # From A = eps * Rmin^12 and B = 2 * eps * Rmin^6:
    # Rmin^6 = A / B * 2, eps = B^2 / (4*A)
    rmin6 = 2.0 * lj_a / lj_b
    rmin = rmin6 ** (1.0 / 6.0)
    eps = lj_b ** 2 / (4.0 * lj_a)
    return (-eps, rmin / 2.0)


def _parse_nonbonded(lines: list[str]) -> dict[str, dict[str, Any]]:
    """Parse NONBONDED section.

    Format: atom ignored -epsilon Rmin/2 [ignored -eps14 Rmin14/2]
    Returns: {atom_type: {"neg_eps": float, "rmin_half": float, "element": None}}
    """
    params: dict[str, dict[str, Any]] = {}
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 4:
            continue
        try:
            float(toks[1])  # ignored
            neg_eps = float(toks[2])
            rmin_half = float(toks[3])
        except ValueError:
            continue
        atom_type = toks[0]
        params[atom_type] = {
            "neg_eps": neg_eps,
            "rmin_half": rmin_half,
        }
    return params


def _parse_nbfix(lines: list[str]) -> list[dict[str, Any]]:
    """Parse NBFIX section: t1 t2 -epsilon Rmin [! comment]."""
    rows = []
    for raw in lines:
        if _is_ignorable(raw):
            continue
        line = _strip_comment(raw)
        toks = line.split()
        if len(toks) < 4:
            continue
        try:
            neg_eps = float(toks[2])
            rmin = float(toks[3])
        except ValueError:
            continue
        a, b = _charmm_eps_rmin_to_lj_ab(neg_eps, rmin / 2.0)
        rows.append({
            "t1": toks[0], "t2": toks[1],
            "lj_a": a, "lj_b": b,
        })
    return rows


def parse_prm_text(
    text: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse CHARMM .prm text into UPM tables dict.

    Returns:
        (tables, raw_sections) where:
        - tables: dict of pandas DataFrames (atom_types, bonds, angles, torsions, etc.)
        - raw_sections: list of preserved raw section data (TITLE, CMAP, HBOND)
    """
    import pandas as pd

    from upm.core.tables import TABLE_COLUMN_ORDER

    sections = _split_prm_sections(text)

    # Parse each section
    bonds_rows = _parse_bonds(sections.get("BONDS", []))
    angles_rows = _parse_angles(sections.get("ANGLES", []))
    dihedrals_rows = _parse_dihedrals(sections.get("DIHEDRALS", []))
    improper_rows = _parse_improper(sections.get("IMPROPER", []))
    nonbond_params = _parse_nonbonded(sections.get("NONBONDED", []))
    nbfix_rows = _parse_nbfix(sections.get("NBFIX", []))

    # Build atom_types from NONBONDED section
    atom_rows = []
    for at, params in sorted(nonbond_params.items()):
        a, b = _charmm_eps_rmin_to_lj_ab(params["neg_eps"], params["rmin_half"])
        atom_rows.append({
            "atom_type": at,
            "element": "X",  # CHARMM .prm doesn't include element info
            "mass_amu": 0.0,  # Mass comes from topology (.rtf), not .prm
            "vdw_style": "lj_ab_12_6",
            "lj_a": a,
            "lj_b": b,
            "notes": None,
        })

    tables: dict[str, Any] = {}

    if atom_rows:
        atom_df = pd.DataFrame(atom_rows)
        atom_df = atom_df.loc[:, TABLE_COLUMN_ORDER["atom_types"]]
        tables["atom_types"] = atom_df

    if bonds_rows:
        bonds_df = pd.DataFrame(bonds_rows)
        bonds_df = bonds_df.loc[:, TABLE_COLUMN_ORDER["bonds"]]
        tables["bonds"] = bonds_df

    if angles_rows:
        angles_df = pd.DataFrame(angles_rows)
        angles_df = angles_df.loc[:, TABLE_COLUMN_ORDER["angles"]]
        tables["angles"] = angles_df

    if dihedrals_rows:
        torsions_df = pd.DataFrame(dihedrals_rows)
        torsions_df = torsions_df.loc[:, TABLE_COLUMN_ORDER["torsions"]]
        tables["torsions"] = torsions_df

    if improper_rows:
        oop_df = pd.DataFrame(improper_rows)
        oop_df = oop_df.loc[:, TABLE_COLUMN_ORDER["out_of_plane"]]
        tables["out_of_plane"] = oop_df

    if nbfix_rows:
        nbfix_df = pd.DataFrame(nbfix_rows)
        tables["pair_overrides"] = nbfix_df

    # Preserve raw sections for roundtrip
    raw_sections = []
    if "TITLE" in sections:
        raw_sections.append({"header": "TITLE", "body": sections["TITLE"]})
    if "CMAP" in sections:
        raw_sections.append({"header": "CMAP", "body": sections["CMAP"]})
    if "HBOND" in sections:
        raw_sections.append({"header": "HBOND", "body": sections["HBOND"]})
    if "NONBONDED_HEADER" in sections:
        raw_sections.append({"header": "NONBONDED_HEADER", "body": sections["NONBONDED_HEADER"]})

    return tables, raw_sections


__all__ = [
    "parse_prm_text",
    "_charmm_eps_rmin_to_lj_ab",
    "_lj_ab_to_charmm_eps_rmin",
]
