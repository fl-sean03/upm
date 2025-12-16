from __future__ import annotations

from pathlib import Path

import pandas as pd

from upm.bundle.io import load_package, save_package
from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc


def _fixture_frc_text() -> str:
    # Keep identical to the codec fixture to ensure we exercise unknown preservation too.
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


def test_at1_import_export_full_roundtrip_via_bundle(tmp_path: Path) -> None:
    # Import (parse) to canonical tables + unknown sections
    src_text = _fixture_frc_text()
    tables1, unknown1 = parse_frc_text(src_text)

    # Save as a package bundle
    pkg_root = tmp_path / "packages" / "demo" / "v0"
    save_package(
        pkg_root,
        name="demo",
        version="v0",
        tables=tables1,
        source_text=src_text,
        unknown_sections=unknown1,
    )

    # Export full from bundle
    bundle = load_package(pkg_root)
    out_path = tmp_path / "full_export.frc"
    write_frc(out_path, tables=bundle.tables, unknown_sections=bundle.raw["unknown_sections"], mode="full")

    # Re-import exported frc and compare
    tables2, unknown2 = read_frc(out_path)

    pd.testing.assert_frame_equal(tables2["atom_types"], tables1["atom_types"], check_like=False)
    pd.testing.assert_frame_equal(tables2["bonds"], tables1["bonds"], check_like=False)

    assert unknown2.get("#unsupported_section") == unknown1.get("#unsupported_section")
    assert unknown2.get("#preamble") == unknown1.get("#preamble")