"""CLI command: upm diff — diff two parameter files."""
from __future__ import annotations

from pathlib import Path

import typer


def register(app: typer.Typer) -> None:
    @app.command("diff")
    def diff(
        left: Path = typer.Argument(..., help="First parameter file (.frc or .prm)"),
        right: Path = typer.Argument(..., help="Second parameter file (.frc or .prm)"),
    ) -> None:
        """Compare parameters between two force field files."""
        from upm.registry.diff import diff_tables

        tables_left = _load_tables(left)
        tables_right = _load_tables(right)

        result = diff_tables(tables_left, tables_right)
        typer.echo(result.summary())


def _load_tables(path: Path) -> dict:
    """Load tables from .frc or .prm file."""
    suffix = path.suffix.lower()
    if suffix == ".prm":
        from upm.codecs.charmm_prm import read_prm
        tables, _ = read_prm(path)
        return tables
    else:
        from upm.codecs.msi_frc import read_frc
        tables, _ = read_frc(path, validate=False)
        return tables
