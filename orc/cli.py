from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orc import github as github_mod
from orc import state
from orc import ticket as ticket_mod
from orc.config import BadConfig, load as load_config
from orc.log import human


def _load_tickets(repo: Path) -> list[ticket_mod.Ticket]:
    tasks_dir = repo / "tasks"
    if not tasks_dir.exists():
        return []
    tickets: list[ticket_mod.Ticket] = []
    for p in sorted(tasks_dir.glob("T-*.md")):
        try:
            tickets.append(ticket_mod.parse(p))
        except ticket_mod.MalformedTicket as e:
            human(f"[warn] skipping malformed ticket: {e}")
    tickets.sort(key=lambda t: t.id)
    return tickets


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    tickets = _load_tickets(repo)

    if not tickets:
        human("No tickets found.")
        human("WIP: 0")
        return 0

    headers = ["ID", "TITLE", "STATUS", "TIER", "ATTEMPTS", "WAVE"]
    rows = [
        [
            t.id,
            t.title,
            t.status,
            str(t.tier) if t.tier is not None else "—",
            "0",
            "—",
        ]
        for t in tickets
    ]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    human(fmt.format(*headers))
    human("  ".join("-" * w for w in widths))
    for row in rows:
        human(fmt.format(*row))

    wip = sum(1 for t in tickets if t.status in {"in_progress", "escalated"})
    human(f"\nWIP: {wip}")
    return 0


def _find_ticket(repo: Path, ticket_id: str) -> ticket_mod.Ticket | None:
    path = repo / "tasks" / f"{ticket_id}.md"
    if not path.exists():
        human(f"[error] ticket not found: {path}")
        return None
    try:
        return ticket_mod.parse(path)
    except ticket_mod.MalformedTicket as e:
        human(f"[error] malformed ticket: {e}")
        return None


def cmd_sync(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    config_path = Path(args.config)
    try:
        config = load_config(config_path)
    except BadConfig as e:
        human(f"[error] {e}")
        return 1
    github_mod.flush(repo, config)
    human("sync complete.")
    return 0


def cmd_unblock(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    ticket = _find_ticket(repo, args.ticket_id)
    if ticket is None:
        return 1
    if ticket.status not in {"blocked", "escalated"}:
        human(f"[error] {ticket.id} has status {ticket.status!r}; expected blocked or escalated")
        return 1
    try:
        state.transition(ticket, "ready")
        human(f"{ticket.id} → ready")
        return 0
    except state.IllegalTransition as e:
        human(f"[error] {e}")
        return 1


def cmd_done(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    ticket = _find_ticket(repo, args.ticket_id)
    if ticket is None:
        return 1
    if ticket.status != "escalated":
        human(f"[error] {ticket.id} has status {ticket.status!r}; expected escalated")
        return 1
    try:
        state.transition(ticket, "done")
        human(f"{ticket.id} → done")
        return 0
    except state.IllegalTransition as e:
        human(f"[error] {e}")
        return 1


def cmd_not_implemented(args: argparse.Namespace) -> int:
    human("not implemented")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orc", description="Ticket orchestrator")
    parser.add_argument("--repo", default=".", help="Path to target repo")
    parser.add_argument("--config", default="orchestrator.toml", help="Path to config file")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run eligible tickets")
    sub.add_parser("status", help="Print ticket status table")
    sub.add_parser("sync", help="Flush sync queue")

    unblock_p = sub.add_parser("unblock", help="Unblock a ticket")
    unblock_p.add_argument("ticket_id")

    done_p = sub.add_parser("done", help="Mark ticket done")
    done_p.add_argument("ticket_id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        sys.exit(cmd_status(args))
    elif args.command == "sync":
        sys.exit(cmd_sync(args))
    elif args.command == "unblock":
        sys.exit(cmd_unblock(args))
    elif args.command == "done":
        sys.exit(cmd_done(args))
    elif args.command == "run":
        sys.exit(cmd_not_implemented(args))
    else:
        parser.print_help()
        sys.exit(1)
