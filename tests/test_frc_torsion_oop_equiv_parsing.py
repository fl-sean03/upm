"""Tests for parsing torsion_1, out_of_plane, and equivalence from .frc text.

Validates that the codec correctly extracts these sections from BIOSYM .frc format
and produces properly structured tables.
"""
from __future__ import annotations

from upm.codecs.msi_frc import parse_frc_text


_FRC_WITH_TORSIONS = """\
!BIOSYM forcefield          1

#atom_types cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 1.0   1    c3   12.011000    C           4        sp3 carbon
 1.0   1    h    1.008000     H           1        hydrogen

#equivalence cvff

!Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
!---- ---   ----  ----     ----    -----    -------    ----
 1.0   1    c3    c        c       c        c          c
 1.0   1    h     h        h       h        h          h

#quadratic_bond cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
 1.0   1     c3    h        1.0900   340.0000

#quadratic_angle cvff

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
 1.0   1     h     c3    h      109.5000    50.0000

#torsion_1 cvff

!Ver  Ref     I     J     K     L           Kphi        n           Phi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
 1.0   1     h     c3    c3    h        0.1500      3      0.0000
 1.0   1     *     c3    c3    *        0.2000      1    180.0000

#out_of_plane cvff

!Ver  Ref     I     J     K     L           Kchi        n           Chi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
 1.0   1     c3    h     h     h        0.1000      2    180.0000

#nonbond(12-6) cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 1.0   1     c3     236919.1      217.67820
 1.0   1     h      2384.2        9.76562
"""


def test_parse_torsions_from_frc() -> None:
    tables, _unknown = parse_frc_text(_FRC_WITH_TORSIONS, validate=False)
    assert "torsions" in tables
    df = tables["torsions"]
    assert len(df) == 2
    assert list(df.columns[:4]) == ["t1", "t2", "t3", "t4"]
    # Check first torsion
    row0 = df.iloc[0]
    assert row0["style"] == "torsion_1"
    assert float(row0["kphi"]) == 0.15 or float(row0["kphi"]) == 0.2  # order may vary


def test_parse_oop_from_frc() -> None:
    tables, _unknown = parse_frc_text(_FRC_WITH_TORSIONS, validate=False)
    assert "out_of_plane" in tables
    df = tables["out_of_plane"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["t1"] == "c3"
    assert float(row["kchi"]) == 0.1
    assert int(row["n"]) == 2
    assert float(row["chi0"]) == 180.0


def test_parse_equivalences_from_frc() -> None:
    tables, _unknown = parse_frc_text(_FRC_WITH_TORSIONS, validate=False)
    assert "equivalences" in tables
    df = tables["equivalences"]
    assert len(df) == 2
    # Sorted by atom_type
    assert list(df["atom_type"]) == ["c3", "h"]
    assert list(df["nonb"]) == ["c", "h"]


def test_torsion_sections_not_in_unknown() -> None:
    """Parsed torsion/OOP/equiv sections should NOT appear in unknown_sections."""
    _tables, unknown = parse_frc_text(_FRC_WITH_TORSIONS, validate=False)
    unknown_headers = [u["header"] for u in unknown]
    # These should be parsed, not unknown
    for section in ("#torsion_1", "#out_of_plane", "#equivalence"):
        assert not any(section in h for h in unknown_headers), (
            f"{section} should be parsed, not in unknown_sections"
        )


def test_wildcard_torsion_type_preserved() -> None:
    """Wildcard * atom types in torsions should be preserved."""
    tables, _unknown = parse_frc_text(_FRC_WITH_TORSIONS, validate=False)
    df = tables["torsions"]
    wildcard_rows = df[df["t1"] == "*"]
    assert len(wildcard_rows) >= 1 or df[df["t4"] == "*"].shape[0] >= 1
