"""CLI command: upm import-prm — import CHARMM .prm file."""
from __future__ import annotations

from pathlib import Path

import typer


def register(app: typer.Typer) -> None:
    @app.command("import-prm")
    def import_prm(
        prm_path: Path = typer.Argument(..., help="Path to .prm file"),
    ) -> None:
        """Import a CHARMM .prm file and display summary."""
        from upm.codecs.charmm_prm import read_prm

        tables, raw = read_prm(prm_path)

        typer.echo(f"Parsed: {prm_path.name}")
        for name, df in sorted(tables.items()):
            typer.echo(f"  {name}: {len(df)} entries")
        for section in raw:
            typer.echo(f"  [raw] {section['header']}: {len(section['body'])} lines")
