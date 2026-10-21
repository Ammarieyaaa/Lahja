"""The judge interface. Same shape as the red-teaming project: a judge behind a Protocol, so the
LLM judge, a rule-based judge, or a test fake are interchangeable."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Grade:
    passed: bool
    reason: str


class JudgeError(RuntimeError):
    """The judge could not produce a usable grade (e.g. unparseable output after retries)."""


class Judge(Protocol):
    name: str  # identity of the grader (judge model key); part of the Judgment cache key
    rubric: str  # rubric name; also part of the cache key

    # Deliberately blind: the judge gets no model name and no language label, only the text.
    def grade(self, *, question: str, reference: str, answer: str) -> Grade: ...
