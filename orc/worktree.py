from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd!r} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def path(repo: Path, branch: str) -> Path:
    slug = branch.replace("/", "-").replace(" ", "-")
    return repo / ".orc-worktrees" / slug


_worktree_path = path


def ensure(repo: Path, branch: str, base_branch: str = "main") -> Path:
    wt_path = path(repo, branch)
    if wt_path.exists():
        return wt_path

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    existing = subprocess.run(
        ["git", "branch", "--list", branch],
        capture_output=True, text=True, cwd=repo,
    )
    if existing.stdout.strip():
        _run(["git", "worktree", "add", str(wt_path), branch], repo)
    else:
        _run(["git", "worktree", "add", "-b", branch, str(wt_path), base_branch], repo)

    return wt_path


def reset(path: Path) -> None:
    _run(["git", "reset", "--hard", "HEAD"], path)
    _run(["git", "clean", "-fd"], path)


def prune(repo: Path) -> None:
    _run(["git", "worktree", "prune"], repo)
