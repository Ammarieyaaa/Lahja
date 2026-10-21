from lahja.runner import run_model
from tests.fakes import FakeClient, failing_on


def test_runs_every_case_for_every_trial_with_system_prompt(session, dataset):
    client = FakeClient()
    summary = run_model(session, dataset, client, trials=2, temperature=0.7)
    assert (summary.created, summary.cached, summary.failed) == (6, 0, 0)
    assert client.calls[0] == [
        {"role": "system", "content": "You are a test bot."},
        {"role": "user", "content": "q fr-1"},
    ]


def test_rerun_only_fills_missing_cells(session, dataset):
    run_model(session, dataset, FakeClient(), trials=2, temperature=0.7)
    client = FakeClient()
    summary = run_model(session, dataset, client, trials=3, temperature=0.7)  # raise trials 2 -> 3
    assert (summary.created, summary.cached) == (3, 6)
    assert len(client.calls) == 3


def test_failures_are_skipped_then_retried_on_next_run(session, dataset):
    first = run_model(session, dataset, FakeClient(reply=failing_on(2)), trials=1, temperature=0.7)
    assert (first.created, first.failed) == (2, 1)
    second = run_model(session, dataset, FakeClient(), trials=1, temperature=0.7)
    assert (second.created, second.cached) == (1, 2)


def test_each_model_gets_its_own_run(session, dataset):
    a = run_model(session, dataset, FakeClient(name="a"), trials=1, temperature=0.7)
    b = run_model(session, dataset, FakeClient(name="b"), trials=1, temperature=0.7)
    assert a.run_id != b.run_id and b.created == 3
