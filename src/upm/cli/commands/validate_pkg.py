"""`upm validate` command (v0.1).

Validates a package bundle on disk:
- loads CSV tables via upm.bundle.io.load_package()
- validates canonical invariants via upm.core.validate.validate_tables()
- optionally validates manifest sha256 hashes
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from upm.bundle.io import load_package
from upm.core.validate import validate_tables


def _parse_package_ref(s: str) -> tuple[str, str]:
    """Parse 'name@version'."""
    if "@" not in s:
        raise ValueError("expected format name@version")
    name, version = s.split("@", 1)
    name = name.strip()
    version = version.strip()
    if not name or not version:
        raise ValueError("expected format name@version")
    return name, version


def _resolve_root(*, path: Optional[str], package: Optional[str]) -> Path:
    if bool(path) == bool(package):
        raise ValueError("specify exactly one of --path or --package")
    if path:
        return Path(path)
    name, version = _parse_package_ref(str(package))
    return Path("packages") / name / version


def register(app: typer.Typer) -> None:
    @app.command("validate")
    def validate(
        path: Optional[str] = typer.Option(None, "--path", help="Path to a package root (packages/<name>/<version>)."),
        package: Optional[str] = typer.Option(None, "--package", help="Package reference name@version."),
        validate_hashes: bool = typer.Option(False, "--validate-hashes", help="Recompute sha256 and compare to manifest."),
    ) -> None:
        """Validate a UPM package bundle."""
        try:
            root = _resolve_root(path=path, package=package)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e

        bundle = load_package(root, validate_hashes=validate_hashes)
        validate_tables(bundle.tables)

        typer.echo("OK")