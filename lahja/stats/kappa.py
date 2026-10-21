"""Cohen's kappa, written out. See docs/03-kappa.md for the derivation and worked examples."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class KappaResult:
    kappa: float  # nan when undefined (both raters used a single, identical category)
    observed: float  # p_o: raw agreement
    expected: float  # p_e: agreement expected by chance from each rater's own marginals
    n: int


def cohen_kappa(rater_a: Sequence[Hashable], rater_b: Sequence[Hashable]) -> KappaResult:
    if len(rater_a) != len(rater_b):
        raise ValueError("both raters must label the same items")
    n = len(rater_a)
    if n == 0:
        raise ValueError("no items")

    p_o = sum(a == b for a, b in zip(rater_a, rater_b)) / n

    # Chance agreement: for each category, P(a says it) * P(b says it), as if independent.
    count_a, count_b = Counter(rater_a), Counter(rater_b)
    p_e = sum((count_a[c] / n) * (count_b[c] / n) for c in count_a.keys() | count_b.keys())

    # p_e == 1 means both raters always gave the same single category: no room above chance.
    kappa = math.nan if math.isclose(p_e, 1.0) else (p_o - p_e) / (1 - p_e)
    return KappaResult(kappa=kappa, observed=p_o, expected=p_e, n=n)


@dataclass(frozen=True)
class Confusion:
    """2x2 table of human (rows) vs judge (columns) for binary PASS/FAIL."""

    both_pass: int
    human_pass_judge_fail: int
    human_fail_judge_pass: int  # the dangerous cell for regression testing: a missed failure
    both_fail: int

    @classmethod
    def of(cls, human: Sequence[bool], judge: Sequence[bool]) -> Confusion:
        pairs = Counter(zip(human, judge))
        return cls(pairs[(True, True)], pairs[(True, False)], pairs[(False, True)], pairs[(False, False)])

    @property
    def human_failures(self) -> int:
        return self.human_fail_judge_pass + self.both_fail
