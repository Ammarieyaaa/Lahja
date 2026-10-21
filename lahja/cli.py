"""Command-line entry point: `lahja --help`."""

import typer

from lahja import __version__
from lahja.config import load_settings

app = typer.Typer(no_args_is_help=True, help="Lahja: regression testing for LLM features, per language.")


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def config() -> None:
    """Show which model plays which role."""
    s = load_settings()
    for role in ("current", "candidate", "judge"):
        typer.echo(f"{role:<10} {s.spec(role).key}")
    typer.echo(f"{'db':<10} {s.db_url}")
    typer.echo(f"{'trials':<10} {s.trials}   temperature {s.temperature}   margin {s.margin:.0%}")
