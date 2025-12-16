"""Pytest configuration.

This repo follows the `src/` layout. Some environments may invoke a `pytest`
entrypoint from a different Python install than the one used for
`python -m pip install -e ...`, which can cause `import upm` to fail.

To keep the skeleton robust, we ensure `src/` is on `sys.path` during tests.
"""

from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    sys.path.insert(0, str(src_dir))