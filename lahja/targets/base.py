"""The interface every model (target or judge) sits behind."""

from typing import Protocol

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": ...}


class ModelCallError(RuntimeError):
    """A model call failed for good (after retries). Callers skip the item; re-running fills the gap."""


class ModelClient(Protocol):
    name: str  # ModelSpec.key, e.g. "ollama:llama3.2:3b"

    def complete(self, messages: list[Message], *, temperature: float) -> str: ...
