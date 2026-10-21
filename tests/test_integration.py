"""Real LLM calls. Not run by default: `pytest -m integration`.

Ollama tests need `ollama serve` with llama3.2:3b pulled; Groq tests need GROQ_API_KEY.
"""

import os

import httpx
import pytest
from typer.testing import CliRunner

from lahja.cli import app
from lahja.config import load_settings
from lahja.judge import LLMJudge, load_rubric
from lahja.targets import make_client

pytestmark = pytest.mark.integration


def _ollama_up() -> bool:
    try:
        return httpx.get("http://localhost:11434/api/tags", timeout=2).is_success
    except httpx.HTTPError:
        return False


needs_ollama = pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
needs_groq = pytest.mark.skipif(not load_settings().groq_api_key, reason="GROQ_API_KEY not set")


@needs_ollama
def test_candidate_answers_via_ollama():
    s = load_settings()
    reply = make_client(s.candidate, s).complete([{"role": "user", "content": "Say bonjour."}], temperature=0)
    assert reply.strip()


@needs_groq
def test_current_model_answers_via_groq():
    s = load_settings()
    reply = make_client(s.current, s).complete([{"role": "user", "content": "Say bonjour."}], temperature=0)
    assert reply.strip()


@needs_groq
def test_groq_judge_passes_an_obviously_correct_answer():
    s = load_settings()
    judge = LLMJudge(make_client(s.judge, s), load_rubric("correctness"))
    grade = judge.grade(
        question="Combien de jours ai-je pour retourner un article ?",
        reference="14 jours après la livraison, article non utilisé dans son emballage d'origine.",
        answer="Vous avez 14 jours après la livraison pour retourner l'article, s'il est inutilisé et dans son emballage d'origine.",
    )
    assert grade.passed, grade.reason


@needs_ollama
def test_full_pipeline_on_examples_with_ollama_in_every_role(tmp_path, monkeypatch):
    """End to end through the CLI. Every role is Ollama here so it runs without a Groq key;
    the verdict itself is meaningless (2 cases, no labels): this checks the plumbing."""
    monkeypatch.setenv("LAHJA_DB_URL", f"sqlite:///{tmp_path / 'e2e.db'}")
    for role in ("CURRENT", "CANDIDATE", "JUDGE"):
        monkeypatch.setenv(f"LAHJA_{role}_PROVIDER", "ollama")
        monkeypatch.setenv(f"LAHJA_{role}_MODEL", "llama3.2:3b")
    monkeypatch.setenv("LAHJA_CURRENT_MODEL", "llama3.2:latest")  # same weights, distinct run key
    runner = CliRunner()

    def ok(*args, codes=(0,)):
        result = runner.invoke(app, list(args))
        assert result.exit_code in codes, result.output
        return result

    ok("dataset", "import", "data/cases.example.jsonl", "--name", "ex", "--system-prompt", "data/system_prompt.example.txt")
    for role in ("current", "candidate"):
        ok("run", "--dataset", "ex", "--role", role, "--trials", "1")
        ok("judge", "--dataset", "ex", "--role", role)
    result = ok("compare", "--dataset", "ex", "--out", str(tmp_path / "reports"), codes=(0, 2, 3))
    assert "VERDICT" in result.output
    assert (tmp_path / "reports" / "ex-correctness.md").exists()
    assert os.path.getsize(tmp_path / "reports" / "ex-correctness.json") > 0
