from pathlib import Path

import pytest
from pydantic import ValidationError

from lahja.dataset import DatasetError, coverage, get_dataset, import_dataset, read_cases
from tests.conftest import make_case

EXAMPLES = Path(__file__).parent.parent / "data" / "cases.example.jsonl"


def test_example_file_is_valid():
    cases = read_cases(EXAMPLES)
    assert coverage(cases) == {("fr", "latn"): 1, ("ar", "arab"): 1}


@pytest.mark.parametrize(
    "overrides",
    [
        {"language": "fr", "script": "arab"},  # French isn't written in Arabic script
        {"language": "ar", "script": "latn"},  # MSA in Latin script isn't a case we model
        {"language": "ary", "script": "arab", "code_switch": ["ary"]},  # main language listed as code-switch
        {"reference": "   "},  # whitespace-only reference
        {"surprise": "field"},  # typo'd / unknown field
    ],
)
def test_invalid_cases_are_rejected(overrides):
    with pytest.raises(ValidationError):
        make_case("x", **overrides)


def test_darija_allows_both_scripts():
    make_case("a", "ary", "arab", code_switch=["fr"])
    make_case("b", "ary", "latn")


def test_read_cases_reports_every_error_with_line_numbers(tmp_path):
    good = make_case("fr-1").model_dump_json()
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join([good, '{"id": "bad"}', "", good]), encoding="utf-8")
    with pytest.raises(DatasetError) as exc:
        read_cases(path)
    message = str(exc.value)
    assert "line 2" in message
    assert "duplicate ids: fr-1" in message


def test_import_stores_cases_and_refuses_name_reuse(session):
    cases = [make_case("fr-1"), make_case("ary-1", "ary", "latn", code_switch=["fr"])]
    import_dataset(session, "v1", cases, system_prompt="sp")
    stored = get_dataset(session, "v1")
    assert [c.external_id for c in stored.cases] == ["fr-1", "ary-1"]
    assert stored.cases[1].code_switch == ["fr"]
    with pytest.raises(DatasetError, match="already exists"):
        import_dataset(session, "v1", cases)
