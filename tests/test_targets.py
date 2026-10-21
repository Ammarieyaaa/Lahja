import httpx
import pytest

from lahja.targets import ModelCallError, OpenAICompatClient


def _client(handler, **kwargs):
    sleeps: list[float] = []
    client = OpenAICompatClient(
        name="test:m", base_url="https://api.example.com/openai/v1", model="m", api_key="k",
        transport=httpx.MockTransport(handler), sleep=sleeps.append, **kwargs,
    )
    return client, sleeps


def _ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_sends_openai_shaped_request_and_returns_content():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read()
        return _ok("bonjour")

    client, _ = _client(handler)
    assert client.complete([{"role": "user", "content": "salut"}], temperature=0.0) == "bonjour"
    assert seen["url"] == "https://api.example.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert b'"temperature":0.0' in seen["body"].replace(b" ", b"")


def test_retries_rate_limits_honouring_retry_after():
    responses = iter([httpx.Response(429, headers={"retry-after": "7"}), httpx.Response(503), _ok("ok")])
    client, sleeps = _client(lambda r: next(responses))
    assert client.complete([], temperature=0) == "ok"
    assert sleeps == [7.0, 2.0]  # Retry-After first, then exponential backoff (2**1)


def test_gives_up_after_max_retries():
    client, sleeps = _client(lambda r: httpx.Response(429), max_retries=2)
    with pytest.raises(ModelCallError, match="429"):
        client.complete([], temperature=0)
    assert len(sleeps) == 2


def test_client_errors_are_not_retried():
    client, sleeps = _client(lambda r: httpx.Response(400, text="bad model"))
    with pytest.raises(ModelCallError, match="bad model"):
        client.complete([], temperature=0)
    assert sleeps == []


def test_strips_inline_reasoning():
    client, _ = _client(lambda r: _ok("<think>hmm</think>\nfinal"))
    assert client.complete([], temperature=0) == "final"
