"""Package discovery for UPM data packages.

Discovers parameter packages installed via pip (entry points) or
available locally (bundle directories).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredPackage:
    """A discovered parameter package.

    Attributes:
        name: Package name (e.g., 'heinz-iff').
        version: Package version string.
        path: Path to the package data directory.
        source: How it was discovered ('entry_point' or 'local').
    """
    name: str
    version: str
    path: Path
    source: str


def discover_packages() -> list[DiscoveredPackage]:
    """Discover all installed UPM data packages via entry points.

    Looks for entry points in group 'upm.data_packages'. Each entry
    point should resolve to a callable that returns a Path to the
    package data directory.

    Returns:
        List of discovered packages, sorted by (name, version).
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return []

    packages: list[DiscoveredPackage] = []

    try:
        eps = entry_points(group="upm.data_packages")
    except TypeError:
        # Python 3.9 compatibility
        all_eps = entry_points()
        eps = all_eps.get("upm.data_packages", [])

    for ep in eps:
        try:
            func = ep.load()
            data_dir = func()
            if isinstance(data_dir, (str, Path)):
                data_path = Path(data_dir)
                if data_path.is_dir():
                    packages.append(DiscoveredPackage(
                        name=ep.name,
                        version=_read_version(data_path),
                        path=data_path,
                        source="entry_point",
                    ))
        except Exception:
            continue

    return sorted(packages, key=lambda p: (p.name, p.version))


def discover_local_packages(root: Path) -> list[DiscoveredPackage]:
    """Discover UPM packages stored locally in a directory tree.

    Scans `root` for subdirectories containing `manifest.json` files
    (the UPM bundle format).

    Args:
        root: Root directory to scan.

    Returns:
        List of discovered packages, sorted by (name, version).
    """
    packages: list[DiscoveredPackage] = []

    if not root.is_dir():
        return packages

    # Look for manifest.json files in the expected layout:
    # root/<name>/<version>/manifest.json
    for manifest_path in root.rglob("manifest.json"):
        try:
            import json
            with open(manifest_path) as f:
                manifest = json.load(f)
            name = manifest.get("name", manifest_path.parent.parent.name)
            version = manifest.get("version", manifest_path.parent.name)
            packages.append(DiscoveredPackage(
                name=name,
                version=version,
                path=manifest_path.parent,
                source="local",
            ))
        except Exception:
            continue

    return sorted(packages, key=lambda p: (p.name, p.version))


def _read_version(data_dir: Path) -> str:
    """Read version from a package data directory."""
    # Try manifest.json first
    manifest = data_dir / "manifest.json"
    if manifest.exists():
        try:
            import json
            with open(manifest) as f:
                data = json.load(f)
            return str(data.get("version", "unknown"))
        except Exception:
            pass

    # Try __init__.py
    init_file = data_dir / "__init__.py"
    if init_file.exists():
        try:
            text = init_file.read_text()
            for line in text.splitlines():
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip("\"'")
        except Exception:
            pass

    return "unknown"


__all__ = [
    "DiscoveredPackage",
    "discover_packages",
    "discover_local_packages",
]
