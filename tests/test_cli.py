import pytest
from typer.testing import CliRunner

from lahja.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LAHJA_DB_URL", f"sqlite:///{tmp_path / 'cli.db'}")


@pytest.mark.parametrize("command", [[], ["dataset"], ["run"], ["judge"], ["label"], ["calibrate"], ["compare"]])
def test_help_renders(command):
    result = runner.invoke(app, [*command, "--help"])
    assert result.exit_code == 0, result.output


def test_dataset_import_and_calibrate_without_labels():
    result = runner.invoke(
        app, ["dataset", "import", "data/cases.example.jsonl", "--name", "ex", "--system-prompt", "data/system_prompt.example.txt"]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["calibrate", "--dataset", "ex"])
    assert result.exit_code == 0, result.output
    assert "INSUFFICIENT" in result.output


def test_unknown_dataset_fails_cleanly():
    result = runner.invoke(app, ["calibrate", "--dataset", "nope"])
    assert result.exit_code == 1
