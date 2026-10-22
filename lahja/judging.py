"""Grade every response of a run with a judge. Cached per (response, rubric, judge model)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.db import Judgment, Response, Run
from lahja.judge import Judge, JudgeError


@dataclass
class JudgeSummary:
    created: int = 0
    cached: int = 0
    failed: int = 0


def judge_run(
    session: Session,
    run: Run,
    judge: Judge,
    *,
    max_trials: int | None = None,
    progress: Callable[[str], None] = lambda _: None,
) -> JudgeSummary:
    """Grade the run's responses, trial 0 of every case first, then trial 1, and so on.

    Trial-first order means a partial pass (e.g. stopped by a daily token quota) still covers
    every case once, so `compare` can run on it. `max_trials` limits grading to trials < N.
    """
    graded = set(
        session.scalars(
            select(Judgment.response_id)
            .join(Response)
            .where(Response.run_id == run.id, Judgment.rubric == judge.rubric, Judgment.judge_model == judge.name)
        )
    )
    summary = JudgeSummary()
    responses = sorted(run.responses, key=lambda r: (r.trial, r.case_id))
    if max_trials is not None:
        responses = [r for r in responses if r.trial < max_trials]
    for response in responses:
        if response.id in graded:
            summary.cached += 1
            continue
        case = response.case
        try:
            grade = judge.grade(question=case.input, reference=case.reference, answer=response.output)
        except JudgeError as e:
            summary.failed += 1
            progress(f"  ! {case.external_id} trial {response.trial}: {e}")
            continue
        session.add(
            Judgment(
                response_id=response.id, rubric=judge.rubric, judge_model=judge.name,
                passed=grade.passed, reason=grade.reason,
            )
        )
        session.commit()
        summary.created += 1
        progress(f"{case.external_id} t{response.trial}: {'PASS' if grade.passed else 'FAIL'}")
    return summary
