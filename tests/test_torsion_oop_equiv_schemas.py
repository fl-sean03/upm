"""Tests for torsion, out_of_plane, and equivalences table schemas.

Covers normalization, validation, and canonicalization for Phase 2 additions.
"""
from __future__ import annotations

import pandas as pd
import pytest

from upm.core.tables import (
    normalize_torsions,
    normalize_out_of_plane,
    normalize_equivalences,
    normalize_tables,
    TABLE_SCHEMAS,
)
from upm.core.validate import (
    validate_torsions,
    validate_out_of_plane,
    validate_equivalences,
    validate_tables,
    TableValidationError,
)


# =============================================================================
# Torsions
# =============================================================================


def _make_torsions_df(**overrides: object) -> pd.DataFrame:
    defaults = {
        "t1": ["a"],
        "t2": ["b"],
        "t3": ["c"],
        "t4": ["d"],
        "style": ["torsion_1"],
        "kphi": [0.5],
        "n": [3],
        "phi0": [0.0],
        "source": [None],
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


def test_torsions_schema_exists() -> None:
    assert "torsions" in TABLE_SCHEMAS
    assert list(TABLE_SCHEMAS["torsions"].keys()) == [
        "t1", "t2", "t3", "t4", "style", "kphi", "n", "phi0", "source",
    ]


def test_normalize_torsions_canonical_order() -> None:
    """Torsion keys are canonicalized: reversed if forward > reversed."""
    df = _make_torsions_df(t1=["d"], t2=["c"], t3=["b"], t4=["a"])
    result = normalize_torsions(df)
    # (d,c,b,a) reversed is (a,b,c,d) which is lexicographically smaller
    assert list(result["t1"]) == ["a"]
    assert list(result["t2"]) == ["b"]
    assert list(result["t3"]) == ["c"]
    assert list(result["t4"]) == ["d"]


def test_normalize_torsions_no_reverse_needed() -> None:
    """Torsion keys already canonical stay unchanged."""
    df = _make_torsions_df(t1=["a"], t2=["b"], t3=["c"], t4=["d"])
    result = normalize_torsions(df)
    assert list(result["t1"]) == ["a"]
    assert list(result["t4"]) == ["d"]


def test_normalize_torsions_sorts() -> None:
    """Multiple torsions are sorted by key columns."""
    df = pd.DataFrame({
        "t1": ["c", "a"], "t2": ["d", "b"], "t3": ["e", "c"], "t4": ["f", "d"],
        "style": ["torsion_1", "torsion_1"],
        "kphi": [1.0, 2.0], "n": [1, 2], "phi0": [0.0, 180.0],
        "source": [None, None],
    })
    result = normalize_torsions(df)
    assert list(result["t1"]) == ["a", "c"]


def test_validate_torsions_valid() -> None:
    df = normalize_torsions(_make_torsions_df())
    validate_torsions(df)  # should not raise


def test_validate_torsions_bad_style() -> None:
    df = normalize_torsions(_make_torsions_df(style=["bad"]))
    with pytest.raises(TableValidationError, match="torsion_1"):
        validate_torsions(df)


def test_validate_torsions_null_key() -> None:
    df = normalize_torsions(_make_torsions_df(t1=[None]))
    with pytest.raises(TableValidationError, match="nulls"):
        validate_torsions(df)


# =============================================================================
# Out-of-plane
# =============================================================================


def _make_oop_df(**overrides: object) -> pd.DataFrame:
    defaults = {
        "t1": ["a"],
        "t2": ["b"],
        "t3": ["c"],
        "t4": ["d"],
        "style": ["out_of_plane"],
        "kchi": [0.1],
        "n": [2],
        "chi0": [180.0],
        "source": [None],
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


def test_oop_schema_exists() -> None:
    assert "out_of_plane" in TABLE_SCHEMAS


def test_normalize_oop_no_reorder() -> None:
    """OOP atoms are NOT canonicalized (ordering is significant)."""
    df = _make_oop_df(t1=["d"], t2=["c"], t3=["b"], t4=["a"])
    result = normalize_out_of_plane(df)
    # Order preserved — no canonicalization for OOP
    assert list(result["t1"]) == ["d"]
    assert list(result["t4"]) == ["a"]


def test_validate_oop_valid() -> None:
    df = normalize_out_of_plane(_make_oop_df())
    validate_out_of_plane(df)  # should not raise


def test_validate_oop_null_kchi() -> None:
    df = normalize_out_of_plane(_make_oop_df(kchi=[None]))
    with pytest.raises(TableValidationError, match="kchi"):
        validate_out_of_plane(df)


# =============================================================================
# Equivalences
# =============================================================================


def _make_equiv_df(**overrides: object) -> pd.DataFrame:
    defaults = {
        "atom_type": ["c3"],
        "nonb": ["c"],
        "bond": ["c"],
        "angle": ["c"],
        "torsion": ["c"],
        "oop": ["c"],
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


def test_equiv_schema_exists() -> None:
    assert "equivalences" in TABLE_SCHEMAS


def test_normalize_equiv_sorts() -> None:
    df = pd.DataFrame({
        "atom_type": ["z_type", "a_type"],
        "nonb": ["z", "a"], "bond": ["z", "a"], "angle": ["z", "a"],
        "torsion": ["z", "a"], "oop": ["z", "a"],
    })
    result = normalize_equivalences(df)
    assert list(result["atom_type"]) == ["a_type", "z_type"]


def test_validate_equiv_valid() -> None:
    df = normalize_equivalences(_make_equiv_df())
    validate_equivalences(df)  # should not raise


def test_validate_equiv_duplicate_key() -> None:
    df = pd.DataFrame({
        "atom_type": ["c3", "c3"],
        "nonb": ["c", "c"], "bond": ["c", "c"], "angle": ["c", "c"],
        "torsion": ["c", "c"], "oop": ["c", "c"],
    })
    df = normalize_equivalences(df)
    with pytest.raises(TableValidationError, match="duplicate"):
        validate_equivalences(df)


# =============================================================================
# Integration: normalize_tables handles new types
# =============================================================================


def test_normalize_tables_includes_torsions() -> None:
    tables = {
        "atom_types": pd.DataFrame({
            "atom_type": ["a"], "element": ["A"], "mass_amu": [1.0],
            "vdw_style": ["lj_ab_12_6"], "lj_a": [1.0], "lj_b": [1.0], "notes": [None],
        }),
        "torsions": _make_torsions_df(),
    }
    result = normalize_tables(tables)
    assert "torsions" in result


def test_normalize_tables_includes_oop() -> None:
    tables = {
        "atom_types": pd.DataFrame({
            "atom_type": ["a"], "element": ["A"], "mass_amu": [1.0],
            "vdw_style": ["lj_ab_12_6"], "lj_a": [1.0], "lj_b": [1.0], "notes": [None],
        }),
        "out_of_plane": _make_oop_df(),
    }
    result = normalize_tables(tables)
    assert "out_of_plane" in result
