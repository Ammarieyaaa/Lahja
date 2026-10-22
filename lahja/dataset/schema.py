"""The shape of one eval case. See docs/01-eval-cases.md for what makes a good one."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ISO 639: fr = French, ar = Modern Standard Arabic, aeb = Tunisian Arabic (Derja).
Language = Literal["fr", "ar", "aeb"]
# Languages that may be mixed INTO an input. Customers also mix in English ("cash on delivery"),
# even though English is not a language Lahja grades.
MixedLanguage = Literal["fr", "ar", "aeb", "en"]
# ISO 15924: latn = Latin script (French, or a dialect written as Arabizi), arab = Arabic script.
Script = Literal["latn", "arab"]

# Which scripts each language may legitimately appear in.
_ALLOWED_SCRIPTS: dict[str, set[str]] = {
    "fr": {"latn"},
    "ar": {"arab"},
    "aeb": {"arab", "latn"},
}


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    language: Language  # the customer's main language
    script: Script
    code_switch: list[MixedLanguage] = []  # other languages mixed into the input, e.g. ["fr"]
    intent: str = Field(min_length=1)  # what the customer wants, e.g. "refund_duplicate_charge"
    input: str = Field(min_length=1)  # the customer's message, exactly as they'd type it
    reference: str = Field(min_length=1)  # the key facts a correct answer must contain
    notes: str = ""  # for humans: why this case exists, what makes it pass/fail. Not shown to the judge.

    @model_validator(mode="after")
    def _consistent(self) -> EvalCase:
        if self.script not in _ALLOWED_SCRIPTS[self.language]:
            raise ValueError(f"language {self.language!r} is not written in script {self.script!r}")
        if self.language in self.code_switch:
            raise ValueError("code_switch lists the *other* languages mixed in, not the main one")
        return self
