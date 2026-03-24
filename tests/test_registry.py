"""Tests for UPM parameter registry: discovery, index, and diff."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from upm.registry.discovery import discover_local_packages, discover_packages, DiscoveredPackage
from upm.registry.index import PackageIndex, SearchResult
from upm.registry.diff import diff_tables, ParameterDiff


# =============================================================================
# Discovery
# =============================================================================


def test_discover_packages_returns_list() -> None:
    """Entry point discovery returns a list (may be empty if no packages installed)."""
    result = discover_packages()
    assert isinstance(result, list)


def test_discover_local_packages_empty_dir(tmp_path: Path) -> None:
    result = discover_local_packages(tmp_path)
    assert result == []


def test_discover_local_packages_finds_manifest(tmp_path: Path) -> None:
    """Local discovery finds packages with manifest.json."""
    pkg_dir = tmp_path / "test-ff" / "v1.0"
    pkg_dir.mkdir(parents=True)
    manifest = {"name": "test-ff", "version": "v1.0", "schema_version": "0.1"}
    (pkg_dir / "manifest.json").write_text(json.dumps(manifest))

    result = discover_local_packages(tmp_path)
    assert len(result) == 1
    assert result[0].name == "test-ff"
    assert result[0].version == "v1.0"
    assert result[0].source == "local"


def test_discover_local_nonexistent_dir() -> None:
    result = discover_local_packages(Path("/nonexistent"))
    assert result == []


# =============================================================================
# PackageIndex
# =============================================================================


def _make_bundle(tmp_path: Path, name: str, atom_types: list[str]) -> DiscoveredPackage:
    """Create a minimal UPM bundle for testing."""
    from upm.bundle.io import save_package
    from upm.core.tables import normalize_atom_types

    pkg_dir = tmp_path / name / "v1"
    rows = [{
        "atom_type": at, "element": "X", "mass_amu": 1.0,
        "vdw_style": "lj_ab_12_6", "lj_a": 100.0, "lj_b": 10.0, "notes": None,
    } for at in atom_types]
    df = normalize_atom_types(pd.DataFrame(rows))

    save_package(
        pkg_dir, name=name, version="v1",
        tables={"atom_types": df},
        source_text="! test", unknown_sections=[],
    )

    return DiscoveredPackage(name=name, version="v1", path=pkg_dir, source="local")


def test_package_index_search_atom_type(tmp_path: Path) -> None:
    pkg = _make_bundle(tmp_path, "metals", ["Au", "Cu", "Pt"])
    index = PackageIndex([pkg])
    results = index.search_atom_type("Au")
    assert len(results) == 1
    assert results[0].package_name == "metals"
    assert results[0].row["atom_type"] == "Au"


def test_package_index_search_not_found(tmp_path: Path) -> None:
    pkg = _make_bundle(tmp_path, "metals", ["Au", "Cu"])
    index = PackageIndex([pkg])
    results = index.search_atom_type("Nonexistent")
    assert results == []


def test_package_index_list_atom_types(tmp_path: Path) -> None:
    pkg = _make_bundle(tmp_path, "metals", ["Au", "Cu", "Pt"])
    index = PackageIndex([pkg])
    listing = index.list_atom_types()
    assert "metals@v1" in listing
    assert listing["metals@v1"] == ["Au", "Cu", "Pt"]


def test_package_index_multi_package(tmp_path: Path) -> None:
    pkg1 = _make_bundle(tmp_path, "metals", ["Au", "Cu"])
    pkg2 = _make_bundle(tmp_path, "oxides", ["Au", "O2"])
    index = PackageIndex([pkg1, pkg2])
    results = index.search_atom_type("Au")
    assert len(results) == 2
    pkg_names = {r.package_name for r in results}
    assert pkg_names == {"metals", "oxides"}


# =============================================================================
# Diff
# =============================================================================


def _tables_with_atom_types(types: dict[str, dict[str, float]]) -> dict:
    rows = []
    for at, params in types.items():
        rows.append({
            "atom_type": at, "element": "X", "mass_amu": params.get("mass", 1.0),
            "vdw_style": "lj_ab_12_6",
            "lj_a": params.get("lj_a", 100.0),
            "lj_b": params.get("lj_b", 10.0),
            "notes": None,
        })
    return {"atom_types": pd.DataFrame(rows)}


def test_diff_no_changes() -> None:
    tables = _tables_with_atom_types({"Au": {"lj_a": 100.0}})
    diff = diff_tables(tables, tables)
    assert not diff.has_changes


def test_diff_added_type() -> None:
    left = _tables_with_atom_types({"Au": {"lj_a": 100.0}})
    right = _tables_with_atom_types({"Au": {"lj_a": 100.0}, "Cu": {"lj_a": 200.0}})
    diff = diff_tables(left, right)
    assert diff.added_types == ["Cu"]
    assert diff.removed_types == []


def test_diff_removed_type() -> None:
    left = _tables_with_atom_types({"Au": {"lj_a": 100.0}, "Cu": {"lj_a": 200.0}})
    right = _tables_with_atom_types({"Au": {"lj_a": 100.0}})
    diff = diff_tables(left, right)
    assert diff.removed_types == ["Cu"]


def test_diff_changed_param() -> None:
    left = _tables_with_atom_types({"Au": {"lj_a": 100.0, "lj_b": 10.0}})
    right = _tables_with_atom_types({"Au": {"lj_a": 200.0, "lj_b": 10.0}})
    diff = diff_tables(left, right)
    assert len(diff.changed_params) == 1
    assert diff.changed_params[0].field == "lj_a"
    assert diff.changed_params[0].old_value == pytest.approx(100.0)
    assert diff.changed_params[0].new_value == pytest.approx(200.0)


def test_diff_summary_output() -> None:
    left = _tables_with_atom_types({"Au": {"lj_a": 100.0}})
    right = _tables_with_atom_types({"Au": {"lj_a": 200.0}, "Cu": {"lj_a": 300.0}})
    diff = diff_tables(left, right)
    summary = diff.summary()
    assert "Added types" in summary
    assert "Cu" in summary
    assert "Changed parameters" in summary
