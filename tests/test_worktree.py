import subprocess
import pytest
from pathlib import Path

from orc.worktree import ensure, reset, prune


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path
    for cmd in [
        ["git", "init", str(repo)],
        ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
        ["git", "-C", str(repo), "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, check=True, capture_output=True)

    (repo / "README.md").write_text("# Test repo")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)

    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    default_branch = result.stdout.strip()
    return repo, default_branch


def test_ensure_creates_worktree(git_repo):
    repo, default_branch = git_repo
    wt = ensure(repo, "task/feature-x", base_branch=default_branch)
    assert wt.exists()
    assert (wt / "README.md").exists()


def test_ensure_returns_existing_path(git_repo):
    repo, default_branch = git_repo
    wt1 = ensure(repo, "task/feature-x", base_branch=default_branch)
    wt2 = ensure(repo, "task/feature-x", base_branch=default_branch)
    assert wt1 == wt2


def test_reset_removes_untracked_files(git_repo):
    repo, default_branch = git_repo
    wt = ensure(repo, "task/feature-x", base_branch=default_branch)

    untracked = wt / "untracked.txt"
    untracked.write_text("noise")
    reset(wt)
    assert not untracked.exists()


def test_reset_restores_modified_tracked_file(git_repo):
    repo, default_branch = git_repo
    wt = ensure(repo, "task/feature-x", base_branch=default_branch)

    (wt / "README.md").write_text("modified")
    reset(wt)
    assert (wt / "README.md").read_text() == "# Test repo"


def test_prune_runs_without_error(git_repo):
    repo, _ = git_repo
    prune(repo)
