import json

from lahja.calibrate import LabelPair, Trust, calibrate
from lahja.compare import compare_cases
from lahja.report import ReportMeta, to_markdown, write_reports
from tests.test_compare import lang_cases
from tests.test_kappa import table

META = ReportMeta("support-v1", "correctness", "groq:judge", "groq:big", "ollama:small", "2026-10-21T00:00:00+00:00")


def scenario():
    human, judge = table(46, 2, 2, 30)
    labels = [LabelPair("fr", "latn", h, j) for h, j in zip(human, judge)]
    calibration = calibrate(labels, ["fr", "ary"])  # Darija never labeled -> INSUFFICIENT
    cases = lang_cases("fr", 100, 80, 80) + lang_cases("ary", 60, 45, 30)
    return compare_cases(cases, calibration.trust, margin=0.03), calibration


def test_markdown_shows_verdict_languages_and_trust():
    comparison, calibration = scenario()
    md = to_markdown(META, comparison, calibration)
    assert "## Verdict: **INCONCLUSIVE**" in md
    assert "| fr | 100 | 80% | 80% | +0.0 |" in md
    assert "JUDGE_UNTRUSTED" in md and "INSUFFICIENT" in md
    assert "ary: judge not trusted" in md
    assert "| all |" in md and "(pooled)" in md


def test_json_is_valid_and_has_no_nan(tmp_path):
    comparison, calibration = scenario()
    json_path, md_path = write_reports(META, comparison, calibration, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))  # strict parse: NaN would still load, so check below
    assert "NaN" not in json_path.read_text(encoding="utf-8")
    assert data["verdict"] == "INCONCLUSIVE"
    ary = next(g for g in data["by_language"] if g["group"] == "ary")
    assert ary["statistical_outcome"] == "FAIL" and ary["verdict"] == "JUDGE_UNTRUSTED"
    trust = {g["group"]: g for g in data["judge_trust"]["by_language"]}
    assert trust["fr"]["trust"] == Trust.TRUSTED.value and trust["ary"]["kappa"] is None
    assert md_path.exists()
