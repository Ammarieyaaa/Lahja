"""Blind human labeling: you grade answers with the same rubric the judge uses, without seeing
the judge's verdict or which model wrote the answer. Your labels are the ground truth for kappa."""

from __future__ import annotations

import html
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


def format_item_markdown(response: Response, rubric: str, position: str) -> str:
    """The same item as Markdown/HTML for an editor preview.

    Terminals can't lay out right-to-left text, so Arabic comes out jumbled there; a Markdown
    preview applies the Unicode bidi algorithm. dir="auto" picks the direction per block.
    """
    case = response.case

    def block(title: str, text: str) -> str:
        body = html.escape(text).replace("\n", "<br>")
        return f'### {title}\n\n<div dir="auto" style="font-size: 1.25em; line-height: 1.7">{body}</div>\n'

    return "\n".join(
        [
            f"# [{position}] {rubric}",
            f"`{case.language}/{case.script}` · case `{case.external_id}` · type **p** / **f** / **s** / **q** in the terminal\n",
            block("Question", case.input),
            block("Reference (key facts)", case.reference),
            block("Answer", response.output),
        ]
    )


def label_interactively(
    session: Session,
    responses: list[Response],
    rubric: str,
    *,
    ask: Callable[[str], str],
    show: Callable[[str], None],
    view: Callable[[str], None] | None = None,
) -> LabelSummary:
    """`view`, if given, receives each item as Markdown (for a readable RTL preview); the
    terminal then only shows a one-line header."""
    summary = LabelSummary()
    for i, response in enumerate(responses, start=1):
        position = f"{i}/{len(responses)}"
        if view is None:
            show(format_item(response, rubric, position))
        else:
            view(format_item_markdown(response, rubric, position))
            show(f"[{position}] {response.case.language}/{response.case.script}  {response.case.external_id}")
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
