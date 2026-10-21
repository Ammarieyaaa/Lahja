import pytest

from lahja.calibrate import LabelPair, Trust, TrustPolicy, calibrate, calibrate_dataset
from lahja.db import HumanLabel, Judgment, Response
from lahja.labeling import label_interactively, pick_for_labeling
from lahja.runner import run_model
from tests.fakes import FakeClient
from tests.test_kappa import table


def pairs(language, cells, script="latn"):
    human, judge = table(*cells)
    return [LabelPair(language, script, h, j) for h, j in zip(human, judge)]


def test_trust_levels_follow_kappa_per_language():
    labels = (
        pairs("fr", (46, 2, 2, 30))  # kappa 0.90
        + pairs("ar", (11, 2, 2, 5), "arab")  # kappa 0.56
        + pairs("ary", (18, 1, 1, 0), "arab")  # kappa -0.05, the Darija example from docs/03
    )
    result = calibrate(labels, ["fr", "ar", "ary"])
    assert result.trust("fr") is Trust.TRUSTED
    assert result.trust("ar") is Trust.CAUTION
    assert result.trust("ary") is Trust.UNTRUSTED


def test_paradox_and_missed_failures_are_flagged():
    ary = calibrate(pairs("ary", (18, 1, 1, 0), "arab"), ["ary"]).by_language["ary"]
    assert any("Kappa paradox" in n for n in ary.notes)
    assert any("passed 1 of 1 answers you failed" in n for n in ary.notes)


def test_too_few_labels_or_unlabeled_language_is_insufficient():
    result = calibrate(pairs("fr", (8, 1, 1, 5)), ["fr", "ary"])
    assert result.trust("fr") is Trust.INSUFFICIENT  # 15 < 20 labels
    assert result.trust("ary") is Trust.INSUFFICIENT  # in the dataset, never labeled
    assert result.by_language["ary"].n == 0


def test_constant_verdicts_make_kappa_undefined():
    g = calibrate(pairs("fr", (25, 0, 0, 0)), ["fr"]).by_language["fr"]
    assert g.trust is Trust.INSUFFICIENT and any("undefined" in n for n in g.notes)


def test_script_breakdown_only_when_language_uses_two_scripts():
    labels = pairs("ary", (10, 0, 0, 10), "arab") + pairs("ary", (5, 3, 3, 4), "latn") + pairs("fr", (10, 0, 0, 10))
    result = calibrate(labels, ["ary", "fr"])
    assert set(result.by_script) == {"ary/arab", "ary/latn"}
    assert result.by_script["ary/latn"].kappa.kappa < result.by_script["ary/arab"].kappa.kappa


def test_good_kappa_with_wide_ci_is_only_caution():
    # kappa 0.56 clears a lowered threshold, but with 20 labels its CI is about [0.13, 0.89].
    lenient = TrustPolicy(trusted_kappa=0.5)
    g = calibrate(pairs("fr", (11, 2, 2, 5)), ["fr"], lenient).by_language["fr"]
    assert g.trust is Trust.CAUTION
    assert g.kappa_ci.low == pytest.approx(0.13, abs=0.01)
    assert any("label more answers" in n for n in g.notes)
    ignore_ci = TrustPolicy(trusted_kappa=0.5, trusted_ci_low=-1)
    assert calibrate(pairs("fr", (11, 2, 2, 5)), ["fr"], ignore_ci).trust("fr") is Trust.TRUSTED


def test_labeling_is_blind_and_feeds_calibration(session, dataset):
    run_model(session, dataset, FakeClient(name="m1"), trials=2, temperature=0.7)
    run_model(session, dataset, FakeClient(name="m2"), trials=2, temperature=0.7)
    items = pick_for_labeling(session, dataset, "correctness", per_language=10, seed=0)
    assert len(items) == 6  # 3 cases x 2 models, trial 0 only
    assert {r.trial for r in items} == {0}

    shown: list[str] = []
    answers = iter(["x", "p", "f", "s", "p", "q"])  # "x" is invalid and re-asked
    summary = label_interactively(session, items, "correctness", ask=lambda q: next(answers), show=shown.append)
    assert (summary.labeled, summary.skipped) == (3, 1)
    assert "m1" not in "".join(shown) and "m2" not in "".join(shown)  # model identity never shown

    for response in session.query(Response):
        session.add(Judgment(response_id=response.id, rubric="correctness", judge_model="j", passed=True))
    session.commit()
    result = calibrate_dataset(session, dataset, "correctness", "j")
    assert sum(g.n for g in result.by_language.values()) == session.query(HumanLabel).count() == 3
    assert len(pick_for_labeling(session, dataset, "correctness", per_language=10, seed=0)) == 3  # labeled ones excluded
