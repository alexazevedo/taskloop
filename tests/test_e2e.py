"""
End-to-end integration tests covering the Stage 5 checklist.
"""
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch

from orc.config import Config, HarnessConfig, GitHubConfig
from orc.runner import run as runner_run
from orc.ticket import parse as parse_ticket

FAKE_HARNESS = Path(__file__).parent / "fakes" / "fake_harness.py"
PYTHON = sys.executable


def _config(repo: Path, mode: str = "pass", wip_cap: int = 5, timeout: int = 10) -> Config:
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


def _setup_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    local = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(local)], check=True, capture_output=True)
    for cmd in [
        ["git", "-C", str(local), "config", "user.email", "test@test.com"],
        ["git", "-C", str(local), "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, check=True, capture_output=True)
    (local / "README.md").write_text("# Repo")
    (local / "tasks").mkdir()
    (local / "tasks" / "reports").mkdir()
    subprocess.run(["git", "-C", str(local), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local), "push", "origin", "HEAD"], check=True, capture_output=True)
    return local


def _write_ticket(
    repo: Path,
    tid: str,
    status: str = "ready",
    depends_on: list[str] | None = None,
    tier: str = "TEST",
    retry_budget: int = 2,
    branch: str | None = None,
    night_batch: bool | None = None,
    body: str = "Body.",
) -> None:
    deps = f"[{', '.join(depends_on or [])}]"
    nb_line = f"night_batch: {'true' if night_batch else 'false'}\n" if night_batch is not None else ""
    (repo / "tasks" / f"{tid}.md").write_text(
        f"---\nid: {tid}\ntitle: Task {tid}\nstatus: {status}\n"
        f"depends_on: {deps}\ntier: {tier}\nretry_budget: {retry_budget}\n"
        f"branch: {branch or f'task/{tid}'}\n{nb_line}"
        f"verify:\n  - test -f orc-output.txt\n---\n\n{body}\n"
    )


# --- Stage 5 checklist ---

def test_e2e_day_run_happy_path(tmp_path):
    """Step 1: day run — ticket goes ready → done, branch pushed."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001")
    runner_run(repo, night=False, config=_config(repo, "pass"))
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "done"
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-remote", "--heads", "origin", "task/T-001"],
        capture_output=True, text=True,
    )
    assert "task/T-001" in result.stdout


def test_e2e_escalation_with_report(tmp_path):
    """Step 2: exhausted retry budget → escalated, report written, branch not pushed."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001", retry_budget=1)
    runner_run(repo, night=False, config=_config(repo, "fail"))
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "escalated"
    assert (repo / "tasks" / "reports" / "T-001-failure.md").exists()
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-remote", "--heads", "origin", "task/T-001"],
        capture_output=True, text=True,
    )
    assert "task/T-001" not in result.stdout


def test_e2e_night_filter(tmp_path):
    """Step 3: night run — only night_batch=true tickets run."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001", night_batch=True)
    _write_ticket(repo, "T-002", night_batch=False)
    runner_run(repo, night=True, config=_config(repo, "pass"))
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "done"
    assert parse_ticket(repo / "tasks" / "T-002.md").status == "ready"


def test_e2e_dry_run_mutates_nothing(tmp_path):
    """Step 4: --dry-run prints plan, changes no files."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001")
    before = (repo / "tasks" / "T-001.md").read_bytes()
    runner_run(repo, night=False, config=_config(repo, "pass"), dry_run=True)
    assert (repo / "tasks" / "T-001.md").read_bytes() == before
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "ready"


def test_e2e_dependency_gating(tmp_path):
    """Step 5: T-002 waits until T-001 is done."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001")
    _write_ticket(repo, "T-002", depends_on=["T-001"])
    runner_run(repo, night=False, config=_config(repo, "pass"))
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "done"
    assert parse_ticket(repo / "tasks" / "T-002.md").status == "done"


def test_e2e_wip_cap_halts_intake(tmp_path):
    """Step 6: WIP cap prevents T-003 from running."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001", status="escalated")
    _write_ticket(repo, "T-002", status="escalated")
    _write_ticket(repo, "T-003")
    runner_run(repo, night=False, config=_config(repo, "pass", wip_cap=2))
    assert parse_ticket(repo / "tasks" / "T-003.md").status == "ready"


def test_e2e_crash_recovery(tmp_path):
    """Step 7: in_progress ticket reset to ready on startup then runs to done."""
    repo = _setup_repo(tmp_path)
    _write_ticket(repo, "T-001", status="in_progress")
    runner_run(repo, night=False, config=_config(repo, "pass"))
    assert parse_ticket(repo / "tasks" / "T-001.md").status == "done"


def test_e2e_orc_status_and_cli_transitions(tmp_path):
    """Step 8: CLI unblock and done transitions work correctly."""
    from orc.cli import cmd_unblock, cmd_done, build_parser

    repo = _setup_repo(tmp_path)
    p = repo / "tasks" / "T-001.md"
    p.write_text(
        "---\nid: T-001\ntitle: T\nstatus: blocked\ndepends_on: []\n---\n\nBody.\n"
    )

    parser = build_parser()
    args = parser.parse_args(["--repo", str(repo), "unblock", "T-001"])
    with patch("orc.cli.human"):
        assert cmd_unblock(args) == 0
    assert parse_ticket(p).status == "ready"

    p.write_text(
        "---\nid: T-001\ntitle: T\nstatus: escalated\ndepends_on: []\n---\n\nBody.\n"
    )
    args = parser.parse_args(["--repo", str(repo), "done", "T-001"])
    with patch("orc.cli.human"):
        assert cmd_done(args) == 0
    assert parse_ticket(p).status == "done"
