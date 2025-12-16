"""`upm import-frc` command (v0.1).

Imports an MSI `.frc` into a canonical UPM package bundle:
- parses supported sections into canonical tables
- preserves unsupported sections as raw text blobs
- writes a CSV bundle under `packages/<name>/<version>/` (or `--out-dir`)
"""

from __future__ import annotations

from pathlib import Path

import typer

from upm.bundle.io import save_package
from upm.codecs.msi_frc import read_frc


def register(app: typer.Typer) -> None:
    @app.command("import-frc")
    def import_frc(
        frc_path: str = typer.Argument(..., help="Path to an MSI .frc file."),
        name: str = typer.Option(..., "--name", help="Package name (folder under packages/)."),
        version: str = typer.Option(..., "--version", help="Package version (folder under packages/<name>/)."),
        out_dir: str = typer.Option(
            "packages",
            "--out-dir",
            help="Output directory for the created UPM package bundle.",
        ),
    ) -> None:
        """Import an MSI `.frc` into a canonical UPM package."""
        frc_p = Path(frc_path)
        source_text = frc_p.read_text(encoding="utf-8")

        tables, unknown_sections = read_frc(frc_p)

        root = Path(out_dir) / name / version
        save_package(
            root,
            name=name,
            version=version,
            tables=tables,
            source_text=source_text,
            unknown_sections=unknown_sections,
        )

        typer.echo(str(root))
