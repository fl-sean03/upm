"""Tests for MDF Topology Parser & Bonded Type Extractor.

Phase 11: Verify extraction of bonded types from CALF20.mdf and test
canonicalization correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from upm.build.topology_extractor import (
    BondedTypeSet,
    canonicalize_angle,
    canonicalize_bond,
    canonicalize_oop,
    canonicalize_torsion,
    extract_bonded_types_from_mdf,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calf20_mdf_path() -> Path:
    """Path to the CALF20.mdf test file."""
    # Navigate from tests/ to workspace root
    workspace_root = Path(__file__).parent.parent.parent.parent.parent
    mdf_path = workspace_root / "workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/inputs/CALF20.mdf"
    if not mdf_path.exists():
        pytest.skip(f"CALF20.mdf not found at {mdf_path}")
    return mdf_path


@pytest.fixture
def calf20_bonded_types(calf20_mdf_path: Path) -> BondedTypeSet:
    """Extract bonded types from CALF20.mdf."""
    return extract_bonded_types_from_mdf(calf20_mdf_path)


# =============================================================================
# Canonicalization Tests
# =============================================================================


class TestCanonicalizeBond:
    """Tests for bond canonicalization."""
    
    def test_already_canonical(self) -> None:
        """Bond already in canonical order stays unchanged."""
        assert canonicalize_bond("A", "B") == ("A", "B")
    
    def test_reverse_order(self) -> None:
        """Bond in reverse order gets sorted."""
        assert canonicalize_bond("B", "A") == ("A", "B")
    
    def test_same_types(self) -> None:
        """Same atom types work correctly."""
        assert canonicalize_bond("N_MOF", "N_MOF") == ("N_MOF", "N_MOF")
    
    def test_mof_types(self) -> None:
        """MOF atom types canonicalize correctly."""
        assert canonicalize_bond("Zn_MOF", "N_MOF") == ("N_MOF", "Zn_MOF")
        assert canonicalize_bond("N_MOF", "Zn_MOF") == ("N_MOF", "Zn_MOF")


class TestCanonicalizeAngle:
    """Tests for angle canonicalization."""
    
    def test_already_canonical(self) -> None:
        """Angle already in canonical order stays unchanged."""
        assert canonicalize_angle("A", "B", "C") == ("A", "B", "C")
    
    def test_reverse_ends(self) -> None:
        """Angle with reversed ends gets sorted (center stays)."""
        assert canonicalize_angle("C", "B", "A") == ("A", "B", "C")
    
    def test_center_preserved(self) -> None:
        """Center atom type always stays in middle."""
        assert canonicalize_angle("Z", "M", "A") == ("A", "M", "Z")
    
    def test_same_end_types(self) -> None:
        """Same end types work correctly."""
        assert canonicalize_angle("N_MOF", "Zn_MOF", "N_MOF") == ("N_MOF", "Zn_MOF", "N_MOF")
    
    def test_mof_angle(self) -> None:
        """MOF angle types canonicalize correctly."""
        # O-Zn-N should become N-Zn-O (alphabetical ends)
        assert canonicalize_angle("O_MOF", "Zn_MOF", "N_MOF") == ("N_MOF", "Zn_MOF", "O_MOF")


class TestCanonicalizeTorsion:
    """Tests for torsion canonicalization."""
    
    def test_already_canonical(self) -> None:
        """Torsion already in canonical order stays unchanged."""
        assert canonicalize_torsion("A", "B", "C", "D") == ("A", "B", "C", "D")
    
    def test_reverse_order(self) -> None:
        """Torsion in reverse order gets reversed."""
        assert canonicalize_torsion("D", "C", "B", "A") == ("A", "B", "C", "D")
    
    def test_compare_by_first(self) -> None:
        """First atom comparison determines order."""
        assert canonicalize_torsion("Z", "B", "C", "A") == ("A", "C", "B", "Z")
    
    def test_equal_first_compare_second(self) -> None:
        """When first atoms equal, compare second atoms."""
        assert canonicalize_torsion("A", "Z", "B", "A") == ("A", "B", "Z", "A")
    
    def test_mof_torsion(self) -> None:
        """MOF torsion types canonicalize correctly."""
        # O-Zn-N-C should become C-N-Zn-O (C < O)
        assert canonicalize_torsion("O_MOF", "Zn_MOF", "N_MOF", "C_MOF") == ("C_MOF", "N_MOF", "Zn_MOF", "O_MOF")


class TestCanonicalizeOop:
    """Tests for out-of-plane canonicalization."""
    
    def test_already_sorted(self) -> None:
        """OOP with already sorted peripherals stays unchanged."""
        assert canonicalize_oop("C", "A", "B", "D") == ("C", "A", "B", "D")
    
    def test_unsorted_peripherals(self) -> None:
        """OOP peripherals get sorted alphabetically."""
        assert canonicalize_oop("C", "D", "A", "B") == ("C", "A", "B", "D")
    
    def test_center_preserved(self) -> None:
        """Center stays in first position."""
        assert canonicalize_oop("X", "C", "A", "B") == ("X", "A", "B", "C")
    
    def test_duplicate_peripherals(self) -> None:
        """Duplicate peripheral types work correctly."""
        assert canonicalize_oop("C_MOF", "N_MOF", "H_MOF", "N_MOF") == ("C_MOF", "H_MOF", "N_MOF", "N_MOF")


# =============================================================================
# CALF20 Extraction Tests
# =============================================================================


class TestCalf20BondTypes:
    """Tests for CALF20 bond type extraction."""
    
    def test_bond_count(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should have exactly 6 unique bond types."""
        assert len(calf20_bonded_types.bonds) == 6
    
    def test_expected_bond_types(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should contain specific expected bond types."""
        bonds = calf20_bonded_types.bonds
        
        # C-H bond (C1-H1A, C2-H2A)
        assert ("C_MOF", "H_MOF") in bonds
        
        # C-N bond (C1-N1, C1-N3, C2-N2, C2-N3)
        assert ("C_MOF", "N_MOF") in bonds
        
        # C-O bond (C3-O1, C3-O2)
        assert ("C_MOF", "O_MOF") in bonds
        
        # N-N bond (N1-N2)
        assert ("N_MOF", "N_MOF") in bonds
        
        # Zn-N bond (Zn1-N1, Zn1-N2, Zn1-N3)
        assert ("N_MOF", "Zn_MOF") in bonds
        
        # Zn-O bond (Zn1-O1, Zn1-O2)
        assert ("O_MOF", "Zn_MOF") in bonds


class TestCalf20AngleTypes:
    """Tests for CALF20 angle type extraction."""
    
    def test_angle_count(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should have expected number of angle types.
        
        Expected angles based on topology:
        - Zn1 (5 neighbors): 10 angles = C(5,2)
        - N1, N2, N3 (3 neighbors each): 3 angles each = 9 total
        - O1, O2 (2 neighbors each): 1 angle each = 2 total
        - C1, C2 (3 neighbors each): 3 angles each = 6 total
        - C3 (2 neighbors): 1 angle
        
        Many of these map to the same canonical types, so unique count is ~11.
        """
        # Allow some variance in expected count
        assert 10 <= len(calf20_bonded_types.angles) <= 13
    
    def test_key_angle_types(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should contain specific key angle types."""
        angles = calf20_bonded_types.angles
        
        # Zn-centered angles
        assert ("N_MOF", "Zn_MOF", "N_MOF") in angles
        assert ("N_MOF", "Zn_MOF", "O_MOF") in angles
        assert ("O_MOF", "Zn_MOF", "O_MOF") in angles
        
        # C-centered angles
        assert ("H_MOF", "C_MOF", "N_MOF") in angles
        assert ("N_MOF", "C_MOF", "N_MOF") in angles
        assert ("O_MOF", "C_MOF", "O_MOF") in angles


class TestCalf20TorsionTypes:
    """Tests for CALF20 torsion type extraction."""
    
    def test_torsion_count(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should have expected number of torsion types.
        
        The exact count depends on the molecular topology.
        Expected ~16 unique torsion types.
        """
        # Allow some variance
        assert 12 <= len(calf20_bonded_types.torsions) <= 20
    
    def test_has_torsion_types(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should have at least some torsion types."""
        assert len(calf20_bonded_types.torsions) > 0


class TestCalf20OopTypes:
    """Tests for CALF20 out-of-plane type extraction."""
    
    def test_oop_count(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should have expected number of OOP types.
        
        OOP centers (atoms with exactly 3 neighbors):
        - N1, N2, N3 (3 neighbors each) -> N_MOF centered
        - C1, C2 (3 neighbors each) -> C_MOF centered
        
        Unique types: ~2-3 (C_MOF and N_MOF centered)
        """
        # N1, N2, N3, C1, C2 all have 3 neighbors
        assert 2 <= len(calf20_bonded_types.out_of_plane) <= 5
    
    def test_expected_oop_types(self, calf20_bonded_types: BondedTypeSet) -> None:
        """CALF20 should contain specific OOP types."""
        oop = calf20_bonded_types.out_of_plane
        
        # C_MOF centered OOP (C1, C2 have H, N, N neighbors)
        assert ("C_MOF", "H_MOF", "N_MOF", "N_MOF") in oop


# =============================================================================
# Determinism Tests
# =============================================================================


class TestDeterministicOutput:
    """Tests for deterministic extraction."""
    
    def test_same_mdf_same_result(self, calf20_mdf_path: Path) -> None:
        """Extracting from the same MDF file produces identical results."""
        result1 = extract_bonded_types_from_mdf(calf20_mdf_path)
        result2 = extract_bonded_types_from_mdf(calf20_mdf_path)
        
        assert result1.bonds == result2.bonds
        assert result1.angles == result2.angles
        assert result1.torsions == result2.torsions
        assert result1.out_of_plane == result2.out_of_plane
    
    def test_bonded_type_set_repr(self, calf20_bonded_types: BondedTypeSet) -> None:
        """BondedTypeSet has useful repr."""
        r = repr(calf20_bonded_types)
        assert "bonds=" in r
        assert "angles=" in r
        assert "torsions=" in r
        assert "out_of_plane=" in r


# =============================================================================
# Edge Cases
# =============================================================================


class TestBondedTypeSetDataclass:
    """Tests for BondedTypeSet dataclass behavior."""
    
    def test_default_empty(self) -> None:
        """Default BondedTypeSet has empty frozensets."""
        bts = BondedTypeSet()
        assert bts.bonds == frozenset()
        assert bts.angles == frozenset()
        assert bts.torsions == frozenset()
        assert bts.out_of_plane == frozenset()
    
    def test_immutable(self) -> None:
        """BondedTypeSet is immutable (frozen=True)."""
        bts = BondedTypeSet(bonds=frozenset({("A", "B")}))
        with pytest.raises(AttributeError):
            bts.bonds = frozenset()  # type: ignore[misc]
    
    def test_hashable(self) -> None:
        """BondedTypeSet is hashable (can be used in sets/dicts)."""
        bts = BondedTypeSet(bonds=frozenset({("A", "B")}))
        s = {bts}
        assert len(s) == 1
