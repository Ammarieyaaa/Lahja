# 02: Judge rubrics

You've already built an LLM judge, so this doc covers only what changes when the judge has to be **calibrated per language** and drive a **regression verdict**.

## Design rules

1. **One rubric = one question.** `correctness` asks "are the facts right and sufficient?" and explicitly *ignores* language. Whether the bot answered in the right language is a different question, so it gets a different rubric. If one rubric mixed both, a FAIL could mean either thing, and you couldn't tell from kappa which one the judge gets wrong. 🎯
2. **Binary verdicts.** PASS/FAIL only. A 1–5 scale feels more informative, but judges are poorly calibrated in the middle of it, and humans disagree on whether something is a 3 or a 4. Binary also gives you a pass rate, which is what the bootstrap compares, and makes kappa easy to read.
3. **Write the FAIL conditions explicitly.** "PASS if the answer is good" leaves the judge to invent the standard. Each FAIL bullet in `correctness.md` names a failure mode seen in practice. "Deflects to support when the info was available" is there because the 3B candidate did exactly that on `fr-001` in the first smoke run.
4. **Decide the borderline cases in writing.** These are where you and the judge will disagree, so settle them in the rubric rather than at labeling time. Then **you label using the same rubric** in `lahja label`. Kappa only means something if you and the judge are applying the same standard.
5. **Reasoning before verdict.** The JSON asks for `reason` before `verdict`, so the model commits to an argument before a label instead of rationalizing a label it already chose.
6. **The rubric is in English even for Darija answers.** That's on purpose. The instructions stay fixed, and calibration then tests whether the judge can *read* Darija. If kappa on Darija is low, a Darija-language rubric is one experiment worth trying, and Lahja will measure whether it helps.

## How the judge is kept honest

- **It's blind.** `Judge.grade(question, reference, answer)` receives no model name and no language label. It can't go easy on "the big model".
- **It's a different family from both models it grades (self-preference bias).** Current is `openai/gpt-oss-120b` (OpenAI), candidate is `llama3.2:3b` (Meta), and the judge is `qwen/qwen3.8-27b` (Alibaba), so it has no "own style" on either side. Qwen is also the stronger Arabic model of the families available on this Groq account. Whether it reads *Darija* well is an open question, and calibration answers it. 🎯
- **Temperature is 0.** We are measuring the target model's randomness, not the grader's.
- **Cache key is (response, rubric, judge model).** Changing the rubric text without renaming it would reuse stale grades. **If you change a rubric's meaning, give it a new name** (e.g. `correctness_v2`).

## The rubric I wrote: [`correctness.md`](../lahja/rubrics/correctness.md)

Read it, then look at the structure: the question → PASS (all of) → FAIL (any of) → Ignore → Borderline cases. The "Ignore" section matters as much as the rest, because it stops the judge from failing a correct answer for being in the "wrong" language, which is the other rubric's job.

## The rubric you write: `language_fidelity`

The system prompt says: *reply in the customer's language and register; Darija in the same script; no switching to MSA/French unless the customer does.* Small models regress on this a lot, sliding from Darija into MSA or French. It may be the biggest Darija regression Lahja catches.

Create `lahja/rubrics/language_fidelity.md` with the same structure. You have to make these decisions; nobody else can make them for you:

- **What counts as Darija rather than MSA?** One MSA phrase in a Darija reply: FAIL? What about a fully MSA reply to a Darija question?
- **Script:** an Arabizi question answered in Arabic-script Darija: PASS or FAIL?
- **Code-switching:** if the customer mixed in French, may the answer use French? How much? Do product terms like "commande" or "remboursement" count as switching?
- **French register:** if the customer uses informal French, is a formal reply a FAIL? (Probably not. Decide and write it down.)
- **What to ignore:** correctness of the facts, since the other rubric grades that.

Then try it on a few answers:
```powershell
lahja judge --dataset support-v1 --role candidate --rubric language_fidelity
```
Every later step (`label`, `calibrate`, `compare`) takes `--rubric`, so each rubric gets its own kappa per language and its own verdict.
