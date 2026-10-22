# Lahja

**Regression testing for LLM features, with first-class support for French, Arabic and Tunisian Derja, including code-switching.**

*Lahja* (لهجة) means "dialect".

A team has an LLM feature, say a support bot, and wants to switch to a cheaper model without quietly making answers worse. Lahja runs a test dataset through **both** models and grades the answers with an LLM judge that has been **checked against your own labels**. It then tells you, **per language**, whether quality dropped, and whether the drop is **real or noise**:

```
  ar      62 cases  delta CI [-4.1, +2.3]     PASS
  aeb     58 cases  delta CI [-31.0, -12.1]   JUDGE_UNTRUSTED
  fr      70 cases  delta CI [-2.9, +3.6]     PASS
VERDICT: INCONCLUSIVE
  - aeb: judge not trusted (UNTRUSTED); label more answers or fix the rubric
  - note: the pooled all-language number alone would have said PASS
```

*(illustrative output)*

## The hard problem, and how Lahja solves it

There are two ways a regression test for multilingual LLM features goes wrong without anyone noticing.

### 1. The grader is reliable in one language and not in another

An LLM judge can grade French well and Tunisian Derja badly. Derja is under-represented in training data, comes in two scripts (Arabic and Arabizi, with digits for sounds like `3` and `7`), and mixes in French mid-sentence. If you validate the judge on all your labels pooled together, the majority language dominates. In [docs/03](docs/03-kappa.md) a pooled κ of 0.86 hides a Tunisian κ of −0.05.

**Solution: a per-language trust gate.**
- You label a sample of answers **blind**: you see no model name and no judge verdict.
- `lahja calibrate` computes **Cohen's kappa separately for each language** (and each script), with a **bootstrap CI on κ**.
- It reports raw agreement, your pass rate and the 2×2 table next to κ, so the **kappa paradox** is visible and not misread.
- It reports the judge's **missed-failure rate**, meaning how often it passes answers you failed. That's the error that hides regressions.
- A language whose judge isn't trusted gets **JUDGE_UNTRUSTED** instead of PASS/FAIL. Lahja won't give a verdict its grader can't support.

### 2. A small difference is mistaken for a real one, or the other way round

A 2-point drop on 150 cases is very likely noise: the paired 95% CI is about [−7.4, +3.4] points ([docs/04](docs/04-bootstrap.md)). In the other direction, a 25-point Tunisian drop can shrink to about 4 points when pooled with plenty of French cases, and get waved through.

**Solution: a paired bootstrap, per language, with a non-inferiority margin.**
- Both models answer the same cases. Trials are averaged into one score per case, and **cases** (the independent unit) are resampled in pairs. Shared case difficulty cancels, so the CI is about half as wide as an unpaired one.
- The question asked is *"is the candidate worse by more than the margin δ?"*, not *"is the difference zero?"*. The answer has three possible outcomes: **PASS** (CI above −δ), **FAIL** (CI below −δ) or **INCONCLUSIVE** (CI straddles −δ, so more data is needed).
- **Overall FAIL if any trusted language FAILs. Overall PASS only if every language passes.** A regression in a minority language can't be averaged away.
- Groups with fewer than 20 cases never get PASS or FAIL, because percentile bootstrap intervals are unreliable that small.

Both statistics, κ and the bootstrap, are **hand-written** (about 40 lines each), derived on paper in the docs, and tested against those worked examples. scikit-learn appears only in tests, as an oracle for kappa.

## Architecture

```
 data/cases.jsonl ──► dataset import ──────────────────────────► SQLite (SQLAlchemy 2.0)
 (language, script,                                               datasets · cases
  code_switch, intent,                                            runs · responses
  input, reference)                                               judgments · human_labels
                                                                    │
 current (Groq gpt-oss) ─┐                                          │
                         ├──► runner: case × trial ──► responses ───┤  cached per (run, case, trial)
 candidate (Ollama 3B) ──┘                                          │
                                                                    │
 judge (Groq, Qwen) ───────► judging: blind, rubric ──► judgments ──┤  cached per (response, rubric, judge)
 you ──────────────────────► labeling: blind ─────────► labels ─────┤
                                                                    │
            calibrate: κ + bootstrap CI per language ──► trust gate ┤
            compare: paired bootstrap per language + margin ────────┴──► PASS / FAIL / INCONCLUSIVE
                                                                         reports/<dataset>-<rubric>.{md,json}
```

