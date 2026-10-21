"""Per-language judge trust: kappa between your blind labels and the judge, one language at a time."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.db import Case, Dataset, HumanLabel, Judgment, Response
from lahja.stats import Confusion, KappaResult, cohen_kappa


class Trust(str, Enum):
    TRUSTED = "TRUSTED"
    CAUTION = "CAUTION"
    UNTRUSTED = "UNTRUSTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class TrustPolicy:
    min_labels: int = 20
    trusted_kappa: float = 0.6
    caution_kappa: float = 0.4
    missed_failure_warning: float = 0.3


@dataclass(frozen=True)
class LabelPair:
    language: str
    script: str
    human: bool
    judge: bool


@dataclass
class GroupCalibration:
    group: str  # "ary", or "ary/latn" for a script breakdown
    n: int
    kappa: KappaResult
    confusion: Confusion
    trust: Trust = Trust.INSUFFICIENT
    notes: list[str] = field(default_factory=list)

    @property
    def human_pass_rate(self) -> float:
        c = self.confusion
        return (c.both_pass + c.human_pass_judge_fail) / self.n if self.n else math.nan

    @property
    def judge_pass_rate(self) -> float:
        c = self.confusion
        return (c.both_pass + c.human_fail_judge_pass) / self.n if self.n else math.nan

    @property
    def missed_failure_rate(self) -> float:
        """Of the answers YOU failed, the share the judge passed. High = the judge hides regressions."""
        c = self.confusion
        return c.human_fail_judge_pass / c.human_failures if c.human_failures else math.nan


@dataclass
class Calibration:
    by_language: dict[str, GroupCalibration]
    by_script: dict[str, GroupCalibration]  # only for languages seen in more than one script

    def trust(self, language: str) -> Trust:
        group = self.by_language.get(language)
        return group.trust if group else Trust.INSUFFICIENT


def assess(group: str, human: list[bool], judge: list[bool], policy: TrustPolicy) -> GroupCalibration:
    n = len(human)
    if n == 0:
        empty = KappaResult(kappa=math.nan, observed=math.nan, expected=math.nan, n=0)
        return GroupCalibration(group, 0, empty, Confusion(0, 0, 0, 0), Trust.INSUFFICIENT, ["no labels yet"])
    result = GroupCalibration(group, n, cohen_kappa(human, judge), Confusion.of(human, judge))
    result.trust = _classify(result, policy)
    result.notes = _notes(result, policy)
    return result


def _classify(g: GroupCalibration, policy: TrustPolicy) -> Trust:
    k = g.kappa.kappa
    if g.n < policy.min_labels or math.isnan(k):
        return Trust.INSUFFICIENT
    if k < policy.caution_kappa:
        return Trust.UNTRUSTED
    if k < policy.trusted_kappa:
        return Trust.CAUTION
    return Trust.TRUSTED


def _notes(g: GroupCalibration, policy: TrustPolicy) -> list[str]:
    notes = []
    k = g.kappa.kappa
    if g.n < policy.min_labels:
        notes.append(f"only {g.n} labels; {policy.min_labels} needed for a trust decision")
    if math.isnan(k):
        notes.append("kappa undefined: every answer got the same verdict; label more varied answers")
    elif g.kappa.observed >= 0.85 and k < policy.caution_kappa:
        notes.append(
            f"high raw agreement ({g.kappa.observed:.0%}) but low kappa: your pass rate is skewed "
            f"({g.human_pass_rate:.0%}). Kappa paradox, see docs/03"
        )
    if g.confusion.human_failures and g.missed_failure_rate > policy.missed_failure_warning:
        notes.append(
            f"judge passed {g.confusion.human_fail_judge_pass} of {g.confusion.human_failures} answers you failed: "
            "it may hide regressions"
        )
    return notes


def calibrate(pairs: list[LabelPair], languages: Iterable[str], policy: TrustPolicy = TrustPolicy()) -> Calibration:
    """`languages`: every language in the dataset, so unlabeled ones show up as INSUFFICIENT, not missing."""
    by_lang: dict[str, list[LabelPair]] = defaultdict(list)
    for p in pairs:
        by_lang[p.language].append(p)
    by_language = {
        lang: assess(lang, [p.human for p in by_lang[lang]], [p.judge for p in by_lang[lang]], policy)
        for lang in sorted(set(languages) | by_lang.keys())
    }
    by_script: dict[str, GroupCalibration] = {}
    for lang, group in sorted(by_lang.items()):
        scripts = sorted({p.script for p in group})
        if len(scripts) > 1:
            for script in scripts:
                sub = [p for p in group if p.script == script]
                name = f"{lang}/{script}"
                by_script[name] = assess(name, [p.human for p in sub], [p.judge for p in sub], policy)
    return Calibration(by_language, by_script)


def load_label_pairs(session: Session, dataset: Dataset, rubric: str, judge_model: str) -> list[LabelPair]:
    """Every response that has both your label and the judge's grade for this rubric."""
    rows = session.execute(
        select(Case.language, Case.script, HumanLabel.passed, Judgment.passed)
        .select_from(HumanLabel)
        .join(Response, HumanLabel.response_id == Response.id)
        .join(Case, Response.case_id == Case.id)
        .join(Judgment, Judgment.response_id == Response.id)
        .where(
            Case.dataset_id == dataset.id,
            HumanLabel.rubric == rubric,
            Judgment.rubric == rubric,
            Judgment.judge_model == judge_model,
        )
    )
    return [LabelPair(lang, script, human, judge) for lang, script, human, judge in rows]


def calibrate_dataset(
    session: Session, dataset: Dataset, rubric: str, judge_model: str, policy: TrustPolicy = TrustPolicy()
) -> Calibration:
    pairs = load_label_pairs(session, dataset, rubric, judge_model)
    return calibrate(pairs, {c.language for c in dataset.cases}, policy)
