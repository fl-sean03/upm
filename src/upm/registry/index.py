"""Package index for cross-package parameter search.

Provides a unified search interface across all discovered parameter packages.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from upm.registry.discovery import DiscoveredPackage


@dataclass(frozen=True)
class SearchResult:
    """A parameter found in a package.

    Attributes:
        package_name: Name of the package containing this parameter.
        package_version: Version of the package.
        table_name: Table where the parameter was found (e.g., 'atom_types').
        row: Dict of the matching row's data.
    """
    package_name: str
    package_version: str
    table_name: str
    row: dict[str, Any]


class PackageIndex:
    """Index across multiple parameter packages for unified search.

    Args:
        packages: List of discovered packages to index.
    """

    def __init__(self, packages: list[DiscoveredPackage] | None = None) -> None:
        self._packages = list(packages or [])
        self._loaded: dict[str, dict[str, Any]] = {}

    @property
    def packages(self) -> list[DiscoveredPackage]:
        return list(self._packages)

    def _load_tables(self, pkg: DiscoveredPackage) -> dict[str, Any]:
        """Load tables from a package (cached)."""
        key = f"{pkg.name}@{pkg.version}"
        if key in self._loaded:
            return self._loaded[key]

        tables: dict[str, Any] = {}
        manifest_path = pkg.path / "manifest.json"

        if manifest_path.exists():
            # UPM bundle format: load from CSV tables
            from upm.bundle.io import load_package
            try:
                bundle = load_package(pkg.path)
                tables = bundle.tables
            except Exception:
                pass
        else:
            # Try loading .frc or .prm files directly
            for frc_file in pkg.path.glob("*.frc"):
                from upm.codecs.msi_frc import read_frc
                try:
                    tables, _ = read_frc(frc_file)
                    break
                except Exception:
                    continue

        self._loaded[key] = tables
        return tables

    def search_atom_type(self, atom_type: str) -> list[SearchResult]:
        """Search for an atom type across all indexed packages.

        Args:
            atom_type: Atom type name to search for.

        Returns:
            List of SearchResult for each package containing this type.
        """
        results: list[SearchResult] = []
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            if "atom_types" not in tables:
                continue
            df = tables["atom_types"]
            matches = df[df["atom_type"] == atom_type]
            for _, row in matches.iterrows():
                results.append(SearchResult(
                    package_name=pkg.name,
                    package_version=pkg.version,
                    table_name="atom_types",
                    row=row.to_dict(),
                ))
        return results

    def search_bond(self, t1: str, t2: str) -> list[SearchResult]:
        """Search for a bond type across all indexed packages."""
        from upm.core.model import canonicalize_bond_key
        ct1, ct2 = canonicalize_bond_key(t1, t2)

        results: list[SearchResult] = []
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            if "bonds" not in tables:
                continue
            df = tables["bonds"]
            matches = df[(df["t1"] == ct1) & (df["t2"] == ct2)]
            for _, row in matches.iterrows():
                results.append(SearchResult(
                    package_name=pkg.name,
                    package_version=pkg.version,
                    table_name="bonds",
                    row=row.to_dict(),
                ))
        return results

    def list_atom_types(self) -> dict[str, list[str]]:
        """List all atom types per package.

        Returns:
            Dict mapping 'name@version' to list of atom type names.
        """
        result: dict[str, list[str]] = {}
        for pkg in self._packages:
            tables = self._load_tables(pkg)
            if "atom_types" not in tables:
                continue
            key = f"{pkg.name}@{pkg.version}"
            result[key] = sorted(tables["atom_types"]["atom_type"].tolist())
        return result


__all__ = [
    "SearchResult",
    "PackageIndex",
]
