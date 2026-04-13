"""Bundle save/load for UPM.

Two entry kinds:

- **Parameter entry** at `parameters/<name>/<version>/`:
    manifest.json, tables/*.csv, raw/source.{frc,prm}, raw/unknown_sections.json

- **Structure entry** at `structures/<class>/<model>/<version>/`:
    manifest.json, geometry/source.{car,mdf,pdb,...}, atoms.csv, (optional) topology.csv

Parameter entries: use `save_package` / `load_package` (backward-compatible).
Structure entries: use `save_structure` / `load_structure`.

All write paths produce schema `upm-2.1` manifests by default.
Load paths accept both `upm-1.0` and `upm-2.1`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from upm.core.tables import TABLE_COLUMN_ORDER, normalize_tables

from .manifest import build_manifest, read_manifest, sha256_file, write_manifest


@dataclass(frozen=True)
class PackageBundle:
    root: Path
    manifest: dict[str, Any]
    tables: dict[str, Any]   # pandas.DataFrame
    raw: dict[str, Any]      # {"source_text": str, "unknown_sections": [...]}


@dataclass(frozen=True)
class StructureBundle:
    root: Path
    manifest: dict[str, Any]
    atoms: Any               # pandas.DataFrame
    topology: Any | None     # pandas.DataFrame or None
    geometry_text: str       # raw source text (CAR/PDB/MDF/etc.)


def _write_text_exact(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def _write_json_stable(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_unknown_sections_ordered(obj: Any | None) -> list[dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        out: list[dict[str, Any]] = []
        for h in sorted(obj.keys()):
            body = obj[h]
            if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
                raise ValueError("unknown_sections: expected dict[str, list[str]] (legacy format)")
            out.append({"header": str(h), "body": list(body)})
        return out
    if isinstance(obj, list):
        out2: list[dict[str, Any]] = []
        for i, item in enumerate(obj):
            if not isinstance(item, dict):
                raise ValueError(f"unknown_sections[{i}]: expected object with 'header' and 'body'")
            if "header" not in item or "body" not in item:
                raise ValueError(f"unknown_sections[{i}]: missing 'header' or 'body'")
            if not isinstance(item["header"], str):
                raise ValueError(f"unknown_sections[{i}].header: expected str")
            body = item["body"]
            if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
                raise ValueError(f"unknown_sections[{i}].body: expected list[str]")
            out2.append({"header": item["header"], "body": list(body)})
        return out2
    raise TypeError(f"unknown_sections: expected list or dict, got {type(obj).__name__}")


def _find_raw_source(root: Path) -> tuple[Path, str]:
    """Return (path, format) of the raw source. Tries .frc, .prm in order."""
    for ext in ("frc", "prm"):
        p = root / "raw" / f"source.{ext}"
        if p.is_file():
            return p, ext
    raise FileNotFoundError(f"raw/source.{{frc,prm}} not found under {root}")


def save_package(
    root: Path,
    *,
    name: str,
    version: str,
    tables: dict[str, Any],
    source_text: str,
    source_format: str = "frc",               # "frc" or "prm"
    unknown_sections: Any | None = None,
    units: dict[str, Any] | None = None,
    nonbonded: dict[str, Any] | None = None,
    features: list[str] | None = None,
    # v2.1 additions (optional, forwarded to build_manifest):
    supersedes: str | None = None,
    deprecated: bool = False,
    deprecation_reason: str | None = None,
    parent_ff: str | None = None,
    overrides: list[dict[str, Any]] | None = None,
    renames: dict[str, str] | None = None,
    breaking: bool = False,
    partial_roundtrip: bool = False,
    provenance: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a parameter bundle. Returns the written manifest dict."""
    if source_format not in ("frc", "prm"):
        raise ValueError(f"source_format must be 'frc' or 'prm', got {source_format!r}")

    root = Path(root)
    (root / "tables").mkdir(parents=True, exist_ok=True)
    (root / "raw").mkdir(parents=True, exist_ok=True)

    unknown_sections_ordered = _coerce_unknown_sections_ordered(unknown_sections)

    source_path_rel = Path("raw") / f"source.{source_format}"
    source_path = root / source_path_rel
    _write_text_exact(source_path, source_text)

    unknown_path_rel = Path("raw") / "unknown_sections.json"
    unknown_path = root / unknown_path_rel
    _write_json_stable(unknown_path, unknown_sections_ordered)

    norm_tables = normalize_tables(tables)

    import pandas as pd

    table_entries: dict[str, dict[str, Any]] = {}
    for table_name, df in norm_tables.items():
        if df is None:
            continue
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"tables['{table_name}']: expected pandas.DataFrame, got {type(df).__name__}")
        out_path_rel = Path("tables") / f"{table_name}.csv"
        out_path = root / out_path_rel
        df_to_write = (
            df.loc[:, TABLE_COLUMN_ORDER[table_name]] if table_name in TABLE_COLUMN_ORDER else df
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df_to_write.to_csv(out_path, index=False, lineterminator="\n", float_format="%.17g")
        table_entries[table_name] = {
            "path": str(out_path_rel).replace("\\", "/"),
            "rows": int(len(df_to_write)),
            "sha256": sha256_file(out_path),
            "dtypes": {c: str(df_to_write[c].dtype) for c in df_to_write.columns},
        }

    sources = [
        {"path": str(source_path_rel).replace("\\", "/"), "sha256": sha256_file(source_path)},
        {"path": str(unknown_path_rel).replace("\\", "/"), "sha256": sha256_file(unknown_path)},
    ]

    manifest = build_manifest(
        name=name,
        version=version,
        sources=sources,
        tables=table_entries,
        units=units,
        nonbonded=nonbonded,
        features=features,
        entry_type="parameters",
        supersedes=supersedes,
        deprecated=deprecated,
        deprecation_reason=deprecation_reason,
        parent_ff=parent_ff,
        overrides=overrides,
        renames=renames,
        breaking=breaking,
        partial_roundtrip=partial_roundtrip,
        provenance=provenance,
        extra=extra,
    )
    write_manifest(root / "manifest.json", manifest)
    return manifest


def load_package(root: Path, *, validate_hashes: bool = False) -> PackageBundle:
    """Load a parameter bundle. Supports both upm-1.0 and upm-2.1 manifests."""
    root = Path(root)
    manifest_path = root / "manifest.json"
    manifest = read_manifest(manifest_path)

    source_path, _source_fmt = _find_raw_source(root)
    source_text = source_path.read_text(encoding="utf-8")

    unknown_path = root / "raw" / "unknown_sections.json"
    unknown_sections_obj = _read_json(unknown_path) if unknown_path.is_file() else []
    unknown_sections_ordered = _coerce_unknown_sections_ordered(unknown_sections_obj)

    import pandas as pd

    tables: dict[str, pd.DataFrame] = {}
    manifest_tables = manifest.get("tables", {})
    if not isinstance(manifest_tables, dict):
        raise ValueError("manifest.json: tables must be an object")

    for table_name, meta in manifest_tables.items():
        if not isinstance(meta, dict):
            raise ValueError(f"manifest.json: tables.{table_name} must be an object")
        rel = meta.get("path")
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"manifest.json: tables.{table_name}.path must be a non-empty string")
        csv_path = root / rel
        tables[table_name] = pd.read_csv(csv_path)

    tables_norm = normalize_tables(tables)

    if validate_hashes:
        sources = manifest.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("manifest.json: sources must be an array")
        for item in sources:
            if not isinstance(item, dict):
                raise ValueError("manifest.json: sources[*] must be an object")
            rel = item.get("path")
            expected = item.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                raise ValueError("manifest.json: sources[*] must have string path and sha256")
            actual = sha256_file(root / rel)
            if actual != expected:
                raise ValueError(f"sha256 mismatch for {rel}: expected {expected}, got {actual}")

        for table_name, meta in manifest_tables.items():
            rel = meta.get("path")
            expected = meta.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                raise ValueError(f"manifest.json: tables.{table_name} must have string path and sha256")
            actual = sha256_file(root / rel)
            if actual != expected:
                raise ValueError(f"sha256 mismatch for {rel}: expected {expected}, got {actual}")

    return PackageBundle(
        root=root,
        manifest=manifest,
        tables=tables_norm,
        raw={"source_text": source_text, "unknown_sections": unknown_sections_ordered},
    )


