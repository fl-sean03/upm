from __future__ import annotations

import json
from pathlib import Path

import pytest

from upm.io.requirements import read_requirements_json


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def test_upm_importable_and_has_version():
    import upm

    assert isinstance(upm.__version__, str)
    assert upm.__version__


def test_read_requirements_defaults_missing_arrays(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, {})

    req = read_requirements_json(p)

    assert req.atom_types == ()
    assert req.bond_types == ()
    assert req.angle_types == ()
    assert req.dihedral_types == ()


def test_read_requirements_bond_canonicalization_and_dedupe_and_sort(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(
        p,
        {
            "atom_types": [" o ", "c3", "h", "h"],  # duplicates + whitespace
            "bond_types": [["o", "c3"], ["c3", "o"], ["c3", "h"]],
        },
    )

    req = read_requirements_json(p)

    # atom_types canonicalized: stripped, unique, sorted
    assert req.atom_types == ("c3", "h", "o")

    # bond_types canonicalized: (t1,t2) sorted internally, then unique + sorted
    assert req.bond_types == (("c3", "h"), ("c3", "o"))


def test_read_requirements_angle_and_dihedral_canonicalization(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(
        p,
        {
            "angle_types": [["z", "mid", "a"], ["a", "mid", "z"]],
            "dihedral_types": [["d", "c", "b", "a"], ["a", "b", "c", "d"]],
        },
    )

    req = read_requirements_json(p)

    # angle endpoints canonicalized so t1 <= t3
    assert req.angle_types == (("a", "mid", "z"),)

    # dihedral reversal canonicalization chooses lexicographically smaller of fwd vs reversed
    assert req.dihedral_types == (("a", "b", "c", "d"),)


def test_read_requirements_rejects_non_object_top_level(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, ["not", "an", "object"])

    with pytest.raises(ValueError, match=r"requirements\.json: expected JSON object"):
        read_requirements_json(p)


def test_read_requirements_rejects_null_arrays(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, {"atom_types": None})

    with pytest.raises(ValueError, match=r"atom_types: must be an array; got null"):
        read_requirements_json(p)


def test_read_requirements_rejects_non_iterable_field(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, {"bond_types": "c3-o"})

    with pytest.raises(ValueError, match=r"bond_types: expected a list/tuple"):
        read_requirements_json(p)


def test_read_requirements_rejects_wrong_tuple_length(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, {"bond_types": [["c3", "o", "extra"]]})

    with pytest.raises(ValueError, match=r"bond_types\[0\]: expected 2 items"):
        read_requirements_json(p)


def test_read_requirements_rejects_empty_strings(tmp_path: Path):
    p = tmp_path / "req.json"
    _write_json(p, {"atom_types": ["   "]})

    with pytest.raises(ValueError, match=r"atom_types\[\*\]: must be a non-empty string"):
        read_requirements_json(p)
