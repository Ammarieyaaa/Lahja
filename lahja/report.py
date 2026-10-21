"""JSON + Markdown reports for a comparison."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lahja.calibrate import Calibration, GroupCalibration
from lahja.compare import Comparison, GroupResult


@dataclass(frozen=True)
class ReportMeta:
    dataset: str
    rubric: str
    judge_model: str
    baseline_model: str
    candidate_model: str
    generated_at: str


def _clean(value: Any) -> Any:
    """JSON has no NaN: emit null instead."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _calibration_dict(g: GroupCalibration) -> dict[str, Any]:
    return {
        "group": g.group,
        "labels": g.n,
        "kappa": g.kappa.kappa,
        "kappa_ci": None if g.kappa_ci is None else [g.kappa_ci.low, g.kappa_ci.high],
        "raw_agreement": g.kappa.observed,
        "chance_agreement": g.kappa.expected,
        "human_pass_rate": g.human_pass_rate,
        "judge_pass_rate": g.judge_pass_rate,
        "missed_failure_rate": g.missed_failure_rate,
        "confusion": asdict(g.confusion),
        "trust": g.trust.value,
        "notes": g.notes,
    }


def _group_dict(g: GroupResult) -> dict[str, Any]:
    return {
        "group": g.group,
        "cases": g.n_cases,
        "baseline_pass_rate": g.baseline_rate,
        "candidate_pass_rate": g.candidate_rate,
        "difference": None if g.diff is None else g.diff.estimate,
        "difference_ci": None if g.diff is None else [g.diff.low, g.diff.high],
        "statistical_outcome": g.statistical.value,
        "judge_trust": None if g.trust is None else g.trust.value,
        "verdict": g.outcome.value,
        "notes": g.notes,
    }


def to_dict(meta: ReportMeta, comparison: Comparison, calibration: Calibration) -> dict[str, Any]:
    return _clean(
        {
            "meta": asdict(meta),
            "verdict": comparison.overall.value,
            "reasons": comparison.reasons,
            "margin": comparison.margin,
            "confidence": comparison.confidence,
            "cases_missing_judgments": comparison.missing_cases,
            "by_language": [_group_dict(g) for g in comparison.by_language],
            "pooled": _group_dict(comparison.pooled),
            "judge_trust": {
                "by_language": [_calibration_dict(g) for g in calibration.by_language.values()],
                "by_script": [_calibration_dict(g) for g in calibration.by_script.values()],
            },
        }
    )


def _pct(x: float) -> str:
    return "–" if math.isnan(x) else f"{x:.0%}"


def _pts(x: float) -> str:
    return f"{x * 100:+.1f}"


def _num(x: float) -> str:
    return "–" if math.isnan(x) else f"{x:.2f}"


def _group_row(g: GroupResult) -> str:
    diff = "–" if g.diff is None else _pts(g.diff.estimate)
    ci = "–" if g.diff is None else f"[{_pts(g.diff.low)}, {_pts(g.diff.high)}]"
    trust = "(pooled)" if g.trust is None else g.trust.value
    return (
        f"| {g.group} | {g.n_cases} | {_pct(g.baseline_rate)} | {_pct(g.candidate_rate)} "
        f"| {diff} | {ci} | {trust} | **{g.outcome.value}** |"
    )


def _calibration_row(g: GroupCalibration) -> str:
    ci = "–" if g.kappa_ci is None else f"[{_num(g.kappa_ci.low)}, {_num(g.kappa_ci.high)}]"
    return (
        f"| {g.group} | {g.n} | {_num(g.kappa.kappa)} | {ci} | {_pct(g.kappa.observed)} "
        f"| {_pct(g.human_pass_rate)} | {_pct(g.missed_failure_rate)} | {g.trust.value} |"
    )


def to_markdown(meta: ReportMeta, comparison: Comparison, calibration: Calibration) -> str:
    c = comparison
    lines = [
        f"# Lahja report: {meta.dataset}",
        "",
        f"## Verdict: **{c.overall.value}**",
        "",
        *[f"- {r}" for r in c.reasons],
        "",
        f"- Current (baseline): `{meta.baseline_model}`",
        f"- Candidate: `{meta.candidate_model}`",
        f"- Rubric: `{meta.rubric}`, judged by `{meta.judge_model}`",
        f"- Tolerated drop (margin): {c.margin:.0%} · {c.confidence:.0%} paired bootstrap CI over cases",
    ]
    if c.missing_cases:
        lines.append(f"- {c.missing_cases} case(s) excluded: not judged for both models")
    lines += [
        "",
        "## By language",
        "",
        "Δ = candidate − current, in percentage points.",
        "",
        "| Language | Cases | Current | Candidate | Δ | 95% CI | Judge trust | Verdict |",
        "|---|---:|---:|---:|---:|---|---|---|",
        *[_group_row(g) for g in c.by_language],
        _group_row(c.pooled),
        "",
    ]
    for g in [*c.by_language, c.pooled]:
        lines += [f"- **{g.group}**: {note}" for note in g.notes]
    lines += [
        "",
        "## Judge trust (your blind labels vs the judge)",
        "",
        "| Group | Labels | κ | κ 95% CI | Raw agreement | Your pass rate | Missed failures | Trust |",
        "|---|---:|---:|---|---:|---:|---:|---|",
        *[_calibration_row(g) for g in [*calibration.by_language.values(), *calibration.by_script.values()]],
        "",
    ]
    for g in [*calibration.by_language.values(), *calibration.by_script.values()]:
        lines += [f"- **{g.group}**: {note}" for note in g.notes]
    lines += [
        "",
        "## How to read this",
        "",
        f"- **PASS**: the whole CI is above −{c.margin:.0%}; any drop is within tolerance.",
        f"- **FAIL**: the whole CI is below −{c.margin:.0%}; the candidate is confidently worse than tolerated.",
        "- **INCONCLUSIVE**: the CI straddles the margin; more cases are needed to tell.",
        "- **JUDGE_UNTRUSTED**: the judge doesn't agree well enough with your labels on this language "
        "(kappa, docs/03), so its grades can't support a verdict.",
        "- Missed failures: of the answers you failed, the share the judge passed. A high value means the judge hides regressions.",
        "",
        f"*Generated {meta.generated_at}*",
        "",
    ]
    return "\n".join(lines)


def write_reports(meta: ReportMeta, comparison: Comparison, calibration: Calibration, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{meta.dataset}-{meta.rubric}"
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(to_dict(meta, comparison, calibration), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(to_markdown(meta, comparison, calibration), encoding="utf-8")
    return json_path, md_path
