import json
import pytest
from pathlib import Path

from orc.verify import run
from orc.telemetry import record


class TestVerifyRun:
    def test_all_pass(self, tmp_path):
        ok, output = run(["echo hello", "echo world"], tmp_path, timeout=10)
        assert ok is True
        assert "hello" in output
        assert "world" in output

    def test_one_fail_returns_false(self, tmp_path):
        ok, output = run(["echo ok", "exit 1"], tmp_path, timeout=10)
        assert ok is False

    def test_empty_commands_ok(self, tmp_path):
        ok, output = run([], tmp_path, timeout=10)
        assert ok is True
        assert output == ""

    def test_output_combined(self, tmp_path):
        ok, output = run(["echo line1", "echo line2"], tmp_path, timeout=10)
        assert "line1" in output
        assert "line2" in output

    def test_timeout_returns_false(self, tmp_path):
        ok, output = run(["sleep 100"], tmp_path, timeout=1)
        assert ok is False
        assert "TIMEOUT" in output

    def test_all_commands_run_even_after_failure(self, tmp_path):
        ok, output = run(["exit 1", "echo after"], tmp_path, timeout=10)
        assert ok is False
        assert "after" in output


class TestTelemetryRecord:
    def test_appends_json_line(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        record(tmp_path, "T-001", "API-MID", 1, 12.5, "pass")
        log = tmp_path / "tasks" / ".telemetry.jsonl"
        assert log.exists()
        data = json.loads(log.read_text().strip())
        assert data["ticket_id"] == "T-001"
        assert data["tier"] == "API-MID"
        assert data["attempt"] == 1
        assert data["verify_result"] == "pass"

    def test_appends_multiple_lines(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        record(tmp_path, "T-001", "API-MID", 1, 1.0, "fail")
        record(tmp_path, "T-001", "API-MID", 2, 2.0, "pass")
        log = tmp_path / "tasks" / ".telemetry.jsonl"
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_null_fields_preserved(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        record(tmp_path, "T-002", "LOCAL-S", 1, 5.0, "fail",
               tokens_in=None, tokens_out=None, cost_usd=None)
        log = tmp_path / "tasks" / ".telemetry.jsonl"
        data = json.loads(log.read_text().strip())
        assert data["tokens_in"] is None
        assert data["cost_usd"] is None

    def test_creates_tasks_dir(self, tmp_path):
        record(tmp_path, "T-001", "API-MID", 1, 1.0, "pass")
        assert (tmp_path / "tasks" / ".telemetry.jsonl").exists()
