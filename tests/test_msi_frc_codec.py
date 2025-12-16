from __future__ import annotations

from pathlib import Path

import pandas as pd

from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc


def _fixture_frc_text() -> str:
    # Includes:
    # - supported sections: atom_types, quadratic_bond, quadratic_angle, nonbond(12-6) with directives
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
            "#quadratic_angle demo_src",
            # order intentionally non-canonical in first row (o > h) to test endpoint canonicalization
            "  o   c3  h   109.5  45.0",
            "  h   c3  h   106.4  39.5",
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
    assert "angles" in tables

    # Unknown preservation (ordered raw section list):
    assert unknown == [
        {
            "header": "#preamble",
            "body": [
                "This is a preamble line that must be preserved.",
                "Another preamble line.",
            ],
        },
        {"header": "#unsupported_section", "body": ["line1", "  line2 with leading spaces", ""]},
    ]

    # Ensure parse normalized & deterministic ordering:
    assert list(tables["atom_types"]["atom_type"]) == ["c3", "h", "o"]

    # Bonds are canonicalized (t1 <= t2) and sorted deterministically.
    assert list(tables["bonds"]["t1"]) == ["c3", "c3"]
    assert list(tables["bonds"]["t2"]) == ["h", "o"]

    # Angles are canonicalized (t1 <= t3) and sorted deterministically.
    assert list(tables["angles"]["t1"]) == ["h", "h"]
    assert list(tables["angles"]["t2"]) == ["c3", "c3"]
    assert list(tables["angles"]["t3"]) == ["h", "o"]
    assert list(tables["angles"]["source"]) == ["demo_src", "demo_src"]


def test_export_full_then_reimport_roundtrip_tables_and_unknown(tmp_path: Path) -> None:
    tables1, unknown1 = parse_frc_text(_fixture_frc_text())

    out_path = tmp_path / "out.frc"
    write_frc(out_path, tables=tables1, unknown_sections=unknown1, include_raw=True, mode="full")

    tables2, unknown2 = read_frc(out_path)

    # Tables should match exactly after normalization.
    pd.testing.assert_frame_equal(tables2["atom_types"], tables1["atom_types"], check_like=False)
    pd.testing.assert_frame_equal(tables2["bonds"], tables1["bonds"], check_like=False)
    pd.testing.assert_frame_equal(tables2["angles"], tables1["angles"], check_like=False)

    # Unknown sections should roundtrip in deterministic encounter order.
    assert unknown2 == unknown1


def test_export_is_deterministic_bytes(tmp_path: Path) -> None:
    tables, unknown = parse_frc_text(_fixture_frc_text())

    p1 = tmp_path / "a.frc"
    p2 = tmp_path / "b.frc"
    write_frc(p1, tables=tables, unknown_sections=unknown, mode="full")
    write_frc(p2, tables=tables, unknown_sections=unknown, mode="full")

    assert p1.read_bytes() == p2.read_bytes()


def test_export_is_deterministic_bytes_include_raw(tmp_path: Path) -> None:
    tables, unknown = parse_frc_text(_fixture_frc_text())

    p1 = tmp_path / "a_raw.frc"
    p2 = tmp_path / "b_raw.frc"
    write_frc(p1, tables=tables, unknown_sections=unknown, include_raw=True, mode="full")
    write_frc(p2, tables=tables, unknown_sections=unknown, include_raw=True, mode="full")

    assert p1.read_bytes() == p2.read_bytes()