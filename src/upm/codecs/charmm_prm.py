"""CHARMM `.prm` codec (stub for v0.1).

The v0.1 DevGuide explicitly keeps CHARMM `.prm` out of scope. This module exists
to provide a clear failure mode and to reserve the API surface for future work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_prm(path: str | Path, *_: Any, **__: Any) -> None:
    """Stub reader for CHARMM `.prm`.

    Raises:
        NotImplementedError: always, in v0.1.
    """
    raise NotImplementedError(
        "CHARMM .prm codec is not implemented in UPM v0.1; "
        "only MSI .frc import/export is supported in this version."
    )


def write_prm(path: str | Path, *_: Any, **__: Any) -> None:
    """Stub writer for CHARMM `.prm`.

    Raises:
        NotImplementedError: always, in v0.1.
    """
    raise NotImplementedError(
        "CHARMM .prm codec is not implemented in UPM v0.1; "
        "only MSI .frc import/export is supported in this version."
    )