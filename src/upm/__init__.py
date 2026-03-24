"""UPM — Unified Parameter Model.

Versioned force-field parameter management: parsing, validation,
querying, and export for MSI `.frc` and CHARMM `.prm` formats.
"""

from __future__ import annotations

from upm.core import Requirements
from upm.io import read_requirements_json

__version__ = "2.0.0"

__all__ = [
    "__version__",
    "Requirements",
    "read_requirements_json",
]
