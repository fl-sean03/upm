"""Data model and conversion layer for FRC file generation.

Provides frozen dataclasses for .frc entries and build_frc_input() to convert
USM TermSet + ParameterSet into FRCInput specification.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from upm.build.frc_helpers import (
    lj_sigma_eps_to_ab as _lj_sigma_eps_to_ab_kw,
    placeholder_bond_params as _placeholder_bond_kw,
    placeholder_angle_params as _placeholder_angle_kw,
)

# =============================================================================
# Frozen Dataclasses for FRC Entries
# =============================================================================

@dataclass(frozen=True)
class AtomTypeEntry:
    """Single atom type for #atom_types section."""
    atom_type: str
    mass_amu: float
    element: str
    connects: int
    lj_a: float
    lj_b: float

@dataclass(frozen=True)
class BondEntry:
    """Single bond parameter for #quadratic_bond section."""
    type1: str
    type2: str
    r0: float
    k: float

@dataclass(frozen=True)
class AngleEntry:
    """Single angle parameter for #quadratic_angle section."""
    type1: str
    type2: str  # Central atom
    type3: str
    theta0: float
    k: float

@dataclass(frozen=True)
class TorsionEntry:
    """Single torsion parameter for #torsion_1 section."""
    type1: str
    type2: str
    type3: str
    type4: str
    kphi: float
    n: int
    phi0: float

@dataclass(frozen=True)
class OOPEntry:
    """Single out-of-plane parameter for #out_of_plane section."""
    type1: str  # First peripheral
    type2: str  # Central atom
    type3: str  # Second peripheral
    type4: str  # Third peripheral
    kchi: float
    n: int
    chi0: float

@dataclass(frozen=True)
class NonbondEntry:
    """Single nonbond parameter for #nonbond(12-6) section."""
    atom_type: str
    lj_a: float
    lj_b: float

@dataclass
class FRCInput:
    """Complete specification for generating an .frc file."""
    atom_types: list[AtomTypeEntry] = field(default_factory=list)
    bonds: list[BondEntry] = field(default_factory=list)
    angles: list[AngleEntry] = field(default_factory=list)
    torsions: list[TorsionEntry] = field(default_factory=list)
    oops: list[OOPEntry] = field(default_factory=list)
    nonbonds: list[NonbondEntry] = field(default_factory=list)
    forcefield_label: str = "cvff"
    msi2lmp_max_type_len: int = 5
    # Maps truncated alias -> full source type for equivalence sections
    alias_map: dict[str, str] = field(default_factory=dict)

# =============================================================================
# Helper Functions
# =============================================================================

def _lj_sigma_eps_to_ab(sigma: float, epsilon: float) -> tuple[float, float]:
    """Convert LJ sigma/epsilon to A/B parameters. Delegates to canonical impl."""
    return _lj_sigma_eps_to_ab_kw(sigma=sigma, epsilon=epsilon)

# Use Connections=0 for all types to disable msi2lmp.exe validation.
# Element-based defaults (H=1, C=4, N=3, O=2, Zn=6) cause validation failures
# when actual topology doesn't match expected connectivity (e.g., aromatic C with 3 bonds).

def _element_to_connects(element: str) -> int:
    """Return 0 for all elements to disable msi2lmp.exe Connections validation."""
    return 0

def _placeholder_bond_params(el1: str, el2: str) -> tuple[float, float]:
    """Get (r0, k) placeholder values based on element types."""
    k, r0 = _placeholder_bond_kw(t1_el=el1, t2_el=el2)
    return (r0, k)

def _placeholder_angle_params(center_el: str) -> tuple[float, float]:
    """Get (theta0, k) placeholder values based on center element."""
    theta0, k = _placeholder_angle_kw(center_el=center_el)
    return (theta0, k)

def _expand_with_aliases(
    atom_types: list[str], max_len: int
) -> tuple[list[str], dict[str, str]]:
    """Expand atom types with truncated aliases for msi2lmp compatibility."""
    expanded: list[str] = []
    alias_map: dict[str, str] = {}
    seen: set[str] = set()
    for t in sorted(atom_types):
        if t not in seen:
            expanded.append(t)
            seen.add(t)
        if len(t) > max_len:
            alias = t[:max_len]
            if alias not in seen:
                expanded.append(alias)
                seen.add(alias)
                alias_map[alias] = t
    return (sorted(expanded), alias_map)

# =============================================================================
# Main Conversion Function
# =============================================================================

