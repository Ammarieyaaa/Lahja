"""The worked examples from docs/03-kappa.md, checked against our code and against scikit-learn."""

import math

import pytest
from sklearn.metrics import cohen_kappa_score

from lahja.stats import Confusion, cohen_kappa


def table(both_pass, human_pass_judge_fail, human_fail_judge_pass, both_fail):
    """Expand a 2x2 table into (human, judge) label lists."""
    cells = [
        (True, True, both_pass),
        (True, False, human_pass_judge_fail),
        (False, True, human_fail_judge_pass),
        (False, False, both_fail),
    ]
    human = [h for h, _, n in cells for _ in range(n)]
    judge = [j for _, j, n in cells for _ in range(n)]
    return human, judge


@pytest.mark.parametrize(
    "cells, p_o, p_e, kappa",
    [
        ((11, 2, 2, 5), 0.80, 0.545, 0.5604),  # example A: decent French judge
        ((18, 1, 1, 0), 0.90, 0.905, -0.0526),  # example B: 90% agreement, kappa < 0
        ((19, 0, 1, 0), 0.95, 0.95, 0.0),  # always-PASS judge on example B's data
        ((91, 4, 1, 4), 0.95, 0.878, 0.5902),  # paradox scenario 1: 95% prevalence
        ((48, 2, 10, 40), 0.88, 0.50, 0.76),  # paradox scenario 2: same judge, 50% prevalence
        ((64, 3, 3, 30), 0.94, 0.5578, 0.8643),  # pooled fr + ary hides the Darija problem
    ],
)
def test_worked_examples(cells, p_o, p_e, kappa):
    human, judge = table(*cells)
    result = cohen_kappa(human, judge)
    assert result.observed == pytest.approx(p_o, abs=1e-4)
    assert result.expected == pytest.approx(p_e, abs=1e-4)
    assert result.kappa == pytest.approx(kappa, abs=1e-4)
    assert result.kappa == pytest.approx(cohen_kappa_score(human, judge), abs=1e-12)


def test_matches_sklearn_on_multiclass():
    a = ["pass", "fail", "partial", "pass", "pass", "fail", "partial", "partial"]
    b = ["pass", "fail", "pass", "pass", "partial", "fail", "partial", "fail"]
    assert cohen_kappa(a, b).kappa == pytest.approx(cohen_kappa_score(a, b))


def test_undefined_when_both_raters_constant():
    result = cohen_kappa([True] * 5, [True] * 5)
    assert math.isnan(result.kappa) and result.observed == 1.0


def test_confusion_counts_cells():
    human, judge = table(11, 2, 2, 5)
    c = Confusion.of(human, judge)
    assert (c.both_pass, c.human_pass_judge_fail, c.human_fail_judge_pass, c.both_fail) == (11, 2, 2, 5)
    assert c.human_failures == 7


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        cohen_kappa([True], [True, False])