# ---------------------------------------------------------------------------
# Structure bundle I/O (v2.1+)

_STRUCTURE_GEOMETRY_EXTS = ("car", "mdf", "pdb", "cif", "xyz", "data")


def _find_structure_geometry(root: Path) -> tuple[Path, str]:
    for ext in _STRUCTURE_GEOMETRY_EXTS:
        p = root / "geometry" / f"source.{ext}"
        if p.is_file():
            return p, ext
    raise FileNotFoundError(f"geometry/source.<ext> not found under {root}")


def save_structure(
    root: Path,
    *,
    name: str,
    version: str,
    atoms_df: Any,
    geometry_text: str,
    geometry_format: str,                      # "car", "mdf", "pdb", ...
    atom_type_family: str,
    parameterized_with: list[dict[str, str]],
    topology_df: Any | None = None,
    charges_source: str = "structure",
    lock_to_original: bool = False,
    validated_with: list[dict[str, str]] | None = None,
    supersedes: str | None = None,
    deprecated: bool = False,
    deprecation_reason: str | None = None,
    provenance: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a structure entry. atoms_df columns: id, element, ff_type, charge, x, y, z."""
    if geometry_format not in _STRUCTURE_GEOMETRY_EXTS:
        raise ValueError(f"geometry_format must be one of {_STRUCTURE_GEOMETRY_EXTS}, got {geometry_format!r}")

    root = Path(root)
    (root / "geometry").mkdir(parents=True, exist_ok=True)

    import pandas as pd
    if not isinstance(atoms_df, pd.DataFrame):
        raise TypeError(f"atoms_df: expected pandas.DataFrame, got {type(atoms_df).__name__}")

    required_cols = ["id", "element", "ff_type", "charge", "x", "y", "z"]
    missing_cols = [c for c in required_cols if c not in atoms_df.columns]
    if missing_cols:
        raise ValueError(f"atoms_df missing required columns: {missing_cols}")

    geometry_path_rel = Path("geometry") / f"source.{geometry_format}"
    geometry_path = root / geometry_path_rel
    _write_text_exact(geometry_path, geometry_text)

    atoms_path_rel = Path("atoms.csv")
    atoms_path = root / atoms_path_rel
    atoms_df.loc[:, required_cols].to_csv(
        atoms_path, index=False, lineterminator="\n", float_format="%.17g"
    )

    geometry_meta = {
        "path": str(geometry_path_rel).replace("\\", "/"),
        "format": geometry_format,
        "sha256": sha256_file(geometry_path),
    }
    atoms_meta = {
        "path": str(atoms_path_rel).replace("\\", "/"),
        "rows": int(len(atoms_df)),
        "sha256": sha256_file(atoms_path),
    }

    topology_meta: dict[str, Any] | None = None
    if topology_df is not None:
        if not isinstance(topology_df, pd.DataFrame):
            raise TypeError(f"topology_df: expected pandas.DataFrame, got {type(topology_df).__name__}")
        topo_rel = Path("topology.csv")
        topo_path = root / topo_rel
        topology_df.to_csv(topo_path, index=False, lineterminator="\n", float_format="%.17g")
        topology_meta = {
            "path": str(topo_rel).replace("\\", "/"),
            "rows": int(len(topology_df)),
            "sha256": sha256_file(topo_path),
        }

    sources = [
        {"path": geometry_meta["path"], "sha256": geometry_meta["sha256"]},
        {"path": atoms_meta["path"], "sha256": atoms_meta["sha256"]},
    ]
    if topology_meta is not None:
        sources.append({"path": topology_meta["path"], "sha256": topology_meta["sha256"]})

    manifest = build_manifest(
        name=name,
        version=version,
        sources=sources,
        tables={},  # structure entries don't have FF tables
        entry_type="structure",
        supersedes=supersedes,
        deprecated=deprecated,
        deprecation_reason=deprecation_reason,
        provenance=provenance,
        atom_type_family=atom_type_family,
        parameterized_with=parameterized_with,
        charges_source=charges_source,
        lock_to_original=lock_to_original,
        validated_with=validated_with,
        geometry=geometry_meta,
        atoms_csv=atoms_meta,
        topology_csv=topology_meta,
        extra=extra,
    )
    write_manifest(root / "manifest.json", manifest)
    return manifest


def load_structure(root: Path, *, validate_hashes: bool = False) -> StructureBundle:
    root = Path(root)
    manifest = read_manifest(root / "manifest.json")
    if manifest.get("type") != "structure":
        raise ValueError(f"not a structure entry: type={manifest.get('type')!r}")

    geometry_path, _fmt = _find_structure_geometry(root)
    geometry_text = geometry_path.read_text(encoding="utf-8")

    import pandas as pd
    atoms_meta = manifest.get("atoms_csv", {})
    atoms_rel = atoms_meta.get("path", "atoms.csv") if isinstance(atoms_meta, dict) else "atoms.csv"
    atoms_df = pd.read_csv(root / atoms_rel)

    topology_df = None
    topo_meta = manifest.get("topology_csv")
    if isinstance(topo_meta, dict) and topo_meta.get("path"):
        topology_df = pd.read_csv(root / topo_meta["path"])

    if validate_hashes:
        for meta_block in (manifest.get("geometry"), atoms_meta, topo_meta):
            if not isinstance(meta_block, dict):
                continue
            rel = meta_block.get("path")
            expected = meta_block.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                continue
            actual = sha256_file(root / rel)
            if actual != expected:
                raise ValueError(f"sha256 mismatch for {rel}: expected {expected}, got {actual}")

    return StructureBundle(
        root=root,
        manifest=manifest,
        atoms=atoms_df,
        topology=topology_df,
        geometry_text=geometry_text,
    )
