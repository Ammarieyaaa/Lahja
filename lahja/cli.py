"""Command-line entry point: `lahja --help`."""

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

import typer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lahja import __version__
from lahja.calibrate import GroupCalibration, calibrate_dataset
from lahja.config import ConfigError, Settings, load_settings
from lahja.dataset import DatasetError, coverage, get_dataset, import_dataset, read_cases
from lahja.db import Case, Dataset, make_session_factory
from lahja.judge import LLMJudge, load_rubric
from lahja.judging import judge_run
from lahja.labeling import label_interactively, pick_for_labeling
from lahja.runner import get_or_create_run, run_model
from lahja.targets import make_client

app = typer.Typer(no_args_is_help=True, help="Lahja: regression testing for LLM features, per language.")
dataset_app = typer.Typer(no_args_is_help=True, help="Validate, import and list eval datasets.")
app.add_typer(dataset_app, name="dataset")


class Target(str, Enum):
    current = "current"
    candidate = "candidate"


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


@app.command()
def run(
    dataset: str = typer.Option(..., help="Dataset name."),
    role: Target = typer.Option(..., help="Which model to run: current or candidate."),
    trials: int | None = typer.Option(None, help="Trials per case (default: LAHJA_TRIALS)."),
) -> None:
    """Generate answers for every case, N trials each. Safe to re-run: only missing answers are generated."""
    with _db() as (settings, session):
        try:
            ds = get_dataset(session, dataset)
            client = make_client(settings.spec(role.value), settings)
        except (DatasetError, ConfigError) as e:
            _fail(str(e))
        n = trials or settings.trials
        typer.echo(f"running {client.name} on {dataset!r}: {len(ds.cases)} cases x {n} trials")
        summary = run_model(session, ds, client, trials=n, temperature=settings.temperature, progress=typer.echo)
        typer.echo(f"done: {summary.created} new, {summary.cached} cached, {summary.failed} failed")
        if summary.failed:
            typer.echo("re-run the same command to retry the failed ones")


@app.command()
def judge(
    dataset: str = typer.Option(..., help="Dataset name."),
    role: Target = typer.Option(..., help="Whose answers to grade: current or candidate."),
    rubric: str = typer.Option("correctness", help="Rubric name (a file in lahja/rubrics/)."),
) -> None:
    """Grade every answer of a run with the judge model. Cached: re-running only grades new answers."""
    with _db() as (settings, session):
        try:
            ds = get_dataset(session, dataset)
            grader = LLMJudge(make_client(settings.judge, settings), load_rubric(rubric))
        except (DatasetError, ConfigError, ValueError) as e:
            _fail(str(e))
        run = get_or_create_run(session, ds, settings.spec(role.value).key)
        if not run.responses:
            _fail(f"no answers yet: run `lahja run --dataset {dataset} --role {role.value}` first")
        typer.echo(f"judging {run.model} with {grader.name} / {rubric}")
        summary = judge_run(session, run, grader, progress=typer.echo)
        typer.echo(f"done: {summary.created} new, {summary.cached} cached, {summary.failed} failed")


@app.command()
def label(
    dataset: str = typer.Option(..., help="Dataset name."),
    rubric: str = typer.Option("correctness", help="Rubric you are labeling against: read it first."),
    per_language: int = typer.Option(10, help="How many answers per language to label this session."),
) -> None:
    """Label answers yourself, blind (no model name, no judge verdict). Ground truth for kappa."""
    with _db() as (settings, session):
        try:
            ds = get_dataset(session, dataset)
            load_rubric(rubric)
        except (DatasetError, ValueError) as e:
            _fail(str(e))
        items = pick_for_labeling(session, ds, rubric, per_language, seed=settings.seed)
        if not items:
            _fail("nothing to label: run the models first, or everything is already labeled")
        typer.echo(f"{len(items)} answers to label against lahja/rubrics/{rubric}.md")
        summary = label_interactively(session, items, rubric, ask=lambda q: typer.prompt(q), show=typer.echo)
        typer.echo(f"saved {summary.labeled} labels ({summary.skipped} skipped)")


def _fmt(x: float, spec: str = ".2f") -> str:
    return "  -  " if x != x else format(x, spec)  # x != x is True only for nan


def _print_calibration(groups: dict[str, GroupCalibration]) -> None:
    typer.echo(f"{'group':<10}{'labels':>7}{'kappa':>8}{'agree':>8}{'you pass':>10}{'missed':>8}  trust")
    for g in groups.values():
        typer.echo(
            f"{g.group:<10}{g.n:>7}{_fmt(g.kappa.kappa):>8}{_fmt(g.kappa.observed, '.0%'):>8}"
            f"{_fmt(g.human_pass_rate, '.0%'):>10}{_fmt(g.missed_failure_rate, '.0%'):>8}  {g.trust.value}"
        )
        for note in g.notes:
            typer.echo(f"{'':<10}- {note}")


@app.command()
def calibrate(
    dataset: str = typer.Option(..., help="Dataset name."),
    rubric: str = typer.Option("correctness", help="Rubric name."),
) -> None:
    """How far to trust the judge, per language: kappa between your labels and the judge."""
    with _db() as (settings, session):
        try:
            ds = get_dataset(session, dataset)
        except DatasetError as e:
            _fail(str(e))
        result = calibrate_dataset(session, ds, rubric, settings.judge.key)
        typer.echo(f"judge {settings.judge.key} / rubric {rubric}")
        _print_calibration(result.by_language)
        if result.by_script:
            typer.echo("\nby script:")
            _print_calibration(result.by_script)
