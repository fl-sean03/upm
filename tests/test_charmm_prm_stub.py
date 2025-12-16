from __future__ import annotations

from pathlib import Path

import pytest

from upm.codecs import charmm_prm


def test_charmm_prm_stub_read_raises_not_implemented(tmp_path: Path) -> None:
    p = tmp_path / "demo.prm"
    p.write_text("* demo\n", encoding="utf-8")

    with pytest.raises(NotImplementedError, match=r"v0\.1"):
        charmm_prm.read_prm(p)


def test_charmm_prm_stub_write_raises_not_implemented(tmp_path: Path) -> None:
    p = tmp_path / "demo_out.prm"

    with pytest.raises(NotImplementedError, match=r"v0\.1"):
        charmm_prm.write_prm(p)