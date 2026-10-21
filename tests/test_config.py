import pytest

from lahja.config import ConfigError, load_settings


def test_defaults_put_candidate_on_ollama(monkeypatch):
    for var in ("LAHJA_CANDIDATE_PROVIDER", "LAHJA_CANDIDATE_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings(use_dotenv=False)
    assert s.candidate.key == "ollama:llama3.2:3b"


def test_env_overrides_model(monkeypatch):
    monkeypatch.setenv("LAHJA_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("LAHJA_JUDGE_MODEL", "some-model")
    assert load_settings(use_dotenv=False).judge.key == "groq:some-model"


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LAHJA_CURRENT_PROVIDER", "openai")
    with pytest.raises(ConfigError):
        load_settings(use_dotenv=False)
