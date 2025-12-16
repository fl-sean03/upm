from __future__ import annotations

from pathlib import Path

import pandas as pd

from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc


def _fixture_frc_text() -> str:
    # Includes:
    # - supported sections: atom_types, quadratic_bond, nonbond(12-6) with directives
    # - unsupported section preserved verbatim (body-only)
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


def test_parse_frc_text_supported_and_unknown_sections_shape() -> None:
    tables, unknown = parse_frc_text(_fixture_frc_text())

    assert "atom_types" in tables
    assert "bonds" in tables

    # Unknown preservation:
    # - key = exact header line
    # - value = list of body lines only, exact content, no trailing newline
    assert unknown["#unsupported_section"] == ["line1", "  line2 with leading spaces", ""]
    assert unknown["#preamble"] == [
        "This is a preamble line that must be preserved.",
        "Another preamble line.",
    ]

    # Ensure parse normalized & deterministic ordering:
    assert list(tables["atom_types"]["atom_type"]) == ["c3", "h", "o"]

    # Bonds are canonicalized (t1 <= t2) and sorted deterministically.
    assert list(tables["bonds"]["t1"]) == ["c3", "c3"]
    assert list(tables["bonds"]["t2"]) == ["h", "o"]


def test_export_full_then_reimport_roundtrip_tables_and_unknown(tmp_path: Path) -> None:
    tables1, unknown1 = parse_frc_text(_fixture_frc_text())

    out_path = tmp_path / "out.frc"
    write_frc(out_path, tables=tables1, unknown_sections=unknown1, mode="full")

    tables2, unknown2 = read_frc(out_path)

    # Tables should match exactly after normalization.
    pd.testing.assert_frame_equal(tables2["atom_types"], tables1["atom_types"], check_like=False)
    pd.testing.assert_frame_equal(tables2["bonds"], tables1["bonds"], check_like=False)

    # Unknown sections should roundtrip.
    assert unknown2["#unsupported_section"] == unknown1["#unsupported_section"]

    # `#preamble` is a synthetic pseudo-section used by the parser to preserve any
    # text before the first real `#...` section header. It should roundtrip
    # unchanged when provided to the exporter.
    assert unknown2.get("#preamble") == unknown1.get("#preamble")


def test_export_is_deterministic_bytes(tmp_path: Path) -> None:
    tables, unknown = parse_frc_text(_fixture_frc_text())

    p1 = tmp_path / "a.frc"
    p2 = tmp_path / "b.frc"
    write_frc(p1, tables=tables, unknown_sections=unknown, mode="full")
    write_frc(p2, tables=tables, unknown_sections=unknown, mode="full")

    assert p1.read_bytes() == p2.read_bytes()