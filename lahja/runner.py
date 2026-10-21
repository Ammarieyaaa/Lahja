"""Run every case of a dataset through one model, N trials each.

Resumable by construction: a Response is unique per (run, case, trial), and a Run is unique per
(dataset, model). Re-running only calls the model for missing cells, so a crash, a rate limit,
or raising --trials from 3 to 5 costs nothing already paid for.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.db import Dataset, Response, Run
from lahja.targets import Message, ModelCallError, ModelClient


@dataclass
class RunSummary:
    run_id: int
    created: int = 0
    cached: int = 0
    failed: int = 0


def build_messages(system_prompt: str, user_input: str) -> list[Message]:
    messages: list[Message] = [{"role": "system", "content": system_prompt}] if system_prompt else []
    return messages + [{"role": "user", "content": user_input}]


def find_run(session: Session, dataset: Dataset, model: str) -> Run | None:
    return session.scalar(select(Run).where(Run.dataset_id == dataset.id, Run.model == model))


def get_or_create_run(session: Session, dataset: Dataset, model: str) -> Run:
    run = find_run(session, dataset, model)
    if run is None:
        run = Run(dataset=dataset, model=model)
        session.add(run)
        session.commit()
    return run


def run_model(
    session: Session,
    dataset: Dataset,
    client: ModelClient,
    *,
    trials: int,
    temperature: float,
    progress: Callable[[str], None] = lambda _: None,
) -> RunSummary:
    run = get_or_create_run(session, dataset, client.name)
    done = {(c, t) for c, t in session.execute(select(Response.case_id, Response.trial).where(Response.run_id == run.id))}
    summary = RunSummary(run_id=run.id)
    for i, case in enumerate(dataset.cases, start=1):
        messages = build_messages(dataset.system_prompt, case.input)
        for trial in range(trials):
            if (case.id, trial) in done:
                summary.cached += 1
                continue
            try:
                output = client.complete(messages, temperature=temperature)
            except ModelCallError as e:
                summary.failed += 1
                progress(f"  ! {case.external_id} trial {trial}: {e}")
                continue
            session.add(Response(run_id=run.id, case_id=case.id, trial=trial, output=output))
            session.commit()  # commit per response so an interruption loses at most one call
            summary.created += 1
        progress(f"[{i}/{len(dataset.cases)}] {case.external_id}")
    return summary
