"""FRC table filtering utilities.

This module provides functions for filtering parsed FRC tables to extract
only the entries needed for a specific termset. It handles:
- Filtering atom_types by exact match
- Filtering bonds/angles by canonicalized type keys
- Deduplication of entries (source FRC files often have multiple versions)

Main function:
    - filter_frc_tables: Filter FRC tables to required atom types from termset
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from upm.core.model import canonicalize_angle_key, canonicalize_bond_key


def filter_frc_tables(
    tables: dict[str, pd.DataFrame],
    termset: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Filter FRC tables to only include entries for required atom types.
    
    This function extracts only the entries from parsed FRC tables that match
    the types specified in the termset. It handles canonicalization of bond
    and angle types to ensure matching regardless of atom type ordering.
    
    Additionally, this function deduplicates entries when the source FRC file
    contains multiple entries for the same type (e.g., different versions).
    For deduplication:
    - atom_types: prefer entries with lj_a/lj_b populated; otherwise keep last
    - bonds: keep last entry for each (t1, t2, style) key
    - angles: keep last entry for each (t1, t2, t3, style) key
    
    Args:
        tables: Parsed FRC tables from read_frc() with keys like 'atom_types',
            'bonds', 'angles', etc. Each value is a pandas DataFrame.
        termset: TermSet dict with keys 'atom_types', 'bond_types', 'angle_types',
            etc. The types are used to filter matching entries from tables.
    
    Returns:
        Filtered tables dict with only matching entries. Tables that have no
        matching entries are omitted from the result. All duplicates are removed.
    
    Example:
        >>> tables, _ = read_frc("large.frc", validate=False)
        >>> termset = {"atom_types": ["cdc", "cdo"], "bond_types": [["cdc", "cdo"]]}
        >>> filtered = filter_frc_tables(tables, termset)
        >>> # filtered["atom_types"] contains only cdc, cdo rows (deduplicated)
        >>> # filtered["bonds"] contains only cdc-cdo bond
    """
    result: dict[str, pd.DataFrame] = {}
    
    # 1. Filter atom_types by exact match on atom_type column
    required_atom_types = set(termset.get("atom_types") or [])
    if "atom_types" in tables and not tables["atom_types"].empty:
        at_df = tables["atom_types"]
        mask = at_df["atom_type"].isin(required_atom_types)
        filtered_at = at_df[mask].copy()
        
        if not filtered_at.empty:
            # Deduplicate: prefer entries with lj_a/lj_b populated
            # Group by atom_type and select best entry
            deduplicated_rows = []
            for atom_type in filtered_at["atom_type"].unique():
                candidates = filtered_at[filtered_at["atom_type"] == atom_type]
                if len(candidates) == 1:
                    deduplicated_rows.append(candidates.iloc[0])
                else:
                    # Prefer entry with lj_a and lj_b populated (not null)
                    has_lj = candidates["lj_a"].notna() & candidates["lj_b"].notna()
                    with_lj = candidates[has_lj]
                    if not with_lj.empty:
                        # Take last entry with LJ params (later versions typically better)
                        deduplicated_rows.append(with_lj.iloc[-1])
                    else:
                        # No entries have LJ params - take last entry
                        deduplicated_rows.append(candidates.iloc[-1])
            
            result["atom_types"] = pd.DataFrame(deduplicated_rows).reset_index(drop=True)
    
    # 2. Filter bonds by canonicalized (t1, t2) matching
    raw_bond_types = termset.get("bond_types") or []
    required_bonds: set[tuple[str, str]] = set()
    for bt in raw_bond_types:
        if len(bt) >= 2:
            # Canonicalize: t1 <= t2 lexicographically
            canon = canonicalize_bond_key(str(bt[0]), str(bt[1]))
            required_bonds.add(canon)
    
    if "bonds" in tables and not tables["bonds"].empty and required_bonds:
        bonds_df = tables["bonds"]
        
        def _bond_matches(row: pd.Series) -> bool:
            t1, t2 = str(row["t1"]), str(row["t2"])
            canon = canonicalize_bond_key(t1, t2)
            return canon in required_bonds
        
        mask = bonds_df.apply(_bond_matches, axis=1)
        filtered_bonds = bonds_df[mask].copy()
        
        if not filtered_bonds.empty:
            # Deduplicate: keep last entry for each (t1, t2, style) key
            # Add canonical key column for deduplication
            def _get_canon_bond_key(row: pd.Series) -> str:
                t1, t2 = canonicalize_bond_key(str(row["t1"]), str(row["t2"]))
                style = str(row["style"]) if pd.notna(row["style"]) else ""
                return f"{t1}|{t2}|{style}"
            
            filtered_bonds["_canon_key"] = filtered_bonds.apply(_get_canon_bond_key, axis=1)
            # Keep last occurrence of each key
            filtered_bonds = filtered_bonds.drop_duplicates(subset=["_canon_key"], keep="last")
            filtered_bonds = filtered_bonds.drop(columns=["_canon_key"]).reset_index(drop=True)
            result["bonds"] = filtered_bonds
    
    # 3. Filter angles by canonicalized (t1, t2, t3) matching
    raw_angle_types = termset.get("angle_types") or []
    required_angles: set[tuple[str, str, str]] = set()
    for at in raw_angle_types:
        if len(at) >= 3:
            # Canonicalize: t1 <= t3 lexicographically (center stays in place)
            canon = canonicalize_angle_key(str(at[0]), str(at[1]), str(at[2]))
            required_angles.add(canon)
    
    if "angles" in tables and not tables["angles"].empty and required_angles:
        angles_df = tables["angles"]
        
        def _angle_matches(row: pd.Series) -> bool:
            t1, t2, t3 = str(row["t1"]), str(row["t2"]), str(row["t3"])
            canon = canonicalize_angle_key(t1, t2, t3)
            return canon in required_angles
        
        mask = angles_df.apply(_angle_matches, axis=1)
        filtered_angles = angles_df[mask].copy()
        
        if not filtered_angles.empty:
            # Deduplicate: keep last entry for each (t1, t2, t3, style) key
            def _get_canon_angle_key(row: pd.Series) -> str:
                t1, t2, t3 = canonicalize_angle_key(
                    str(row["t1"]), str(row["t2"]), str(row["t3"])
                )
                style = str(row["style"]) if pd.notna(row["style"]) else ""
                return f"{t1}|{t2}|{t3}|{style}"
            
            filtered_angles["_canon_key"] = filtered_angles.apply(_get_canon_angle_key, axis=1)
            # Keep last occurrence of each key
            filtered_angles = filtered_angles.drop_duplicates(subset=["_canon_key"], keep="last")
            filtered_angles = filtered_angles.drop(columns=["_canon_key"]).reset_index(drop=True)
            result["angles"] = filtered_angles
    
    # 4. Filter bond_increments by canonicalized (t1, t2) matching (same as bonds)
    if "bond_increments" in tables and not tables["bond_increments"].empty and required_bonds:
        bi_df = tables["bond_increments"]
        
        def _bi_matches(row: pd.Series) -> bool:
            t1, t2 = str(row["t1"]), str(row["t2"])
            canon = canonicalize_bond_key(t1, t2)
            return canon in required_bonds
        
        mask = bi_df.apply(_bi_matches, axis=1)
        filtered_bi = bi_df[mask].copy()
        
        if not filtered_bi.empty:
            # Deduplicate: keep last entry for each (t1, t2) key
            def _get_canon_bi_key(row: pd.Series) -> str:
                t1, t2 = canonicalize_bond_key(str(row["t1"]), str(row["t2"]))
                return f"{t1}|{t2}"
            
            filtered_bi["_canon_key"] = filtered_bi.apply(_get_canon_bi_key, axis=1)
            # Keep last occurrence of each key
            filtered_bi = filtered_bi.drop_duplicates(subset=["_canon_key"], keep="last")
            filtered_bi = filtered_bi.drop(columns=["_canon_key"]).reset_index(drop=True)
            result["bond_increments"] = filtered_bi
    
    return result


__all__ = ["filter_frc_tables"]
