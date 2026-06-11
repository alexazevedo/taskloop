from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from orc.config import Config
    from orc.ticket import Ticket

SyncRunner = Callable[[list[str]], int]


def _default_runner(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True).returncode


def _queue_path(repo: Path) -> Path:
    return repo / "tasks" / ".sync-queue"


def _enqueue(repo: Path, entry: dict) -> None:
    path = _queue_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _build_cmd(action: str, ticket: "Ticket", config: "Config") -> list[str] | None:
    if not config.github.enabled or not config.github.repo:
        return None

    gh_repo = config.github.repo

    if action == "create":
        return [
            "gh", "issue", "create",
            "--repo", gh_repo,
            "--title", f"[{ticket.id}] {ticket.title}",
            "--body", f"Ticket: {ticket.id}\nStatus: {ticket.status}",
            "--label", ticket.status,
        ]
    if action == "update_labels":
        if ticket.github_issue is None:
            return None
        return [
            "gh", "issue", "edit",
            str(ticket.github_issue),
            "--repo", gh_repo,
            "--add-label", ticket.status,
        ]
    if action == "comment":
        if ticket.github_issue is None:
            return None
        return [
            "gh", "issue", "comment",
            str(ticket.github_issue),
            "--repo", gh_repo,
            "--body", f"Status changed to: {ticket.status}",
        ]
    return None


def mirror(
    action: str,
    ticket: "Ticket",
    config: "Config",
    repo: Path,
    runner: SyncRunner | None = None,
) -> None:
    if runner is None:
        runner = _default_runner

    cmd = _build_cmd(action, ticket, config)
    if cmd is None:
        return

    exit_code = runner(cmd)
    if exit_code != 0:
        _enqueue(repo, {
            "action": action,
            "ticket_id": ticket.id,
            "payload": {"cmd": cmd},
            "queued_at": time.time(),
        })


def flush(repo: Path, config: "Config", runner: SyncRunner | None = None) -> None:
    if runner is None:
        runner = _default_runner

    queue_path = _queue_path(repo)
    if not queue_path.exists():
        return

    entries: list[dict] = []
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not entries:
        queue_path.unlink(missing_ok=True)
        return

    remaining: list[dict] = []
    for entry in entries:
        cmd = entry.get("payload", {}).get("cmd")
        if not cmd:
            continue
        if runner(cmd) != 0:
            remaining.append(entry)

    if remaining:
        queue_path.write_text(
            "\n".join(json.dumps(e) for e in remaining) + "\n",
            encoding="utf-8",
        )
    else:
        queue_path.unlink(missing_ok=True)
