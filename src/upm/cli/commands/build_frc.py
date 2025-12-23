"""`upm build-frc` command (v0.1.2).

Build a nonbonded-only MSI `.frc` from TermSet + ParameterSet JSON artifacts.
"""

from __future__ import annotations

from pathlib import Path

import typer

from upm.build.frc_builders import MissingTypesError, build_frc_nonbond_only
from upm.io.parameterset import read_parameterset_json
from upm.io.termset import read_termset_json


def register(app: typer.Typer) -> None:
    @app.command("build-frc")
    def build_frc(
        termset: str = typer.Option(..., "--termset", help="Path to termset.json (molsaic.termset.v0.1.2)."),
        parameters: str = typer.Option(
            ..., "--parameters", help="Path to parameterset.json (upm.parameterset.v0.1.2)."
        ),
        mode: str = typer.Option("nonbonded-only", "--mode", help="Build mode (v0.1.2 supports only nonbonded-only)."),
        out: str = typer.Option(..., "--out", help="Output .frc file path."),
    ) -> None:
        """Build an MSI `.frc` from TermSet + ParameterSet."""

        if mode != "nonbonded-only":
            raise typer.BadParameter("mode must be 'nonbonded-only'")

        ts = read_termset_json(termset)
        ps = read_parameterset_json(parameters)

        out_path = Path(out)
        try:
            build_frc_nonbond_only(ts, ps, out_path=out_path)
        except MissingTypesError as e:
            raise typer.BadParameter(str(e)) from e

        typer.echo(str(out_path))

