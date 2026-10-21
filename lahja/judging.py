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
    session: Session, run: Run, judge: Judge, *, progress: Callable[[str], None] = lambda _: None
) -> JudgeSummary:
    graded = set(
        session.scalars(
            select(Judgment.response_id)
            .join(Response)
            .where(Response.run_id == run.id, Judgment.rubric == judge.rubric, Judgment.judge_model == judge.name)
        )
    )
    summary = JudgeSummary()
    for response in run.responses:
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
