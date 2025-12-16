"""UPM CLI entrypoint.

This is a minimal Typer application skeleton. Commands are placeholders until
later subtasks implement real functionality.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="upm",
    add_completion=False,
    no_args_is_help=True,
    help="UPM (Unified Parameter Model) command line interface.",
)


@app.callback()
def _callback() -> None:
    """UPM CLI."""
    # Intentionally empty; subcommands are registered below.
    return


@app.command("version")
def version() -> None:
    """Print the installed UPM version."""
    from upm import __version__

    typer.echo(__version__)


def _register_commands() -> None:
    """Register CLI subcommands.

    Importing these modules must remain lightweight so `upm --help` is fast.
    """
    from upm.cli.commands import export_frc as export_frc_cmd
    from upm.cli.commands import import_frc as import_frc_cmd
    from upm.cli.commands import validate_pkg as validate_pkg_cmd

    import_frc_cmd.register(app)
    validate_pkg_cmd.register(app)
    export_frc_cmd.register(app)


_register_commands()
