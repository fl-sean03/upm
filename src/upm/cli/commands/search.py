"""CLI command: upm search — search for atom types across packages."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer


def register(app: typer.Typer) -> None:
    @app.command("search")
    def search(
        atom_type: str = typer.Argument(..., help="Atom type to search for"),
        packages_dir: Optional[Path] = typer.Option(
            None, "--packages", "-p", help="Local packages directory to search",
        ),
    ) -> None:
        """Search for an atom type across parameter packages."""
        from upm.registry import discover_packages, discover_local_packages, PackageIndex

        pkgs = discover_packages()
        if packages_dir and packages_dir.is_dir():
            pkgs.extend(discover_local_packages(packages_dir))

        if not pkgs:
            typer.echo("No parameter packages found.")
            raise typer.Exit(1)

        index = PackageIndex(pkgs)
        results = index.search_atom_type(atom_type)

        if not results:
            typer.echo(f"Atom type '{atom_type}' not found in any package.")
            raise typer.Exit(1)

        for r in results:
            typer.echo(f"\n[{r.package_name}@{r.package_version}]")
            for k, v in sorted(r.row.items()):
                typer.echo(f"  {k}: {v}")
