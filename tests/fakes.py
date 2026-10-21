"""Test doubles for the ModelClient interface."""

from collections.abc import Callable

from lahja.targets import Message, ModelCallError


class FakeClient:
    """Answers via `reply(messages, call_number)`; raise ModelCallError from it to simulate failures."""

    def __init__(self, name: str = "fake:model", reply: Callable[[list[Message], int], str] | None = None):
        self.name = name
        self.calls: list[list[Message]] = []
        self._reply = reply or (lambda messages, n: f"answer {n}")

    def complete(self, messages: list[Message], *, temperature: float) -> str:
        self.calls.append(messages)
        return self._reply(messages, len(self.calls))


def failing_on(*call_numbers: int) -> Callable[[list[Message], int], str]:
    def reply(messages, n):
        if n in call_numbers:
            raise ModelCallError(f"simulated failure on call {n}")
        return f"answer {n}"

    return reply
