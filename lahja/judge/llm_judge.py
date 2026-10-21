"""An LLM-as-judge that grades one answer against one rubric and returns PASS/FAIL."""

from __future__ import annotations

import json
import re

from lahja.judge.base import Grade, JudgeError
from lahja.judge.rubrics import Rubric
from lahja.targets import Message, ModelCallError, ModelClient

SYSTEM = "You are a strict, impartial grader. You follow the rubric exactly and reply with JSON only."

TEMPLATE = """{rubric}

---

<question>
{question}
</question>

<reference_answer>
{reference}
</reference_answer>

<answer_to_grade>
{answer}
</answer_to_grade>

Grade <answer_to_grade> using the rubric above. First write your reasoning, then the verdict.
Reply with ONLY this JSON object:
{{"reason": "<one to three sentences>", "verdict": "PASS" or "FAIL"}}"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_grade(text: str) -> Grade:
    """Extract {"reason", "verdict"} from the judge's reply, tolerating code fences and prose around it."""
    match = _JSON_OBJECT.search(text)
    if match is None:
        raise JudgeError(f"no JSON object in judge output: {text[:200]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise JudgeError(f"invalid JSON from judge: {e}") from e
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in ("PASS", "FAIL"):
        raise JudgeError(f"verdict must be PASS or FAIL, got {data.get('verdict')!r}")
    return Grade(passed=verdict == "PASS", reason=str(data.get("reason", "")).strip())


class LLMJudge:
    def __init__(self, client: ModelClient, rubric: Rubric, *, attempts: int = 2) -> None:
        self.client = client
        self.name = client.name
        self.rubric = rubric.name
        self._rubric_text = rubric.text
        self._attempts = attempts

    def messages(self, *, question: str, reference: str, answer: str) -> list[Message]:
        prompt = TEMPLATE.format(rubric=self._rubric_text, question=question, reference=reference, answer=answer)
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]

    def grade(self, *, question: str, reference: str, answer: str) -> Grade:
        messages = self.messages(question=question, reference=reference, answer=answer)
        error: Exception | None = None
        for _ in range(self._attempts):
            try:
                # temperature 0: we want the judge as repeatable as possible; the
                # randomness we are measuring is the target model's, not the grader's.
                return parse_grade(self.client.complete(messages, temperature=0.0))
            except (JudgeError, ModelCallError) as e:
                error = e
        raise JudgeError(f"judge failed after {self._attempts} attempts: {error}")
