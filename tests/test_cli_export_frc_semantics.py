from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from upm.bundle.io import save_package
from upm.cli.main import app
from upm.codecs.msi_frc import parse_frc_text


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_frc_text_with_raw() -> str:
    # Include preamble + unsupported section so we can verify include-raw behavior.
    return "\n".join(
        [
            "This is a preamble line that must be preserved.",
            "#atom_types",
            "  c3  C  12.011  carbon sp3",
            "  h   H  1.008   hydrogen",
            "#quadratic_bond",
            "  c3 h   250.0  1.09",
            "#nonbond(12-6)",
            "  @type A-B",
            "  @combination geometric",
            "  c3  1.0   2.0",
            "  h   0.1   0.2",
            "#unsupported_section",
            "line1",
            "",
        ]
    ) + "\n"


def _make_demo_bundle(tmp_path: Path) -> Path:
    src_text = _fixture_frc_text_with_raw()
    tables, unknown_sections = parse_frc_text(src_text)

    pkg_root = tmp_path / "packages" / "demo" / "v0"
    save_package(
        pkg_root,
        name="demo",
        version="v0",
        tables=tables,
        source_text=src_text,
        unknown_sections=unknown_sections,
    )
    return pkg_root


def test_export_frc_full_omit_raw_by_default_and_include_raw_when_requested(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    out_no_raw = tmp_path / "full_no_raw.frc"
    res1 = runner.invoke(app, ["export-frc", "--out", str(out_no_raw), "--mode", "full", "--path", str(pkg_root)])
    assert res1.exit_code == 0
    txt1 = out_no_raw.read_text(encoding="utf-8")
    assert "#unsupported_section" not in txt1
    assert "This is a preamble line that must be preserved." not in txt1

    out_with_raw = tmp_path / "full_with_raw.frc"
    res2 = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_with_raw),
            "--mode",
            "full",
            "--path",
            str(pkg_root),
            "--include-raw",
        ],
    )
    assert res2.exit_code == 0
    txt2 = out_with_raw.read_text(encoding="utf-8")
    assert "#unsupported_section" in txt2
    assert "This is a preamble line that must be preserved." in txt2


def test_export_frc_minimal_missing_default_is_exit_2_and_no_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    req_path = tmp_path / "req.json"
    _write_json(
        req_path,
        {
            "atom_types": ["c3", "x_missing"],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
        },
    )

    out_frc = tmp_path / "min.frc"
    res = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_frc),
            "--mode",
            "minimal",
            "--path",
            str(pkg_root),
            "--requirements",
            str(req_path),
        ],
    )
    # Typer usage error (BadParameter)
    assert res.exit_code == 2
    assert not out_frc.exists()
    assert not out_frc.with_name("missing.json").exists()


def test_export_frc_minimal_allow_missing_writes_missing_json_and_exits_1(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    req_path = tmp_path / "req.json"
    _write_json(
        req_path,
        {
            "atom_types": ["c3", "x_missing"],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
        },
    )

    out_frc = tmp_path / "min_allow.frc"
    res = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_frc),
            "--mode",
            "minimal",
            "--path",
            str(pkg_root),
            "--requirements",
            str(req_path),
            "--allow-missing",
        ],
    )
    assert res.exit_code == 1
    assert out_frc.exists()

    miss_path = out_frc.with_name("missing.json")
    assert miss_path.exists()

    expected = {
        "angle_types": [],
        "atom_types": ["x_missing"],
        "bond_types": [],
        "dihedral_types": [],
    }
    assert miss_path.read_text(encoding="utf-8") == json.dumps(expected, indent=2, sort_keys=True) + "\n"


def test_export_frc_minimal_allow_missing_force_exits_0(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    req_path = tmp_path / "req.json"
    _write_json(
        req_path,
        {
            "atom_types": ["c3", "x_missing"],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
        },
    )

    out_frc = tmp_path / "min_force.frc"
    res = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_frc),
            "--mode",
            "minimal",
            "--path",
            str(pkg_root),
            "--requirements",
            str(req_path),
            "--allow-missing",
            "--force",
        ],
    )
    assert res.exit_code == 0
    assert out_frc.exists()
    assert out_frc.with_name("missing.json").exists()


def test_export_frc_minimal_allow_missing_no_missing_exits_0_and_writes_empty_missing_json(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    req_path = tmp_path / "req.json"
    _write_json(
        req_path,
        {
            "atom_types": ["c3", "h"],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
        },
    )

    out_frc = tmp_path / "min_nomiss.frc"
    res = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_frc),
            "--mode",
            "minimal",
            "--path",
            str(pkg_root),
            "--requirements",
            str(req_path),
            "--allow-missing",
        ],
    )
    assert res.exit_code == 0
    assert out_frc.exists()

    miss_path = out_frc.with_name("missing.json")
    assert miss_path.exists()

    expected = {
        "angle_types": [],
        "atom_types": [],
        "bond_types": [],
        "dihedral_types": [],
    }
    assert miss_path.read_text(encoding="utf-8") == json.dumps(expected, indent=2, sort_keys=True) + "\n"


def test_export_frc_minimal_missing_report_path_override(tmp_path: Path) -> None:
    runner = CliRunner()
    pkg_root = _make_demo_bundle(tmp_path)

    req_path = tmp_path / "req.json"
    _write_json(
        req_path,
        {
            "atom_types": ["c3", "x_missing"],
            "bond_types": [],
            "angle_types": [],
            "dihedral_types": [],
        },
    )

    out_frc = tmp_path / "min_custom_report.frc"
    report_path = tmp_path / "reports" / "missing_custom.json"
    res = runner.invoke(
        app,
        [
            "export-frc",
            "--out",
            str(out_frc),
            "--mode",
            "minimal",
            "--path",
            str(pkg_root),
            "--requirements",
            str(req_path),
            "--allow-missing",
            "--missing-report",
            str(report_path),
        ],
    )
    assert res.exit_code == 1
    assert report_path.exists()
    # The default adjacent missing.json should not be required; this assertion ensures
    # we honored the override path.
    assert not out_frc.with_name("missing.json").exists()