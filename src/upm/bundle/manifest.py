"""Bundle manifest utilities.

Schema versions:
- upm-1.0: original (name, version, created_utc, units, nonbonded, features, sources, tables)
- upm-2.1: adds entry-type, lineage (supersedes, parent_ff), conflict declarations
  (overrides, renames, breaking, partial_roundtrip), deprecation, structure-entry
  fields (atom_type_family, parameterized_with, charges_source, lock_to_original,
  validated_with, geometry, atoms_csv), and arbitrary `provenance` block.

Loaders accept both. Writers default to upm-2.1.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = "upm-2.1"


def sha256_bytes(b: bytes) -> str:
    if not isinstance(b, (bytes, bytearray)):
        raise TypeError(f"sha256_bytes: expected bytes, got {type(b).__name__}")
    return hashlib.sha256(bytes(b)).hexdigest()


def sha256_file(path: Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_utc_iso() -> str:
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
    schema_version: str = CURRENT_SCHEMA_VERSION,
    # Parameter-entry fields (kept at top level for backward compat)
    units: dict[str, Any] | None = None,
    nonbonded: dict[str, Any] | None = None,
    features: list[str] | None = None,
    # v2.1 additions (all optional):
    entry_type: str = "parameters",           # "parameters" | "structure"
    supersedes: str | None = None,
    deprecated: bool = False,
    deprecation_reason: str | None = None,
    parent_ff: str | None = None,
    overrides: list[dict[str, Any]] | None = None,
    renames: dict[str, str] | None = None,
    breaking: bool = False,
    partial_roundtrip: bool = False,
    provenance: dict[str, Any] | None = None,
    # Structure-entry specific (only used when entry_type == "structure"):
    atom_type_family: str | None = None,
    parameterized_with: list[dict[str, str]] | None = None,
    charges_source: str = "structure",
    lock_to_original: bool = False,
    validated_with: list[dict[str, str]] | None = None,
    geometry: dict[str, Any] | None = None,
    atoms_csv: dict[str, Any] | None = None,
    topology_csv: dict[str, Any] | None = None,
    # Catch-all for future extensions:
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a manifest. Returns a dict ready for write_manifest()."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("manifest: name must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("manifest: version must be a non-empty string")
    if entry_type not in ("parameters", "structure"):
        raise ValueError(f"manifest: entry_type must be 'parameters' or 'structure', got {entry_type!r}")
    if entry_type == "structure":
        if not atom_type_family:
            raise ValueError("manifest: structure entries require atom_type_family")
        if not parameterized_with or not isinstance(parameterized_with, list):
            raise ValueError("manifest: structure entries require parameterized_with (non-empty list)")
        for i, ref in enumerate(parameterized_with):
            if not isinstance(ref, dict) or "name" not in ref or "version" not in ref:
                raise ValueError(f"manifest: parameterized_with[{i}] must have 'name' and 'version'")

    if created_utc is None:
        created_utc = _now_utc_iso()

    if units is None:
        units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
    if nonbonded is None:
        nonbonded = {"style": "A-B", "form": "12-6", "mixing": "geometric"}
    if features is None:
        features = []
    if provenance is None:
        provenance = {}

    if not isinstance(sources, list):
        raise TypeError("manifest: sources must be a list")
    if not isinstance(tables, dict):
        raise TypeError("manifest: tables must be a dict")

    m: dict[str, Any] = {
        "schema_version": schema_version,
        "name": name.strip(),
        "version": version.strip(),
        "type": entry_type,
        "created_utc": created_utc,
        "sources": sources,
        "tables": tables,
        "provenance": provenance,
        "deprecated": bool(deprecated),
    }

    # Parameter-entry fields
    if entry_type == "parameters":
        m["units"] = units
        m["nonbonded"] = nonbonded
        m["features"] = features
        if parent_ff is not None:
            m["parent_ff"] = parent_ff
        if overrides:
            m["overrides"] = overrides
        if renames:
            m["renames"] = renames
        if breaking:
            m["breaking"] = True
        if partial_roundtrip:
            m["partial_roundtrip"] = True

    # Structure-entry fields
    if entry_type == "structure":
        m["atom_type_family"] = atom_type_family
        m["parameterized_with"] = parameterized_with
        m["charges_source"] = charges_source
        if lock_to_original:
            m["lock_to_original"] = True
        if validated_with:
            m["validated_with"] = validated_with
        if geometry is not None:
            m["geometry"] = geometry
        if atoms_csv is not None:
            m["atoms_csv"] = atoms_csv
        if topology_csv is not None:
            m["topology_csv"] = topology_csv

    # Lineage (common)
    if supersedes is not None:
        m["supersedes"] = supersedes
    if deprecation_reason is not None:
        m["deprecation_reason"] = deprecation_reason

    # Extension escape hatch
    if extra:
        for k, v in extra.items():
            if k not in m:
                m[k] = v

    return m
