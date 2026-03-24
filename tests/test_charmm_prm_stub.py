"""Tests for CHARMM .prm codec API contract.

Both read_prm and write_prm now work in v2.0.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from upm.codecs import charmm_prm


def test_charmm_prm_read_works(tmp_path: Path) -> None:
    """read_prm successfully parses a minimal .prm file."""
    p = tmp_path / "demo.prm"
    p.write_text("* demo\n*\n\nNONBONDED\n!\nCT  0.0  -0.1  1.8\n\nEND\n", encoding="utf-8")
    tables, raw = charmm_prm.read_prm(p)
    assert "atom_types" in tables


def test_charmm_prm_write_works(tmp_path: Path) -> None:
    """write_prm generates a valid .prm file."""
    p = tmp_path / "out.prm"
    tables = {
        "atom_types": pd.DataFrame([{
            "atom_type": "CT", "element": "C", "mass_amu": 12.0,
            "vdw_style": "lj_ab_12_6", "lj_a": 100.0, "lj_b": 10.0, "notes": None,
        }]),
    }
    result = charmm_prm.write_prm(p, tables=tables)
    assert Path(result).exists()
    text = Path(result).read_text()
    assert "NONBONDED" in text
    assert "END" in text
