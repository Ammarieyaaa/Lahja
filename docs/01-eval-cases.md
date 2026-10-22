# 01: What makes a good eval case

Lahja can only detect a regression if the dataset contains a case where it shows up. **The dataset is the specification.** The statistics come later and can only tell you how sure to be about what the dataset measured.

## The five fields, and why each exists

```json
{"id": "fr-001", "language": "fr", "script": "latn", "code_switch": [], "intent": "refund_duplicate_charge",
 "input": "...", "reference": "...", "notes": "..."}
```

| Field | What it is | Why Lahja needs it |
|---|---|---|
| `input` | The customer's message, **exactly as a real customer would type it**: typos, no accents, mixed languages. | If the inputs are cleaner than real traffic, you are testing a model that doesn't exist. |
| `reference` | The **key facts** a correct answer must contain, not a model answer to copy. | The judge checks facts against it. If it is vague ("explains the refund policy"), the judge has nothing to check against and its grades become noise. |
| `language` / `script` / `code_switch` | The language label: `fr`, `ar` (MSA), `ary` (Moroccan Darija) or `aeb` (Tunisian Derja). `script` is `arab` or `latn` (Arabizi), and `code_switch` lists the other languages mixed in (`en` is allowed here too). | Every verdict and every judge-trust score is **split by language**. Script is tracked separately because "the judge reads Darija" and "the judge reads Arabizi" are different claims. |
| `intent` | What the customer wants (`refund_duplicate_charge`, `delivery_status`, ...). | Coverage and confounding, explained below. |
| `notes` | For humans only: why this case exists and what makes it pass or fail. | It's the curator's reasoning. **The judge never sees it.** If a fact matters for grading, it belongs in `reference`. |

## Five properties of a good case

1. **Answerable from what the bot knows.** The reference must follow from [the system prompt](../data/system_prompt.example.txt). A case whose right answer the bot couldn't know measures luck, not quality.
2. **Unambiguous pass/fail.** Two careful people reading `reference` should agree on the grade. If you can't decide yourself, the judge can't either, and that case will drag down kappa for the wrong reason.
3. **Discriminating.** A case every model passes tells you nothing about the difference between models. The best cases make the model *apply* the policy, not recite it. For example, `ar-001` requires knowing that Oujda falls in the "elsewhere" window, so 6 days is not late. Small models fail at exactly this.
4. **Realistic distribution.** Roughly match the mix of intents and languages in real traffic, and include the messy inputs.
5. **Independent.** Don't write 10 near-copies of one case. The bootstrap treats each case as an independent sample of "real usage". Near-duplicates make the dataset look bigger than it is, so the confidence intervals come out too narrow. 🎯

## 🎯 Confounding: why `intent` matters for per-language verdicts

Say your Darija cases happen to be mostly hard intents (multi-step returns) and your French cases mostly easy ones (tracking). Lahja then reports "the candidate regressed on Darija". But was it the language, or the intent? You can't tell. **Spread the same intents across every language/script cell** so that per-language comparisons are like for like.

That does **not** mean translating. A French case translated into Darija gives *translationese*: Darija nobody actually writes, often drifting toward MSA. Write each language's cases natively, with the same intents but different, natural messages. 🎯

## How many cases?

Each language gets its own confidence interval, so what matters is **cases per language**, not the total. With about 50 cases in one language, only large drops (roughly 13+ points) produce a confident FAIL. Smaller drops come out INCONCLUSIVE. [docs/04-bootstrap.md](04-bootstrap.md) shows where that number comes from. Aim for at least 50 per language you want a verdict on, and at least 50 per script if you care about Arabizi separately.

## Worked examples (written by me)

These two cases are in [data/cases.example.jsonl](../data/cases.example.jsonl):

- **`fr-001`** (duplicate charge). The input is informal ("Comment je récupère mon argent ?"), as people really write. The reference lists exactly four checkable facts: full refund, original card, 5 business days, order number only. The notes record the failure modes we expect (asking for bank statements, a made-up delay, a bare "contact support").
- **`ar-001`** (delivery status, MSA). It tests *applying* the policy: Oujda → 4–8 days → 6 days is not late. It's a discriminating case.

