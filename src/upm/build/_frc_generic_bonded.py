"""Generic bonded parameter generation for FRC files.

This module provides functions for generating generic/placeholder bonded
parameters for CVFF .frc files. The generic parameters are safe defaults
that allow msi2lmp.exe to run without the -ignore flag.

Main functions:
    - generate_generic_bonded_params: Generate formatted bonded parameter lines
    - build_frc_cvff_with_generic_bonded: Build complete FRC with generic bonded params

This is the RECOMMENDED approach for Phase 12+ production workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from upm.build.validators import MissingTypesError
from upm.build.frc_helpers import (
    lj_sigma_eps_to_ab,
    placeholder_bond_params,
    placeholder_angle_params,
    format_skeleton_atom_type_entry,
    format_skeleton_equivalence_entry,
    format_skeleton_auto_equivalence_entry,
    format_skeleton_nonbond_entry,
    format_skeleton_bond_entry,
    format_skeleton_angle_entry,
    format_skeleton_torsion_entry,
    format_skeleton_oop_entry,
    format_skeleton_bond_increment_entry,
    skeleton_element_to_connects,
    build_skeleton_alias_map,
)
from upm.build.frc_templates import CVFF_MINIMAL_SKELETON


def _join_entries_with_trailing_newline(entries: list[str]) -> str:
    """Join entries with newlines, adding trailing newline if non-empty.
    
    This is critical for CVFF_MINIMAL_SKELETON template - when a placeholder
    has content, it needs a trailing newline before the next section header.
    When empty, no trailing newline should be added to avoid blank lines.
    """
    if entries:
        return "\n".join(entries) + "\n"
    return ""


def generate_generic_bonded_params(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    msi2lmp_max_atom_type_len: int = 5,
    expand_bonded_aliases: bool = False,
) -> dict[str, list[str]]:
    """Generate CVFF-formatted bonded parameter lines from termset.
    
    This function extracts bonded type information from the termset and
    generates .frc-formatted entry lines with generic/placeholder parameters.
    The element information from parameterset is used to select appropriate
    parameter values.
    
    Args:
        termset: Output of derive_termset_v0_1_2() with keys:
            - bond_types: list of [t1, t2] pairs
            - angle_types: list of [t1, t2, t3] triplets
            - dihedral_types: list of [t1, t2, t3, t4] quadruplets
            - improper_types: list of [t1, t2, t3, t4] quadruplets
        parameterset: Output of derive_parameterset_v0_1_2() with key:
            - atom_types: dict mapping type name to {"element": ..., ...}
        msi2lmp_max_atom_type_len: Maximum atom type name length for
            msi2lmp.exe compatibility. Only used when expand_bonded_aliases=True.
        expand_bonded_aliases: If True, emit alias variants for bonded entries
            (like Zn_MO for Zn_MOF). If False (default), only use original
            type names from termset.
    
    Returns:
        Dict with keys:
            - bond_entries: list of formatted #quadratic_bond lines
            - angle_entries: list of formatted #quadratic_angle lines
            - torsion_entries: list of formatted #torsion_1 lines
            - oop_entries: list of formatted #out_of_plane lines
            - bond_increment_entries: list of formatted #bond_increments lines
    """
    # 1. Extract atom types and build element mapping
    ts_types = list(termset.get("atom_types") or [])
    ps_map = dict(parameterset.get("atom_types") or {})
    
    # Build element mapping for placeholder parameter selection
    at_to_element: dict[str, str] = {}
    for at in ts_types:
        rec = ps_map.get(at, {})
        at_to_element[at] = str(rec.get("element") or "X")
    
    # 2. Build alias map for msi2lmp truncation compatibility (only if expanding)
    alias_to_source: dict[str, str] = {}
    if expand_bonded_aliases:
        alias_to_source, _ = build_skeleton_alias_map(
            ts_types, msi2lmp_max_atom_type_len
        )
        # Extend element mapping for aliases
        for alias, source in alias_to_source.items():
            at_to_element[alias] = at_to_element.get(source, "X")
    
    # 3. Extract bonded terms from termset
    bond_types = [tuple(x) for x in (termset.get("bond_types") or [])]
    angle_types = [tuple(x) for x in (termset.get("angle_types") or [])]
    dihedral_types = [tuple(x) for x in (termset.get("dihedral_types") or [])]
    improper_types = [tuple(x) for x in (termset.get("improper_types") or [])]
    
    # 4. Helper to get type variants (full name + truncated alias if enabled)
    def _variants(at: str) -> list[str]:
        out = [str(at)]
        if expand_bonded_aliases:
            # Check if at has an alias (at is source, alias is truncated)
            for alias, source in alias_to_source.items():
                if source == at:
                    out.append(alias)
        return sorted(set(out))
    
    def _sort_key(seq: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(str(x) for x in seq)
    
    # 5. Build bonded term lists (no alias expansion when expand_bonded_aliases=False)
    exp_bonds: set[tuple[str, str]] = set()
    for a, b in bond_types:
        for va in _variants(str(a)):
            for vb in _variants(str(b)):
                exp_bonds.add((va, vb))
    
    exp_angles: set[tuple[str, str, str]] = set()
    for a, b, c in angle_types:
        for va in _variants(str(a)):
            for vb in _variants(str(b)):
                for vc in _variants(str(c)):
                    # Include both endpoint orderings (I-J-K and K-J-I)
                    exp_angles.add((va, vb, vc))
                    exp_angles.add((vc, vb, va))
    
    exp_dihedrals: set[tuple[str, str, str, str]] = set()
    for a, b, c, d in dihedral_types:
        for va in _variants(str(a)):
            for vb in _variants(str(b)):
                for vc in _variants(str(c)):
                    for vd in _variants(str(d)):
                        exp_dihedrals.add((va, vb, vc, vd))
    
    # For OOP (impropers): emit original entries only, no permutations
    exp_impropers: set[tuple[str, str, str, str]] = set()
    for a, b, c, d in improper_types:
        for va in _variants(str(a)):
            for vb in _variants(str(b)):
                for vc in _variants(str(c)):
                    for vd in _variants(str(d)):
                        exp_impropers.add((va, vb, vc, vd))
    
    # 6. Sort for deterministic output
    bond_types_sorted = sorted(list(exp_bonds), key=_sort_key)
    angle_types_sorted = sorted(list(exp_angles), key=_sort_key)
    dihedral_types_sorted = sorted(list(exp_dihedrals), key=_sort_key)
    improper_types_sorted = sorted(list(exp_impropers), key=_sort_key)
    
    # 7. Generate bonded entry lines
    bond_entries: list[str] = []
    for t1, t2 in bond_types_sorted:
        el1 = at_to_element.get(t1, "X")
        el2 = at_to_element.get(t2, "X")
        k, r0 = placeholder_bond_params(t1_el=el1, t2_el=el2)
        bond_entries.append(format_skeleton_bond_entry(t1, t2, r0, k))
    
    angle_entries: list[str] = []
    for t1, t2, t3 in angle_types_sorted:
        center_el = at_to_element.get(t2, "X")
        theta0, k = placeholder_angle_params(center_el=center_el)
        angle_entries.append(format_skeleton_angle_entry(t1, t2, t3, theta0, k))
    
    torsion_entries: list[str] = []
    for t1, t2, t3, t4 in dihedral_types_sorted:
        torsion_entries.append(format_skeleton_torsion_entry(t1, t2, t3, t4))
    
    oop_entries: list[str] = []
    for t1, t2, t3, t4 in improper_types_sorted:
        oop_entries.append(format_skeleton_oop_entry(t1, t2, t3, t4))
    
    # Generate bond_increment entries (required by msi2lmp.exe)
    bond_increment_entries: list[str] = []
    for t1, t2 in bond_types_sorted:
        bond_increment_entries.append(format_skeleton_bond_increment_entry(t1, t2))
    
    return {
        "bond_entries": bond_entries,
        "angle_entries": angle_entries,
        "torsion_entries": torsion_entries,
        "oop_entries": oop_entries,
        "bond_increment_entries": bond_increment_entries,
    }


def build_frc_cvff_with_generic_bonded(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
    msi2lmp_max_atom_type_len: int = 5,
    expand_aliases: bool = False,
) -> str:
    """RECOMMENDED: Build minimal CVFF .frc with generic bonded params.
    
    This is the RECOMMENDED builder for Phase 12+ production workflows.
    It produces a compact .frc file (~150-200 lines) that:
    1. Uses the M29/skeleton base structure for minimal overhead
    2. Contains custom atom types from parameterset with LJ parameters
    3. Contains generic bonded parameters for ALL bonded types in termset
    4. Works with msi2lmp.exe WITHOUT the -ignore flag
    
    Args:
        termset: Output of derive_termset_v0_1_2() containing bonded types.
        parameterset: Output of derive_parameterset_v0_1_2() containing
            atom type parameters (mass, LJ sigma/epsilon, element).
        out_path: Where to write the .frc file.
        msi2lmp_max_atom_type_len: Maximum atom type name length (default 5).
        expand_aliases: If True, emit truncated alias variants for long type
            names (e.g., Zn_MO for Zn_MOF).
    
    Returns:
        The output path as a string.
    
    Raises:
        MissingTypesError: If parameterset is missing entries for termset types.
    """
    # 1. Validate coverage
    ts_types = list(termset.get("atom_types") or [])
    ps_map = dict(parameterset.get("atom_types") or {})
    missing = sorted([t for t in ts_types if t not in ps_map])
    if missing:
        raise MissingTypesError(tuple(missing))
    
    # 2. Build alias map for msi2lmp truncation compatibility (only if expanding)
    if expand_aliases:
        alias_to_source, expanded_types = build_skeleton_alias_map(
            ts_types, msi2lmp_max_atom_type_len
        )
    else:
        # No aliases - use original types only
        alias_to_source = {}
        expanded_types = sorted(ts_types)
    
    # Build reverse map: emitted_type -> source_type (for parameter lookup)
    emitted_to_source: dict[str, str] = {}
    for at in ts_types:
        emitted_to_source[at] = at
    for alias, source in alias_to_source.items():
        emitted_to_source[alias] = source
    
    # 3. Generate atom_types, equivalence, auto_equivalence, and nonbond entries
    atom_types_entries: list[str] = []
    equivalence_entries: list[str] = []
    auto_equivalence_entries: list[str] = []
    nonbond_entries: list[str] = []
    
    for at in expanded_types:
        src_at = emitted_to_source[at]
        rec = ps_map[src_at]
        
        # Get element and mass
        element = str(rec.get("element") or "X")
        mass = float(rec["mass_amu"])
        connects = skeleton_element_to_connects(element)
        
        # atom_types entry
        atom_types_entries.append(
            format_skeleton_atom_type_entry(at, mass, element, connects)
        )
        
        # equivalence entry - use source type for all equivalence columns
        equivalence_entries.append(
            format_skeleton_equivalence_entry(at, src_at, src_at, src_at, src_at, src_at)
        )
        
        # auto_equivalence entry - all columns use source type
        auto_equivalence_entries.append(
            format_skeleton_auto_equivalence_entry(at, src_at)
        )
        
        # nonbond entry - compute A/B from sigma/epsilon
        sigma = float(rec["lj_sigma_angstrom"])
        eps = float(rec["lj_epsilon_kcal_mol"])
        a, b = lj_sigma_eps_to_ab(sigma=sigma, epsilon=eps)
        nonbond_entries.append(
            format_skeleton_nonbond_entry(at, a, b)
        )
    
    # 4. Generate bonded parameter entries using the new function
    bonded_params = generate_generic_bonded_params(
        termset, parameterset,
        msi2lmp_max_atom_type_len=msi2lmp_max_atom_type_len,
        expand_bonded_aliases=expand_aliases,
    )
    
    # 5. Populate skeleton with entries
    # Use _join_entries_with_trailing_newline for sections that precede another
    # section header directly (without a blank line) in the template
    content = CVFF_MINIMAL_SKELETON.format(
        atom_types_entries="\n".join(atom_types_entries),
        equivalence_entries="\n".join(equivalence_entries),
        auto_equivalence_entries=_join_entries_with_trailing_newline(auto_equivalence_entries),
        bond_entries="\n".join(bonded_params["bond_entries"]),
        angle_entries="\n".join(bonded_params["angle_entries"]),
        torsion_entries=_join_entries_with_trailing_newline(bonded_params["torsion_entries"]),
        oop_entries=_join_entries_with_trailing_newline(bonded_params["oop_entries"]),
        nonbond_entries="\n".join(nonbond_entries),
        bond_increments_entries="\n".join(bonded_params["bond_increment_entries"]),
    )
    
    # 6. Write output
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


__all__ = [
    "generate_generic_bonded_params",
    "build_frc_cvff_with_generic_bonded",
]
