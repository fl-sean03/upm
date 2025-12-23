"""Tests for filter_frc_tables utility function.

This module tests the functionality of filtering FRC tables based on termsets
to extract only the parameters needed for specific molecules.
"""
from __future__ import annotations

import pytest

from upm.build.frc_builders import filter_frc_tables

from conftest import (
    make_termset,
    make_atom_types_df,
    make_bonds_df,
    make_angles_df,
)


# =============================================================================
# Tests for filter_frc_tables
# =============================================================================


class TestFilterFrcTables:
    """Tests for filter_frc_tables utility function."""

    def test_filters_atom_types_by_exact_match(self) -> None:
        """filter_frc_tables keeps only atom types in termset."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "cdc", "mass_amu": 12.0, "element": "C", "lj_a": 236919.1, "lj_b": 217.678},
                {"atom_type": "cdo", "mass_amu": 16.0, "element": "O", "lj_a": 207547.3, "lj_b": 315.631},
                {"atom_type": "other", "mass_amu": 14.0, "element": "N", "lj_a": 100.0, "lj_b": 50.0},
            ])
        }
        termset = make_termset(["cdc", "cdo"])

        result = filter_frc_tables(tables, termset)

        assert "atom_types" in result
        assert len(result["atom_types"]) == 2
        assert set(result["atom_types"]["atom_type"]) == {"cdc", "cdo"}

    def test_filters_bonds_by_canonical_key(self) -> None:
        """filter_frc_tables matches bonds regardless of atom type order."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "cdc", "mass_amu": 12.0, "element": "C"},
                {"atom_type": "cdo", "mass_amu": 16.0, "element": "O"},
            ]),
            "bonds": make_bonds_df([
                {"t1": "cdo", "t2": "cdc", "r0": 1.162, "k": 1140.0},  # Reversed order
                {"t1": "other", "t2": "another", "r0": 1.5, "k": 300.0},
            ])
        }
        termset = make_termset(["cdc", "cdo"], bond_types=[["cdc", "cdo"]])

        result = filter_frc_tables(tables, termset)

        assert "bonds" in result
        assert len(result["bonds"]) == 1
        # Should match even though source has cdo-cdc and termset has cdc-cdo
        row = result["bonds"].iloc[0]
        assert {row["t1"], row["t2"]} == {"cdc", "cdo"}

    def test_filters_angles_by_canonical_key(self) -> None:
        """filter_frc_tables matches angles with center atom preserved."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "cdc", "mass_amu": 12.0, "element": "C"},
                {"atom_type": "cdo", "mass_amu": 16.0, "element": "O"},
            ]),
            "angles": make_angles_df([
                {"t1": "cdo", "t2": "cdc", "t3": "cdo", "theta0_deg": 180.0, "k": 100.0},
                {"t1": "other", "t2": "center", "t3": "another", "theta0_deg": 109.5, "k": 50.0},
            ])
        }
        termset = make_termset(
            ["cdc", "cdo"],
            angle_types=[["cdo", "cdc", "cdo"]]
        )

        result = filter_frc_tables(tables, termset)

        assert "angles" in result
        assert len(result["angles"]) == 1
        row = result["angles"].iloc[0]
        assert row["t2"] == "cdc"  # Center preserved

    def test_deduplicates_atom_types_preferring_lj_populated(self) -> None:
        """filter_frc_tables prefers entries with lj_a/lj_b when deduplicating."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "cdc", "mass_amu": 12.0, "element": "C", "lj_a": None, "lj_b": None},
                {"atom_type": "cdc", "mass_amu": 12.0, "element": "C", "lj_a": 236919.1, "lj_b": 217.678},
            ])
        }
        termset = make_termset(["cdc"])

        result = filter_frc_tables(tables, termset)

        assert len(result["atom_types"]) == 1
        row = result["atom_types"].iloc[0]
        # Should keep the entry with LJ params populated
        assert float(row["lj_a"]) == pytest.approx(236919.1)

    def test_deduplicates_bonds_keeping_last(self) -> None:
        """filter_frc_tables keeps last bond entry when duplicates exist."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "cdc", "mass_amu": 12.0},
                {"atom_type": "cdo", "mass_amu": 16.0},
            ]),
            "bonds": make_bonds_df([
                {"t1": "cdc", "t2": "cdo", "r0": 1.1, "k": 1000.0},
                {"t1": "cdc", "t2": "cdo", "r0": 1.162, "k": 1140.0},  # Last entry
            ])
        }
        termset = make_termset(["cdc", "cdo"], bond_types=[["cdc", "cdo"]])

        result = filter_frc_tables(tables, termset)

        assert len(result["bonds"]) == 1
        row = result["bonds"].iloc[0]
        # Should keep last entry
        assert float(row["r0"]) == pytest.approx(1.162)
        assert float(row["k"]) == pytest.approx(1140.0)

    def test_returns_empty_when_no_matches(self) -> None:
        """filter_frc_tables omits tables with no matching entries."""
        tables = {
            "atom_types": make_atom_types_df([
                {"atom_type": "other", "mass_amu": 14.0, "element": "N"},
            ])
        }
        termset = make_termset(["cdc", "cdo"])

        result = filter_frc_tables(tables, termset)

        # Table should be omitted (not empty DataFrame)
        assert "atom_types" not in result

    def test_handles_empty_tables(self) -> None:
        """filter_frc_tables handles empty input tables gracefully."""
        tables = {
            "atom_types": make_atom_types_df([]),
        }
        termset = make_termset(["cdc"])

        result = filter_frc_tables(tables, termset)

        assert "atom_types" not in result
