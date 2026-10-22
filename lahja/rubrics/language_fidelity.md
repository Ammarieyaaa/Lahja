# Language Fidelity Rubric

## Question

Does the assistant reply in the customer's language and expected register, using Tunisian Derja rather than MSA when the customer writes in Derja, and following the applicable script and code-switching rules?

Judge language fidelity only. Do not grade factual correctness, policy compliance, completeness, or whether the assistant solved the customer's issue.

## PASS (all must be true)

- The main reply uses the same language or dialect as the customer's message:
  - French customer → French reply.
  - MSA customer → MSA reply.
  - Tunisian Derja customer → recognizably Tunisian Derja, not a reply written mainly in MSA.
- For Tunisian Derja, the reply uses the same script as the customer: Arabic script for Arabic-script Derja, and Arabizi/Latin script for Arabizi.
- The reply is understandable and linguistically coherent. Minor spelling, punctuation, or transliteration differences do not cause failure.
- French code-switching is consistent with the customer's message. If the customer mixes French and Derja, the assistant may also mix them naturally, but Derja must remain the main language of a Derja reply.
- French replies may be formal or informal. A formal French reply to an informal French customer is still a PASS if it remains natural and respectful.

## FAIL (any one is enough)

- The assistant replies in a different primary language from the customer's language, such as English to a French, MSA, or Derja customer.
- A Derja customer receives a reply written entirely or mainly in MSA, even if the Arabic is grammatical and understandable.
- A Derja reply is mainly in another Arabic dialect, such as Moroccan Darija or Egyptian Arabic, rather than Tunisian Derja.
- The assistant changes the script of a Derja reply: Arabic-script Derja customer → Arabizi reply, or Arabizi customer → Arabic-script Derja reply.
- The assistant switches to a full French reply when the customer wrote in Derja without using French.
- French is used so heavily in a Derja reply that the reply is effectively French rather than Derja, or the French switching is unrelated and not supported by the customer's language choice.
- The response is too linguistically mixed or incoherent to identify a consistent reply language.

## Ignore

- Whether the facts, prices, delivery windows, return rules, or other policy details are correct. The `correctness` rubric grades those.
- Whether the assistant answers every part of the question, escalates correctly, or invents information.
- The response's length, helpfulness, politeness, or tone, except where the language/register itself becomes inappropriate or incoherent.
- Minor typos, spelling variants, punctuation, diacritics, and common Arabizi spelling variation.
- Common French-origin support words used naturally in Tunisian Derja, such as `commande`, `livraison`, `colis`, or `remboursement`. These words alone do not make the reply a French reply or require `code_switch` to be marked.
- A small, isolated MSA phrase within an otherwise clearly Tunisian Derja reply. Do not fail for one brief conventional phrase; fail when MSA becomes the main style or replaces Derja throughout the answer.
- For French customers, whether the assistant mirrors informal slang exactly. Formal but natural French is acceptable.
- The reference answer and its language. References are written in English for curation; judge only the reply against the customer's message.

## Borderline cases

- **One MSA phrase in a Derja reply:** PASS if the rest of the reply is clearly Tunisian Derja and the phrase is brief. FAIL if the reply shifts into MSA for a substantial part or its main answer.
- **Entire reply in MSA to a Derja customer:** FAIL. Shared Arabic script does not make MSA equivalent to Tunisian Derja.
- **Derja with a few French terms:** PASS if Derja grammar and structure remain dominant. Common support vocabulary such as `commande` or `livraison` is acceptable even when the input has no French code-switch label.
- **Customer explicitly code-switches between Derja and French:** the assistant may use French terms or short French phrases naturally, but a Derja reply must remain primarily Derja. A fully French answer is FAIL unless the customer's message is effectively French rather than Derja.
- **Arabizi question answered in Arabic-script Derja (or vice versa):** FAIL because the Derja script must match the customer's script.
- **Formal French to informal French:** PASS if natural and respectful.
- **A few dialect-neutral Arabic words:** do not fail merely because a word also occurs in MSA. Judge the overall grammar, vocabulary, and sentence structure rather than one word in isolation.
- **Uncertain dialect identification:** if there is not enough evidence to confidently distinguish Tunisian Derja from MSA or another dialect, do not infer failure from a single word. Judge the overall response and use FAIL only when a stated failure condition is clear.

## Reason

Give the verdict in the JSON format requested below. The reason should name the relevant language, dialect, script, or code-switching behavior, and should not discuss factual correctness.