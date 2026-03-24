"""MDF Topology Parser & Bonded Type Extractor.

Phase 11 utility: Parse MSI MDF files and extract all bonded topology types
needed for forcefield parameter assignment.

This module provides:
- BondedTypeSet dataclass for structured bonded type storage
- extract_bonded_types_from_mdf() for MDF file parsing
- extract_bonded_types_from_usm() for direct USM processing
- Canonicalization functions for deterministic ordering

Usage:
    from upm.build.topology_extractor import extract_bonded_types_from_mdf
    
    result = extract_bonded_types_from_mdf("CALF20.mdf")
    print(f"Bond types: {len(result.bonds)}")
    print(f"Angle types: {len(result.angles)}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, FrozenSet

import pandas as pd

if TYPE_CHECKING:
    from usm.core.model import USM


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True)
class BondedTypeSet:
    """Immutable set of canonical bonded interaction types extracted from topology.
    
    All tuples are canonicalized for deterministic ordering:
    - bonds: (A, B) where A <= B alphabetically
    - angles: (A, B, C) where A <= C, B is center
    - torsions: (A, B, C, D) where tuple <= reversed tuple lexicographically
    - out_of_plane: (center, p1, p2, p3) where p1 <= p2 <= p3
    
    Attributes:
        bonds: Canonical bond type pairs (t1, t2)
        angles: Canonical angle type triplets (end, center, end)
        torsions: Canonical torsion type quadruplets (t1, t2, t3, t4)
        out_of_plane: Canonical OOP types (center, peripheral1, peripheral2, peripheral3)
    """
    
    bonds: FrozenSet[tuple[str, str]] = field(default_factory=frozenset)
    angles: FrozenSet[tuple[str, str, str]] = field(default_factory=frozenset)
    torsions: FrozenSet[tuple[str, str, str, str]] = field(default_factory=frozenset)
    out_of_plane: FrozenSet[tuple[str, str, str, str]] = field(default_factory=frozenset)
    
    def __repr__(self) -> str:
        return (
            f"BondedTypeSet(bonds={len(self.bonds)}, angles={len(self.angles)}, "
            f"torsions={len(self.torsions)}, out_of_plane={len(self.out_of_plane)})"
        )


@dataclass
class _MolecularGraph:
    """Internal graph representation for topology traversal.
    
    Attributes:
        atom_types: Mapping from atom name to atom type
        adjacency: Mapping from atom name to set of neighbor atom names
    """
    
    atom_types: dict[str, str] = field(default_factory=dict)
    adjacency: dict[str, set[str]] = field(default_factory=dict)


# =============================================================================
# Canonicalization Functions
# =============================================================================


def canonicalize_bond(t1: str, t2: str) -> tuple[str, str]:
    """Canonicalize a bond type pair by sorting alphabetically.
    
    Args:
        t1: First atom type
        t2: Second atom type
        
    Returns:
        Canonical (min, max) tuple
        
    Example:
        >>> canonicalize_bond("Zn_MOF", "N_MOF")
        ('N_MOF', 'Zn_MOF')
    """
    return (t1, t2) if t1 <= t2 else (t2, t1)


def canonicalize_angle(t1: str, center: str, t2: str) -> tuple[str, str, str]:
    """Canonicalize an angle type triplet (center stays in middle).
    
    Args:
        t1: First end atom type
        center: Center atom type
        t2: Second end atom type
        
    Returns:
        Canonical (min_end, center, max_end) tuple
        
    Example:
        >>> canonicalize_angle("O_MOF", "Zn_MOF", "N_MOF")
        ('N_MOF', 'Zn_MOF', 'O_MOF')
    """
    if t1 <= t2:
        return (t1, center, t2)
    return (t2, center, t1)


def canonicalize_torsion(t1: str, t2: str, t3: str, t4: str) -> tuple[str, str, str, str]:
    """Canonicalize a torsion type quadruplet by comparing forward vs reverse.
    
    Args:
        t1: First atom type
        t2: Second atom type (bonded to t1)
        t3: Third atom type (bonded to t2)
        t4: Fourth atom type (bonded to t3)
        
    Returns:
        Canonical tuple where forward <= reverse lexicographically
        
    Example:
        >>> canonicalize_torsion("O_MOF", "Zn_MOF", "N_MOF", "C_MOF")
        ('C_MOF', 'N_MOF', 'Zn_MOF', 'O_MOF')
    """
    forward = (t1, t2, t3, t4)
    reverse = (t4, t3, t2, t1)
    return forward if forward <= reverse else reverse


def canonicalize_oop(center: str, p1: str, p2: str, p3: str) -> tuple[str, str, str, str]:
    """Canonicalize an out-of-plane type (center fixed, peripherals sorted).
    
    Args:
        center: Center atom type (stays in position 0)
        p1: First peripheral atom type
        p2: Second peripheral atom type
        p3: Third peripheral atom type
        
    Returns:
        Canonical (center, sorted_p1, sorted_p2, sorted_p3) tuple
        
    Example:
        >>> canonicalize_oop("C_MOF", "N_MOF", "H_MOF", "N_MOF")
        ('C_MOF', 'H_MOF', 'N_MOF', 'N_MOF')
    """
    peripherals = tuple(sorted([p1, p2, p3]))
    return (center, peripherals[0], peripherals[1], peripherals[2])


# =============================================================================
# Graph Construction
# =============================================================================


def _build_molecular_graph_from_usm(usm: "USM") -> _MolecularGraph:
    """Build internal molecular graph from USM object.
    
    Args:
        usm: USM object with atoms and bonds DataFrames
        
    Returns:
        MolecularGraph with atom_types and adjacency mappings
    """
    graph = _MolecularGraph()
    
    # Build atom_types map: name -> type
    # Use (mol_label, mol_index, name) as unique key, but for single-molecule
    # MDF files, just name is sufficient
    atoms = usm.atoms
    
    # Create a unique key for each atom
    for _, row in atoms.iterrows():
        mol_label = str(row.get("mol_label", "XXXX"))
        mol_index = int(row.get("mol_index", 1))
        name = str(row["name"])
        atom_type = str(row["atom_type"])
        
        # Use tuple key for multi-molecule support
        key = (mol_label, mol_index, name)
        graph.atom_types[key] = atom_type
        graph.adjacency[key] = set()
    
    # Build adjacency from bonds
    if usm.bonds is not None and len(usm.bonds) > 0:
        # Create aid -> key mapping
        aid_to_key: dict[int, tuple[str, int, str]] = {}
        for _, row in atoms.iterrows():
            aid = int(row["aid"])
            mol_label = str(row.get("mol_label", "XXXX"))
            mol_index = int(row.get("mol_index", 1))
            name = str(row["name"])
            aid_to_key[aid] = (mol_label, mol_index, name)
        
        for _, bond in usm.bonds.iterrows():
            a1 = int(bond["a1"])
            a2 = int(bond["a2"])
            
            key1 = aid_to_key.get(a1)
            key2 = aid_to_key.get(a2)
            
            if key1 is not None and key2 is not None:
                graph.adjacency[key1].add(key2)
                graph.adjacency[key2].add(key1)
    
    return graph


# =============================================================================
# Bonded Type Extraction
# =============================================================================


def _extract_bonds(graph: _MolecularGraph) -> FrozenSet[tuple[str, str]]:
    """Extract canonical bond types from molecular graph.
    
    Args:
        graph: Molecular graph with atom_types and adjacency
        
    Returns:
        FrozenSet of canonical bond type tuples
    """
    bonds: set[tuple[str, str]] = set()
    seen_edges: set[tuple[tuple[str, int, str], tuple[str, int, str]]] = set()
    
    for atom_key, neighbors in graph.adjacency.items():
        t1 = graph.atom_types[atom_key]
        
        for neighbor_key in neighbors:
            # Avoid counting same edge twice
            edge = tuple(sorted([atom_key, neighbor_key], key=str))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            
            t2 = graph.atom_types[neighbor_key]
            bonds.add(canonicalize_bond(t1, t2))
    
    return frozenset(bonds)


def _extract_angles(graph: _MolecularGraph) -> FrozenSet[tuple[str, str, str]]:
    """Extract canonical angle types from molecular graph.
    
    An angle is defined by a center atom with at least 2 neighbors.
    For each pair of neighbors, we create an angle: (neighbor1, center, neighbor2).
    
    Args:
        graph: Molecular graph with atom_types and adjacency
        
    Returns:
        FrozenSet of canonical angle type tuples
    """
    angles: set[tuple[str, str, str]] = set()
    
    for center_key, neighbors in graph.adjacency.items():
        if len(neighbors) < 2:
            continue
        
        center_type = graph.atom_types[center_key]
        neighbor_list = list(neighbors)
        
        # Enumerate all pairs of neighbors
        for n1_key, n2_key in combinations(neighbor_list, 2):
            t1 = graph.atom_types[n1_key]
            t2 = graph.atom_types[n2_key]
            angles.add(canonicalize_angle(t1, center_type, t2))
    
    return frozenset(angles)


def _extract_torsions(graph: _MolecularGraph) -> FrozenSet[tuple[str, str, str, str]]:
    """Extract canonical torsion (dihedral) types from molecular graph.
    
    A torsion is defined by a central bond (a-b) and neighbors on each end:
    neighbor_a - a - b - neighbor_b
    
    Args:
        graph: Molecular graph with atom_types and adjacency
        
    Returns:
        FrozenSet of canonical torsion type tuples
    """
    torsions: set[tuple[str, str, str, str]] = set()
    seen_edges: set[tuple[tuple[str, int, str], tuple[str, int, str]]] = set()
    
    # Iterate over all bonds (edges)
    for a_key, neighbors_a in graph.adjacency.items():
        for b_key in neighbors_a:
            # Avoid processing same edge twice
            edge = tuple(sorted([a_key, b_key], key=str))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            
            t_a = graph.atom_types[a_key]
            t_b = graph.atom_types[b_key]
            
            # Get neighbors of a (excluding b)
            neighbors_a_excl = [n for n in graph.adjacency[a_key] if n != b_key]
            # Get neighbors of b (excluding a)
            neighbors_b_excl = [n for n in graph.adjacency[b_key] if n != a_key]
            
            # Create all torsions: neighbor_a - a - b - neighbor_b
            for na_key in neighbors_a_excl:
                t_na = graph.atom_types[na_key]
                for nb_key in neighbors_b_excl:
                    t_nb = graph.atom_types[nb_key]
                    torsions.add(canonicalize_torsion(t_na, t_a, t_b, t_nb))
    
    return frozenset(torsions)


def _extract_out_of_plane(graph: _MolecularGraph) -> FrozenSet[tuple[str, str, str, str]]:
    """Extract canonical out-of-plane (improper) types from molecular graph.
    
    An OOP center is an atom with exactly 3 neighbors (trigonal planar centers).
    The OOP type is (center, peripheral1, peripheral2, peripheral3).
    
    Args:
        graph: Molecular graph with atom_types and adjacency
        
    Returns:
        FrozenSet of canonical OOP type tuples
    """
    oop: set[tuple[str, str, str, str]] = set()
    
    for center_key, neighbors in graph.adjacency.items():
        if len(neighbors) != 3:
            continue
        
        center_type = graph.atom_types[center_key]
        neighbor_types = [graph.atom_types[n] for n in neighbors]
        
        oop.add(canonicalize_oop(center_type, neighbor_types[0], neighbor_types[1], neighbor_types[2]))
    
    return frozenset(oop)


# =============================================================================
# Public API
# =============================================================================


def extract_bonded_types_from_usm(usm: "USM") -> BondedTypeSet:
    """Extract all bonded types from a USM object.
    
    Args:
        usm: USM object with atoms and bonds DataFrames
        
    Returns:
        BondedTypeSet with all canonical bonded interaction types
        
    Example:
        >>> from usm.io.mdf import load_mdf
        >>> usm = load_mdf("CALF20.mdf")
        >>> result = extract_bonded_types_from_usm(usm)
        >>> len(result.bonds)
        6
    """
    graph = _build_molecular_graph_from_usm(usm)
    
    return BondedTypeSet(
        bonds=_extract_bonds(graph),
        angles=_extract_angles(graph),
        torsions=_extract_torsions(graph),
        out_of_plane=_extract_out_of_plane(graph),
    )


def extract_bonded_types_from_mdf(mdf_path: str | Path) -> BondedTypeSet:
    """Extract all bonded types from an MDF file.
    
    This is the main entry point for MDF topology parsing. It:
    1. Loads the MDF file using the USM parser
    2. Builds a molecular graph from the connectivity
    3. Extracts and canonicalizes all bonded interaction types
    
    Args:
        mdf_path: Path to the MDF file
        
    Returns:
        BondedTypeSet with all canonical bonded interaction types
        
    Example:
        >>> result = extract_bonded_types_from_mdf("CALF20.mdf")
        >>> print(f"Bond types: {len(result.bonds)}")
        Bond types: 6
        >>> print(f"Angle types: {len(result.angles)}")
        Angle types: 11
        >>> ("N_MOF", "Zn_MOF") in result.bonds
        True
    """
    # Import here to avoid circular imports
    from usm.io.mdf import load_mdf
    
    usm = load_mdf(str(mdf_path))
    return extract_bonded_types_from_usm(usm)
