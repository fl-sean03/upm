"""Bundle save/load (CSV) for UPM v0.1.1.

A bundle is a folder rooted at `packages/<name>/<version>/` containing:
- manifest.json
- tables/*.csv
- raw/source.frc
- raw/unknown_sections.json

Unknown/raw sections persistence (v0.1.1):
- Canonical on-disk format is an *ordered list* of objects:
  `[{ "header": str, "body": [str, ...] }, ...]`
  This preserves encounter order and supports duplicate section headers.
- Legacy format (v0.1.0): `{ "<header>": ["<body line>", ...], ... }`
  is still accepted on load and is converted deterministically by sorted header.

This module intentionally avoids any dependency on codecs/CLI to prevent cycles.
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
    tables: dict[str, "Any"]  # pandas.DataFrame; kept Any to avoid importing pandas at import time
    raw: dict[str, Any]  # {"source_text": str, "unknown_sections": list[{"header": str, "body": list[str]}]}


def _write_text_exact(path: Path, text: str) -> None:
    # newline="" prevents Python from translating newlines on write
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def _write_json_stable(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _table_csv_path(root: Path, table_name: str) -> Path:
    return root / "tables" / f"{table_name}.csv"


def _coerce_unknown_sections_ordered(obj: Any | None) -> list[dict[str, Any]]:
    """Coerce unknown/raw sections into canonical ordered-list format.

    Accepts:
      - None -> []
      - canonical list format:
          [{"header": str, "body": [str, ...]}, ...]
      - legacy dict format:
          {"<header>": ["<body line>", ...], ...}
        (converted deterministically by sorted header)

    Raises:
        TypeError/ValueError for invalid shapes.
    """
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
            header = item["header"]
            body = item["body"]
            if not isinstance(header, str):
                raise ValueError(f"unknown_sections[{i}].header: expected str")
            if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
                raise ValueError(f"unknown_sections[{i}].body: expected list[str]")
            out2.append({"header": header, "body": list(body)})
        return out2
    raise TypeError(f"unknown_sections: expected list or dict, got {type(obj).__name__}")


def save_package(
    root: Path,
    *,
    name: str,
    version: str,
    tables: dict[str, "Any"],  # pandas.DataFrame
    source_text: str,
    unknown_sections: Any | None = None,
    units: dict[str, Any] | None = None,
    nonbonded: dict[str, Any] | None = None,
    features: list[str] | None = None,
) -> dict[str, Any]:
    """Save a package bundle to disk and return the manifest dict."""
    root = Path(root)
    tables_dir = root / "tables"
    raw_dir = root / "raw"
    tables_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    unknown_sections_ordered = _coerce_unknown_sections_ordered(unknown_sections)

    # ---- write raw blobs (exact) ----
    source_path_rel = Path("raw") / "source.frc"
    source_path = root / source_path_rel
    _write_text_exact(source_path, source_text)

    unknown_path_rel = Path("raw") / "unknown_sections.json"
    unknown_path = root / unknown_path_rel
    _write_json_stable(unknown_path, unknown_sections_ordered)

    # ---- normalize tables then write CSVs ----
    # Normalize for deterministic column ordering + key canonicalization.
    norm_tables = normalize_tables(tables)

    import pandas as pd  # local import to keep module import-light

    table_entries: dict[str, dict[str, Any]] = {}
    for table_name, df in norm_tables.items():
        if df is None:
            continue
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"tables['{table_name}']: expected pandas.DataFrame, got {type(df).__name__}")

        out_path_rel = Path("tables") / f"{table_name}.csv"
        out_path = root / out_path_rel

        # Enforce canonical column order for known tables.
        if table_name in TABLE_COLUMN_ORDER:
            df_to_write = df.loc[:, TABLE_COLUMN_ORDER[table_name]]
        else:
            df_to_write = df

        out_path.parent.mkdir(parents=True, exist_ok=True)
        df_to_write.to_csv(
            out_path,
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )

        table_entries[table_name] = {
            "path": str(out_path_rel).replace("\\", "/"),
            "rows": int(len(df_to_write)),
            "sha256": sha256_file(out_path),
            "dtypes": {c: str(df_to_write[c].dtype) for c in df_to_write.columns},
        }

    # ---- sources list + manifest ----
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
    )

    write_manifest(root / "manifest.json", manifest)
    return manifest


def load_package(root: Path, *, validate_hashes: bool = False) -> PackageBundle:
    """Load a bundle from disk.

    If validate_hashes is True, recompute sha256 for sources and tables and raise
    ValueError on any mismatch.
    """
    root = Path(root)
    manifest_path = root / "manifest.json"
    manifest = read_manifest(manifest_path)

    # ---- read raw blobs ----
    source_path = root / "raw" / "source.frc"
    unknown_path = root / "raw" / "unknown_sections.json"

    source_text = source_path.read_text(encoding="utf-8")
    unknown_sections_obj = _read_json(unknown_path)
    unknown_sections_ordered = _coerce_unknown_sections_ordered(unknown_sections_obj)

    # ---- read tables from manifest ----
    import pandas as pd  # local import

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
        df = pd.read_csv(csv_path)
        tables[table_name] = df

    # Normalize after read to enforce canonical dtypes and key ordering.
    tables_norm = normalize_tables(tables)

    # ---- optional hash validation ----
    if validate_hashes:
        # Validate sources
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

        # Validate tables
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