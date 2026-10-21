"""Percentile bootstrap, written out. See docs/04-bootstrap.md for why it works."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Interval:
    estimate: float  # the statistic on the real sample
    low: float
    high: float
    confidence: float

    def contains(self, x: float) -> bool:
        return self.low <= x <= self.high


def _percentile_bounds(samples: np.ndarray, confidence: float) -> tuple[float, float]:
    alpha = 1 - confidence
    low, high = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)


def paired_diff_ci(
    baseline: np.ndarray | list[float],
    candidate: np.ndarray | list[float],
    *,
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Interval:
    """CI for mean(candidate - baseline), resampling CASES with replacement.

    baseline[i] and candidate[i] are the two models' scores on the same case i (each score is
    the pass rate over that case's trials). Keeping the pair together is what makes it paired:
    a hard case is hard for both models, and that shared difficulty cancels in the difference.
    """
    base = np.asarray(baseline, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if base.ndim != 1 or base.shape != cand.shape:
        raise ValueError("baseline and candidate must be 1-D and the same length (one score per case)")
    n = len(base)
    if n < 2:
        raise ValueError("need at least 2 cases to bootstrap")

    diffs = cand - base
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples)
    chunk = max(1, 2_000_000 // n)  # bound memory: at most ~2M indices in flight
    for start in range(0, n_resamples, chunk):
        size = min(chunk, n_resamples - start)
        idx = rng.integers(0, n, size=(size, n))  # each row = one resampled dataset of n cases
        means[start : start + size] = diffs[idx].mean(axis=1)
    low, high = _percentile_bounds(means, confidence)
    return Interval(float(diffs.mean()), low, high, confidence)


def bootstrap_ci(
    statistic: Callable[[np.ndarray], float],
    n: int,
    *,
    n_resamples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Interval:
    """Generic percentile bootstrap. `statistic(idx)` computes the statistic on the items at `idx`.

    Resamples where the statistic is undefined (nan, e.g. kappa when a resample contains no
    failures) are dropped; if more than half are undefined the interval is reported as nan.
    """
    if n < 2:
        raise ValueError("need at least 2 items to bootstrap")
    rng = np.random.default_rng(seed)
    estimate = float(statistic(np.arange(n)))
    values = np.array([statistic(rng.integers(0, n, size=n)) for _ in range(n_resamples)], dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < n_resamples / 2:
        return Interval(estimate, math.nan, math.nan, confidence)
    low, high = _percentile_bounds(values, confidence)
    return Interval(estimate, low, high, confidence)
