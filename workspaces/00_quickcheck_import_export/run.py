"""Quickcheck workspace: import -> export(full) -> reimport -> compare (v0.1).

This workspace is self-contained (no repo-level assets required). It uses a small
synthetic `.frc` fixture string, writes a temporary package bundle under
`workspaces/00_quickcheck_import_export/outputs/packages/<name>/<version>/`,
exports a full `.frc`, re-imports it, and writes a JSON report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from upm.bundle.io import load_package, save_package
from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc


def _fixture_frc_text() -> str:
    # Mirrors the codec test fixture to keep behavior aligned with AT1.
    return "\n".join(
        [
            "This is a preamble line that must be preserved.",
            "Another preamble line.",
            "#atom_types",
            "  c3  C  12.011  carbon sp3",
            "  o   O  15.999  oxygen",
            "  h   H  1.008   hydrogen",
            "#quadratic_bond",
            "  o  c3  100.0  1.23  src:demo",
            "  c3 h   250.0  1.09",
            "#nonbond(12-6)",
            "  @type A-B",
            "  @combination geometric",
            "  c3  1.0   2.0",
            "  o   10.0  20.0",
            "  h   0.1   0.2",
            "#unsupported_section",
            "line1",
            "  line2 with leading spaces",
            "",
        ]
    ) + "\n"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    here = Path(__file__).resolve().parent
    outputs = here / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    pkg_name = "demo-ff"
    pkg_version = "v0"
    pkg_root = outputs / "packages" / pkg_name / pkg_version

    src_text = _fixture_frc_text()
    tables1, unknown1 = parse_frc_text(src_text)

    save_package(
        pkg_root,
        name=pkg_name,
        version=pkg_version,
        tables=tables1,
        source_text=src_text,
        unknown_sections=unknown1,
    )

    full_out = outputs / "full_export.frc"
    bundle1 = load_package(pkg_root)
    write_frc(
        full_out,
        tables=bundle1.tables,
        unknown_sections=bundle1.raw["unknown_sections"],
        include_raw=True,
        mode="full",
    )

    tables2, unknown2 = read_frc(full_out)

    # Compare supported tables
    ok_tables = True
    try:
        pd.testing.assert_frame_equal(tables2["atom_types"], tables1["atom_types"], check_like=False)
        pd.testing.assert_frame_equal(tables2["bonds"], tables1["bonds"], check_like=False)
    except AssertionError:
        ok_tables = False

    # Compare unknown preservation (ordered list of sections)
    ok_unknown = unknown2 == unknown1

    report = {
        "package_root": str(pkg_root),
        "full_export_path": str(full_out),
        "tables_equal": ok_tables,
        "unknown_sections_equal": ok_unknown,
        "unknown_sections_len": len(unknown2),
        "unknown_sections_headers": [x.get("header") for x in unknown2],
    }
    _write_json(outputs / "roundtrip_report.json", report)

    if not (ok_tables and ok_unknown):
        raise SystemExit("roundtrip failed; see outputs/roundtrip_report.json")


if __name__ == "__main__":
    main()
