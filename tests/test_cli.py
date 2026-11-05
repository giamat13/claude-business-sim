import json

import pytest

pytest.importorskip("anthropic")

from business_sim.cli import main  # noqa: E402

from conftest import stub_message  # noqa: E402


def _only_run_dir(root):
    run_dirs = list(root.iterdir())
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_cli_rules_operator_writes_a_run_directory(tmp_path):
    assert main(["run", "--days", "2", "--operator", "rules", "--out", str(tmp_path)]) == 0
    summary = json.loads((_only_run_dir(tmp_path) / "summary.json").read_text())
    assert summary["operator"] == "rules"
    assert summary["days_closed"] == 2


def test_cli_claude_operator_runs_through_the_sdk_and_its_base_url(stub_api, monkeypatch, tmp_path):
    # The SDK reads ANTHROPIC_BASE_URL, so this exercises the real CLI path against the stub.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{stub_api.server_port}")
    stub_api.replies = [
        stub_message([{"type": "tool_use", "id": "toolu_1", "name": "end_day", "input": {}}]),
    ]

    assert main(["run", "--days", "1", "--operator", "claude", "--model", "stub-model", "--out", str(tmp_path)]) == 0

    summary = json.loads((_only_run_dir(tmp_path) / "summary.json").read_text())
    assert summary["operator"] == "claude"
    assert summary["days_closed"] == 1
    assert stub_api.requests[0]["model"] == "stub-model"


def test_cli_claude_operator_without_a_key_fails_cleanly(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["run", "--days", "1", "--operator", "claude", "--out", str(tmp_path)]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not any(tmp_path.iterdir())
