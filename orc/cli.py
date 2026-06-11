from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orc import ticket as ticket_mod
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


def cmd_not_implemented(args: argparse.Namespace) -> int:
    human("not implemented")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orc", description="Ticket orchestrator")
    parser.add_argument("--repo", default=".", help="Path to target repo")

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
    elif args.command in ("run", "sync", "unblock", "done"):
        sys.exit(cmd_not_implemented(args))
    else:
        parser.print_help()
        sys.exit(1)
