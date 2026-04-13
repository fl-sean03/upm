"""Package index for cross-package parameter search.

Provides unified search across all discovered parameter packages plus
key-level inverted indexes for conflict detection and coverage analysis.

Indexes built lazily on first access; cached thereafter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from upm.registry.discovery import DiscoveredPackage

_NUMERIC_RTOL_DEFAULT = 1e-6


@dataclass(frozen=True)
class SearchResult:
    package_name: str
    package_version: str
    table_name: str
    row: dict[str, Any]


@dataclass(frozen=True)
class KeyOccurrence:
    """A (package, row) where a key appears. Used as value in inverted indexes."""
    package_name: str
    package_version: str
    row: dict[str, Any]


@dataclass(frozen=True)
class Conflict:
    """Two packages define the same key with different numeric values."""
    scope: str                          # "atom_types" | "bonds" | "angles" | "torsions"
    key: tuple                          # normalized key tuple
    occurrences: tuple[KeyOccurrence, ...]
    disagreements: tuple[str, ...]      # column names that differ


@dataclass
class CoverageCell:
    parameters: list[str] = field(default_factory=list)   # "name@version"
    structures: list[str] = field(default_factory=list)


class PackageIndex:
    """Index across multiple discovered packages.

    Backward-compat surface: search_atom_type, search_bond, list_atom_types.
    New v2.1 surface: atom_type_index, bond_index, angle_index, torsion_index,
    material_coverage(), conflicts().
    """

    def __init__(self, packages: list[DiscoveredPackage] | None = None) -> None:
        self._packages = list(packages or [])
        # Package-level caches
        self._loaded_tables: dict[str, dict[str, Any]] = {}
        self._loaded_manifests: dict[str, dict[str, Any]] = {}
        # Lazy inverted indexes
        self._atom_index: dict[str, list[KeyOccurrence]] | None = None
        self._bond_index: dict[tuple[str, str], list[KeyOccurrence]] | None = None
        self._angle_index: dict[tuple[str, str, str], list[KeyOccurrence]] | None = None
        self._torsion_index: dict[tuple[str, str, str, str], list[KeyOccurrence]] | None = None

    @property
    def packages(self) -> list[DiscoveredPackage]:
        return list(self._packages)

    def invalidate(self) -> None:
        """Drop all caches — useful after new entries are added on disk."""
        self._loaded_tables.clear()
        self._loaded_manifests.clear()
        self._atom_index = None
        self._bond_index = None
        self._angle_index = None
        self._torsion_index = None

    # --- manifest + table loading ---

    def _pkg_key(self, pkg: DiscoveredPackage) -> str:
        return f"{pkg.name}@{pkg.version}"

    def _load_manifest(self, pkg: DiscoveredPackage) -> dict[str, Any]:
        key = self._pkg_key(pkg)
        if key in self._loaded_manifests:
            return self._loaded_manifests[key]
        manifest_path = pkg.path / "manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            import json
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        self._loaded_manifests[key] = manifest
        return manifest

    def _load_tables(self, pkg: DiscoveredPackage) -> dict[str, Any]:
        key = self._pkg_key(pkg)
        if key in self._loaded_tables:
            return self._loaded_tables[key]

        tables: dict[str, Any] = {}
        manifest_path = pkg.path / "manifest.json"

        if manifest_path.exists():
            manifest = self._load_manifest(pkg)
            if manifest.get("type") == "structure":
                # structure entries don't carry FF tables
                self._loaded_tables[key] = tables
                return tables
            from upm.bundle.io import load_package
            try:
                bundle = load_package(pkg.path)
                tables = bundle.tables
            except Exception:
                pass
        else:
            for frc_file in pkg.path.glob("*.frc"):
                from upm.codecs.msi_frc import read_frc
                try:
                    tables, _ = read_frc(frc_file)
                    break
                except Exception:
                    continue

        self._loaded_tables[key] = tables
        return tables

    # --- backward-compat search API ---

    def search_atom_type(self, atom_type: str) -> list[SearchResult]:
        out: list[SearchResult] = []
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            df = tables.get("atom_types")
            if df is None or len(df) == 0:
                continue
            matches = df[df["atom_type"] == atom_type]
            for _, row in matches.iterrows():
                out.append(SearchResult(pkg.name, pkg.version, "atom_types", row.to_dict()))
        return out

    def search_bond(self, t1: str, t2: str) -> list[SearchResult]:
        from upm.core.model import canonicalize_bond_key
        ct1, ct2 = canonicalize_bond_key(t1, t2)
        out: list[SearchResult] = []
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            df = tables.get("bonds")
            if df is None or len(df) == 0:
                continue
            matches = df[(df["t1"] == ct1) & (df["t2"] == ct2)]
            for _, row in matches.iterrows():
                out.append(SearchResult(pkg.name, pkg.version, "bonds", row.to_dict()))
        return out

    def list_atom_types(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            if "atom_types" not in tables:
                continue
            result[self._pkg_key(pkg)] = sorted(tables["atom_types"]["atom_type"].tolist())
        return result

    # --- v2.1 key-level inverted indexes ---

    @property
    def atom_type_index(self) -> dict[str, list[KeyOccurrence]]:
        if self._atom_index is None:
            self._build_key_indexes()
        assert self._atom_index is not None
        return self._atom_index

    @property
    def bond_index(self) -> dict[tuple[str, str], list[KeyOccurrence]]:
        if self._bond_index is None:
            self._build_key_indexes()
        assert self._bond_index is not None
        return self._bond_index

    @property
    def angle_index(self) -> dict[tuple[str, str, str], list[KeyOccurrence]]:
        if self._angle_index is None:
            self._build_key_indexes()
        assert self._angle_index is not None
        return self._angle_index

    @property
    def torsion_index(self) -> dict[tuple[str, str, str, str], list[KeyOccurrence]]:
        if self._torsion_index is None:
            self._build_key_indexes()
        assert self._torsion_index is not None
        return self._torsion_index

    def _build_key_indexes(self) -> None:
        atom_idx: dict[str, list[KeyOccurrence]] = {}
        bond_idx: dict[tuple[str, str], list[KeyOccurrence]] = {}
        angle_idx: dict[tuple[str, str, str], list[KeyOccurrence]] = {}
        torsion_idx: dict[tuple[str, str, str, str], list[KeyOccurrence]] = {}

        for pkg in self._packages:
            tables = self._load_tables(pkg)
            if not tables:
                continue

            df = tables.get("atom_types")
            if df is not None:
                for _, row in df.iterrows():
                    key = str(row["atom_type"])
                    atom_idx.setdefault(key, []).append(
                        KeyOccurrence(pkg.name, pkg.version, row.to_dict())
                    )

            df = tables.get("bonds")
            if df is not None:
                for _, row in df.iterrows():
                    key = (str(row["t1"]), str(row["t2"]))
                    bond_idx.setdefault(key, []).append(
                        KeyOccurrence(pkg.name, pkg.version, row.to_dict())
                    )

            df = tables.get("angles")
            if df is not None:
                for _, row in df.iterrows():
                    key = (str(row["t1"]), str(row["t2"]), str(row["t3"]))
                    angle_idx.setdefault(key, []).append(
                        KeyOccurrence(pkg.name, pkg.version, row.to_dict())
                    )

            df = tables.get("torsions")
            if df is not None:
                for _, row in df.iterrows():
                    key = (str(row["t1"]), str(row["t2"]), str(row["t3"]), str(row["t4"]))
                    torsion_idx.setdefault(key, []).append(
                        KeyOccurrence(pkg.name, pkg.version, row.to_dict())
                    )

        self._atom_index = atom_idx
        self._bond_index = bond_idx
        self._angle_index = angle_idx
        self._torsion_index = torsion_idx

    # --- material coverage ---

    def material_coverage(self) -> dict[str, CoverageCell]:
        """Map material name -> CoverageCell{parameters, structures}.

        Materials taken from manifest.provenance.materials for each live entry.
        """
        cells: dict[str, CoverageCell] = {}
        for pkg in self._packages:
            manifest = self._load_manifest(pkg)
            provenance = manifest.get("provenance", {}) if isinstance(manifest, dict) else {}
            materials = provenance.get("materials", []) if isinstance(provenance, dict) else []
            entry_type = manifest.get("type", "parameters")
            pkg_ref = self._pkg_key(pkg)
            for mat in materials:
                cell = cells.setdefault(mat, CoverageCell())
                if entry_type == "structure":
                    cell.structures.append(pkg_ref)
                else:
                    cell.parameters.append(pkg_ref)
        return cells

    # --- cross-package conflicts ---

    def conflicts(self, *, numeric_rtol: float = _NUMERIC_RTOL_DEFAULT) -> list[Conflict]:
        """Return cross-package key collisions where values disagree.

        Two packages defining the same key with identical numeric values are
        NOT conflicts — they're harmless duplicates. Only return collisions
        that show real disagreement.

        Intra-family version evolution (v1.0 vs v1.1 of the same name) is
        NOT a conflict by design: pass only the "latest" versions to the
        PackageIndex if you want that behavior.
        """
        conflicts: list[Conflict] = []

        for scope, index, numeric_cols in (
            ("atom_types", self.atom_type_index, ("mass_amu", "lj_a", "lj_b")),
            ("bonds", self.bond_index, ("k", "r0")),
            ("angles", self.angle_index, ("k", "theta0_deg")),
            ("torsions", self.torsion_index, ("kphi", "n", "phi0")),
        ):
            for key, occurrences in index.items():
                # Dedup by (name, version) — only care about cross-family collisions
                families = {(o.package_name, o.package_version) for o in occurrences}
                if len(families) < 2:
                    continue
                disagreements = _find_disagreements(occurrences, numeric_cols, numeric_rtol)
                if disagreements:
                    conflicts.append(Conflict(
                        scope=scope,
                        key=(key,) if isinstance(key, str) else key,
                        occurrences=tuple(occurrences),
                        disagreements=tuple(disagreements),
                    ))
        return conflicts


def _find_disagreements(
    occurrences: list[KeyOccurrence],
    numeric_cols: tuple[str, ...],
    rtol: float,
) -> list[str]:
    disagreements: list[str] = []
    for col in numeric_cols:
        values = [o.row.get(col) for o in occurrences]
        if any(v is None for v in values):
            continue
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (TypeError, ValueError):
                numeric_values = None
                break
        if numeric_values is None:
            # non-numeric — fall back to equality
            if len(set(str(v) for v in values)) > 1:
                disagreements.append(col)
            continue
        # all NaN counts as agreement
        if all(math.isnan(v) for v in numeric_values):
            continue
        ref = numeric_values[0]
        if math.isnan(ref):
            # mixed NaN/non-NaN is a disagreement
            if any(not math.isnan(v) for v in numeric_values):
                disagreements.append(col)
            continue
        for v in numeric_values[1:]:
            if math.isnan(v):
                disagreements.append(col)
                break
            if abs(v - ref) > rtol * max(abs(v), abs(ref), 1.0):
                disagreements.append(col)
                break
    return disagreements


__all__ = [
    "SearchResult",
    "KeyOccurrence",
    "Conflict",
    "CoverageCell",
    "PackageIndex",
]
