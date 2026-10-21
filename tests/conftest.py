import pytest

from lahja.dataset import EvalCase, import_dataset
from lahja.db import make_session_factory


@pytest.fixture
def session():
    with make_session_factory("sqlite://")() as s:  # in-memory DB per test
        yield s


def make_case(id: str, language: str = "fr", script: str = "latn", **overrides) -> EvalCase:
    fields = dict(id=id, language=language, script=script, intent="test", input=f"q {id}", reference=f"r {id}")
    return EvalCase(**(fields | overrides))


@pytest.fixture
def dataset(session):
    cases = [make_case("fr-1"), make_case("fr-2"), make_case("ar-1", "ar", "arab")]
    return import_dataset(session, "ds", cases, system_prompt="You are a test bot.")
