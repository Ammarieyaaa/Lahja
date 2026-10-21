"""Blind human labeling: you grade answers with the same rubric the judge uses, without seeing
the judge's verdict or which model wrote the answer. Your labels are the ground truth for kappa."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.db import Dataset, HumanLabel, Response, Run


@dataclass
class LabelSummary:
    labeled: int = 0
    skipped: int = 0


def pick_for_labeling(session: Session, dataset: Dataset, rubric: str, per_language: int, seed: int) -> list[Response]:
    """Up to `per_language` unlabeled answers per language, drawn from ALL runs (both models).

    - Both models: the weaker candidate fails more often, so the sample contains failures,
      which kappa needs (see the kappa paradox in docs/03). We never select on the judge's
      verdict: that would bias the agreement we are trying to measure.
    - Trial 0 only: other trials of the same case are near-duplicates and add little information.
    """
    labeled = set(session.scalars(select(HumanLabel.response_id).where(HumanLabel.rubric == rubric)))
    responses = session.scalars(
        select(Response).join(Run).where(Run.dataset_id == dataset.id, Response.trial == 0).order_by(Response.id)
    )
    by_language: dict[str, list[Response]] = defaultdict(list)
    for r in responses:
        if r.id not in labeled:
            by_language[r.case.language].append(r)
    rng = random.Random(seed)
    picked: list[Response] = []
    for language in sorted(by_language):
        pool = by_language[language]
        rng.shuffle(pool)
        picked += pool[:per_language]
    rng.shuffle(picked)  # interleave so the order gives away nothing about language or model
    return picked


def format_item(response: Response, rubric: str, position: str) -> str:
    case = response.case
    rule = "─" * 60
    return (
        f"\n{rule}\n[{position}]  rubric: {rubric}   language: {case.language}/{case.script}   case: {case.external_id}\n"
        f"{rule}\nQUESTION:\n{case.input}\n\nREFERENCE (key facts):\n{case.reference}\n\nANSWER:\n{response.output}\n"
    )


def label_interactively(
    session: Session,
    responses: list[Response],
    rubric: str,
    *,
    ask: Callable[[str], str],
    show: Callable[[str], None],
) -> LabelSummary:
    summary = LabelSummary()
    for i, response in enumerate(responses, start=1):
        show(format_item(response, rubric, f"{i}/{len(responses)}"))
        while True:
            choice = ask("[p]ass  [f]ail  [s]kip  [q]uit").strip().lower()[:1]
            if choice in ("p", "f", "s", "q"):
                break
        if choice == "q":
            break
        if choice == "s":
            summary.skipped += 1
            continue
        session.add(HumanLabel(response_id=response.id, rubric=rubric, passed=choice == "p"))
        session.commit()
        summary.labeled += 1
    return summary
