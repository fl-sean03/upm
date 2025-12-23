from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from upm.build.frc_builders import MissingTypesError, build_frc_nonbond_only
from upm.codecs.msi_frc import parse_frc_text


def _termset(atom_types: list[str]) -> dict[str, object]:
    # Minimal validated shape for builder.
    return {
        "schema": "molsaic.termset.v0.1.2",
        "atom_types": list(atom_types),
        "bond_types": [],
        "angle_types": [],
        "dihedral_types": [],
        "improper_types": [],
    }


def _parameterset(atom_types: dict[str, dict[str, float | str]]) -> dict[str, object]:
    return {
        "schema": "upm.parameterset.v0.1.2",
        "atom_types": dict(atom_types),
    }


def test_build_frc_nonbond_only_missing_types_error_is_sorted(tmp_path: Path) -> None:
    ts = _termset(["b", "a"])  # order shouldn't matter for missing list ordering
    ps = _parameterset({"a": {"mass_amu": 1.0, "lj_sigma_angstrom": 3.0, "lj_epsilon_kcal_mol": 0.1}})

    with pytest.raises(MissingTypesError) as ei:
        build_frc_nonbond_only(ts, ps, out_path=tmp_path / "out.frc")

    assert ei.value.missing_atom_types == ("b",)


def test_build_frc_nonbond_only_is_byte_deterministic(tmp_path: Path) -> None:
    ts = _termset(["a", "b"])
    ps = _parameterset(
        {
            "a": {"mass_amu": 10.0, "lj_sigma_angstrom": 2.0, "lj_epsilon_kcal_mol": 0.5},
            "b": {"mass_amu": 20.0, "lj_sigma_angstrom": 3.0, "lj_epsilon_kcal_mol": 0.0},
        }
    )

    p1 = tmp_path / "a1.frc"
    p2 = tmp_path / "a2.frc"
    build_frc_nonbond_only(ts, ps, out_path=p1)
    build_frc_nonbond_only(ts, ps, out_path=p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_build_frc_nonbond_only_emits_only_required_sections_and_roundtrips(tmp_path: Path) -> None:
    ts = _termset(["a", "b"])
    ps = _parameterset(
        {
            "a": {"mass_amu": 10.0, "lj_sigma_angstrom": 2.0, "lj_epsilon_kcal_mol": 0.5, "element": "A"},
            "b": {"mass_amu": 20.0, "lj_sigma_angstrom": 3.0, "lj_epsilon_kcal_mol": 0.0},
        }
    )

    out = tmp_path / "ff.frc"
    build_frc_nonbond_only(ts, ps, out_path=out)
    text = out.read_text(encoding="utf-8")

    assert "#atom_types" in text
    assert "#nonbond(12-6)" in text
    assert "@type A-B" in text
    assert "@combination geometric" in text
    assert "#quadratic_bond" not in text
    assert "#quadratic_angle" not in text

    tables, unknown = parse_frc_text(text)
    assert unknown == []

    atom_types = tables["atom_types"].copy()

    # expected A/B for type a: sigma=2, eps=0.5
    # A=4*0.5*2^12=2*4096=8192
    # B=4*0.5*2^6=2*64=128
    row_a = atom_types.loc[atom_types["atom_type"] == "a"].iloc[0]
    assert float(row_a["mass_amu"]) == pytest.approx(10.0)
    assert float(row_a["lj_a"]) == pytest.approx(8192.0)
    assert float(row_a["lj_b"]) == pytest.approx(128.0)

    # type b epsilon=0 -> A=B=0
    row_b = atom_types.loc[atom_types["atom_type"] == "b"].iloc[0]
    assert float(row_b["lj_a"]) == pytest.approx(0.0)
    assert float(row_b["lj_b"]) == pytest.approx(0.0)

    # canonical ordering by atom_type
    assert list(atom_types["atom_type"]) == ["a", "b"]
    # placeholder element is deterministic when missing
    assert str(row_b["element"]) == "X"

    # ensure schema columns exist
    expected_cols = [
        "atom_type",
        "element",
        "mass_amu",
        "vdw_style",
        "lj_a",
        "lj_b",
        "notes",
    ]
    assert list(atom_types.columns) == expected_cols
    pd.testing.assert_series_equal(atom_types["vdw_style"], pd.Series(["lj_ab_12_6", "lj_ab_12_6"], dtype="string"))

