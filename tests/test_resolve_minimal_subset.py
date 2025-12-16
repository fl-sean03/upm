from __future__ import annotations

from pathlib import Path

import pytest

from upm.bundle.io import load_package, save_package
from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc
from upm.core.model import Requirements
from upm.core.resolve import MissingTermsError, resolve_minimal


def _fixture_frc_text() -> str:
    # Contains extra terms so minimal resolver can subset.
    return "\n".join(
        [
            "#atom_types",
            "  c3  C  12.011  carbon sp3",
            "  o   O  15.999  oxygen",
            "  h   H  1.008   hydrogen",
            "#quadratic_bond",
            "  o  c3  100.0  1.23",
            "  c3 h   250.0  1.09",
            "#nonbond(12-6)",
            "  @type A-B",
            "  @combination geometric",
            "  c3  1.0   2.0",
            "  o   10.0  20.0",
            "  h   0.1   0.2",
            "#unsupported_section",
            "kept",
        ]
    ) + "\n"


def test_at2_resolve_minimal_subset_and_export_reimport(tmp_path: Path) -> None:
    tables_full, unknown = parse_frc_text(_fixture_frc_text())

    req = Requirements(atom_types=["c3", "h"], bond_types=[["h", "c3"]])

    resolved = resolve_minimal(tables_full, req)

    # Subset correctness (atom_types)
    assert list(resolved.atom_types["atom_type"]) == ["c3", "h"]

    # Subset correctness (bonds): only c3-h
    assert list(resolved.bonds["t1"]) == ["c3"]
    assert list(resolved.bonds["t2"]) == ["h"]

    # Export minimal and re-import: must contain only required supported rows
    out_path = tmp_path / "min.frc"
    write_frc(out_path, tables={"atom_types": resolved.atom_types, "bonds": resolved.bonds}, unknown_sections=unknown, mode="minimal")

    tables_min, unknown_min = read_frc(out_path)
    assert list(tables_min["atom_types"]["atom_type"]) == ["c3", "h"]
    assert list(tables_min["bonds"]["t1"]) == ["c3"]
    assert list(tables_min["bonds"]["t2"]) == ["h"]

    # Unknown section preservation
    assert unknown_min.get("#unsupported_section") == unknown.get("#unsupported_section")


def test_at3_missing_atom_types_error_lists_missing() -> None:
    tables_full, _unknown = parse_frc_text(_fixture_frc_text())
    req = Requirements(atom_types=["c3", "x_missing"], bond_types=[["c3", "h"]])

    with pytest.raises(MissingTermsError) as e:
        _ = resolve_minimal(tables_full, req)

    msg = str(e.value)
    assert "missing required atom_types" in msg
    assert "x_missing" in msg
    assert e.value.missing_atom_types == ("x_missing",)


def test_at3_missing_bond_types_error_lists_missing() -> None:
    tables_full, _unknown = parse_frc_text(_fixture_frc_text())
    req = Requirements(atom_types=["c3", "h"], bond_types=[["c3", "o"], ["c3", "x_missing"]])

    with pytest.raises(MissingTermsError) as e:
        _ = resolve_minimal(tables_full, req)

    msg = str(e.value)
    assert "missing required bond_types" in msg
    # Both missing bonds should be listed; ('c3','o') exists, ('c3','x_missing') does not.
    assert "('c3', 'x_missing')" in msg
    assert e.value.missing_bond_types == (("c3", "x_missing"),)


def test_resolve_minimal_missing_bonds_when_table_absent_lists_all_required() -> None:
    # If requirements include bonds but input tables dict has no 'bonds' table,
    # all required bond types must be reported missing.
    tables_full, _unknown = parse_frc_text(_fixture_frc_text())
    tables_no_bonds = {"atom_types": tables_full["atom_types"]}

    req = Requirements(atom_types=["c3", "h"], bond_types=[["c3", "h"]])

    with pytest.raises(MissingTermsError) as e:
        _ = resolve_minimal(tables_no_bonds, req)

    assert e.value.missing_bond_types == (("c3", "h"),)


def test_minimal_export_from_bundle_matches_requirements_exactly(tmp_path: Path) -> None:
    # Same as AT2, but exercises bundle save/load path explicitly.
    src_text = _fixture_frc_text()
    tables_full, unknown = parse_frc_text(src_text)

    pkg_root = tmp_path / "packages" / "demo" / "v0"
    save_package(pkg_root, name="demo", version="v0", tables=tables_full, source_text=src_text, unknown_sections=unknown)

    bundle = load_package(pkg_root)

    req = Requirements(atom_types=["c3", "h"], bond_types=[["c3", "h"]])
    resolved = resolve_minimal(bundle.tables, req)

    out_path = tmp_path / "minimal.frc"
    write_frc(
        out_path,
        tables={"atom_types": resolved.atom_types, "bonds": resolved.bonds},
        unknown_sections=bundle.raw["unknown_sections"],
        mode="minimal",
    )

    tables_min, _unknown_min = read_frc(out_path)
    assert list(tables_min["atom_types"]["atom_type"]) == ["c3", "h"]
    assert list(tables_min["bonds"]["t1"]) == ["c3"]
    assert list(tables_min["bonds"]["t2"]) == ["h"]