import sys
import subprocess
import pytest
from pathlib import Path

from orc.config import Config, HarnessConfig, GitHubConfig
from orc.ticket import parse as parse_ticket
from orc.runner import run

FAKE_HARNESS = Path(__file__).parent / "fakes" / "fake_harness.py"
PYTHON = sys.executable


def _make_config(repo: Path, mode: str = "pass", wip_cap: int = 5, timeout: int = 10) -> Config:
    return Config(
        repo=str(repo),
        wip_cap=wip_cap,
        night_wallclock_minutes=360,
        max_parallel=2,
        default_branch=_default_branch(repo),
        memory_file="CLAUDE.md",
        timeouts={"TEST": timeout},
        harness={"TEST": HarnessConfig(
            command=f"FAKE_MODE={mode} {PYTHON} {FAKE_HARNESS} {{context}} {{workdir}}"
        )},
        github=GitHubConfig(),
    )


def _default_branch(repo: Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() or "main"


def _git_setup(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    local = tmp_path / "repo"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(local)], check=True, capture_output=True)

    for cfg in [
        ["git", "-C", str(local), "config", "user.email", "test@test.com"],
        ["git", "-C", str(local), "config", "user.name", "Test"],
    ]:
        subprocess.run(cfg, check=True, capture_output=True)

    (local / "README.md").write_text("# Repo")
    (local / "tasks").mkdir()
    (local / "tasks" / "reports").mkdir()

    subprocess.run(["git", "-C", str(local), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(local), "commit", "-m", "init"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(local), "push", "origin", "HEAD"], check=True, capture_output=True
    )
    return local


def _write_ticket(
    repo: Path,
    tid: str,
    status: str = "ready",
    depends_on: list[str] | None = None,
    tier: str = "TEST",
    retry_budget: int = 2,
    branch: str | None = None,
    body_lines: list[str] | None = None,
) -> None:
    deps = f"[{', '.join(depends_on or [])}]"
    branch_name = branch or f"task/{tid}"
    body = "\n".join(body_lines or [f"# {tid}", "Body."])
    content = (
        f"---\n"
        f"id: {tid}\n"
        f"title: Task {tid}\n"
        f"status: {status}\n"
        f"depends_on: {deps}\n"
        f"tier: {tier}\n"
        f"retry_budget: {retry_budget}\n"
        f"branch: {branch_name}\n"
        f"verify:\n"
        f"  - test -f orc-output.txt\n"
        f"---\n\n"
        f"{body}\n"
    )
    (repo / "tasks" / f"{tid}.md").write_text(content)


class TestHappyPath:
    def test_ticket_goes_done_and_branch_pushed(self, tmp_path):
        repo = _git_setup(tmp_path)
        _write_ticket(repo, "T-001")
        config = _make_config(repo, mode="pass")

        run(repo, night=False, config=config)

        ticket = parse_ticket(repo / "tasks" / "T-001.md")
        assert ticket.status == "done"

        # Branch pushed to remote
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-remote", "--heads", "origin", "task/T-001"],
            capture_output=True, text=True,
        )
        assert "task/T-001" in result.stdout


class TestEscalationPath:
    def test_ticket_escalated_with_report(self, tmp_path):
        repo = _git_setup(tmp_path)
        _write_ticket(repo, "T-001", retry_budget=2)
        config = _make_config(repo, mode="fail")

        run(repo, night=False, config=config)

        ticket = parse_ticket(repo / "tasks" / "T-001.md")
        assert ticket.status == "escalated"

        report = repo / "tasks" / "reports" / "T-001-failure.md"
        assert report.exists()
        content = report.read_text()
        assert "T-001" in content

    def test_escalated_branch_not_pushed(self, tmp_path):
        repo = _git_setup(tmp_path)
        _write_ticket(repo, "T-001", retry_budget=1)
        config = _make_config(repo, mode="fail")

        run(repo, night=False, config=config)

        result = subprocess.run(
            ["git", "-C", str(repo), "ls-remote", "--heads", "origin", "task/T-001"],
            capture_output=True, text=True,
        )
        assert "task/T-001" not in result.stdout


class TestWipCap:
    def test_wip_cap_halts_intake(self, tmp_path):
        repo = _git_setup(tmp_path)
        # escalated tickets count as WIP and are not reset by crash recovery
        _write_ticket(repo, "T-001", status="escalated")
        _write_ticket(repo, "T-002", status="escalated")
        _write_ticket(repo, "T-003")
        config = _make_config(repo, mode="pass", wip_cap=2)

        run(repo, night=False, config=config)

        ticket = parse_ticket(repo / "tasks" / "T-003.md")
        assert ticket.status == "ready"


class TestCrashRecovery:
    def test_in_progress_reset_to_ready_on_startup(self, tmp_path):
        repo = _git_setup(tmp_path)
        _write_ticket(repo, "T-001", status="in_progress")
        config = _make_config(repo, mode="pass")

        run(repo, night=False, config=config)

        # After run, ticket should be done (recovered → ready → dispatched → done)
        ticket = parse_ticket(repo / "tasks" / "T-001.md")
        assert ticket.status == "done"


class TestPlanReviewTrigger:
    def test_plan_review_blocks_same_region_ready_tickets(self, tmp_path):
        repo = _git_setup(tmp_path)
        # T-001 and T-002 escalate in region "orc"
        _write_ticket(
            repo, "T-001", retry_budget=1,
            body_lines=["# T-001", "- CREATE: orc/foo.py"],
        )
        _write_ticket(
            repo, "T-002", retry_budget=1,
            body_lines=["# T-002", "- CREATE: orc/bar.py"],
        )
        # T-003 is in same region, no dep on T-001/T-002 (eligible)
        _write_ticket(
            repo, "T-003",
            body_lines=["# T-003", "- CREATE: orc/baz.py"],
        )
        config = _make_config(repo, mode="fail")

        run(repo, night=False, config=config)

        t1 = parse_ticket(repo / "tasks" / "T-001.md")
        t2 = parse_ticket(repo / "tasks" / "T-002.md")
        assert t1.status == "escalated"
        assert t2.status == "escalated"

        t3 = parse_ticket(repo / "tasks" / "T-003.md")
        assert t3.status == "blocked"
