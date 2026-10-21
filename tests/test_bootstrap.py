"""The worked examples from docs/04-bootstrap.md."""

import math

import numpy as np
import pytest

from lahja.stats import cohen_kappa
from lahja.stats.bootstrap import bootstrap_ci, paired_diff_ci
from tests.test_kappa import table


def worked_example():
    """150 cases: 110 both pass, 23 both fail, 10 only current passes, 7 only candidate passes."""
    current = np.array([1] * 110 + [0] * 23 + [1] * 10 + [0] * 7, dtype=float)
    candidate = np.array([1] * 110 + [0] * 23 + [0] * 10 + [1] * 7, dtype=float)
    return current, candidate


def test_worked_example_rates_and_spread():
    current, candidate = worked_example()
    assert (current.mean(), candidate.mean()) == pytest.approx((0.80, 0.78))
    d = candidate - current
    assert d.std(ddof=1) == pytest.approx(0.337, abs=1e-3)
    assert d.std(ddof=1) / math.sqrt(150) == pytest.approx(0.0275, abs=1e-4)


def test_bootstrap_reproduces_the_analytic_ci():
    current, candidate = worked_example()
    ci = paired_diff_ci(current, candidate)
    d = candidate - current
    half = 1.96 * d.std(ddof=1) / math.sqrt(len(d))
    assert ci.estimate == pytest.approx(-0.02)
    assert ci.low == pytest.approx(d.mean() - half, abs=0.005)  # about -0.074
    assert ci.high == pytest.approx(d.mean() + half, abs=0.005)  # about +0.034


def test_pairing_narrows_the_interval():
    current, candidate = worked_example()
    paired = paired_diff_ci(current, candidate)
    rng = np.random.default_rng(0)
    unpaired = paired_diff_ci(current, rng.permutation(candidate))  # destroy the pairing
    assert (unpaired.high - unpaired.low) > 1.5 * (paired.high - paired.low)


def test_identical_models_give_a_zero_width_interval():
    scores = np.array([1, 0, 1, 1, 0.5])
    ci = paired_diff_ci(scores, scores)
    assert (ci.estimate, ci.low, ci.high) == (0, 0, 0)


def test_large_real_drop_excludes_zero():
    current = np.ones(200)
    candidate = np.array([1.0] * 140 + [0.0] * 60)  # 30-point drop
    ci = paired_diff_ci(current, candidate)
    assert ci.high < -0.2


def test_seeded_and_deterministic():
    current, candidate = worked_example()
    assert paired_diff_ci(current, candidate, seed=3) == paired_diff_ci(current, candidate, seed=3)


def test_coverage_is_close_to_nominal():
    """Simulate many datasets with a known true difference; ~95% of CIs should contain it."""
    rng = np.random.default_rng(42)
    # current passes 80%; on a random 15% of cases the candidate instead passes with p=0.5.
    # True mean difference = 0.15 * (0.5 - 0.8) = -0.045.
    true_diff, hits, trials = 0.15 * (0.5 - 0.80), 0, 300
    for i in range(trials):
        current = (rng.random(150) < 0.80).astype(float)
        redo = rng.random(150) < 0.15
        candidate = np.where(redo, rng.random(150) < 0.5, current).astype(float)
        ci = paired_diff_ci(current, candidate, n_resamples=2000, seed=i)
        hits += ci.contains(true_diff)
    assert 0.90 <= hits / trials <= 0.99


@pytest.mark.parametrize(
    "cells, low, high",
    [((11, 2, 2, 5), 0.13, 0.89), ((22, 4, 4, 10), 0.24, 0.80), ((46, 2, 2, 30), 0.78, 0.98)],
)
def test_kappa_interval_matches_doc_table(cells, low, high):
    human, judge = map(np.array, table(*cells))
    ci = bootstrap_ci(lambda i: cohen_kappa(human[i], judge[i]).kappa, len(human))
    assert (ci.low, ci.high) == pytest.approx((low, high), abs=0.01)


def test_mostly_undefined_statistic_gives_nan_interval():
    ci = bootstrap_ci(lambda i: math.nan, 10)
    assert math.isnan(ci.low) and math.isnan(ci.high)
