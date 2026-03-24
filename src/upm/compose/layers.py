"""Parameter layers for composable force field construction.

A ParameterLayer holds a set of parameter tables (atom_types, bonds,
angles, etc.) that can be stacked with other layers. Later layers
override earlier ones for the same atom type / interaction key.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class ParameterLayer:
    """A single layer of force field parameters.

    Attributes:
        name: Human-readable layer name (e.g., "base-cvff-v1.5").
        tables: Dict of DataFrames (atom_types, bonds, angles, etc.)
        provenance: Optional metadata about where this layer came from.
    """

    name: str
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_bundle(cls, bundle_path: Path) -> "ParameterLayer":
        """Load a layer from a UPM bundle directory.

        Args:
            bundle_path: Path to bundle dir containing manifest.json.
        """
        import json
        from upm.bundle.io import load_package

        bundle = load_package(bundle_path)
        manifest = json.loads((bundle_path / "manifest.json").read_text())

        return cls(
            name=f"{manifest.get('name', 'unknown')}@{manifest.get('version', '?')}",
            tables=bundle.tables,
            provenance=manifest.get("provenance", {}),
        )

    @classmethod
    def from_frc(cls, path: Path, *, name: str | None = None) -> "ParameterLayer":
        """Load a layer directly from a .frc file."""
        from upm.codecs.msi_frc import read_frc

        tables, _ = read_frc(str(path), validate=False)
        return cls(
            name=name or path.stem,
            tables=tables,
            provenance={"source_file": path.name},
        )

    @classmethod
    def from_prm(cls, path: Path, *, name: str | None = None) -> "ParameterLayer":
        """Load a layer directly from a .prm file."""
        from upm.codecs.charmm_prm import read_prm

        tables, _ = read_prm(str(path))
        return cls(
            name=name or path.stem,
            tables=tables,
            provenance={"source_file": path.name},
        )

    @classmethod
    def from_dict(
        cls,
        overrides: dict[str, dict[str, dict[str, Any]]],
        *,
        name: str = "patch",
    ) -> "ParameterLayer":
        """Create a patch layer from a dict of parameter overrides.

        Args:
            overrides: Nested dict like:
                {"atom_types": {"Au": {"lj_b": 6085.0}, "Ag": {"lj_a": 90000.0}}}
            name: Layer name.

        Returns:
            ParameterLayer with single-row DataFrames for each override.
        """
        tables: dict[str, pd.DataFrame] = {}

        if "atom_types" in overrides:
            rows = []
            for atom_type, params in overrides["atom_types"].items():
                row = {"atom_type": atom_type}
                row.update(params)
                rows.append(row)
            if rows:
                tables["atom_types"] = pd.DataFrame(rows)

        if "bonds" in overrides:
            rows = []
            for key, params in overrides["bonds"].items():
                t1, t2 = key.split("-")
                row = {"t1": t1, "t2": t2}
                row.update(params)
                rows.append(row)
            if rows:
                tables["bonds"] = pd.DataFrame(rows)

        return cls(name=name, tables=tables, provenance={"type": "patch"})

    def atom_type_count(self) -> int:
        if "atom_types" in self.tables:
            return len(self.tables["atom_types"])
        return 0


def stack_layers(layers: list[ParameterLayer]) -> ParameterLayer:
    """Stack multiple parameter layers, later layers override earlier ones.

    For atom_types: if the same atom_type appears in multiple layers,
    the LAST layer's values win. New atom types from later layers are added.

    For bonds/angles/torsions: same key matching, last wins.

    Args:
        layers: List of layers in priority order (first = base, last = highest priority).

    Returns:
        A merged ParameterLayer with combined tables.
    """
    if not layers:
        raise ValueError("stack_layers: need at least one layer")

    if len(layers) == 1:
        return layers[0]

    # Collect all table names across all layers
    all_table_names: set[str] = set()
    for layer in layers:
        all_table_names.update(layer.tables.keys())

    merged_tables: dict[str, pd.DataFrame] = {}

    for table_name in sorted(all_table_names):
        # Collect DataFrames for this table from all layers that have it
        dfs = [layer.tables[table_name] for layer in layers if table_name in layer.tables]
        if not dfs:
            continue

        # Determine the key columns for deduplication
        key_cols = _get_key_columns(table_name)

        if key_cols:
            # Concatenate all, then drop duplicates keeping LAST occurrence
            combined = pd.concat(dfs, ignore_index=True)
            # Keep last occurrence of each key (later layers override)
            merged = combined.drop_duplicates(subset=key_cols, keep="last")
            merged = merged.sort_values(key_cols, kind="mergesort").reset_index(drop=True)
            merged_tables[table_name] = merged
        else:
            # No key columns — just concatenate (e.g., bond_increments)
            merged_tables[table_name] = pd.concat(dfs, ignore_index=True)

    # Build provenance chain
    layer_names = [layer.name for layer in layers]

    return ParameterLayer(
        name=" + ".join(layer_names),
        tables=merged_tables,
        provenance={"layers": layer_names, "type": "stacked"},
    )


def _get_key_columns(table_name: str) -> list[str]:
    """Return the key columns for deduplication per table type."""
    keys: dict[str, list[str]] = {
        "atom_types": ["atom_type"],
        "bonds": ["t1", "t2"],
        "angles": ["t1", "t2", "t3"],
        "torsions": ["t1", "t2", "t3", "t4"],
        "out_of_plane": ["t1", "t2", "t3", "t4"],
        "equivalences": ["atom_type"],
        "pair_overrides": ["t1", "t2"],
    }
    return keys.get(table_name, [])


__all__ = [
    "ParameterLayer",
    "stack_layers",
]
