"""Settings, read from the environment (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

Provider = Literal["groq", "ollama"]
Role = Literal["current", "candidate", "judge"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
PROVIDERS: tuple[str, ...] = ("groq", "ollama")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    provider: Provider
    model: str

    @property
    def key(self) -> str:
        """Stable identity used in the DB, e.g. 'ollama:llama3.2:3b'."""
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class Settings:
    db_url: str
    groq_api_key: str | None
    ollama_base_url: str
    current: ModelSpec
    candidate: ModelSpec
    judge: ModelSpec
    trials: int
    temperature: float  # generation temperature: use what production uses
    margin: float  # non-inferiority margin, as a fraction (0.03 = 3 points)
    seed: int

    def spec(self, role: Role) -> ModelSpec:
        return getattr(self, role)


def _spec(prefix: str, default_provider: str, default_model: str) -> ModelSpec:
    provider = os.getenv(f"{prefix}_PROVIDER", default_provider)
    if provider not in PROVIDERS:
        raise ConfigError(f"{prefix}_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    return ModelSpec(provider=provider, model=os.getenv(f"{prefix}_MODEL", default_model))  # type: ignore[arg-type]


def load_settings(*, use_dotenv: bool = True) -> Settings:
    if use_dotenv:
        load_dotenv()
    return Settings(
        db_url=os.getenv("LAHJA_DB_URL", "sqlite:///lahja.db"),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        # Three different model families, so the judge can't favour either side (self-preference bias):
        # current = OpenAI (gpt-oss), candidate = Meta (Llama), judge = Alibaba (Qwen).
        current=_spec("LAHJA_CURRENT", "groq", "openai/gpt-oss-120b"),
        candidate=_spec("LAHJA_CANDIDATE", "ollama", "llama3.2:3b"),
        judge=_spec("LAHJA_JUDGE", "groq", "qwen/qwen3.8-27b"),
        trials=int(os.getenv("LAHJA_TRIALS", "3")),
        temperature=float(os.getenv("LAHJA_TEMPERATURE", "0.7")),
        margin=float(os.getenv("LAHJA_MARGIN", "0.03")),
        seed=int(os.getenv("LAHJA_SEED", "0")),
    )