| Module | Responsibility |
|---|---|
| [lahja/dataset/](lahja/dataset/) | `EvalCase` schema (ISO 639 language, ISO 15924 script, code-switch, intent); JSONL loader |
| [lahja/db/](lahja/db/) | SQLAlchemy 2.0 models. Unique constraints double as caches, so every step is resumable |
| [lahja/targets/](lahja/targets/) | `ModelClient` protocol; one OpenAI-compatible client for Groq and Ollama, with 429/5xx backoff |
| [lahja/judge/](lahja/judge/) | `Judge` protocol, `LLMJudge`, rubric loading. Rubrics are in [lahja/rubrics/](lahja/rubrics/) |
| [lahja/stats/](lahja/stats/) | `cohen_kappa`, `paired_diff_ci`, `bootstrap_ci`, written by hand |
| [lahja/calibrate.py](lahja/calibrate.py) | Per-language/per-script κ, κ CI, trust classification, paradox and leniency warnings |
| [lahja/compare.py](lahja/compare.py) | Case scores → paired CI per language → non-inferiority outcome → trust gate → overall verdict |
| [lahja/report.py](lahja/report.py) | JSON and Markdown reports |

**Design choices worth defending:**
- The judge is a **different model family from both models it grades** (OpenAI vs Meta, judged by Alibaba Qwen). LLM judges prefer outputs that resemble their own (self-preference bias), and that bias would tilt a current-vs-candidate comparison.
- The judge is **blind** to which model wrote the answer and runs at temperature 0.
- Verdicts are **binary**, with **one question per rubric** (`correctness` ignores language; `language_fidelity` grades only language). Kappa per rubric is then interpretable.
- Datasets are **immutable**: edit the cases, import as `-v2`. Old runs stay tied to the exact cases they were graded on.
- **Out of scope for the MVP:** dashboard, GitHub App, queue workers, cost/latency tracking.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env      # add GROQ_API_KEY; confirm the Groq model IDs
ollama pull llama3.2:3b
lahja config                # shows which model plays which role
```

## Workflow

```powershell
lahja dataset validate data\cases.jsonl
lahja dataset import data\cases.jsonl --name support-v1 --system-prompt data\system_prompt.example.txt

lahja run   --dataset support-v1 --role current     # N trials per case; re-run resumes
lahja run   --dataset support-v1 --role candidate
lahja judge --dataset support-v1 --role current
lahja judge --dataset support-v1 --role candidate

lahja label     --dataset support-v1 --per-language 25   # blind; repeat until each language has ≥ 20 labels
lahja calibrate --dataset support-v1                     # per-language κ + trust

lahja compare   --dataset support-v1                     # exit 0 PASS · 2 FAIL · 3 INCONCLUSIVE · 1 error
```

Each of `judge`, `label`, `calibrate` and `compare` takes `--rubric`. Run the full loop once per rubric.

## Tests

```powershell
pytest                    # unit tests, LLMs mocked (about 80 tests, ~15 s)
pytest -m integration     # real calls: Ollama end-to-end; Groq tests skip without GROQ_API_KEY
```

## Docs: read in this order

1. [docs/01-eval-cases.md](docs/01-eval-cases.md): what makes a good eval case, confounding, the Tunisian Derja template
2. [docs/02-rubrics.md](docs/02-rubrics.md): rubric design, and the `language_fidelity` rubric to write
3. [docs/03-kappa.md](docs/03-kappa.md): Cohen's kappa on paper, the kappa paradox, why per language
4. [docs/04-bootstrap.md](docs/04-bootstrap.md): paired bootstrap on paper, why 2 points on 150 cases can be noise, the margin

## Status

- [x] Pipeline: dataset → run → judge → label → calibrate → compare → report
- [x] Model roles confirmed against this Groq account: current `openai/gpt-oss-120b`, candidate Ollama `llama3.2:3b`, judge `qwen/qwen3.8-27b`
- [x] Curated dataset `support-v1`: 236 cases, 59 scenarios × French, MSA, Tunisian Derja (Arabic script) and Tunisian Derja (Arabizi)
- [x] `language_fidelity` rubric
- [x] Candidate run (708 answers)
- [ ] Current run: finishing under Groq's free-tier daily token cap
- [ ] Judging, first trial per case, both rubrics
- [ ] Labels: at least 20 per language (and per Derja script) per rubric
- [ ] Results: calibration + verdict per language, written up here
