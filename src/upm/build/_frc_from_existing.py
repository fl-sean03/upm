"""Build FRC files by extracting parameters from existing source FRC.

This module provides functionality to create minimal FRC files by extracting
real parameters (not placeholders) from a larger source FRC file. This is
useful when you have a comprehensive force field file and need to create
a minimal version containing only the parameters for specific atom types.

Main function:
    - build_frc_from_existing: Extract params from source FRC for termset types
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from upm.codecs.msi_frc import read_frc
from upm.core.model import canonicalize_angle_key, canonicalize_bond_key
from upm.build.validators import MissingTypesError
from upm.build.frc_helpers import (
    format_skeleton_atom_type_entry,
    format_skeleton_equivalence_entry,
    format_skeleton_nonbond_entry,
    format_skeleton_bond_entry,
    format_skeleton_angle_entry,
    format_skeleton_bond_increment_entry,
)
from upm.build.frc_templates import CVFF_MINIMAL_SKELETON
from upm.build._frc_filters import filter_frc_tables


def build_frc_from_existing(
    termset: dict[str, Any],
    source_frc_path: str | Path,
    *,
    out_path: str | Path,
    parameterset: dict[str, Any] | None = None,
    strict: bool = True,
) -> str:
    """Build minimal FRC by extracting real params from existing FRC.
    
    This builder parses an existing .frc file and extracts only the parameters
    needed for the atom types specified in the termset. Unlike
    build_frc_cvff_with_generic_bonded() which uses placeholder parameters,
    this function extracts the actual k, r0, theta0 values from the source file.
    
    This is useful when you have a large comprehensive .frc file (e.g., cvff_iff_ILs.frc)
    and want to create a minimal version containing only the parameters needed
    for a specific molecule.
    
    Args:
        termset: Required types from derive_termset_v0_1_2(). Must contain keys:
            - atom_types: list of atom type names
            - bond_types: list of [t1, t2] pairs (optional)
            - angle_types: list of [t1, t2, t3] triplets (optional)
        source_frc_path: Path to large existing .frc file to extract params from.
        out_path: Where to write the minimal .frc file.
        parameterset: Optional. If provided, can be used to supplement or
            override mass values from the source FRC. Currently unused but
            reserved for future extensibility.
        strict: If True (default), raise MissingTypesError if the source .frc
            file doesn't contain all required atom types. If False, proceed
            with whatever types were found (useful for debugging).
    
    Returns:
        Output path as string.
        
    Raises:
        MissingTypesError: If strict=True and source doesn't have all required
            atom types from termset.
        FileNotFoundError: If source_frc_path doesn't exist.
    
    Example:
        >>> termset = {
        ...     "atom_types": ["cdc", "cdo"],
        ...     "bond_types": [["cdc", "cdo"]],
        ...     "angle_types": [["cdo", "cdc", "cdo"]],
        ... }
        >>> build_frc_from_existing(
        ...     termset,
        ...     "cvff_iff_ILs.frc",  # Large source file
        ...     out_path="minimal_co2.frc",
        ... )
        'minimal_co2.frc'
    """
    # Suppress unused parameter warning - reserved for future use
    _ = parameterset
    
    # 1. Parse source FRC file
    # Use validate=False because source FRC files often have duplicate entries
    # (e.g., same atom type with different versions). Deduplication happens in
    # filter_frc_tables() after filtering to only the required types.
    source_path = Path(source_frc_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source FRC file not found: {source_path}")
    
    tables, _unknown_sections = read_frc(source_path, validate=False)
    
    # 2. Filter tables to only required types
    filtered_tables = filter_frc_tables(tables, termset)
    
    # 3. Check for missing atom types (if strict mode)
    required_atom_types = set(termset.get("atom_types") or [])
    if "atom_types" in filtered_tables:
        found_atom_types = set(filtered_tables["atom_types"]["atom_type"].tolist())
    else:
        found_atom_types = set()
    
    missing = sorted(required_atom_types - found_atom_types)
    if missing and strict:
        raise MissingTypesError(tuple(missing))
    
    # 4. Check for missing bond types (if strict mode)
    if strict:
        required_bonds = set()
        for bt in (termset.get("bond_types") or []):
            if len(bt) >= 2:
                required_bonds.add(canonicalize_bond_key(str(bt[0]), str(bt[1])))
        
        if required_bonds:
            found_bonds = set()
            if "bonds" in filtered_tables:
                for _, row in filtered_tables["bonds"].iterrows():
                    found_bonds.add(canonicalize_bond_key(str(row["t1"]), str(row["t2"])))
            
            missing_bonds = required_bonds - found_bonds
            if missing_bonds:
                # Format as readable string for error message
                missing_bond_strs = [f"{b[0]}-{b[1]}" for b in sorted(missing_bonds)]
                raise MissingTypesError(tuple(missing_bond_strs))
    
    # 5. Check for missing angle types (if strict mode)
    if strict:
        required_angles = set()
        for at in (termset.get("angle_types") or []):
            if len(at) >= 3:
                required_angles.add(canonicalize_angle_key(str(at[0]), str(at[1]), str(at[2])))
        
        if required_angles:
            found_angles = set()
            if "angles" in filtered_tables:
                for _, row in filtered_tables["angles"].iterrows():
                    found_angles.add(canonicalize_angle_key(
                        str(row["t1"]), str(row["t2"]), str(row["t3"])
                    ))
            
            missing_angles = required_angles - found_angles
            if missing_angles:
                # Format as readable string for error message
                missing_angle_strs = [f"{a[0]}-{a[1]}-{a[2]}" for a in sorted(missing_angles)]
                raise MissingTypesError(tuple(missing_angle_strs))
    
    # 6. Generate formatted entries from filtered tables using the skeleton template
    # The skeleton template is required for msi2lmp.exe compatibility because it
    # needs all the CVFF sections (equivalence, auto_equivalence, hbond_definition, etc.)
    
    # Generate atom_types entries
    atom_types_entries: list[str] = []
    equivalence_entries: list[str] = []
    # NOTE: auto_equivalence section must be EMPTY (header only) per FINDINGS.md
    # Entries in #auto_equivalence cause msi2lmp segfaults
    
    if "atom_types" in filtered_tables:
        at_df = filtered_tables["atom_types"]
        for _, row in at_df.iterrows():
            at = str(row["atom_type"])
            mass = float(row["mass_amu"]) if pd.notna(row["mass_amu"]) else 0.0
            element = str(row["element"]) if pd.notna(row["element"]) else "X"
            notes = str(row["notes"]) if pd.notna(row["notes"]) else ""
            
            # Parse connects from notes if present (e.g., "2 C in CO2" -> connects=2)
            connects = 1
            if notes and notes[0].isdigit():
                parts = notes.split(None, 1)
                if parts:
                    try:
                        connects = int(parts[0])
                        notes = parts[1] if len(parts) > 1 else ""
                    except ValueError:
                        pass
            
            # Format: ver ref type mass element connects notes
            atom_types_entries.append(
                format_skeleton_atom_type_entry(at, mass, element, connects)
            )
            
            # Equivalence entry - all columns use same type
            equivalence_entries.append(
                format_skeleton_equivalence_entry(at, at, at, at, at, at)
            )
    
    # Generate bond entries
    bond_entries: list[str] = []
    bond_increment_entries: list[str] = []
    
    # Build bond_increments lookup from filtered tables if available
    bi_lookup: dict[tuple[str, str], tuple[float, float]] = {}
    if "bond_increments" in filtered_tables:
        bi_df = filtered_tables["bond_increments"]
        for _, row in bi_df.iterrows():
            t1, t2 = str(row["t1"]), str(row["t2"])
            canon = canonicalize_bond_key(t1, t2)
            bi_lookup[canon] = (float(row["delta_ij"]), float(row["delta_ji"]))
    
    if "bonds" in filtered_tables:
        bonds_df = filtered_tables["bonds"]
        for _, row in bonds_df.iterrows():
            t1 = str(row["t1"])
            t2 = str(row["t2"])
            r0 = float(row["r0"]) if pd.notna(row["r0"]) else 1.5
            k = float(row["k"]) if pd.notna(row["k"]) else 300.0
            
            bond_entries.append(format_skeleton_bond_entry(t1, t2, r0, k))
            
            # Look up actual bond increment values or use defaults
            canon = canonicalize_bond_key(t1, t2)
            if canon in bi_lookup:
                delta_ij, delta_ji = bi_lookup[canon]
            else:
                delta_ij, delta_ji = 0.0, 0.0
            bond_increment_entries.append(
                format_skeleton_bond_increment_entry(t1, t2, delta_ij, delta_ji)
            )
    
    # Generate angle entries
    angle_entries: list[str] = []
    
    if "angles" in filtered_tables:
        angles_df = filtered_tables["angles"]
        for _, row in angles_df.iterrows():
            t1 = str(row["t1"])
            t2 = str(row["t2"])
            t3 = str(row["t3"])
            theta0 = float(row["theta0_deg"]) if pd.notna(row["theta0_deg"]) else 109.5
            k = float(row["k"]) if pd.notna(row["k"]) else 50.0
            
            angle_entries.append(format_skeleton_angle_entry(t1, t2, t3, theta0, k))
    
    # Generate nonbond entries from atom_types (lj_a, lj_b)
    nonbond_entries: list[str] = []
    
    if "atom_types" in filtered_tables:
        at_df = filtered_tables["atom_types"]
        for _, row in at_df.iterrows():
            at = str(row["atom_type"])
            lj_a = float(row["lj_a"]) if pd.notna(row["lj_a"]) else 0.0
            lj_b = float(row["lj_b"]) if pd.notna(row["lj_b"]) else 0.0
            
            nonbond_entries.append(format_skeleton_nonbond_entry(at, lj_a, lj_b))
    
    # 7. Populate skeleton with entries
    # NOTE: auto_equivalence_entries MUST be empty per FINDINGS.md to avoid msi2lmp segfaults
    content = CVFF_MINIMAL_SKELETON.format(
        atom_types_entries="\n".join(atom_types_entries),
        equivalence_entries="\n".join(equivalence_entries),
        auto_equivalence_entries="",  # MUST be empty - entries cause segfault
        bond_entries="\n".join(bond_entries),
        angle_entries="\n".join(angle_entries),
        torsion_entries="",  # No torsions for simple molecules
        oop_entries="",      # No out-of-plane for simple molecules
        nonbond_entries="\n".join(nonbond_entries),
        bond_increments_entries="\n".join(bond_increment_entries),
    )
    
    # 8. Write output
    output_path = Path(out_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    
    return str(output_path)


__all__ = ["build_frc_from_existing"]
