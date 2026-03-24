"""Internal writer helpers for MSI `.frc` codec.

This module contains the export/formatting logic for `.frc` files:
- DataFrame validation
- Float formatting
- Section formatting (atom_types, bonds, angles, nonbond)

This is a private module; public API is in `msi_frc.py`.
"""

from __future__ import annotations

from typing import Any


def _require_df(obj: Any, *, table: str) -> "Any":
    """Validate that object is a pandas DataFrame."""
    import pandas as pd

    if not isinstance(obj, pd.DataFrame):
        raise TypeError(f"{table}: expected pandas.DataFrame, got {type(obj).__name__}")
    return obj


def _fmt_float(x: Any) -> str:
    """Stable, compact formatting for frc text (locked in tests)."""
    return ("%.8g" % float(x)).rstrip()


def _format_atom_types_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #atom_types section for export.
    
    Args:
        df: atom_types DataFrame.
        label: Forcefield label to append to header (e.g., 'cvff').
               This is required by msi2lmp.exe.
    
    The MSI FRC format for atom_types is:
        version ref atom_type mass element connects notes
    Example:
        3.6  32    cdc   12.011150    C           2        C in CO2, By ChengZhu
    """
    # Emit the section header with forcefield label as MSI/msi2lmp expects.
    header = f"#atom_types\t{label}" if label else "#atom_types"
    lines: list[str] = [header]
    # Deterministic order already guaranteed by normalization.
    for _, row in df.iterrows():
        atom_type = str(row["atom_type"])
        element = row["element"]
        mass = row["mass_amu"]
        notes = row["notes"]

        # Default version=1.0, reference=1 for generated entries
        ver = "1.0"
        ref = "1"
        
        # Format: ver ref type mass element connects notes
        # connects is typically 1-4 for atom valence; default to 1
        connects = "1"
        
        parts = [ver, ref, atom_type]
        if mass is not None and str(mass) != "<NA>":
            parts.append(_fmt_float(mass))
        else:
            parts.append("0.0")
        if element is not None and str(element) != "<NA>":
            parts.append(str(element))
        else:
            parts.append("X")
        parts.append(connects)
        if notes is not None and str(notes) != "<NA>":
            parts.append(str(notes))
        lines.append("  " + "  ".join(parts))
    return lines


def _format_quadratic_bond_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #quadratic_bond section for export.
    
    Args:
        df: bonds DataFrame.
        label: Forcefield label to append to header (e.g., 'cvff').
    
    The MSI FRC format for quadratic_bond is:
        version ref t1 t2 r0 k
    Example:
        3.6  32     cdc   cdo       1.1620   1140.0000
    """
    header = f"#quadratic_bond\t{label}" if label else "#quadratic_bond"
    lines: list[str] = [header]
    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        k = _fmt_float(row["k"])
        r0 = _fmt_float(row["r0"])

        # Default version=1.0, reference=1
        ver = "1.0"
        ref = "1"
        
        # Format: ver ref t1 t2 r0 k (note: r0 before k!)
        parts = [ver, ref, t1, t2, r0, k]
        lines.append("  " + "  ".join(parts))
    return lines


def _format_quadratic_angle_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #quadratic_angle section for export.
    
    Args:
        df: angles DataFrame.
        label: Default forcefield label if source not present (e.g., 'cvff').
    
    The MSI FRC format for quadratic_angle is:
        version ref t1 t2 t3 theta0 k
    Example:
        3.6  32     cdo   cdc   cdo     180.0000    100.0000
    """
    header = f"#quadratic_angle\t{label}" if label else "#quadratic_angle"
    lines: list[str] = [header]

    for _, row in df.iterrows():
        t1 = str(row["t1"])
        t2 = str(row["t2"])
        t3 = str(row["t3"])
        theta0 = _fmt_float(row["theta0_deg"])
        k = _fmt_float(row["k"])
        
        # Default version=1.0, reference=1
        ver = "1.0"
        ref = "1"
        
        # Format: ver ref t1 t2 t3 theta0 k
        parts = [ver, ref, t1, t2, t3, theta0, k]
        lines.append("  " + "  ".join(parts))

    return lines


def _format_nonbond_12_6_section_from_atom_types(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #nonbond(12-6) section from atom_types DataFrame.
    
    Args:
        df: atom_types DataFrame with lj_a and lj_b columns.
        label: Forcefield label to append to header (e.g., 'cvff').
    
    The MSI FRC format for nonbond(12-6) is:
        version ref atom_type A B
    Example:
        3.6  32     cdc     236919.1	     217.67820
    """
    header = f"#nonbond(12-6)\t{label}" if label else "#nonbond(12-6)"
    lines: list[str] = [header, "  @type A-B", "  @combination geometric"]
    for _, row in df.iterrows():
        at = str(row["atom_type"])
        a = _fmt_float(row["lj_a"])
        b = _fmt_float(row["lj_b"])
        
        # Default version=1.0, reference=1
        ver = "1.0"
        ref = "1"
        
        # Format: ver ref atom_type A B
        lines.append(f"  {ver}  {ref}  {at}  {a}  {b}")
    return lines


def _format_torsion_1_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #torsion_1 section for export.

    Format: ver ref t1 t2 t3 t4 kphi n phi0
    """
    header = f"#torsion_1\t{label}" if label else "#torsion_1"
    lines: list[str] = [header]
    for _, row in df.iterrows():
        t1, t2, t3, t4 = str(row["t1"]), str(row["t2"]), str(row["t3"]), str(row["t4"])
        kphi = _fmt_float(row["kphi"])
        n = str(int(row["n"]))
        phi0 = _fmt_float(row["phi0"])
        lines.append(f"  1.0  1  {t1}  {t2}  {t3}  {t4}  {kphi}  {n}  {phi0}")
    return lines


def _format_out_of_plane_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #out_of_plane section for export.

    Format: ver ref t1 t2 t3 t4 kchi n chi0
    """
    header = f"#out_of_plane\t{label}" if label else "#out_of_plane"
    lines: list[str] = [header]
    for _, row in df.iterrows():
        t1, t2, t3, t4 = str(row["t1"]), str(row["t2"]), str(row["t3"]), str(row["t4"])
        kchi = _fmt_float(row["kchi"])
        n = str(int(row["n"]))
        chi0 = _fmt_float(row["chi0"])
        lines.append(f"  1.0  1  {t1}  {t2}  {t3}  {t4}  {kchi}  {n}  {chi0}")
    return lines


def _format_equivalence_section(df: Any, *, label: str = "cvff") -> list[str]:
    """Format #equivalence section for export.

    Format: ver ref atom_type nonb bond angle torsion oop
    """
    header = f"#equivalence\t{label}" if label else "#equivalence"
    lines: list[str] = [header]
    for _, row in df.iterrows():
        at = str(row["atom_type"])
        nonb = str(row["nonb"])
        bond = str(row["bond"])
        angle = str(row["angle"])
        torsion = str(row["torsion"])
        oop = str(row["oop"])
        lines.append(f"  1.0  1  {at}  {nonb}  {bond}  {angle}  {torsion}  {oop}")
    return lines
