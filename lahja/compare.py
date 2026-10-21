"""Turn two judged runs into a verdict: per language, paired bootstrap, non-inferiority margin,
gated by how far the judge can be trusted on that language."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.calibrate import Trust
from lahja.db import Dataset, Judgment, Response, Run
from lahja.stats.bootstrap import Interval, paired_diff_ci

SMALL_N = 20  # below this, percentile bootstrap intervals are known to run too narrow


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    JUDGE_UNTRUSTED = "JUDGE_UNTRUSTED"


@dataclass(frozen=True)
class PairedCase:
    case_id: str
    language: str
    baseline: float  # current model's pass rate over this case's trials
    candidate: float


@dataclass
class GroupResult:
    group: str
    n_cases: int
    baseline_rate: float
    candidate_rate: float
    diff: Interval | None  # candidate - baseline
    statistical: Outcome  # what the numbers alone say
    outcome: Outcome  # after the judge-trust gate
    trust: Trust | None = None  # None for the pooled row
    notes: list[str] = field(default_factory=list)


@dataclass
class Comparison:
    overall: Outcome
    reasons: list[str]
    pooled: GroupResult
    by_language: list[GroupResult]
    margin: float
    confidence: float
    missing_cases: int = 0


def decide(diff: Interval, margin: float) -> Outcome:
    """Non-inferiority: is the candidate worse than the baseline by more than `margin`?"""
    if diff.low > -margin:
        return Outcome.PASS  # every plausible difference is within tolerance
    if diff.high < -margin:
        return Outcome.FAIL  # every plausible difference is a drop bigger than tolerated
    return Outcome.INCONCLUSIVE  # the data cannot tell


def _group(
    name: str, cases: list[PairedCase], trust: Trust | None, margin: float, confidence: float, seed: int
) -> GroupResult:
    n = len(cases)
    base = [c.baseline for c in cases]
    cand = [c.candidate for c in cases]
    rate = (lambda xs: sum(xs) / len(xs)) if n else (lambda xs: float("nan"))
    notes: list[str] = []
    if n < 2:
        diff, statistical = None, Outcome.INCONCLUSIVE
        notes.append(f"{n} case(s): too few to estimate anything")
    else:
        diff = paired_diff_ci(base, cand, confidence=confidence, seed=seed)
        statistical = decide(diff, margin)
        if n < SMALL_N:
            # Percentile bootstrap intervals run too narrow on small samples: don't let one decide.
            notes.append(
                f"only {n} cases (< {SMALL_N}): too few for a reliable interval; "
                f"the interval alone would say {statistical.value}"
            )
            statistical = Outcome.INCONCLUSIVE
    outcome = statistical
    if trust in (Trust.UNTRUSTED, Trust.INSUFFICIENT):
        outcome = Outcome.JUDGE_UNTRUSTED
        notes.append(f"judge trust is {trust.value} here; the numbers alone would say {statistical.value}")
    elif trust is Trust.CAUTION:
        notes.append("judge only moderately reliable here (CAUTION): read with care")
    return GroupResult(name, n, rate(base), rate(cand), diff, statistical, outcome, trust, notes)


def compare_cases(
    cases: list[PairedCase],
    trust: Callable[[str], Trust],
    *,
    margin: float,
    confidence: float = 0.95,
    seed: int = 0,
) -> Comparison:
    by_lang: dict[str, list[PairedCase]] = defaultdict(list)
    for c in cases:
        by_lang[c.language].append(c)
    languages = [_group(lang, by_lang[lang], trust(lang), margin, confidence, seed) for lang in sorted(by_lang)]
    pooled = _group("all", cases, None, margin, confidence, seed)

    # Overall rule: one confident, trusted regression in any language fails the switch.
    # PASS needs every language to pass; anything else is INCONCLUSIVE, with the reasons listed.
    reasons: list[str] = []
    if any(g.outcome is Outcome.FAIL for g in languages):
        overall = Outcome.FAIL
        reasons += [f"{g.group}: candidate is worse by more than {margin:.0%}" for g in languages if g.outcome is Outcome.FAIL]
    elif languages and all(g.outcome is Outcome.PASS for g in languages):
        overall = Outcome.PASS
    else:
        overall = Outcome.INCONCLUSIVE
        for g in languages:
            if g.outcome is Outcome.JUDGE_UNTRUSTED:
                reasons.append(f"{g.group}: judge not trusted ({g.trust.value}); label more answers or fix the rubric")
            elif g.outcome is Outcome.INCONCLUSIVE:
                reasons.append(f"{g.group}: interval straddles the -{margin:.0%} margin; more cases needed")
    if pooled.outcome is Outcome.PASS and overall is not Outcome.PASS:
        reasons.append("note: the pooled all-language number alone would have said PASS")
    return Comparison(overall, reasons, pooled, languages, margin, confidence)


def case_scores(session: Session, run: Run, rubric: str, judge_model: str) -> dict[int, float]:
    """Case id -> pass rate over that case's judged trials. Trials are averaged first: the case is the unit."""
    passes: dict[int, list[bool]] = defaultdict(list)
    rows = session.execute(
        select(Response.case_id, Judgment.passed)
        .join(Judgment, Judgment.response_id == Response.id)
        .where(Response.run_id == run.id, Judgment.rubric == rubric, Judgment.judge_model == judge_model)
    )
    for case_id, passed in rows:
        passes[case_id].append(passed)
    return {case_id: sum(v) / len(v) for case_id, v in passes.items()}


def compare_runs(
    session: Session,
    dataset: Dataset,
    baseline: Run,
    candidate: Run,
    *,
    rubric: str,
    judge_model: str,
    trust: Callable[[str], Trust],
    margin: float,
    seed: int = 0,
) -> Comparison:
    base = case_scores(session, baseline, rubric, judge_model)
    cand = case_scores(session, candidate, rubric, judge_model)
    # Only cases judged for BOTH models: the comparison must stay paired.
    paired = [
        PairedCase(c.external_id, c.language, base[c.id], cand[c.id])
        for c in dataset.cases
        if c.id in base and c.id in cand
    ]
    result = compare_cases(paired, trust, margin=margin, seed=seed)
    result.missing_cases = len(dataset.cases) - len(paired)
    return result
