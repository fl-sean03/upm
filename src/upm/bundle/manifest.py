"""Bundle manifest utilities (v0.1).

This module is intentionally small and dependency-light to avoid import cycles.
It provides:
- sha256 hashing helpers
- manifest.json read/write
- a minimal manifest builder compatible with the v0.1 DevGuide
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(b: bytes) -> str:
    """Return hex-encoded sha256 for bytes."""
    if not isinstance(b, (bytes, bytearray)):
        raise TypeError(f"sha256_bytes: expected bytes, got {type(b).__name__}")
    return hashlib.sha256(bytes(b)).hexdigest()


def sha256_file(path: Path) -> str:
    """Return hex-encoded sha256 for a file on disk."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_utc_iso() -> str:
    # Stable, explicit UTC marker.
    # Example: 2025-12-16T00:00:00Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_manifest(path: Path) -> dict[str, Any]:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("manifest.json: expected JSON object")
    return obj


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    p.write_text(text, encoding="utf-8")


def build_manifest(
    *,
    name: str,
    version: str,
    sources: list[dict[str, Any]],
    tables: dict[str, dict[str, Any]],
    created_utc: str | None = None,
    schema_version: str = "upm-1.0",
    units: dict[str, Any] | None = None,
    nonbonded: dict[str, Any] | None = None,
    features: list[str] | None = None,
) -> dict[str, Any]:
    """Construct a minimal manifest.

    Manifest required fields are taken from the DevGuide section:
    - schema_version, name, version, created_utc
    - units, nonbonded, features
    - sources: list[{path, sha256}]
    - tables: map table_name -> {path, rows, sha256, dtypes}
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("manifest: name must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("manifest: version must be a non-empty string")

    if created_utc is None:
        created_utc = _now_utc_iso()

    # Provide stable defaults while remaining v0.1-minimal.
    if units is None:
        units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
    if nonbonded is None:
        nonbonded = {"style": "A-B", "form": "12-6", "mixing": "geometric"}
    if features is None:
        features = []

    if not isinstance(sources, list):
        raise TypeError("manifest: sources must be a list")
    if not isinstance(tables, dict):
        raise TypeError("manifest: tables must be a dict")

    return {
        "schema_version": schema_version,
        "name": name.strip(),
        "version": version.strip(),
        "created_utc": created_utc,
        "units": units,
        "nonbonded": nonbonded,
        "features": features,
        "sources": sources,
        "tables": tables,
    }