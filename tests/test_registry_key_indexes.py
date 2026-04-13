"""Unit tests for v2.1 PackageIndex key-level indexes, coverage, conflicts."""

from __future__ import annotations


import pandas as pd
import pytest

from upm.bundle.io import save_package, save_structure
from upm.registry.discovery import DiscoveredPackage, discover_local_packages
from upm.registry.index import PackageIndex


@pytest.fixture
def two_param_packages(tmp_path) -> list[DiscoveredPackage]:
    """Two parameter bundles that overlap on atom type 'ti4f' with different values."""
    base_root = tmp_path / "parameters" / "base" / "v1.0"
    mxene_root = tmp_path / "parameters" / "mxene" / "v1.0"

    atom_types_base = pd.DataFrame({
        "atom_type": ["ti4f", "o2"],
        "element": ["Ti", "O"],
        "mass_amu": [47.88, 16.0],
        "vdw_style": ["lj_A_B", "lj_A_B"],
        "lj_a": [1.0e6, 5.0e5],
        "lj_b": [500.0, 300.0],
        "notes": ["", ""],
    })
    atom_types_mxene = pd.DataFrame({
        "atom_type": ["ti4f", "c3a"],
        "element": ["Ti", "C"],
        "mass_amu": [47.88, 12.01],
        "vdw_style": ["lj_A_B", "lj_A_B"],
        "lj_a": [1.1e6, 2.0e5],      # disagrees with base
        "lj_b": [500.0, 200.0],
        "notes": ["", ""],
    })

    bonds_base = pd.DataFrame({
        "t1": ["ti4f"],
        "t2": ["o2"],
        "style": ["harm"],
        "k": [300.0],
        "r0": [1.8],
        "source": ["base"],
    })
    bonds_mxene = pd.DataFrame({
        "t1": ["ti4f"],
        "t2": ["o2"],
        "style": ["harm"],
        "k": [280.0],               # disagrees
        "r0": [1.8],
        "source": ["mxene"],
    })

    save_package(
        base_root, name="base", version="v1.0",
        tables={"atom_types": atom_types_base, "bonds": bonds_base},
        source_text="# base\n",
        provenance={"materials": ["Ti", "SiO2"]},
    )
    save_package(
        mxene_root, name="mxene", version="v1.0",
        tables={"atom_types": atom_types_mxene, "bonds": bonds_mxene},
        source_text="# mxene\n",
        parent_ff="base/v1.0",
        provenance={"materials": ["Ti", "MXene"]},
    )
    return discover_local_packages(tmp_path)


def test_discover_finds_both(two_param_packages):
    names = sorted(p.name for p in two_param_packages)
    assert names == ["base", "mxene"]


def test_atom_type_index_collects_occurrences(two_param_packages):
    idx = PackageIndex(two_param_packages)
    at = idx.atom_type_index
    assert "ti4f" in at
    assert len(at["ti4f"]) == 2           # one from base, one from mxene
    assert "o2" in at and len(at["o2"]) == 1
    assert "c3a" in at and len(at["c3a"]) == 1


def test_bond_index_keys(two_param_packages):
    idx = PackageIndex(two_param_packages)
    bi = idx.bond_index
    # normalize_tables canonicalizes bond keys alphabetically
    assert ("o2", "ti4f") in bi
    assert len(bi[("o2", "ti4f")]) == 2


def test_conflicts_detects_value_disagreement(two_param_packages):
    idx = PackageIndex(two_param_packages)
    conflicts = idx.conflicts()
    # ti4f atom_types disagree on lj_a; ti4f-o2 bond disagrees on k
    atom_conflicts = [c for c in conflicts if c.scope == "atom_types"]
    bond_conflicts = [c for c in conflicts if c.scope == "bonds"]
    assert len(atom_conflicts) == 1
    assert atom_conflicts[0].key == ("ti4f",)
    assert "lj_a" in atom_conflicts[0].disagreements
    assert len(bond_conflicts) == 1
    assert "k" in bond_conflicts[0].disagreements


def test_conflicts_ignores_harmless_duplicates(tmp_path):
    # Two packages defining the same atom type with identical values — not a conflict.
    df = pd.DataFrame({
        "atom_type": ["h1"], "element": ["H"], "mass_amu": [1.008],
        "vdw_style": ["lj_A_B"], "lj_a": [1.0], "lj_b": [0.1], "notes": [""],
    })
    for name in ("a", "b"):
        save_package(
            tmp_path / "parameters" / name / "v1.0",
            name=name, version="v1.0",
            tables={"atom_types": df},
            source_text="\n",
        )
    idx = PackageIndex(discover_local_packages(tmp_path))
    assert idx.conflicts() == []


def test_material_coverage(two_param_packages):
    idx = PackageIndex(two_param_packages)
    cov = idx.material_coverage()
    assert "Ti" in cov
    assert sorted(cov["Ti"].parameters) == ["base@v1.0", "mxene@v1.0"]
    assert "SiO2" in cov and cov["SiO2"].parameters == ["base@v1.0"]
    assert "MXene" in cov and cov["MXene"].parameters == ["mxene@v1.0"]


def test_material_coverage_includes_structures(tmp_path):
    # parameters side
    df = pd.DataFrame({
        "atom_type": ["ti4f"], "element": ["Ti"], "mass_amu": [47.88],
        "vdw_style": ["lj_A_B"], "lj_a": [1.0], "lj_b": [1.0], "notes": [""],
    })
    save_package(
        tmp_path / "parameters" / "cvff-mxene" / "v1.0",
        name="cvff-mxene", version="v1.0",
        tables={"atom_types": df},
        source_text="",
        provenance={"materials": ["MXene"]},
    )
    # structure side
    atoms = pd.DataFrame({
        "id": [1], "element": ["Ti"], "ff_type": ["ti4f"], "charge": [1.5],
        "x": [0.0], "y": [0.0], "z": [0.0],
    })
    save_structure(
        tmp_path / "structures" / "mxene" / "Ti3C2" / "v1.0",
        name="Ti3C2", version="v1.0",
        atoms_df=atoms, geometry_text="", geometry_format="car",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        provenance={"materials": ["MXene"]},
    )
    pkgs = discover_local_packages(tmp_path)
    cov = PackageIndex(pkgs).material_coverage()
    assert "MXene" in cov
    assert "cvff-mxene@v1.0" in cov["MXene"].parameters
    assert "Ti3C2@v1.0" in cov["MXene"].structures


def test_invalidate_forces_reload(two_param_packages):
    idx = PackageIndex(two_param_packages)
    _ = idx.atom_type_index   # materialize
    idx.invalidate()
    # rebuilding should still work
    assert "ti4f" in idx.atom_type_index
