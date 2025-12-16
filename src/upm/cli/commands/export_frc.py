"""`upm export-frc` command (v0.1).

Exports an MSI `.frc` from a package bundle.

Modes:
- full: export all supported rows present in the package tables
- minimal: load a Requirements JSON, resolve a minimal subset, export only required rows

Unknown/unsupported sections are preserved and appended to the output for lossless
roundtrips (deterministic order).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from upm.bundle.io import load_package
from upm.codecs.msi_frc import write_frc
from upm.core.resolve import MissingTermsError, resolve_minimal
from upm.io.requirements import read_requirements_json


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
    @app.command("export-frc")
    def export_frc(
        out: str = typer.Option(..., "--out", help="Output .frc file path."),
        mode: str = typer.Option("full", "--mode", help="Export mode: full|minimal."),
        path: Optional[str] = typer.Option(None, "--path", help="Path to a package root (packages/<name>/<version>)."),
        package: Optional[str] = typer.Option(None, "--package", help="Package reference name@version."),
        requirements: Optional[str] = typer.Option(
            None,
            "--requirements",
            help="Requirements JSON path (required for --mode minimal).",
        ),
    ) -> None:
        """Export an MSI `.frc` from a UPM package bundle."""
        if mode not in {"full", "minimal"}:
            raise typer.BadParameter("mode must be 'full' or 'minimal'")

        try:
            root = _resolve_root(path=path, package=package)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e

        bundle = load_package(root)

        unknown_sections = bundle.raw.get("unknown_sections", {})
        if unknown_sections is None:
            unknown_sections = {}

        out_path = Path(out)

        if mode == "full":
            write_frc(out_path, tables=bundle.tables, unknown_sections=unknown_sections, mode="full")
            typer.echo(str(out_path))
            return

        # minimal mode
        if not requirements:
            raise typer.BadParameter("--requirements is required for --mode minimal")

        req = read_requirements_json(requirements)
        try:
            resolved = resolve_minimal(bundle.tables, req)
        except MissingTermsError as e:
            raise typer.BadParameter(str(e)) from e

        tables_subset: dict[str, object] = {"atom_types": resolved.atom_types}
        if resolved.bonds is not None:
            tables_subset["bonds"] = resolved.bonds
        if resolved.angles is not None:
            tables_subset["angles"] = resolved.angles

        write_frc(out_path, tables=tables_subset, unknown_sections=unknown_sections, mode="minimal")
        typer.echo(str(out_path))