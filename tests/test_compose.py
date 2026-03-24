"""Tests for layered force field composition."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from upm.compose.layers import ParameterLayer, stack_layers
from upm.compose.export import export_frc


def _make_base_layer() -> ParameterLayer:
    """Base layer: 3 atom types."""
    atoms = pd.DataFrame([
        {"atom_type": "Au", "element": "Au", "mass_amu": 196.967,
         "vdw_style": "lj_ab_12_6", "lj_a": 2307000.0, "lj_b": 6987.0, "notes": None},
        {"atom_type": "c3", "element": "C", "mass_amu": 12.011,
         "vdw_style": "lj_ab_12_6", "lj_a": 954568.0, "lj_b": 617.92, "notes": None},
        {"atom_type": "h", "element": "H", "mass_amu": 1.008,
         "vdw_style": "lj_ab_12_6", "lj_a": 2384.2, "lj_b": 9.766, "notes": None},
    ])
    bonds = pd.DataFrame([
        {"t1": "Au", "t2": "Au", "style": "quadratic", "k": 100.0, "r0": 2.884, "source": None},
        {"t1": "c3", "t2": "h", "style": "quadratic", "k": 340.0, "r0": 1.09, "source": None},
    ])
    return ParameterLayer(name="base", tables={"atom_types": atoms, "bonds": bonds})


def _make_extension_layer() -> ParameterLayer:
    """Extension: adds new atom types, keeps some overlap."""
    atoms = pd.DataFrame([
        {"atom_type": "si", "element": "Si", "mass_amu": 28.086,
         "vdw_style": "lj_ab_12_6", "lj_a": 500000.0, "lj_b": 300.0, "notes": None},
        {"atom_type": "o_si", "element": "O", "mass_amu": 15.999,
         "vdw_style": "lj_ab_12_6", "lj_a": 200000.0, "lj_b": 400.0, "notes": None},
    ])
    return ParameterLayer(name="silica-ext", tables={"atom_types": atoms})


def _make_patch_layer() -> ParameterLayer:
    """Patch: overrides Au LJ parameters."""
    return ParameterLayer.from_dict(
        {"atom_types": {"Au": {"lj_b": 7100.0, "lj_a": 2400000.0}}},
        name="au-opt-patch",
    )


def test_single_layer() -> None:
    base = _make_base_layer()
    result = stack_layers([base])
    assert result.name == "base"
    assert len(result.tables["atom_types"]) == 3


def test_stack_adds_new_types() -> None:
    base = _make_base_layer()
    ext = _make_extension_layer()
    result = stack_layers([base, ext])
    assert len(result.tables["atom_types"]) == 5  # 3 base + 2 new


def test_stack_patch_overrides() -> None:
    base = _make_base_layer()
    patch = _make_patch_layer()
    result = stack_layers([base, patch])

    # Should still have 3 atom types (patch overrides, doesn't add)
    at = result.tables["atom_types"]
    assert len(at) == 3

    # Au should have the patched value
    au = at[at["atom_type"] == "Au"].iloc[0]
    assert float(au["lj_b"]) == pytest.approx(7100.0)
    assert float(au["lj_a"]) == pytest.approx(2400000.0)

    # c3 should be unchanged
    c3 = at[at["atom_type"] == "c3"].iloc[0]
    assert float(c3["lj_a"]) == pytest.approx(954568.0)


def test_stack_three_layers() -> None:
    base = _make_base_layer()
    ext = _make_extension_layer()
    patch = _make_patch_layer()
    result = stack_layers([base, ext, patch])

    at = result.tables["atom_types"]
    assert len(at) == 5  # 3 base + 2 ext, Au overridden by patch

    au = at[at["atom_type"] == "Au"].iloc[0]
    assert float(au["lj_b"]) == pytest.approx(7100.0)

    # si from extension should be present
    si = at[at["atom_type"] == "si"]
    assert len(si) == 1


def test_stack_preserves_bonds() -> None:
    base = _make_base_layer()
    ext = _make_extension_layer()
    result = stack_layers([base, ext])

    # Bonds from base should survive (ext has no bonds)
    assert "bonds" in result.tables
    assert len(result.tables["bonds"]) == 2


def test_stack_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        stack_layers([])


def test_provenance_chain() -> None:
    base = _make_base_layer()
    ext = _make_extension_layer()
    patch = _make_patch_layer()
    result = stack_layers([base, ext, patch])

    assert result.provenance["layers"] == ["base", "silica-ext", "au-opt-patch"]
    assert result.name == "base + silica-ext + au-opt-patch"


def test_export_frc_produces_valid_file(tmp_path: Path) -> None:
    base = _make_base_layer()
    ext = _make_extension_layer()
    stacked = stack_layers([base, ext])

    out_path = tmp_path / "stacked.frc"
    result = export_frc(stacked, out_path)

    assert Path(result).exists()
    text = Path(result).read_text()
    assert "#atom_types" in text
    assert "#nonbond(12-6)" in text
    assert "Au" in text
    assert "si" in text

    # Verify it can be parsed back
    from upm.codecs.msi_frc import parse_frc_text
    tables, _ = parse_frc_text(text, validate=False)
    assert len(tables["atom_types"]) == 5


def test_from_dict_bond_overrides() -> None:
    layer = ParameterLayer.from_dict(
        {"bonds": {"Au-Au": {"k": 150.0, "r0": 2.9}}},
        name="bond-patch",
    )
    assert "bonds" in layer.tables
    assert len(layer.tables["bonds"]) == 1
    assert layer.tables["bonds"].iloc[0]["t1"] == "Au"
