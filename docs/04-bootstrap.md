# 04: Is the drop real? The paired bootstrap, on paper

**Question:** the candidate's pass rate is 2 points lower than the current model's. Did quality really drop, or is that noise?
**Method:** build a confidence interval (CI) for the difference with a **paired bootstrap over cases**, then compare the interval to a tolerance margin.

Read this before [`lahja/stats/bootstrap.py`](../lahja/stats/bootstrap.py).

## Step 1: Where does the noise come from?

Your 150 cases are a **sample** of the questions customers could ask. Pick a different 150 and you'd get a slightly different pass rate for each model, so a slightly different difference. The "2-point drop" is one draw from that distribution. **A CI describes how wide that distribution is**: the range of differences that are plausible given what you observed.

(Each answer also varies from trial to trial. Lahja handles that first, by averaging each case's N trials into a single **case score**: 3 trials → 0, ⅓, ⅔ or 1. After that, the case is the unit, as explained below.)

## Step 2: Pair the cases

Both models answered the **same** 150 cases, so for each case compute

$$d_i = \text{candidate}_i - \text{baseline}_i$$

With one trial per case, $d_i$ is −1 (only the current model passed), +1 (only the candidate passed) or 0 (both passed or both failed). The quantity of interest is the mean of the $d_i$.

**The worked example.** Out of 150 cases:

| | count | $d_i$ |
|---|---:|---:|
| both pass | 110 | 0 |
| both fail | 23 | 0 |
| only current passes | 10 | −1 |
| only candidate passes | 7 | +1 |

Current = 120/150 = **80%**, candidate = 117/150 = **78%**. Mean $d$ = (−10 + 7)/150 = **−0.02**, the 2-point drop.

Look at where that drop comes from. The 133 ties carry no information about *which model is better*. **The whole difference rests on 10 vs 7 discordant cases**, a gap of 3 cases. If two equally good models disagreed on 17 cases at random (a fair coin flip per case), a 10/7 split or a wider one would happen about **63%** of the time. That's the intuition. Now let's make it precise.

## Step 3: The analytic CI (to check the bootstrap against)

The $d_i$ have standard deviation $s = 0.337$ (from the counts above; the test file checks this). The standard error of their mean is

$$SE = \frac{s}{\sqrt{n}} = \frac{0.337}{\sqrt{150}} = 0.0275$$

and a 95% CI is roughly mean ± 1.96·SE = −0.02 ± 0.054 = **[−7.4, +3.4] points**.

So a 2-point drop on 150 examples is consistent with anything from "the candidate is 7 points worse" to "it's 3 points better". **That's noise, or at least it isn't evidence.** 🎯

## Step 4: The bootstrap, by hand

The formula above relies on the mean being roughly normal. It's fine here, but there's no equally simple formula for kappa, for small per-language samples, or for trial-averaged scores. The **bootstrap** needs no formula.

**The idea (plug-in principle):** we can't draw new samples of 150 cases from the real world, but our sample is our best picture of that world. So we draw new samples **from our sample**: 150 cases *with replacement*, so some cases appear twice and some not at all. We recompute the mean difference on each one. The spread of those recomputed differences approximates how much the real estimate would vary across samples.

A toy run with 5 cases, $d$ = [0, −1, 0, +1, −1], mean −0.2:

| resample (case numbers) | $d$ values | mean |
|---|---|---:|
| 2, 2, 4, 1, 5 | −1, −1, +1, 0, −1 | −0.4 |
| 3, 1, 3, 4, 4 | 0, 0, 0, +1, +1 | +0.4 |
| 5, 2, 1, 3, 2 | −1, −1, 0, 0, −1 | −0.6 |
| … 10,000 times | | |

Sort the 10,000 means. The value at the 2.5th percentile is the low end of the 95% CI and the value at the 97.5th is the high end. That's a **percentile bootstrap**, and the whole algorithm is about 5 lines in `paired_diff_ci`.

**Check:** on the 150-case example, Lahja's bootstrap gives **[−7.3, +3.3]**, against the analytic [−7.4, +3.4]. `tests/test_bootstrap.py` asserts they agree. The bootstrap isn't a black box: in the case where we can do the math, it reproduces the math.

## Step 5: Why paired? 🎯

Treat the two runs as unrelated, i.e. compare 80% vs 78% as two independent samples. The standard error becomes

$$\sqrt{\tfrac{0.80 \cdot 0.20}{150} + \tfrac{0.78 \cdot 0.22}{150}} = 0.047$$

That gives a CI of **[−11.2, +7.2]**, almost twice as wide. (Lahja's bootstrap without pairing gives [−11.3, +7.3].)

Pairing helps because **most of the variance comes from cases, not models**. Some questions are hard for every model. The unpaired view counts that shared difficulty as noise. The paired view cancels it: in $d_i$, a case both models fail contributes exactly 0. Same data, tighter answer, and no extra assumptions, because the models really did answer the same cases.

## Step 6: Why resample cases and not answers? 🎯

With 3 trials, 150 cases × 3 = 450 answers. Resampling the 450 as if they were independent would make the CI about √3 times narrower, which is false precision. Three answers to the *same* question are correlated: if the question is ambiguous, all three suffer. **The case is the independent unit**, so Lahja averages trials into a case score and resamples cases. (The general name is a *cluster bootstrap*.)

What trials do buy you: a less noisy score per case. A coin-flip case contributes ⅓ or ⅔ instead of a random 0 or 1, and that does narrow the CI honestly.

## Step 7: From a CI to a verdict, the non-inferiority margin 🎯

"Is the difference zero?" is the wrong question. A cheaper model that is 0.5 points worse may be a great trade. Instead the team picks a **margin** $\delta$, the largest drop they would accept (Lahja's default is 3 points), and asks whether the CI rules out a drop bigger than that:

```
                    −δ        0
   PASS              |   [====|====]       whole CI above −δ: any drop is within tolerance
   FAIL     [=====]  |        |            whole CI below −δ: confidently worse than tolerated
   INCONCLUSIVE   [==|=====]  |            CI straddles −δ: the data can't tell, so get more cases
```

The worked example: CI [−7.3, +3.3] straddles −3, so the verdict is **INCONCLUSIVE**. That's the honest answer, not a failure of the tool.

**How many cases to settle it?** Keep the same discordance pattern ($s \approx 0.337$). For a CI half-width of 2 points: $n = (1.96 \cdot 0.337 / 0.02)^2 \approx$ **1,100 cases**. Small regressions are expensive to detect. With 50 cases in one language, half-width ≈ 1.96 · 0.337/√50 ≈ 9.3 points, so only drops of about 12–13+ points can produce a confident FAIL. That's why per-language verdicts on small sets are often INCONCLUSIVE.

## Step 8: Bootstrapping kappa, with the same tool

Kappa from 20 labels is also a single draw. Resample the 20 (human, judge) pairs, recompute κ, take percentiles:

| labels | κ | 95% CI |
|---|---:|---|
| example A, 20 labels | 0.56 | **[0.13, 0.89]** |
| same proportions, 40 labels | 0.56 | [0.24, 0.80] |
| 80 French labels (docs/03) | 0.90 | [0.78, 0.98] |

With 20 labels, "κ = 0.56" is consistent with anything from "barely better than chance" to "excellent". So TRUSTED requires **both** κ ≥ 0.6 **and** a CI lower bound ≥ 0.4. A judge that looks good on a handful of labels gets CAUTION until you label more.

## Known limitations (say these before an interviewer does)

- **Small n:** the percentile bootstrap undercovers when there are fewer than about 20 cases: its intervals come out too narrow. Lahja therefore never gives PASS or FAIL to a group with fewer than 20 cases. It reports INCONCLUSIVE and notes what the interval alone would have said.
- **Multiple comparisons:** a 95% CI per language means three languages give roughly a 14% chance (1 − 0.95³) that at least one of them is "confidently" wrong by luck. A stricter version would use a Bonferroni-corrected confidence of 1 − 0.05/k per language. It's not on by default. Know the trade-off.
- **The judge's errors aren't in this CI.** The bootstrap covers sampling noise in *cases*. A biased judge shifts both pass rates, and the per-language trust gate is what guards against that.

## Interview checklist 🎯

- Why could a 2-point drop on 150 cases be noise? *It rests on a handful of discordant cases; the paired CI is about ±5.4 points.*
- Why paired? *Same cases, so shared case difficulty cancels; the CI is roughly half as wide.*
- Why resample cases, not answers? *Trials of one case are correlated, and treating them as independent gives false precision.*
- Why a margin, not "is the difference zero"? *Non-inferiority: the business question is "is it worse by more than we can accept?"*
- Why three outcomes? *A CI that straddles the margin is an honest "we don't know yet; collect more data".*
