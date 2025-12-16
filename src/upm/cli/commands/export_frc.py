"""`upm export-frc` command (v0.1.1).

Exports an MSI `.frc` from a package bundle.

Modes:
- full: export all supported rows present in the package tables
- minimal: load a Requirements JSON, resolve a minimal subset, export only required rows

Raw/unknown sections:
- preserved on import (stored in the bundle)
- omitted by default on export
- re-emitted only when `--include-raw` is set (deterministic encounter order)

Missing-term modes (minimal export only):
- default: hard error if any required term is missing (exit code 2)
- `--allow-missing`: export anyway, write `missing.json`, exit code 1 if any missing
- `--allow-missing --force`: export anyway, write `missing.json`, exit code 0
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
        include_raw: bool = typer.Option(
            False,
            "--include-raw",
            help="Include raw/unknown .frc sections preserved in the package bundle (deterministic encounter order).",
        ),
        allow_missing: bool = typer.Option(
            False,
            "--allow-missing",
            help="Allow missing required terms in minimal export; write missing report and continue.",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            help="Exit 0 even if missing terms exist (only meaningful with --allow-missing).",
        ),
        missing_report: Optional[str] = typer.Option(
            None,
            "--missing-report",
            help="Path to write missing.json (default: alongside --out as missing.json).",
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

        unknown_sections = bundle.raw.get("unknown_sections", [])
        if unknown_sections is None:
            unknown_sections = []

        out_path = Path(out)

        if mode == "full":
            if allow_missing or force:
                raise typer.BadParameter("--allow-missing/--force are only valid with --mode minimal")
            write_frc(
                out_path,
                tables=bundle.tables,
                unknown_sections=unknown_sections,
                include_raw=include_raw,
                mode="full",
            )
            typer.echo(str(out_path))
            return

        # minimal mode
        if not requirements:
            raise typer.BadParameter("--requirements is required for --mode minimal")

        if force and not allow_missing:
            raise typer.BadParameter("--force requires --allow-missing")

        req = read_requirements_json(requirements)

        if allow_missing:
            resolved, missing = resolve_minimal(bundle.tables, req, allow_missing=True)
        else:
            try:
                resolved = resolve_minimal(bundle.tables, req)
            except MissingTermsError as e:
                raise typer.BadParameter(str(e)) from e
            missing = None

        tables_subset: dict[str, object] = {"atom_types": resolved.atom_types}
        if resolved.bonds is not None:
            tables_subset["bonds"] = resolved.bonds
        if resolved.angles is not None:
            tables_subset["angles"] = resolved.angles

        write_frc(
            out_path,
            tables=tables_subset,
            unknown_sections=unknown_sections,
            include_raw=include_raw,
            mode="minimal",
        )
        typer.echo(str(out_path))

        # Missing report policy:
        # - Only written when --allow-missing is set
        # - Always written (even if all lists are empty)
        # - Deterministic schema/ordering
        if allow_missing and missing is not None:
            report_path = Path(missing_report) if missing_report else out_path.with_name("missing.json")
            report_obj = {
                "angle_types": [list(x) for x in missing.missing_angle_types],
                "atom_types": list(missing.missing_atom_types),
                "bond_types": [list(x) for x in missing.missing_bond_types],
                "dihedral_types": [list(x) for x in missing.missing_dihedral_types],
            }
            report_text = __import__("json").dumps(report_obj, indent=2, sort_keys=True) + "\n"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_text, encoding="utf-8")

            has_missing = bool(
                missing.missing_atom_types
                or missing.missing_bond_types
                or missing.missing_angle_types
                or missing.missing_dihedral_types
            )
            if has_missing and not force:
                raise typer.Exit(code=1)
        return