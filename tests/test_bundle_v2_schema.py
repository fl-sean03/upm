"""Unit tests for UPM v2.1 bundle schema extensions."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from upm.bundle.io import load_package, load_structure, save_package, save_structure
from upm.bundle.manifest import CURRENT_SCHEMA_VERSION, build_manifest


# ---------------------------------------------------------------------------
# build_manifest

def test_default_schema_is_upm_2_1():
    m = build_manifest(name="x", version="v1.0", sources=[], tables={})
    assert m["schema_version"] == "upm-2.1"
    assert CURRENT_SCHEMA_VERSION == "upm-2.1"


def test_parameter_entry_default_type():
    m = build_manifest(name="x", version="v1.0", sources=[], tables={})
    assert m["type"] == "parameters"
    assert "units" in m
    assert "nonbonded" in m


def test_parameter_entry_lineage_fields():
    m = build_manifest(
        name="cvff-mxene", version="v1.1", sources=[], tables={},
        supersedes="v1.0",
        parent_ff="cvff-interface/v1.5",
        overrides=[{"target": "cvff-interface/v1.5", "scope": "bonds", "reason": "DFT"}],
        renames={"ti4f": "ti4fh"},
        breaking=True,
        partial_roundtrip=True,
    )
    assert m["supersedes"] == "v1.0"
    assert m["parent_ff"] == "cvff-interface/v1.5"
    assert m["overrides"][0]["scope"] == "bonds"
    assert m["renames"]["ti4f"] == "ti4fh"
    assert m["breaking"] is True
    assert m["partial_roundtrip"] is True


def test_structure_entry_requires_family_and_parameterized_with():
    with pytest.raises(ValueError, match="atom_type_family"):
        build_manifest(name="s", version="v1.0", sources=[], tables={}, entry_type="structure")
    with pytest.raises(ValueError, match="parameterized_with"):
        build_manifest(
            name="s", version="v1.0", sources=[], tables={},
            entry_type="structure", atom_type_family="cvff-mxene",
        )
    with pytest.raises(ValueError, match="parameterized_with"):
        build_manifest(
            name="s", version="v1.0", sources=[], tables={},
            entry_type="structure", atom_type_family="cvff-mxene",
            parameterized_with=[{"wrong": "shape"}],
        )


def test_structure_entry_fields_roundtrip():
    m = build_manifest(
        name="Ti3C2_F", version="v1.0", sources=[], tables={},
        entry_type="structure",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        charges_source="structure",
        lock_to_original=True,
        validated_with=[{"name": "cvff-mxene", "version": "v1.1"}],
    )
    assert m["type"] == "structure"
    assert m["atom_type_family"] == "cvff-mxene"
    assert m["parameterized_with"][0]["version"] == "v1.0"
    assert m["lock_to_original"] is True
    assert m["validated_with"][0]["version"] == "v1.1"


def test_deprecation_flag():
    m = build_manifest(
        name="x", version="v1.0", sources=[], tables={},
        deprecated=True, deprecation_reason="refined in v1.1",
    )
    assert m["deprecated"] is True
    assert m["deprecation_reason"] == "refined in v1.1"


def test_rejects_invalid_entry_type():
    with pytest.raises(ValueError, match="entry_type"):
        build_manifest(name="x", version="v1.0", sources=[], tables={}, entry_type="bogus")


# ---------------------------------------------------------------------------
# save_package / load_package

def _minimal_atom_types_df() -> pd.DataFrame:
    return pd.DataFrame({
        "atom_type": ["ti4f", "o2"],
        "element": ["Ti", "O"],
        "mass_amu": [47.88, 16.00],
        "vdw_style": ["lj_A_B", "lj_A_B"],
        "lj_a": [1.0e6, 5.0e5],
        "lj_b": [500.0, 300.0],
        "notes": ["", ""],
    })


def test_save_load_package_roundtrip_frc(tmp_path):
    tables = {"atom_types": _minimal_atom_types_df()}
    save_package(
        tmp_path,
        name="cvff-test", version="v1.0",
        tables=tables,
        source_text="# fake frc source\n",
        source_format="frc",
        provenance={"author": "Test User"},
    )
    bundle = load_package(tmp_path, validate_hashes=True)
    assert bundle.manifest["name"] == "cvff-test"
    assert bundle.manifest["type"] == "parameters"
    assert bundle.manifest["provenance"]["author"] == "Test User"
    assert (tmp_path / "raw" / "source.frc").is_file()
    assert "atom_types" in bundle.tables


def test_save_load_package_roundtrip_prm(tmp_path):
    """Regression: save_package used to hardcode source.frc; now supports .prm."""
    save_package(
        tmp_path,
        name="charmm-test", version="v1.0",
        tables={"atom_types": _minimal_atom_types_df()},
        source_text="* CHARMM test\n",
        source_format="prm",
    )
    assert (tmp_path / "raw" / "source.prm").is_file()
    assert not (tmp_path / "raw" / "source.frc").exists()
    bundle = load_package(tmp_path, validate_hashes=True)
    assert bundle.raw["source_text"].startswith("* CHARMM")


def test_save_package_persists_v2_fields(tmp_path):
    save_package(
        tmp_path, name="x", version="v1.0",
        tables={"atom_types": _minimal_atom_types_df()},
        source_text="\n",
        supersedes="v0.9",
        parent_ff="base/v1.5",
        overrides=[{"target": "base/v1.5", "scope": "bonds"}],
        renames={"old": "new"},
        breaking=True,
        partial_roundtrip=True,
        provenance={"notes": "demo"},
    )
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["supersedes"] == "v0.9"
    assert m["parent_ff"] == "base/v1.5"
    assert m["renames"]["old"] == "new"
    assert m["breaking"] is True
    assert m["partial_roundtrip"] is True
    assert m["provenance"]["notes"] == "demo"


def test_save_package_invalid_source_format(tmp_path):
    with pytest.raises(ValueError, match="source_format"):
        save_package(
            tmp_path, name="x", version="v1.0",
            tables={"atom_types": _minimal_atom_types_df()},
            source_text="", source_format="xml",
        )


# ---------------------------------------------------------------------------
# save_structure / load_structure

def _atoms_df() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 3],
        "element": ["Ti", "C", "F"],
        "ff_type": ["ti4f", "c3a", "f1"],
        "charge": [1.5, -0.3, -0.9],
        "x": [0.0, 1.0, 2.0],
        "y": [0.0, 0.5, 0.0],
        "z": [0.0, 0.0, 0.5],
    })


def test_save_load_structure_roundtrip(tmp_path):
    save_structure(
        tmp_path,
        name="Ti3C2_F_tiny", version="v1.0",
        atoms_df=_atoms_df(),
        geometry_text="!BIOSYM car\n<geometry>\n",
        geometry_format="car",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        provenance={"author": "Alice"},
    )
    bundle = load_structure(tmp_path, validate_hashes=True)
    assert bundle.manifest["type"] == "structure"
    assert bundle.manifest["atom_type_family"] == "cvff-mxene"
    assert len(bundle.atoms) == 3
    assert set(bundle.atoms.columns) >= {"id", "element", "ff_type", "charge", "x", "y", "z"}
    assert bundle.topology is None
    assert (tmp_path / "geometry" / "source.car").is_file()


def test_save_structure_with_topology(tmp_path):
    topology = pd.DataFrame({
        "kind": ["bond", "bond", "angle"],
        "i": [1, 2, 1],
        "j": [2, 3, 2],
        "k": [None, None, 3],
    })
    save_structure(
        tmp_path,
        name="s", version="v1.0",
        atoms_df=_atoms_df(),
        topology_df=topology,
        geometry_text="",
        geometry_format="car",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    bundle = load_structure(tmp_path, validate_hashes=True)
    assert bundle.topology is not None
    assert len(bundle.topology) == 3


def test_save_structure_rejects_missing_columns(tmp_path):
    bad = pd.DataFrame({"id": [1], "element": ["C"]})
    with pytest.raises(ValueError, match="missing required columns"):
        save_structure(
            tmp_path, name="s", version="v1.0",
            atoms_df=bad, geometry_text="", geometry_format="car",
            atom_type_family="cvff-mxene",
            parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        )


def test_structure_atoms_csv_hash_mismatch_detected(tmp_path):
    save_structure(
        tmp_path, name="s", version="v1.0",
        atoms_df=_atoms_df(), geometry_text="", geometry_format="car",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    (tmp_path / "atoms.csv").write_text("id,element,ff_type,charge,x,y,z\n9,X,x1,0,0,0,0\n")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_structure(tmp_path, validate_hashes=True)
