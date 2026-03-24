"""FRC file formatting and writing for CVFF forcefield files.

Takes an FRCInput specification and produces a deterministic CVFF .frc file
compatible with msi2lmp.exe (without -ignore flag).
"""
from __future__ import annotations

from pathlib import Path

from .frc_templates import CVFF_SKELETON
from .frc_input import (
    AngleEntry,
    AtomTypeEntry,
    BondEntry,
    FRCInput,
    NonbondEntry,
    OOPEntry,
    TorsionEntry,
)


# =============================================================================
# Internal Formatting Functions
# =============================================================================


def _format_atom_type_entry(entry: AtomTypeEntry) -> str:
    """Format single #atom_types row.

    Format: Ver Ref Type Mass Element Connects
    Example: " 2.0  18    C_MOF  12.011000  C       4"
    """
    return f" 2.0  18    {entry.atom_type:<6s} {entry.mass_amu:10.6f}  {entry.element:<2s}      {entry.connects:d}"


def _format_equivalence_entry(atom_type: str, source_type: str) -> str:
    """Format single #equivalence row.

    The first column is the atom type, subsequent columns are the source type
    (which may differ for truncated aliases like Zn_MO -> Zn_MOF).
    """
    t = atom_type
    s = source_type
    return f" 1.0   1    {t:<6s} {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}"


def _format_auto_equivalence_entry(atom_type: str, source_type: str) -> str:
    """Format single #auto_equivalence row.

    The first column is the atom type, subsequent columns are the source type.
    """
    t = atom_type
    s = source_type
    return f" 2.0  18    {t:<6s} {s:<6s} {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}  {s:<6s}"


def _format_bond_entry(entry: BondEntry) -> str:
    """Format single #quadratic_bond row.

    Format: Ver Ref I J R0 K2
    """
    return f" 2.0  18    {entry.type1:<6s} {entry.type2:<6s} {entry.r0:10.6f} {entry.k:12.6f}"


def _format_angle_entry(entry: AngleEntry) -> str:
    """Format single #quadratic_angle row.

    Format: Ver Ref I J K Theta0 K2
    """
    return f" 2.0  18    {entry.type1:<6s} {entry.type2:<6s} {entry.type3:<6s} {entry.theta0:10.6f} {entry.k:12.6f}"


def _format_torsion_entry(entry: TorsionEntry) -> str:
    """Format single #torsion_1 row.

    Format: Ver Ref I J K L Kphi n Phi0
    """
    return f" 2.0  18    {entry.type1:<6s} {entry.type2:<6s} {entry.type3:<6s} {entry.type4:<6s} {entry.kphi:10.6f}   {entry.n:d}   {entry.phi0:10.6f}"


def _format_oop_entry(entry: OOPEntry) -> str:
    """Format single #out_of_plane row.

    Format: Ver Ref I J K L Kchi n Chi0
    """
    return f" 2.0  18    {entry.type1:<6s} {entry.type2:<6s} {entry.type3:<6s} {entry.type4:<6s} {entry.kchi:10.6f}   {entry.n:d}   {entry.chi0:10.6f}"


def _format_nonbond_entry(entry: NonbondEntry) -> str:
    """Format single #nonbond(12-6) row.

    Format: Ver Ref I A B
    """
    return f" 2.0  18    {entry.atom_type:<6s} {entry.lj_a:14.6f}  {entry.lj_b:14.6f}"


# =============================================================================
# Main Writer Function
# =============================================================================


def write_cvff_frc(
    frc_input: FRCInput,
    out_path: Path | str,
    *,
    skeleton: str = CVFF_SKELETON,
) -> str:
    """Write a CVFF .frc file from FRCInput specification.

    Args:
        frc_input: Complete specification of all entries.
        out_path: Where to write the file.
        skeleton: Template string (default: canonical CVFF skeleton).

    Returns:
        The output path as a string.

    Notes:
        - Output is deterministic (sorted entries, stable formatting)
        - File is UTF-8 encoded with Unix line endings
        - Entries are sorted alphabetically for stable diffs
    """
    # Extract unique atom types for equivalence sections
    atom_types = sorted({e.atom_type for e in frc_input.atom_types})
    
    # Build mapping from type -> source type (for aliases, source is the full type)
    alias_map = frc_input.alias_map
    def get_source(t: str) -> str:
        return alias_map.get(t, t)

    # Format all sections with deterministic sorting
    atom_types_block = "\n".join(
        _format_atom_type_entry(e)
        for e in sorted(frc_input.atom_types, key=lambda x: x.atom_type)
    )

    equivalences_block = "\n".join(
        _format_equivalence_entry(t, get_source(t)) for t in atom_types
    )

    auto_equivalences_block = "\n".join(
        _format_auto_equivalence_entry(t, get_source(t)) for t in atom_types
    )

    bonds_block = "\n".join(
        _format_bond_entry(e)
        for e in sorted(frc_input.bonds, key=lambda x: (x.type1, x.type2))
    )

    angles_block = "\n".join(
        _format_angle_entry(e)
        for e in sorted(frc_input.angles, key=lambda x: (x.type1, x.type2, x.type3))
    )

    torsions_block = "\n".join(
        _format_torsion_entry(e)
        for e in sorted(frc_input.torsions, key=lambda x: (x.type1, x.type2, x.type3, x.type4))
    )

    oops_block = "\n".join(
        _format_oop_entry(e)
        for e in sorted(frc_input.oops, key=lambda x: (x.type1, x.type2, x.type3, x.type4))
    )

    nonbonds_block = "\n".join(
        _format_nonbond_entry(e)
        for e in sorted(frc_input.nonbonds, key=lambda x: x.atom_type)
    )

    # Populate skeleton template
    content = skeleton.format(
        atom_types=atom_types_block,
        equivalences=equivalences_block,
        auto_equivalences=auto_equivalences_block,
        bonds=bonds_block,
        angles=angles_block,
        torsions=torsions_block,
        oops=oops_block,
        nonbonds=nonbonds_block,
    )

    # Write with Unix line endings
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8", newline="\n")

    return str(out)


__all__ = ["write_cvff_frc"]
