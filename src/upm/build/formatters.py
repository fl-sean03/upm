"""Consolidated formatting functions for FRC file generation.

This module provides consistent formatting for all FRC section entries.
These functions format individual entries as strings suitable for
inclusion in MSI .frc files.

All formatters follow a consistent pattern:
- Required parameters for the entry values
- Optional ver (version) and ref (reference) strings with defaults
- Return a single formatted line (without trailing newline)

The formatting matches MSI FRC conventions expected by msi2lmp.exe.
"""

from __future__ import annotations


def format_atom_type_entry(
    atom_type: str,
    mass: float,
    element: str,
    connects: int,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #atom_types entry.

    Args:
        atom_type: The atom type name.
        mass: Atomic mass in amu.
        element: Element symbol.
        connects: Typical connectivity count.
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #atom_types section.

    Example:
        >>> format_atom_type_entry("c3", 12.011, "C", 4)
        ' 1.0   1    c3   12.011000    C           4'
    """
    return f" {ver}   {ref}    {atom_type}   {mass:.6f}    {element}           {connects}"


def format_equivalence_entry(
    atom_type: str,
    nonb: str,
    bond: str,
    angle: str,
    torsion: str,
    oop: str,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #equivalence entry.

    The equivalence section maps atom types to their equivalent types
    for different interaction categories.

    Args:
        atom_type: The atom type being defined.
        nonb: Equivalent type for nonbond interactions.
        bond: Equivalent type for bond parameters.
        angle: Equivalent type for angle parameters.
        torsion: Equivalent type for torsion parameters.
        oop: Equivalent type for out-of-plane parameters.
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #equivalence section.

    Example:
        >>> format_equivalence_entry("c3", "c", "c", "c", "c", "c")
        ' 1.0   1    c3   c   c   c   c   c'
    """
    return f" {ver}   {ref}    {atom_type}   {nonb}   {bond}   {angle}   {torsion}   {oop}"


def format_auto_equivalence_entry(
    atom_type: str,
    source_type: str,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #auto_equivalence entry.

    Auto-equivalence maps an atom type to a source type for all
    parameter categories (nonb, bond_inct, bond, angle, torsion,
    oop, etc.).

    Args:
        atom_type: The atom type being defined.
        source_type: The source type for all categories.
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #auto_equivalence section.
    """
    s = source_type
    return (
        f" {ver}   {ref}    {atom_type}  {s}   {s}     {s}       "
        f"{s}       {s}        {s}       {s}         {s}       {s}"
    )


def format_nonbond_entry(
    atom_type: str,
    a_coeff: float,
    b_coeff: float,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #nonbond(12-6) entry.

    Uses A/B form of Lennard-Jones 12-6 potential.

    Args:
        atom_type: The atom type name.
        a_coeff: A coefficient (repulsive term).
        b_coeff: B coefficient (attractive term).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #nonbond(12-6) section.

    Example:
        >>> format_nonbond_entry("c3", 236919.1, 217.67820)
        ' 1.0   1     c3     236919.1\t     217.67820'
    """
    return f" {ver}   {ref}     {atom_type}     {a_coeff:.1f}\t     {b_coeff:.5f}"


def format_bond_entry(
    t1: str,
    t2: str,
    r0: float,
    k: float,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #quadratic_bond entry.

    Args:
        t1: First atom type in the bond.
        t2: Second atom type in the bond.
        r0: Equilibrium bond length in Angstroms.
        k: Force constant in kcal/(mol·Å²).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #quadratic_bond section.

    Example:
        >>> format_bond_entry("c3", "c3", 1.526, 310.0)
        ' 1.0   1     c3   c3       1.5260   310.0000'
    """
    return f" {ver}   {ref}     {t1}   {t2}       {r0:.4f}   {k:.4f}"


def format_angle_entry(
    t1: str,
    t2: str,
    t3: str,
    theta0: float,
    k: float,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #quadratic_angle entry.

    Args:
        t1: First atom type (end atom).
        t2: Center atom type (apex).
        t3: Third atom type (other end).
        theta0: Equilibrium angle in degrees.
        k: Force constant in kcal/(mol·rad²).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #quadratic_angle section.

    Example:
        >>> format_angle_entry("c3", "c3", "c3", 112.7, 63.0)
        ' 1.0   1     c3   c3   c3     112.7000    63.0000'
    """
    return f" {ver}   {ref}     {t1}   {t2}   {t3}     {theta0:.4f}    {k:.4f}"


def format_torsion_entry(
    t1: str,
    t2: str,
    t3: str,
    t4: str,
    kphi: float = 0.0,
    n: int = 1,
    phi0: float = 0.0,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #torsion_1 entry.

    Args:
        t1: First atom type.
        t2: Second atom type (central bond start).
        t3: Third atom type (central bond end).
        t4: Fourth atom type.
        kphi: Torsional barrier height in kcal/mol (default 0.0).
        n: Periodicity (default 1).
        phi0: Phase angle in degrees (default 0.0).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #torsion_1 section.

    Example:
        >>> format_torsion_entry("c3", "c3", "c3", "c3", 0.18, 3, 0.0)
        ' 1.0   1     c3   c3   c3   c3      0.1800      3      0.0000'
    """
    return f" {ver}   {ref}     {t1}   {t2}   {t3}   {t4}      {kphi:.4f}      {n}      {phi0:.4f}"


def format_oop_entry(
    t1: str,
    t2: str,
    t3: str,
    t4: str,
    kchi: float = 0.1,
    n: int = 2,
    chi0: float = 180.0,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #out_of_plane entry.

    Note: Testing shows msi2lmp.exe v3.9.6 requires non-zero OOP parameters
    (0.1/2/180) to avoid segfaults. Zero values cause undefined behavior.

    Args:
        t1: Central atom type.
        t2: First bonded atom type.
        t3: Second bonded atom type.
        t4: Third bonded atom type.
        kchi: Out-of-plane force constant in kcal/mol (default 0.1).
        n: Periodicity (default 2).
        chi0: Equilibrium angle in degrees (default 180.0).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #out_of_plane section.

    Example:
        >>> format_oop_entry("c2", "c3", "c3", "o", 0.1, 2, 180.0)
        ' 1.0   1     c2   c3   c3   o      0.1000      2      180.0000'
    """
    return f" {ver}   {ref}     {t1}   {t2}   {t3}   {t4}      {kchi:.4f}      {n}      {chi0:.4f}"


def format_bond_increment_entry(
    t1: str,
    t2: str,
    delta_ij: float = 0.0,
    delta_ji: float = 0.0,
    ver: str = "1.0",
    ref: str = "1",
) -> str:
    """Format a single #bond_increments entry.

    Bond increments define partial charge transfers between bonded atoms.

    Note: M01 experiment showed msi2lmp.exe crashes with SIGSEGV when
    bond_increments section is empty.

    Args:
        t1: First atom type.
        t2: Second atom type.
        delta_ij: Charge increment i->j (default 0.0).
        delta_ji: Charge increment j->i (default 0.0).
        ver: Version string (default "1.0").
        ref: Reference number string (default "1").

    Returns:
        Formatted entry line for #bond_increments section.

    Example:
        >>> format_bond_increment_entry("c3", "h1", 0.053, -0.053)
        ' 1.0   1     c3   h1      0.05300     -0.05300'
    """
    return f" {ver}   {ref}     {t1}   {t2}      {delta_ij:.5f}     {delta_ji:.5f}"


def join_entries_with_trailing_newline(entries: list[str]) -> str:
    """Join formatted entries into a section body with trailing newline.

    Args:
        entries: List of formatted entry lines (without trailing newlines).

    Returns:
        Joined string with newlines between entries and one trailing newline.

    Example:
        >>> entries = [format_bond_entry("c", "c", 1.54, 300.0)]
        >>> result = join_entries_with_trailing_newline(entries)
        >>> result.endswith("\\n")
        True
    """
    if not entries:
        return ""
    return "\n".join(entries) + "\n"


__all__ = [
    "format_atom_type_entry",
    "format_equivalence_entry",
    "format_auto_equivalence_entry",
    "format_nonbond_entry",
    "format_bond_entry",
    "format_angle_entry",
    "format_torsion_entry",
    "format_oop_entry",
    "format_bond_increment_entry",
    "join_entries_with_trailing_newline",
]
