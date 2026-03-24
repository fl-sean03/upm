"""Tests for CHARMM .prm codec.

Tests parsing of real IFF CHARMM36 .prm file and conversion accuracy.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from upm.codecs.charmm_prm import read_prm, write_prm
from upm.codecs._charmm_parser import (
    parse_prm_text,
    _charmm_eps_rmin_to_lj_ab,
    _lj_ab_to_charmm_eps_rmin,
)


# =============================================================================
# Conversion function tests
# =============================================================================


def test_eps_rmin_to_lj_ab_known_values() -> None:
    """Test CHARMM→LJ A/B conversion with known values."""
    # epsilon=0.1, Rmin/2=1.5 → Rmin=3.0
    a, b = _charmm_eps_rmin_to_lj_ab(-0.1, 1.5)
    rmin = 3.0
    expected_a = 0.1 * rmin**12
    expected_b = 2.0 * 0.1 * rmin**6
    assert a == pytest.approx(expected_a, rel=1e-10)
    assert b == pytest.approx(expected_b, rel=1e-10)


def test_lj_ab_roundtrip() -> None:
    """Test A/B → eps/Rmin → A/B roundtrip preserves values."""
    a_orig, b_orig = 236919.1, 217.67820
    neg_eps, rmin_half = _lj_ab_to_charmm_eps_rmin(a_orig, b_orig)
    a_back, b_back = _charmm_eps_rmin_to_lj_ab(neg_eps, rmin_half)
    assert a_back == pytest.approx(a_orig, rel=1e-6)
    assert b_back == pytest.approx(b_orig, rel=1e-6)


def test_lj_ab_zero_handling() -> None:
    """Zero A/B values convert to zero eps/Rmin."""
    neg_eps, rmin_half = _lj_ab_to_charmm_eps_rmin(0.0, 0.0)
    assert neg_eps == 0.0
    assert rmin_half == 0.0


# =============================================================================
# Small .prm text parsing
# =============================================================================

_SMALL_PRM = """\
* Test parameter file
*

BONDS
!
!atom type  Kb      b0
!
CT1  CT1   222.500     1.5000
CT1  HA    309.000     1.1110

ANGLES
!
CT1  CT1  CT1   58.350    113.50   11.16   2.56100
CT1  CT1  HA    26.500    110.10   22.53   2.17900

DIHEDRALS
!
HA   CT1  CT1  HA      0.1950  3     0.00
X    CT1  CT1  X       0.1500  1   180.00

IMPROPER
!
CPB  CPA  NPH  CPA    20.8000         0      0.0000

NONBONDED nbxmod  5 atom cdiel shift vatom vdistance vfswitch -
cutnb 14.0 ctofnb 12.0 ctonnb 10.0 eps 1.0 e14fac 1.0 wmin 1.5
!
CT1    0.000000  -0.020000     2.275000   0.000000  -0.010000     1.900000
HA     0.000000  -0.022000     1.320000

NBFIX
!              Emin         Rmin
SOD    CLI      -0.083875   3.731

