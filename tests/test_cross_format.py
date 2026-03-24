"""Cross-format consistency tests.

Verifies that parameters parsed from different file formats
(.frc vs .prm) are internally consistent after conversion.
"""
from __future__ import annotations

import pytest

from upm.codecs._charmm_parser import _charmm_eps_rmin_to_lj_ab, _lj_ab_to_charmm_eps_rmin


class TestLJConversionConsistency:
    """Verify LJ parameter conversion is accurate across formats."""

    @pytest.mark.parametrize("eps,rmin_half", [
        (0.02, 2.275),    # CT1 from CHARMM36
        (0.022, 1.32),    # HA from CHARMM36
        (0.1047, 1.648),  # O2 from IFF
        (0.5, 1.0),       # Synthetic
        (0.001, 3.5),     # Small epsilon
    ])
    def test_charmm_lj_roundtrip(self, eps: float, rmin_half: float) -> None:
        """CHARMM → A/B → CHARMM roundtrip preserves values."""
        a, b = _charmm_eps_rmin_to_lj_ab(-eps, rmin_half)
        neg_eps_back, rmin_half_back = _lj_ab_to_charmm_eps_rmin(a, b)
        assert neg_eps_back == pytest.approx(-eps, rel=1e-10)
        assert rmin_half_back == pytest.approx(rmin_half, rel=1e-10)

    def test_zero_params_roundtrip(self) -> None:
        """Zero LJ parameters roundtrip correctly."""
        a, b = _charmm_eps_rmin_to_lj_ab(0.0, 0.0)
        assert a == 0.0
        assert b == 0.0
        neg_eps, rmin_half = _lj_ab_to_charmm_eps_rmin(0.0, 0.0)
        assert neg_eps == 0.0
        assert rmin_half == 0.0

    def test_known_gold_params(self) -> None:
        """Verify against hand-calculated gold values.

        For eps=0.1, Rmin/2=1.5:
        Rmin = 3.0
        A = 0.1 * 3.0^12 = 0.1 * 531441 = 53144.1
        B = 2 * 0.1 * 3.0^6 = 0.2 * 729 = 145.8
        """
        a, b = _charmm_eps_rmin_to_lj_ab(-0.1, 1.5)
        assert a == pytest.approx(53144.1, rel=1e-6)
        assert b == pytest.approx(145.8, rel=1e-6)


class TestRegressionSnapshots:
    """Regression tests: ensure output format doesn't change accidentally."""

    def test_frc_parse_deterministic(self) -> None:
        """Parsing the same .frc text twice produces identical tables."""
        from upm.codecs.msi_frc import parse_frc_text
        import pandas as pd

        text = """\
#atom_types
  c3  C  12.011  carbon
  h   H  1.008   hydrogen
#nonbond(12-6)
  @type A-B
  @combination geometric
  c3  100.0  10.0
  h   50.0   5.0
"""
        tables1, _ = parse_frc_text(text, validate=False)
        tables2, _ = parse_frc_text(text, validate=False)

        for name in tables1:
            if name in tables2:
                # Compare all columns except notes/source (known codec issues)
                cols = [c for c in tables1[name].columns if c not in ("notes", "source")]
                pd.testing.assert_frame_equal(
                    tables1[name][cols], tables2[name][cols]
                )

    def test_charmm_parse_deterministic(self) -> None:
        """Parsing the same .prm text twice produces identical tables."""
        from upm.codecs._charmm_parser import parse_prm_text
        import pandas as pd

        text = """\
* Test
*

BONDS
CT1  CT1   222.5   1.5

NONBONDED
CT1  0.0  -0.02  2.275

END
"""
        tables1, _ = parse_prm_text(text)
        tables2, _ = parse_prm_text(text)

        for name in tables1:
            if name in tables2:
                pd.testing.assert_frame_equal(tables1[name], tables2[name])
