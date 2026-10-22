import pytest

from lahja.calibrate import Trust
from lahja.compare import Outcome, PairedCase, compare_cases, compare_runs, decide
from lahja.db import Judgment, Run
from lahja.runner import run_model
from lahja.stats.bootstrap import Interval
from tests.fakes import FakeClient

MARGIN = 0.03


@pytest.mark.parametrize(
    "low, high, outcome",
    [
        (-0.02, 0.04, Outcome.PASS),  # every plausible drop is within 3 points
        (-0.12, -0.05, Outcome.FAIL),  # confidently worse than tolerated
        (-0.073, 0.033, Outcome.INCONCLUSIVE),  # docs/04 worked example
        (-0.04, -0.01, Outcome.INCONCLUSIVE),  # a real drop, but maybe within tolerance
    ],
)
def test_decide_is_non_inferiority(low, high, outcome):
    assert decide(Interval(0, low, high, 0.95), MARGIN) is outcome


def lang_cases(language, n, base_pass, cand_pass):
    """n cases; first base_pass pass for baseline, first cand_pass pass for candidate (paired by index)."""
    return [PairedCase(f"{language}-{i}", language, float(i < base_pass), float(i < cand_pass)) for i in range(n)]


def trusted(_):
    return Trust.TRUSTED


def test_all_languages_hold_up_gives_pass():
    cases = lang_cases("fr", 100, 80, 80) + lang_cases("aeb", 100, 70, 70)
    result = compare_cases(cases, trusted, margin=MARGIN)
    assert result.overall is Outcome.PASS and result.reasons == []


def test_tunisian_regression_fails_even_when_pooled_looks_fine():
    # French: identical. Tunisian: 25-point drop, but only 40 of 240 cases, so the pooled drop is ~4 points.
    cases = lang_cases("fr", 200, 160, 160) + lang_cases("aeb", 40, 30, 20)
    result = compare_cases(cases, trusted, margin=MARGIN)
    by = {g.group: g for g in result.by_language}
    assert by["fr"].outcome is Outcome.PASS
    assert by["aeb"].outcome is Outcome.FAIL
    assert result.overall is Outcome.FAIL
    assert result.pooled.outcome is not Outcome.FAIL  # the pooled view would not have caught it


def test_untrusted_judge_blocks_the_verdict_for_that_language():
    cases = lang_cases("fr", 100, 80, 80) + lang_cases("aeb", 100, 80, 40)  # big Tunisian "drop"
    trust = {"fr": Trust.TRUSTED, "aeb": Trust.UNTRUSTED}.get
    result = compare_cases(cases, trust, margin=MARGIN)
    aeb = next(g for g in result.by_language if g.group == "aeb")
    assert aeb.statistical is Outcome.FAIL and aeb.outcome is Outcome.JUDGE_UNTRUSTED
    assert result.overall is Outcome.INCONCLUSIVE
    assert any("aeb: judge not trusted" in r for r in result.reasons)


def test_caution_keeps_the_verdict_but_warns():
    result = compare_cases(lang_cases("fr", 100, 80, 80), lambda _: Trust.CAUTION, margin=MARGIN)
    assert result.overall is Outcome.PASS
    assert any("CAUTION" in n for n in result.by_language[0].notes)


def test_small_groups_are_flagged_and_tiny_ones_inconclusive():
    result = compare_cases(lang_cases("fr", 10, 8, 8) + lang_cases("ar", 1, 1, 1), trusted, margin=MARGIN)
    by = {g.group: g for g in result.by_language}
    assert by["fr"].outcome is Outcome.INCONCLUSIVE  # identical scores, but 10 cases can't support a PASS
    assert any("only 10 cases" in n and "would say PASS" in n for n in by["fr"].notes)
    assert by["ar"].diff is None and by["ar"].outcome is Outcome.INCONCLUSIVE


def test_compare_runs_averages_trials_and_keeps_pairs(session, dataset):
    current = run_model(session, dataset, FakeClient("cur"), trials=2, temperature=0.7)
    candidate = run_model(session, dataset, FakeClient("cand"), trials=2, temperature=0.7)
    base_run, cand_run = session.get(Run, current.run_id), session.get(Run, candidate.run_id)
    for r in base_run.responses:
        session.add(Judgment(response_id=r.id, rubric="correctness", judge_model="j", passed=True))
    for r in cand_run.responses:
        if r.case.external_id != "ar-1":  # leave one case unjudged for the candidate
            session.add(Judgment(response_id=r.id, rubric="correctness", judge_model="j", passed=r.trial == 0))
    session.commit()

    result = compare_runs(
        session, dataset, base_run, cand_run, rubric="correctness", judge_model="j", trust=trusted, margin=MARGIN
    )
    assert result.missing_cases == 1
    fr = result.by_language[0]
    assert (fr.group, fr.n_cases, fr.baseline_rate, fr.candidate_rate) == ("fr", 2, 1.0, 0.5)
