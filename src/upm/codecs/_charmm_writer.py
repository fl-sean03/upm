"""Internal writer for CHARMM .prm format.

Generates NAMD-compatible parameter files from UPM tables.
Private module; public API is in `charmm_prm.py`.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from upm.codecs._charmm_parser import _lj_ab_to_charmm_eps_rmin

if TYPE_CHECKING:
    import pandas as pd


def write_prm_text(
    tables: dict[str, Any],
    raw_sections: list[dict[str, Any]] | None = None,
) -> str:
    """Generate CHARMM .prm text from UPM tables.

    Args:
        tables: Dict of DataFrames (atom_types, bonds, angles, etc.)
        raw_sections: Preserved raw sections (TITLE, CMAP, HBOND, etc.)

    Returns:
        Complete .prm file content as string.
    """
    raw = {s["header"]: s["body"] for s in (raw_sections or [])}
    parts: list[str] = []

    # Title
    if "TITLE" in raw:
        parts.extend(raw["TITLE"])
    else:
        parts.append("* UPM-generated CHARMM parameter file")
        parts.append("*")
    parts.append("")

    # BONDS
    if "bonds" in tables and len(tables["bonds"]) > 0:
        parts.append("BONDS")
        parts.append("!")
        parts.append("!V(bond) = Kb(b - b0)**2")
        parts.append("!")
        parts.append("!Kb: kcal/mole/A**2")
        parts.append("!b0: A")
        parts.append("!")
        parts.append("!atom type Kb          b0")
        parts.append("!")
        parts.extend(_format_bonds(tables["bonds"]))
        parts.append("")

    # ANGLES
    if "angles" in tables and len(tables["angles"]) > 0:
        parts.append("ANGLES")
        parts.append("!")
        parts.append("!V(angle) = Ktheta(Theta - Theta0)**2")
        parts.append("!")
        parts.append("!Ktheta: kcal/mole/rad**2")
        parts.append("!Theta0: degrees")
        parts.append("!")
        parts.append("!atom types     Ktheta    Theta0")
        parts.append("!")
        parts.extend(_format_angles(tables["angles"]))
        parts.append("")

    # DIHEDRALS
    if "torsions" in tables and len(tables["torsions"]) > 0:
        parts.append("DIHEDRALS")
        parts.append("!")
        parts.append("!V(dihedral) = Kchi(1 + cos(n(chi) - delta))")
        parts.append("!")
        parts.append("!Kchi: kcal/mole")
        parts.append("!n: multiplicity")
        parts.append("!delta: degrees")
        parts.append("!")
        parts.append("!atom types             Kchi    n   delta")
        parts.append("!")
        parts.extend(_format_dihedrals(tables["torsions"]))
        parts.append("")

    # IMPROPER
    if "out_of_plane" in tables and len(tables["out_of_plane"]) > 0:
        parts.append("IMPROPER")
        parts.append("!")
        parts.append("!V(improper) = Kpsi(psi - psi0)**2")
        parts.append("!")
        parts.append("!Kpsi: kcal/mole/rad**2")
        parts.append("!psi0: degrees")
        parts.append("!note that the second column of numbers (0) is ignored")
        parts.append("!")
        parts.append("!atom types           Kpsi                   psi0")
        parts.append("!")
        parts.extend(_format_improper(tables["out_of_plane"]))
        parts.append("")

    # CMAP (raw passthrough)
    if "CMAP" in raw:
        parts.append("CMAP")
        parts.extend(raw["CMAP"])
        parts.append("")

    # NONBONDED
    if "atom_types" in tables and len(tables["atom_types"]) > 0:
        header_lines = raw.get("NONBONDED_HEADER", [
            "NONBONDED nbxmod  5 atom cdiel fshift vatom vdistance vfswitch -",
            "cutnb 14.0 ctofnb 12.0 ctonnb 10.0 eps 1.0 e14fac 1.0 wmin 1.5",
        ])
        parts.extend(header_lines)
        parts.append("!")
        parts.append("!atom  ignored    epsilon      Rmin/2")
        parts.append("!")
        parts.extend(_format_nonbonded(tables["atom_types"]))
        parts.append("")

    # HBOND (raw passthrough)
    if "HBOND" in raw:
        parts.extend(raw["HBOND"])
        parts.append("")

    # NBFIX
    if "pair_overrides" in tables and len(tables["pair_overrides"]) > 0:
        parts.append("NBFIX")
        parts.append("!              Emin         Rmin")
        parts.append("!            (kcal/mol)     (A)")
        parts.extend(_format_nbfix(tables["pair_overrides"]))
        parts.append("")

    parts.append("END")
    parts.append("")

    return "\n".join(parts)


def _format_bonds(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        k = float(row["k"])
        r0 = float(row["r0"])
        lines.append(f"{t1:<5s}{t2:<6s}{k:10.3f}     {r0:.4f}")
    return lines


def _format_angles(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        t3 = str(row["t3"])
        k = float(row["k"])
        theta0 = float(row["theta0_deg"])
        lines.append(f"{t1:<5s}{t2:<5s}{t3:<6s}{k:10.3f}   {theta0:8.2f}")
    return lines


def _format_dihedrals(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        t3 = str(row["t3"])
        t4 = str(row["t4"])
        kphi = float(row["kphi"])
        n = int(row["n"])
        phi0 = float(row["phi0"])
        lines.append(f"{t1:<5s}{t2:<5s}{t3:<5s}{t4:<10s}{kphi:10.4f}  {n:>3d}   {phi0:8.2f}")
    return lines


def _format_improper(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        t3 = str(row["t3"])
        t4 = str(row["t4"])
        kchi = float(row["kchi"])
        chi0 = float(row["chi0"])
        lines.append(f"{t1:<5s}{t2:<5s}{t3:<5s}{t4:<10s}{kchi:10.4f}         0   {chi0:8.4f}")
    return lines


def _format_nonbonded(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        at = str(row["atom_type"])
        lj_a = float(row["lj_a"]) if row["lj_a"] is not None else 0.0
        lj_b = float(row["lj_b"]) if row["lj_b"] is not None else 0.0
        neg_eps, rmin_half = _lj_ab_to_charmm_eps_rmin(lj_a, lj_b)
        lines.append(f"{at:<7s}{0.0:10.6f}  {neg_eps:12.6f}     {rmin_half:.6f}")
    return lines


def _format_nbfix(df: "pd.DataFrame") -> list[str]:
    lines = []
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        lj_a = float(row["lj_a"])
        lj_b = float(row["lj_b"])
        neg_eps, rmin_half = _lj_ab_to_charmm_eps_rmin(lj_a, lj_b)
        rmin = 2.0 * rmin_half
        lines.append(f"{t1:<7s}{t2:<9s}{neg_eps:12.6f}   {rmin:.3f}")
    return lines


__all__ = [
    "write_prm_text",
]
