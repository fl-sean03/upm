"""UPM Parameter Registry — discover, index, query, and diff parameter packages.

The registry discovers installed parameter data packages via Python entry points
(group: 'upm.data_packages') and provides a unified interface for searching
and comparing parameters across packages.

Usage:
    from upm.registry import discover_packages, PackageIndex

    packages = discover_packages()
    index = PackageIndex(packages)
    results = index.search_atom_type("Au")
"""

from upm.registry.discovery import discover_packages, discover_local_packages
from upm.registry.index import PackageIndex
from upm.registry.diff import diff_tables, ParameterDiff

__all__ = [
    "discover_packages",
    "discover_local_packages",
    "PackageIndex",
    "diff_tables",
    "ParameterDiff",
]
