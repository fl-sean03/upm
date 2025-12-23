"""Tests for the unified FRCBuilder API (Phase 14).

Tests the new Protocol-based architecture:
- FRCBuilder class
- ParameterSource implementations
- ChainedSource fallback behavior
- Legacy API compatibility
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from upm.build import (
    FRCBuilder,
    FRCBuilderConfig,
    ChainedSource,
    PlaceholderSource,
    ParameterSetSource,
    MissingTypesError,
)
from upm.build.entries import AtomTypeInfo, BondParams, NonbondParams


def _termset(
    *,
    atom_types: list[str],
    bond_types: list[tuple[str, str]] | None = None,
    angle_types: list[tuple[str, str, str]] | None = None,
    dihedral_types: list[tuple[str, str, str, str]] | None = None,
    improper_types: list[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "molsaic.termset.v0.1.2",
        "atom_types": list(atom_types),
        "bond_types": [list(x) for x in (bond_types or [])],
        "angle_types": [list(x) for x in (angle_types or [])],
        "dihedral_types": [list(x) for x in (dihedral_types or [])],
        "improper_types": [list(x) for x in (improper_types or [])],
    }


def _parameterset(*, atom_types: dict[str, dict[str, float | str]]) -> dict[str, Any]:
    return {
        "schema": "upm.parameterset.v0.1.2",
        "atom_types": dict(atom_types),
    }


class TestPlaceholderSource:
    """Tests for PlaceholderSource."""
    
    def test_returns_none_for_atom_type_info(self) -> None:
        """PlaceholderSource returns None for atom type info."""
        source = PlaceholderSource({"C_MOF": "C"})
        assert source.get_atom_type_info("C_MOF") is None
    
    def test_returns_none_for_nonbond_params(self) -> None:
        """PlaceholderSource returns None for nonbond params."""
        source = PlaceholderSource({"C_MOF": "C"})
        assert source.get_nonbond_params("C_MOF") is None
    
    def test_provides_bond_params_based_on_element(self) -> None:
        """PlaceholderSource provides bond params based on element."""
        source = PlaceholderSource({"C_MOF": "C", "H_MOF": "H"})
        params = source.get_bond_params("C_MOF", "H_MOF")
        assert params is not None
        # H bonds use k=340, r0=1.09
        assert params.k == 340.0
        assert params.r0 == 1.09
    
    def test_provides_angle_params_based_on_center(self) -> None:
        """PlaceholderSource provides angle params based on center element."""
        source = PlaceholderSource({"C_MOF": "C", "H_MOF": "H"})
        params = source.get_angle_params("H_MOF", "C_MOF", "H_MOF")
        assert params is not None
        # C center uses theta0=109.5
        assert params.theta0_deg == 109.5


class TestParameterSetSource:
    """Tests for ParameterSetSource."""
    
    def test_provides_atom_type_info(self) -> None:
        """ParameterSetSource provides atom type info from parameterset."""
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.011, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        source = ParameterSetSource(ps)
        info = source.get_atom_type_info("C_MOF")
        assert info is not None
        assert info.mass_amu == 12.011
        assert info.element == "C"
    
    def test_provides_nonbond_params_with_lj_conversion(self) -> None:
        """ParameterSetSource converts LJ sigma/epsilon to A/B."""
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.0, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        source = ParameterSetSource(ps)
        params = source.get_nonbond_params("C_MOF")
        assert params is not None
        assert params.lj_a > 0  # Converted from sigma/epsilon
        assert params.lj_b > 0
    
    def test_returns_none_for_unknown_type(self) -> None:
        """ParameterSetSource returns None for unknown types."""
        ps = _parameterset(atom_types={"C_MOF": {"mass_amu": 12.0, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}})
        source = ParameterSetSource(ps)
        assert source.get_atom_type_info("UNKNOWN") is None


class TestChainedSource:
    """Tests for ChainedSource fallback behavior."""
    
    def test_falls_back_to_second_source(self) -> None:
        """ChainedSource falls back when first source returns None."""
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.0, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        source = ChainedSource([
            ParameterSetSource(ps),
            PlaceholderSource({"C_MOF": "C"}),
        ])
        
        # ParameterSetSource provides atom info
        info = source.get_atom_type_info("C_MOF")
        assert info is not None
        
        # ParameterSetSource doesn't provide bond params, falls back to Placeholder
        params = source.get_bond_params("C_MOF", "C_MOF")
        assert params is not None


class TestFRCBuilder:
    """Tests for FRCBuilder class."""
    
    def test_builds_frc_content(self) -> None:
        """FRCBuilder produces valid FRC content."""
        termset = _termset(atom_types=["C_MOF"])
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.011, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        
        source = ChainedSource([
            ParameterSetSource(ps),
            PlaceholderSource({"C_MOF": "C"}),
        ])
        
        builder = FRCBuilder(termset, source)
        content = builder.build()
        
        assert "!BIOSYM forcefield" in content
        assert "#atom_types" in content
        assert "C_MOF" in content
    
    def test_validates_missing_types(self) -> None:
        """FRCBuilder.validate() returns missing types."""
        termset = _termset(atom_types=["C_MOF", "MISSING"])
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.0, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        
        source = ParameterSetSource(ps)
        builder = FRCBuilder(termset, source)
        
        missing = builder.validate()
        assert any("MISSING" in m for m in missing)
    
    def test_raises_on_missing_when_strict(self) -> None:
        """FRCBuilder raises MissingTypesError in strict mode."""
        termset = _termset(atom_types=["C_MOF", "MISSING"])
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.0, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        
        source = ParameterSetSource(ps)
        config = FRCBuilderConfig(strict=True)
        builder = FRCBuilder(termset, source, config)
        
        with pytest.raises(MissingTypesError):
            builder.build()
    
    def test_writes_to_file(self, tmp_path: Path) -> None:
        """FRCBuilder.write() creates output file."""
        termset = _termset(atom_types=["C_MOF"])
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.011, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1}
        })
        
        source = ChainedSource([
            ParameterSetSource(ps),
            PlaceholderSource({"C_MOF": "C"}),
        ])
        
        builder = FRCBuilder(termset, source)
        out = tmp_path / "test.frc"
        result = builder.write(out)
        
        assert out.exists()
        assert result == str(out)
        assert out.stat().st_size > 0


class TestLegacyAPI:
    """Tests for legacy API backward compatibility."""
    
    def test_build_frc_cvff_with_generic_bonded_works(self, tmp_path: Path) -> None:
        """Legacy build_frc_cvff_with_generic_bonded still works."""
        from upm.build import build_frc_cvff_with_generic_bonded
        
        termset = _termset(
            atom_types=["C_MOF", "H_MOF"],
            bond_types=[("C_MOF", "H_MOF")],
        )
        ps = _parameterset(atom_types={
            "C_MOF": {"mass_amu": 12.011, "element": "C", "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"mass_amu": 1.008, "element": "H", "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        })
        
        out = tmp_path / "legacy.frc"
        result = build_frc_cvff_with_generic_bonded(termset, ps, out_path=out)
        
        assert out.exists()
        assert "C_MOF" in out.read_text()
