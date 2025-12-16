"""UPM — Unified Parameter Model.

v0.1.x focuses on a minimal import/export/resolver pipeline for MSI `.frc`.
Business logic is intentionally implemented in later subtasks.
"""

from __future__ import annotations

from upm.core import Requirements
from upm.io import read_requirements_json

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Requirements",
    "read_requirements_json",
]
