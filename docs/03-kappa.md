# 03: Cohen's kappa, on paper

**Question:** can we trust the judge's PASS/FAIL for language X?
**Method:** you label a sample of answers yourself (blind), then measure how well the judge agrees with you, **separately for each language**.

Read this before [`lahja/stats/kappa.py`](../lahja/stats/kappa.py). The code is a direct transcription of the formula below.

## Step 1: Why not raw agreement?

Here are 20 Darija answers you labeled, next to the judge's verdicts:

|                | judge PASS | judge FAIL | total |
|----------------|-----------:|-----------:|------:|
| **you PASS**   | 18         | 1          | 19    |
| **you FAIL**   | 1          | 0          | 1     |
| total          | 19         | 1          | 20    |

The judge agrees with you on 18 of 20 answers, so **raw agreement = 90%**. Looks great.

Now consider a broken judge that **says PASS to everything without reading**. It agrees with you on every answer you passed: 19 of 20 = **95%**. The judge that does nothing scores *higher* than the real one.

Raw agreement rewards a judge for guessing the majority class. When most answers pass, which is the normal case for a decent model, any lazy judge gets high agreement. **A regression shows up as answers moving from PASS to FAIL.** A judge that can't recognize FAIL can't detect a regression, however high its agreement is.

## Step 2: Subtract the agreement you'd get by chance

Kappa asks: how much better than *chance* does the judge agree with you?

"Chance" here means a judge that keeps its own overall PASS rate but decides **independently of the actual answer**, like a weighted coin.

- You pass answers at rate $p_{you}$. The coin judge passes at $p_{judge}$.
- If the two are independent, P(both say PASS) = $p_{you} \cdot p_{judge}$. That's just the probability of two independent events both happening.
- Likewise, P(both say FAIL) = $(1-p_{you})(1-p_{judge})$.

So the **expected chance agreement** is

$$p_e = p_{you}\,p_{judge} + (1-p_{you})(1-p_{judge})$$

and the **observed agreement** $p_o$ is just the diagonal of the table divided by n.

## Step 3: Rescale

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

Read it as a fraction:
- The **numerator** is how much agreement the judge achieved *above chance*.
- The **denominator** is the most agreement above chance that was *possible*, since perfect agreement is 1.
- So **κ is the share of the achievable above-chance agreement the judge actually achieved.** 1 = perfect, 0 = no better than a coin with the right bias, negative = worse than chance (systematically disagreeing with you).

## Worked example A: a decent French judge (20 labels)

|                | judge PASS | judge FAIL | total |
|----------------|-----------:|-----------:|------:|
| **you PASS**   | 11         | 2          | 13    |
| **you FAIL**   | 2          | 5          | 7     |
| total          | 13         | 7          | 20    |

- $p_o = (11 + 5)/20 = 0.80$
- $p_{you} = 13/20 = 0.65$ and $p_{judge} = 13/20 = 0.65$
- $p_e = 0.65 \times 0.65 + 0.35 \times 0.35 = 0.4225 + 0.1225 = 0.545$
- $\kappa = (0.80 - 0.545)/(1 - 0.545) = 0.255 / 0.455 = \mathbf{0.56}$

## Worked example B: the Darija table from step 1

- $p_o = 18/20 = 0.90$
- $p_{you} = 19/20 = 0.95$ and $p_{judge} = 19/20 = 0.95$
- $p_e = 0.95 \times 0.95 + 0.05 \times 0.05 = 0.9025 + 0.0025 = 0.905$
- $\kappa = (0.90 - 0.905)/(1 - 0.905) = -0.005/0.095 = \mathbf{-0.05}$

**90% agreement, kappa below zero.** The judge passed the one answer you failed, and failed one you passed. On the only thing that matters for regression detection, recognizing a bad answer, it went 0 for 1.

And the always-PASS judge: $p_o = 0.95$, $p_{judge} = 1$, so $p_e = 0.95 \cdot 1 + 0.05 \cdot 0 = 0.95$, and $\kappa = 0/0.05 = \mathbf{0}$. Exactly chance, which is right, because it is a coin that always lands PASS.

## The kappa paradox

**"Paradox": high raw agreement, low kappa.** Example B is the first half of it, and there κ was *right* to be low. The other half is less comfortable: **κ depends on prevalence, not only on how good the judge is.**