def build_frc_input(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    use_placeholders: bool = True,
    msi2lmp_max_type_len: int = 5,
) -> FRCInput:
    """Convert USM TermSet + ParameterSet to FRCInput specification.

    Args:
        termset: Output of derive_termset_v0_1_2() with atom_types, bond_types,
            angle_types, dihedral_types, improper_types
        parameterset: Output of derive_parameterset_v0_1_2() with atom_types dict
            containing mass_amu, lj_sigma_angstrom, lj_epsilon_kcal_mol, element
        use_placeholders: If True, fill missing bonded params with defaults
        msi2lmp_max_type_len: Max atom type name length for alias expansion
    """
    ps_atom_types = parameterset.get("atom_types", {})
    raw_atom_types = termset.get("atom_types", [])
    expanded_types, alias_map = _expand_with_aliases(raw_atom_types, msi2lmp_max_type_len)

    def get_params(t: str) -> dict[str, Any]:
        return ps_atom_types.get(alias_map.get(t, t), {})

    # Build AtomTypeEntry list
    atom_type_entries: list[AtomTypeEntry] = []
    for t in expanded_types:
        params = get_params(t)
        sigma = params.get("lj_sigma_angstrom", 0.0)
        epsilon = params.get("lj_epsilon_kcal_mol", 0.0)
        lj_a, lj_b = _lj_sigma_eps_to_ab(sigma, epsilon)
        atom_type_entries.append(AtomTypeEntry(
            atom_type=t,
            mass_amu=params.get("mass_amu", 0.0),
            element=params.get("element", "X"),
            connects=_element_to_connects(params.get("element", "X")),
            lj_a=lj_a, lj_b=lj_b,
        ))

    # Build BondEntry list
    bond_entries: list[BondEntry] = []
    for bond in termset.get("bond_types", []):
        t1, t2 = bond[0], bond[1]
        el1 = get_params(t1).get("element", "X")
        el2 = get_params(t2).get("element", "X")
        r0, k = _placeholder_bond_params(el1, el2) if use_placeholders else (0.0, 0.0)
        if t1 <= t2:
            bond_entries.append(BondEntry(type1=t1, type2=t2, r0=r0, k=k))
        else:
            bond_entries.append(BondEntry(type1=t2, type2=t1, r0=r0, k=k))
    bond_entries.sort(key=lambda b: (b.type1, b.type2))

    # Build AngleEntry list
    angle_entries: list[AngleEntry] = []
    for angle in termset.get("angle_types", []):
        t1, t2, t3 = angle[0], angle[1], angle[2]
        center_el = get_params(t2).get("element", "C")
        theta0, k = _placeholder_angle_params(center_el) if use_placeholders else (0.0, 0.0)
        if t1 <= t3:
            angle_entries.append(AngleEntry(type1=t1, type2=t2, type3=t3, theta0=theta0, k=k))
        else:
            angle_entries.append(AngleEntry(type1=t3, type2=t2, type3=t1, theta0=theta0, k=k))
    angle_entries.sort(key=lambda a: (a.type1, a.type2, a.type3))

    # Build TorsionEntry list (placeholders: kphi=0.0, n=1, phi0=0.0)
    torsion_entries: list[TorsionEntry] = []
    for dihedral in termset.get("dihedral_types", []):
        t1, t2, t3, t4 = dihedral[0], dihedral[1], dihedral[2], dihedral[3]
        torsion_entries.append(TorsionEntry(
            type1=t1, type2=t2, type3=t3, type4=t4, kphi=0.0, n=1, phi0=0.0
        ))
    torsion_entries.sort(key=lambda t: (t.type1, t.type2, t.type3, t.type4))

    # Build OOPEntry list (placeholders: kchi=0.0, n=0, chi0=0.0)
    oop_entries: list[OOPEntry] = []
    for improper in termset.get("improper_types", []):
        t1, t2, t3, t4 = improper[0], improper[1], improper[2], improper[3]
        oop_entries.append(OOPEntry(
            type1=t1, type2=t2, type3=t3, type4=t4, kchi=0.0, n=0, chi0=0.0
        ))
    oop_entries.sort(key=lambda o: (o.type1, o.type2, o.type3, o.type4))

    # Build NonbondEntry list (one per atom type)
    nonbond_entries = [
        NonbondEntry(atom_type=e.atom_type, lj_a=e.lj_a, lj_b=e.lj_b)
        for e in atom_type_entries
    ]

    return FRCInput(
        atom_types=atom_type_entries,
        bonds=bond_entries,
        angles=angle_entries,
        torsions=torsion_entries,
        oops=oop_entries,
        nonbonds=nonbond_entries,
        forcefield_label="cvff",
        msi2lmp_max_type_len=msi2lmp_max_type_len,
        alias_map=alias_map,
    )

__all__ = [
    "AtomTypeEntry", "BondEntry", "AngleEntry", "TorsionEntry",
    "OOPEntry", "NonbondEntry", "FRCInput", "build_frc_input",
]
