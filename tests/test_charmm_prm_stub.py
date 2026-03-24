"""Tests for CHARMM .prm codec API contract.

read_prm now works (v2.0). write_prm still raises NotImplementedError.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from upm.codecs import charmm_prm


def test_charmm_prm_read_works(tmp_path: Path) -> None:
    """read_prm successfully parses a minimal .prm file."""
    p = tmp_path / "demo.prm"
    p.write_text("* demo\n*\n\nNONBONDED\n!\nCT  0.0  -0.1  1.8\n\nEND\n", encoding="utf-8")
    tables, raw = charmm_prm.read_prm(p)
    assert "atom_types" in tables


def test_charmm_prm_write_raises_not_implemented(tmp_path: Path) -> None:
    p = tmp_path / "demo_out.prm"
    with pytest.raises(NotImplementedError, match=r"v2\.0"):
        charmm_prm.write_prm(p, tables={})
