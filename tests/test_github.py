import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from orc.config import Config, GitHubConfig
from orc.github import mirror, flush, _queue_path
from orc.ticket import parse as parse_ticket


def _make_config(enabled: bool = True, gh_repo: str = "owner/name") -> Config:
    return Config(
        repo=".",
        wip_cap=5,
        night_wallclock_minutes=360,
        max_parallel=3,
        default_branch="main",
        memory_file="CLAUDE.md",
        timeouts={},
        harness={},
        github=GitHubConfig(enabled=enabled, repo=gh_repo),
    )


def _make_ticket(tmp_path: Path, status: str = "ready", github_issue: int | None = None) -> object:
    p = tmp_path / "T-001.md"
    gi_line = f"github_issue: {github_issue}\n" if github_issue else ""
    p.write_text(
        f"---\nid: T-001\ntitle: Test\nstatus: {status}\ndepends_on: []\n{gi_line}---\n\nBody.\n"
    )
    return parse_ticket(p)


class TestMirrorEnqueue:
    def test_success_no_queue(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path)
        runner = MagicMock(return_value=0)
        mirror("create", ticket, _make_config(), tmp_path, runner=runner)
        assert not _queue_path(tmp_path).exists()
        runner.assert_called_once()

    def test_failure_enqueues(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path)
        runner = MagicMock(return_value=1)
        mirror("create", ticket, _make_config(), tmp_path, runner=runner)
        queue = _queue_path(tmp_path)
        assert queue.exists()
        entry = json.loads(queue.read_text().strip())
        assert entry["action"] == "create"
        assert entry["ticket_id"] == "T-001"

    def test_disabled_config_no_call(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path)
        runner = MagicMock(return_value=0)
        mirror("create", ticket, _make_config(enabled=False), tmp_path, runner=runner)
        runner.assert_not_called()
        assert not _queue_path(tmp_path).exists()

    def test_never_writes_ticket_file(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path)
        original = ticket.path.read_bytes()
        runner = MagicMock(return_value=1)
        mirror("create", ticket, _make_config(), tmp_path, runner=runner)
        assert ticket.path.read_bytes() == original

    def test_update_labels_skipped_without_issue(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path)
        runner = MagicMock(return_value=0)
        mirror("update_labels", ticket, _make_config(), tmp_path, runner=runner)
        runner.assert_not_called()

    def test_update_labels_called_with_issue(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        ticket = _make_ticket(tmp_path, github_issue=42)
        runner = MagicMock(return_value=0)
        mirror("update_labels", ticket, _make_config(), tmp_path, runner=runner)
        runner.assert_called_once()


class TestFlush:
    def test_replays_and_removes_queue(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        entry = {
            "action": "create",
            "ticket_id": "T-001",
            "payload": {"cmd": ["gh", "issue", "create"]},
            "queued_at": 0,
        }
        _queue_path(tmp_path).write_text(json.dumps(entry) + "\n")
        runner = MagicMock(return_value=0)
        flush(tmp_path, _make_config(), runner=runner)
        runner.assert_called_once()
        assert not _queue_path(tmp_path).exists()

    def test_keeps_failed_entries(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        entry = {
            "action": "create",
            "ticket_id": "T-001",
            "payload": {"cmd": ["gh", "issue", "create"]},
            "queued_at": 0,
        }
        _queue_path(tmp_path).write_text(json.dumps(entry) + "\n")
        runner = MagicMock(return_value=1)
        flush(tmp_path, _make_config(), runner=runner)
        assert _queue_path(tmp_path).exists()

    def test_idempotent_on_empty(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        runner = MagicMock(return_value=0)
        flush(tmp_path, _make_config(), runner=runner)
        runner.assert_not_called()

    def test_multiple_entries_all_succeed(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        entries = [
            {"action": "create", "ticket_id": f"T-00{i}", "payload": {"cmd": ["gh", str(i)]}, "queued_at": 0}
            for i in range(3)
        ]
        _queue_path(tmp_path).write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        runner = MagicMock(return_value=0)
        flush(tmp_path, _make_config(), runner=runner)
        assert runner.call_count == 3
        assert not _queue_path(tmp_path).exists()

    def test_partial_failure_keeps_remaining(self, tmp_path):
        (tmp_path / "tasks").mkdir()
        entries = [
            {"action": "a", "ticket_id": "T-001", "payload": {"cmd": ["gh", "ok"]}, "queued_at": 0},
            {"action": "b", "ticket_id": "T-002", "payload": {"cmd": ["gh", "fail"]}, "queued_at": 0},
        ]
        _queue_path(tmp_path).write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        # first call succeeds, second fails
        runner = MagicMock(side_effect=[0, 1])
        flush(tmp_path, _make_config(), runner=runner)
        remaining = json.loads(_queue_path(tmp_path).read_text().strip())
        assert remaining["ticket_id"] == "T-002"


class TestCLITransitions:
    def test_unblock_blocked_to_ready(self, tmp_path):
        from orc.cli import cmd_unblock, build_parser
        (tmp_path / "tasks").mkdir()
        p = tmp_path / "tasks" / "T-001.md"
        p.write_text("---\nid: T-001\ntitle: T\nstatus: blocked\ndepends_on: []\n---\n\nBody.\n")
        parser = build_parser()
        args = parser.parse_args(["--repo", str(tmp_path), "unblock", "T-001"])
        with patch("orc.cli.human"):
            result = cmd_unblock(args)
        assert result == 0
        assert parse_ticket(p).status == "ready"

    def test_unblock_escalated_to_ready(self, tmp_path):
        from orc.cli import cmd_unblock, build_parser
        (tmp_path / "tasks").mkdir()
        p = tmp_path / "tasks" / "T-001.md"
        p.write_text("---\nid: T-001\ntitle: T\nstatus: escalated\ndepends_on: []\n---\n\nBody.\n")
        parser = build_parser()
        args = parser.parse_args(["--repo", str(tmp_path), "unblock", "T-001"])
        with patch("orc.cli.human"):
            result = cmd_unblock(args)
        assert result == 0
        assert parse_ticket(p).status == "ready"

    def test_done_escalated_to_done(self, tmp_path):
        from orc.cli import cmd_done, build_parser
        (tmp_path / "tasks").mkdir()
        p = tmp_path / "tasks" / "T-001.md"
        p.write_text("---\nid: T-001\ntitle: T\nstatus: escalated\ndepends_on: []\n---\n\nBody.\n")
        parser = build_parser()
        args = parser.parse_args(["--repo", str(tmp_path), "done", "T-001"])
        with patch("orc.cli.human"):
            result = cmd_done(args)
        assert result == 0
        assert parse_ticket(p).status == "done"

    def test_done_wrong_status_fails(self, tmp_path):
        from orc.cli import cmd_done, build_parser
        (tmp_path / "tasks").mkdir()
        p = tmp_path / "tasks" / "T-001.md"
        p.write_text("---\nid: T-001\ntitle: T\nstatus: ready\ndepends_on: []\n---\n\nBody.\n")
        parser = build_parser()
        args = parser.parse_args(["--repo", str(tmp_path), "done", "T-001"])
        with patch("orc.cli.human"):
            result = cmd_done(args)
        assert result == 1
