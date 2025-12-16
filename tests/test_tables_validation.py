from __future__ import annotations

import pandas as pd
import pytest

from upm.core.tables import normalize_atom_types, normalize_bonds
from upm.core.validate import TableValidationError, validate_atom_types


def test_normalize_bonds_canonicalizes_swapped_endpoints_and_sorts():
    df = pd.DataFrame(
        [
            # swapped endpoint ordering
            {"t1": "o", "t2": "c3", "style": "quadratic", "k": 1.0, "r0": 2.0, "source": None},
            # already canonical, but comes "later" in input
            {"t1": "c3", "t2": "h", "style": "quadratic", "k": 3.0, "r0": 4.0, "source": None},
        ]
    )

    out = normalize_bonds(df)

    assert list(out["t1"]) == ["c3", "c3"]
    assert list(out["t2"]) == ["h", "o"]

    # deterministic sorting by (t1, t2, style) means (c3,h,...) row comes before (c3,o,...)
    assert list(out["t2"]) == ["h", "o"]


def test_validate_atom_types_rejects_missing_required_columns():
    # missing vdw_style, lj_a, lj_b, etc
    df = pd.DataFrame([{"atom_type": "c3", "element": "C", "mass_amu": 12.0, "notes": None}])

    with pytest.raises(TableValidationError, match=r"atom_types: missing required columns"):
        validate_atom_types(df)


def test_validate_atom_types_rejects_duplicate_atom_type():
    df = pd.DataFrame(
        [
            {
                "atom_type": "c3",
                "element": "C",
                "mass_amu": 12.0,
                "vdw_style": "lj_ab_12_6",
                "lj_a": 1.0,
                "lj_b": 2.0,
                "notes": None,
            },
            {
                "atom_type": "c3",  # duplicate
                "element": "C",
                "mass_amu": 12.0,
                "vdw_style": "lj_ab_12_6",
                "lj_a": 1.1,
                "lj_b": 2.1,
                "notes": None,
            },
        ]
    )

    norm = normalize_atom_types(df)

    with pytest.raises(TableValidationError, match=r"duplicate key rows"):
        validate_atom_types(norm)


def test_normalize_atom_types_deterministic_row_order():
    rows = [
        {
            "atom_type": "o",
            "element": "O",
            "mass_amu": 16.0,
            "vdw_style": "lj_ab_12_6",
            "lj_a": 10.0,
            "lj_b": 20.0,
            "notes": None,
        },
        {
            "atom_type": "c3",
            "element": "C",
            "mass_amu": 12.0,
            "vdw_style": "lj_ab_12_6",
            "lj_a": 1.0,
            "lj_b": 2.0,
            "notes": None,
        },
    ]

    df1 = pd.DataFrame(rows)
    df2 = pd.DataFrame(list(reversed(rows)))

    out1 = normalize_atom_types(df1)
    out2 = normalize_atom_types(df2)

    pd.testing.assert_frame_equal(out1, out2, check_like=False)