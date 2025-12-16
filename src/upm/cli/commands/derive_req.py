"""`upm derive-req` command (v0.1.1).

Derive canonical v0.1 Requirements JSON from a minimal toy structure JSON.

Toy structure schema:
{
  "atoms": [{"aid": 0, "atom_type": "c3"}, ...],
  "bonds": [{"a1": 0, "a2": 1}, ...]   # optional
}

Output (always full v0.1 schema keys):
{
  "atom_types": [...],
  "bond_types": [[...], ...],
  "angle_types": [[...], ...],
  "dihedral_types": []
}
"""

from __future__ import annotations

from pathlib import Path

import typer

from upm.io.requirements import requirements_from_structure_json, write_requirements_json


def register(app: typer.Typer) -> None:
    @app.command("derive-req")
    def derive_req(
        structure: str = typer.Option(..., "--structure", help="Path to toy structure JSON."),
        out: str = typer.Option(..., "--out", help="Output Requirements JSON path."),
    ) -> None:
        """Derive canonical v0.1 Requirements JSON from a toy `structure.json`."""
        req = requirements_from_structure_json(structure)
        out_path = Path(out)
        write_requirements_json(req, out_path)
        typer.echo(str(out_path))