Take one judge, with the same skill in both scenarios: it catches 80% of the answers you'd fail and wrongly fails about 4% of the answers you'd pass.

**Scenario 1:** 100 labels, you fail only 5 (95% pass rate).

|            | judge PASS | judge FAIL |
|------------|-----------:|-----------:|
| you PASS   | 91         | 4          |
| you FAIL   | 1          | 4          |

$p_o = 0.95$, $p_{you} = 0.95$, $p_{judge} = 0.92$, $p_e = 0.95 \cdot 0.92 + 0.05 \cdot 0.08 = 0.878$, so $\kappa = 0.072/0.122 = \mathbf{0.59}$.

**Scenario 2:** 100 labels, you fail 50 (50% pass rate).

|            | judge PASS | judge FAIL |
|------------|-----------:|-----------:|
| you PASS   | 48         | 2          |
| you FAIL   | 10         | 40         |

$p_o = 0.88$, $p_{you} = 0.50$, $p_{judge} = 0.58$, $p_e = 0.5 \cdot 0.58 + 0.5 \cdot 0.42 = 0.50$, so $\kappa = 0.38/0.50 = \mathbf{0.76}$.

Same judge, **κ 0.59 vs 0.76**, and the scenario with *higher* raw agreement (95%) got the *lower* kappa. When almost everything passes, $p_e$ is close to 1, so the denominator $1 - p_e$ is tiny. Kappa then rests on the handful of failing answers, and one mistake among them moves it a lot.

### What Lahja does about it

1. **Report kappa together with raw agreement, your pass rate, and the 2×2 table.** All three, never kappa alone. `lahja calibrate` flags "high agreement but low kappa" automatically.
2. **Make sure the labeled sample contains failures.** `lahja label` samples answers from **both** models. The weaker candidate fails more often, which pushes prevalence away from 95%.
   - Do *not* fix prevalence by picking answers *the judge* failed. That selects on the judge's own output and inflates its apparent agreement. 🎯
3. **Small samples, wide uncertainty.** In example B, κ is decided by **one** answer. Lahja won't call a language TRUSTED from fewer than 20 labels, and in [docs/04](04-bootstrap.md) we add a confidence interval on κ itself.
4. **Watch for leniency.** For regression testing, the dangerous error is the judge *passing* an answer you failed (a missed regression). Lahja reports that rate separately.

## Why per language: pooling hides the problem 🎯

80 French labels with a good judge (46 / 2 / 2 / 30, so κ = 0.90), plus example B's 20 Darija labels (κ = −0.05). Pool them:

|            | judge PASS | judge FAIL |
|------------|-----------:|-----------:|
| you PASS   | 64         | 3          |
| you FAIL   | 3          | 30         |

$p_o = 0.94$, $p_{you} = p_{judge} = 0.67$, $p_e = 0.67^2 + 0.33^2 = 0.558$, so **κ = 0.86**.

The pooled number says "almost perfect" while the judge is useless on Darija. The majority language dominates the pooled kappa. This is the core reason Lahja's trust gate works per language.

## What counts as "trusted"?

The usual bands (Landis & Koch, 1977) are: <0 poor, 0–0.20 slight, 0.21–0.40 fair, 0.41–0.60 moderate, 0.61–0.80 substantial, 0.81+ almost perfect. They're a **convention, not a law**. Lahja's defaults:

| Trust | Rule |
|---|---|
| INSUFFICIENT | fewer than 20 labels, or κ undefined (you or the judge gave only one verdict) |
| UNTRUSTED | κ < 0.4 |
| CAUTION | 0.4 ≤ κ < 0.6 |
| TRUSTED | κ ≥ 0.6, and (from increment 5) the lower end of κ's 95% CI ≥ 0.4 |

A language that isn't TRUSTED or CAUTION gets **JUDGE UNTRUSTED** instead of PASS/FAIL in the final report.

## Interview checklist 🎯

- Why kappa and not accuracy? *Chance correction: a constant judge gets high agreement at skewed prevalence and κ = 0.*
- What is the kappa paradox? *κ depends on prevalence. At extreme pass rates $p_e \to 1$, so κ becomes unstable and low even for decent judges. Report it with raw agreement and the confusion matrix, and sample enough failures.*
- Why per language? *A pooled κ is dominated by the majority language and can hide a judge that fails on a minority language.*
- Why blind labeling? *If you see the judge's verdict first, you anchor on it, and κ measures your agreement with yourself.*