END
"""


def test_parse_small_prm_bonds() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "bonds" in tables
    df = tables["bonds"]
    assert len(df) == 2
    assert list(df["t1"]) == ["CT1", "CT1"]
    assert float(df.iloc[0]["k"]) == pytest.approx(222.5)
    assert float(df.iloc[0]["r0"]) == pytest.approx(1.5)


def test_parse_small_prm_angles() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "angles" in tables
    df = tables["angles"]
    assert len(df) == 2
    assert float(df.iloc[0]["theta0_deg"]) == pytest.approx(113.5)


def test_parse_small_prm_dihedrals() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "torsions" in tables
    df = tables["torsions"]
    assert len(df) == 2
    row0 = df.iloc[0]
    assert float(row0["kphi"]) == pytest.approx(0.195)
    assert int(row0["n"]) == 3


def test_parse_small_prm_improper() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "out_of_plane" in tables
    df = tables["out_of_plane"]
    assert len(df) == 1
    assert float(df.iloc[0]["kchi"]) == pytest.approx(20.8)


def test_parse_small_prm_nonbonded() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "atom_types" in tables
    df = tables["atom_types"]
    assert len(df) == 2
    # CT1: eps=0.02, Rmin/2=2.275 → Rmin=4.55
    ct1 = df[df["atom_type"] == "CT1"].iloc[0]
    a, b = _charmm_eps_rmin_to_lj_ab(-0.02, 2.275)
    assert float(ct1["lj_a"]) == pytest.approx(a, rel=1e-6)
    assert float(ct1["lj_b"]) == pytest.approx(b, rel=1e-6)


def test_parse_small_prm_nbfix() -> None:
    tables, _raw = parse_prm_text(_SMALL_PRM)
    assert "pair_overrides" in tables
    df = tables["pair_overrides"]
    assert len(df) == 1
    assert df.iloc[0]["t1"] == "SOD"
    assert df.iloc[0]["t2"] == "CLI"


def test_parse_small_prm_preserves_title() -> None:
    _tables, raw = parse_prm_text(_SMALL_PRM)
    titles = [r for r in raw if r["header"] == "TITLE"]
    assert len(titles) == 1
    assert any("Test parameter file" in line for line in titles[0]["body"])


# =============================================================================
# Real IFF CHARMM36 .prm file
# =============================================================================

_ASSET_PRM = Path(__file__).resolve().parent.parent / "assets" / "IFF_CHARMM36_metal_and_alumina_phases_V8.prm"


@pytest.mark.skipif(not _ASSET_PRM.exists(), reason="IFF CHARMM36 .prm not available")
class TestRealCHARMM:

    def test_read_prm_parses_successfully(self) -> None:
        tables, raw = read_prm(_ASSET_PRM)
        assert "atom_types" in tables
        assert "bonds" in tables
        assert "angles" in tables
        assert "torsions" in tables

    def test_atom_types_count(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        # IFF CHARMM36 has 239 nonbonded atom type entries
        assert len(tables["atom_types"]) > 200

    def test_bonds_count(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        assert len(tables["bonds"]) > 200

    def test_angles_count(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        assert len(tables["angles"]) > 500

    def test_dihedrals_count(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        assert len(tables["torsions"]) > 900

    def test_improper_count(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        assert len(tables["out_of_plane"]) > 50

    def test_cmap_preserved(self) -> None:
        _tables, raw = read_prm(_ASSET_PRM)
        cmap_sections = [r for r in raw if r["header"] == "CMAP"]
        assert len(cmap_sections) == 1
        # CMAP should have substantial content
        assert len(cmap_sections[0]["body"]) > 100

    def test_nbfix_parsed(self) -> None:
        tables, _raw = read_prm(_ASSET_PRM)
        assert "pair_overrides" in tables
        assert len(tables["pair_overrides"]) > 0

    def test_lj_params_nonzero(self) -> None:
        """Verify LJ A/B values are reasonable (not all zero)."""
        tables, _raw = read_prm(_ASSET_PRM)
        df = tables["atom_types"]
        nonzero_a = (df["lj_a"].astype(float) > 0).sum()
        assert nonzero_a > 100, f"Only {nonzero_a} atom types have nonzero lj_a"

    def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        """Semantic roundtrip: parse → write → parse → compare tables."""
        from upm.codecs.charmm_prm import write_prm

        tables1, raw1 = read_prm(_ASSET_PRM)
        out_path = tmp_path / "roundtrip.prm"
        write_prm(out_path, tables=tables1, raw_sections=raw1)

        tables2, _raw2 = read_prm(out_path)

        # Atom types count should match
        assert len(tables2["atom_types"]) == len(tables1["atom_types"])
        # Bonds count should match
        assert len(tables2["bonds"]) == len(tables1["bonds"])
        # LJ params should roundtrip accurately
        for at in ["AU", "AG", "CT1"]:
            row1 = tables1["atom_types"]
            row2 = tables2["atom_types"]
            match1 = row1[row1["atom_type"] == at]
            match2 = row2[row2["atom_type"] == at]
            if len(match1) > 0 and len(match2) > 0:
                a1 = float(match1.iloc[0]["lj_a"])
                a2 = float(match2.iloc[0]["lj_a"])
                assert a2 == pytest.approx(a1, rel=1e-4), f"{at} lj_a mismatch"
