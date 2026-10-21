# Rubric: correctness

You are grading ONE answer from a customer-support assistant. Decide a single question:

**Does the answer give the customer correct and sufficient information to resolve their request, consistent with the reference answer?**

The reference answer lists the key facts a correct answer must contain. It is not a script: the answer may use different wording, order, or language.

## PASS only if ALL of these hold
1. Every key fact from the reference that the customer needs in order to act (amounts, delays, steps, conditions) is present, or a correct equivalent is.
2. Nothing in the answer contradicts the reference, and the answer invents no policy (no made-up delays, fees, documents, exceptions or promises).
3. The answer addresses what the customer actually asked.

## FAIL if ANY of these hold
- A key fact the customer needs is missing or wrong.
- The answer contradicts the reference or invents policy.
- The answer deflects ("contact support", "a human agent will help you") when the reference shows the information could have been given directly.
- The answer responds to a different question.

## Ignore
- Wording, tone, length and formatting, unless they make the answer wrong or unusable.
- Which language the answer is written in. That is graded by a separate rubric. Grade the content even if the language differs from the question's.
- Extra information that is correct and harmless.

## Borderline cases
- Some key facts right, one needed fact missing: FAIL. A customer missing one step cannot act.
- A fact stated vaguely but not wrongly ("in a few days" when the reference says "5 business days"): FAIL if the customer needs the exact figure to act, PASS otherwise.
- If the reference itself says the correct behavior is to hand off to a human, a hand-off is a PASS.
