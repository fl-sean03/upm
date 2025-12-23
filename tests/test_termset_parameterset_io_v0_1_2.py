from __future__ import annotations

import json
from pathlib import Path

import pytest

from upm.io.parameterset import ParameterSetValidationError, read_parameterset_json
from upm.io.termset import TermSetValidationError, read_termset_json


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def test_read_termset_json_rejects_wrong_schema(tmp_path: Path) -> None:
    p = tmp_path / "termset.json"
    _write_json(
        p,
        {
            "schema": "molsaic.termset.v0.9.9",
            "atom_types": [],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
            "improper_types": [],
        },
    )
    with pytest.raises(TermSetValidationError, match=r"expected 'molsaic\.termset\.v0\.1\.2'"):
        read_termset_json(p)


def test_read_termset_json_rejects_non_canonical_bond_key(tmp_path: Path) -> None:
    p = tmp_path / "termset.json"
    _write_json(
        p,
        {
            "schema": "molsaic.termset.v0.1.2",
            "atom_types": ["a", "b"],
            # non-canonical: t1 > t2
            "bond_types": [["z", "a"]],
            "angle_types": [],
            "dihedral_types": [],
            "improper_types": [],
        },
    )
    with pytest.raises(TermSetValidationError, match=r"bond key must satisfy t1 <= t2"):
        read_termset_json(p)


def test_read_parameterset_json_rejects_negative_sigma(tmp_path: Path) -> None:
    p = tmp_path / "parameterset.json"
    _write_json(
        p,
        {
            "schema": "upm.parameterset.v0.1.2",
            "atom_types": {
                # intentionally unsorted key order; reader should still accept and sort output
                "c3": {
                    "mass_amu": 12.0,
                    "lj_sigma_angstrom": -1.0,
                    "lj_epsilon_kcal_mol": 0.2,
                }
            },
        },
    )
    with pytest.raises(ParameterSetValidationError, match=r"lj_sigma_angstrom: must be > 0"):
        read_parameterset_json(p)


def test_read_parameterset_json_allows_zero_epsilon(tmp_path: Path) -> None:
    p = tmp_path / "parameterset.json"
    _write_json(
        p,
        {
            "schema": "upm.parameterset.v0.1.2",
            "atom_types": {
                "c3": {
                    "mass_amu": 12.0,
                    "lj_sigma_angstrom": 3.4,
                    "lj_epsilon_kcal_mol": 0.0,
                }
            },
        },
    )
    out = read_parameterset_json(p)
    assert out["atom_types"]["c3"]["lj_epsilon_kcal_mol"] == 0.0
