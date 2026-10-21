import pytest

from lahja.db import Run
from lahja.judge import JudgeError, LLMJudge, available_rubrics, load_rubric, parse_grade
from lahja.judging import judge_run
from lahja.runner import run_model
from tests.fakes import FakeClient


@pytest.mark.parametrize(
    "text, passed",
    [
        ('{"reason": "all facts", "verdict": "PASS"}', True),
        ('```json\n{"reason": "missing delay", "verdict": "fail"}\n```', False),
        ('Sure! {"reason": "ok", "verdict": "PASS"} hope that helps', True),
    ],
)
def test_parse_grade_tolerates_wrapping(text, passed):
    assert parse_grade(text).passed is passed


@pytest.mark.parametrize("text", ["PASS", '{"verdict": "MAYBE"}', "{not json}"])
def test_parse_grade_rejects_garbage(text):
    with pytest.raises(JudgeError):
        parse_grade(text)


def test_correctness_rubric_ships_with_package():
    assert "correctness" in available_rubrics()
    assert "PASS only if ALL" in load_rubric("correctness").text


def test_unknown_rubric_lists_available():
    with pytest.raises(ValueError, match="correctness"):
        load_rubric("nope")


def test_judge_is_blind_to_model_identity():
    client = FakeClient(reply=lambda m, n: '{"reason": "r", "verdict": "PASS"}')
    judge = LLMJudge(client, load_rubric("correctness"))
    judge.grade(question="Q?", reference="REF", answer="ANS")
    prompt = client.calls[0][1]["content"]
    assert "Q?" in prompt and "REF" in prompt and "ANS" in prompt
    assert "candidate" not in prompt.lower() and "llama" not in prompt.lower()


def test_judge_retries_once_on_unparseable_output():
    replies = iter(["I think it passes", '{"reason": "r", "verdict": "FAIL"}'])
    judge = LLMJudge(FakeClient(reply=lambda m, n: next(replies)), load_rubric("correctness"))
    assert judge.grade(question="q", reference="r", answer="a").passed is False


def test_judge_run_caches_per_rubric_and_skips_failures(session, dataset):
    summary = run_model(session, dataset, FakeClient(), trials=2, temperature=0.7)
    run = session.get(Run, summary.run_id)

    def reply(messages, n):
        return "garbage" if n in (1, 2) else '{"reason": "r", "verdict": "PASS"}'  # first response fails twice

    first = judge_run(session, run, LLMJudge(FakeClient("judge", reply), load_rubric("correctness")))
    assert (first.created, first.failed) == (5, 1)
    ok = FakeClient("judge", lambda m, n: '{"reason": "r", "verdict": "FAIL"}')
    second = judge_run(session, run, LLMJudge(ok, load_rubric("correctness")))
    assert (second.created, second.cached) == (1, 5)