## A real ambiguity, caught by the first run

Version 1 of `fr-001`'s reference said the refund happens *"dès que le client envoie le numéro de commande au support"* (once the customer sends the order number to support). But the customer had **already given** the number in their message. On the first real run, gpt-oss answered three times:

- Trial 0: "we're processing it now". The Qwen judge gave **FAIL**: *"fails to include the specific action required: the customer must send the order number"*.
- Trials 1 and 2 repeated the order-number condition back. Both **PASS**.

The judge applied the reference literally. **The case was ambiguous, not the judge wrong.** Two careful humans could disagree on trial 0 too, which breaks property 2. The fix: the reference now says the customer has already given the number and needs to provide nothing else.

Lessons for when you curate:
- **Read the judge's `reason` whenever a verdict surprises you.** A surprise usually points to the reference or the rubric before it points to the judge.
- **Fix the case, not the grade.** Then import again under a new name (`examples-v2`). Old runs stay tied to the old wording.
- **Write references against the actual input.** A policy fact is only part of the answer if the customer hasn't already covered it.

## Tunisian Derja (`aeb`)

Use the same format as the Darija template below with `"language": "aeb"`, and `"script": "arab"` or `"latn"` (Tunisian Arabizi). Use the Tunisian policy in [data/system_prompt.tunisia.txt](../data/system_prompt.tunisia.txt): Tunis/Sfax/Sousse, prices in TND. It has the same rules as the Moroccan one, so the existing scenarios carry over by swapping cities and currency.

**Write and label only the dialect you're fluent in.** Your blind labels are the ground truth for the judge's kappa. If you're unsure of a dialect, your labels add noise, and Lahja's trust gate stops meaning anything for that language.

**Keep each dataset tied to one policy.** A dataset is imported with a single system prompt, and every reference must follow from it. Tunisian cases plus French cases about Tunis and TND go together in one dataset with `system_prompt.tunisia.txt`. Don't mix Moroccan-policy and Tunisian-policy cases in one dataset.

## Darija: your part

I'm not writing Darija content. You know how it's actually written and I would produce translationese. Here is the format with each field annotated:

```json
{
  "id": "ary-001",
  "language": "ary",
  "script": "arab",
  "code_switch": ["fr"],
  "intent": "return_defective_item",
  "input": "<your Darija message, typed the way a real customer would: Arabic script here; for Arabizi set script to \"latn\">",
  "reference": "<the key facts a correct answer must contain, taken from the system prompt>",
  "notes": "<why this case exists; what makes it PASS or FAIL>"
}
```

In the real file, each case is **one line** (JSONL). The format above is spread out only for readability.

Decisions that are yours to make. Write them down in this doc once you've made them:

- **What language is `reference` written in?** For the correctness rubric it's a list of facts, so the language matters less than precision. Writing Darija references in French or English can make the judge's job easier. Writing them in Darija keeps the dataset self-contained. Pick one convention and keep it.
- **`code_switch`:** list a language only when it is really mixed in. "Darija with the usual French loanwords" may count as plain Darija for you. Decide where your line is.
- **Arabizi vs Arabic script:** include both if real customers use both. Lahja reports them as separate breakdowns.
- **Edge cases worth having:** a Darija message that ends in French; an Arabizi message using digits (3, 7, 9); a short or ambiguous message; a question the policy doesn't cover (correct behavior is to hand off to a human).

## Workflow

```powershell
lahja dataset validate data\cases.jsonl          # checks the schema and shows per-language coverage
lahja dataset import data\cases.jsonl --name support-v1 --system-prompt data\system_prompt.example.txt
lahja dataset list
```

Datasets are immutable once imported: if you edit cases, import them again as `support-v2`. Old runs keep pointing at exactly the cases they were graded on.
