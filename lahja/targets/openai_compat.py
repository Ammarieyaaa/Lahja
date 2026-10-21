"""One client for any OpenAI-compatible chat endpoint. Groq and Ollama (/v1) both speak it."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import httpx

from lahja.targets.base import Message, ModelCallError

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OpenAICompatClient:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,  # tests inject httpx.MockTransport
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.name = name
        self.model = model
        self.max_retries = max_retries
        self._sleep = sleep
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout, transport=transport)

    def complete(self, messages: list[Message], *, temperature: float) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                r = self._http.post("/chat/completions", json=payload)
            except httpx.TransportError as e:
                if last:
                    raise ModelCallError(f"{self.name}: {e!r}") from e
                self._sleep(self._backoff(attempt, None))
                continue
            if r.status_code in RETRYABLE_STATUS and not last:
                # 429 = rate limited (Groq free tier); honour Retry-After when given.
                self._sleep(self._backoff(attempt, r.headers.get("retry-after")))
                continue
            if r.is_error:
                raise ModelCallError(f"{self.name}: HTTP {r.status_code}: {r.text[:300]}")
            content = r.json()["choices"][0]["message"].get("content") or ""
            # Some reasoning models inline their chain of thought; it is not part of the answer.
            content = _THINK.sub("", content).strip()
            if not content:
                raise ModelCallError(f"{self.name}: empty response")
            return content
        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return float(min(2**attempt, 30))
