"""UPM bundle I/O (package-on-disk format).

v0.1 minimal scope:
- Save/load canonical tables as CSV under `tables/`
- Preserve raw source text + unknown sections under `raw/`
- Write/read `manifest.json` with sha256 hashes for reproducibility
"""

from __future__ import annotations

from .io import PackageBundle, load_package, save_package

__all__ = [
    "PackageBundle",
    "save_package",
    "load_package",
]