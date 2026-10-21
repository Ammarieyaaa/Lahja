"""Command-line entry point: `lahja --help`."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lahja import __version__
from lahja.config import Settings, load_settings
from lahja.dataset import DatasetError, coverage, import_dataset, read_cases
from lahja.db import Case, Dataset, make_session_factory

app = typer.Typer(no_args_is_help=True, help="Lahja: regression testing for LLM features, per language.")
dataset_app = typer.Typer(no_args_is_help=True, help="Validate, import and list eval datasets.")
app.add_typer(dataset_app, name="dataset")


@contextmanager
def _db() -> Iterator[tuple[Settings, Session]]:
    settings = load_settings()
    with make_session_factory(settings.db_url)() as session:
        yield settings, session


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


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


@dataset_app.command("validate")
def dataset_validate(path: Path) -> None:
    """Check a JSONL file and show per-language coverage."""
    try:
        cases = read_cases(path)
    except DatasetError as e:
        _fail(str(e))
    typer.echo(f"{len(cases)} valid cases")
    for (language, script), n in sorted(coverage(cases).items()):
        typer.echo(f"  {language}/{script}: {n}")


@dataset_app.command("import")
def dataset_import(
    path: Path,
    name: str = typer.Option(..., help="Dataset name, e.g. support-v1."),
    system_prompt: Path | None = typer.Option(None, help="Text file with the feature's system prompt."),
) -> None:
    """Import a JSONL file as a new, immutable dataset."""
    prompt = system_prompt.read_text(encoding="utf-8") if system_prompt else ""
    with _db() as (_, session):
        try:
            dataset = import_dataset(session, name, read_cases(path), prompt)
        except DatasetError as e:
            _fail(str(e))
        typer.echo(f"imported {len(dataset.cases)} cases as {name!r}")


@dataset_app.command("list")
def dataset_list() -> None:
    """List imported datasets."""
    with _db() as (_, session):
        rows = session.execute(
            select(Dataset.name, func.count(Case.id)).join(Case).group_by(Dataset.id).order_by(Dataset.id)
        ).all()
        for name, n in rows:
            typer.echo(f"{name}  ({n} cases)")
