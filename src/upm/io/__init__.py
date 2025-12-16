"""UPM I/O helpers.

v0.1 includes Requirements JSON loading in [`read_requirements_json()`](requirements.py:1).
"""

from __future__ import annotations

from .requirements import read_requirements_json

__all__ = ["read_requirements_json"]