from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from orc import state

if TYPE_CHECKING:
    from orc.ticket import Ticket


def _code_region(ticket: "Ticket") -> str | None:
    for line in ticket.body.splitlines():
        m = re.match(r"[-*]?\s*CREATE\s*:\s*(.+)", line.strip(), re.IGNORECASE)
        if m:
            files = [f.strip() for f in m.group(1).split(",")]
            for f in files:
                f = re.sub(r"\s*\(.*\)\s*$", "", f.strip())
                if f:
                    parent = str(Path(f).parent)
                    return parent if parent != "." else f
    return None


def write_report(ticket: "Ticket", attempts: list[dict]) -> None:
    report_dir = ticket.path.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{ticket.id}-failure.md"

    lines = [
        f"# Failure report: {ticket.id}\n\n",
        f"**Title:** {ticket.title}\n",
        f"**Tier:** {ticket.tier}\n",
        f"**Attempts:** {len(attempts)}\n\n",
        "## Attempt log\n",
    ]

    for a in attempts:
        lines.append(f"\n### Attempt {a['n']}: {a['outcome']}\n")
        if a.get("verify_output"):
            lines.append("```\n")
            lines.append(a["verify_output"])
            lines.append("\n```\n")

    report_path.write_text("".join(lines), encoding="utf-8")


def plan_review_check(tickets: list["Ticket"]) -> str:
    region_escalations: dict[str, list[str]] = {}
    for t in tickets:
        if t.status == "escalated":
            region = _code_region(t)
            if region:
                region_escalations.setdefault(region, []).append(t.id)

    trigger_regions = {r: ids for r, ids in region_escalations.items() if len(ids) >= 2}
    if not trigger_regions:
        return ""

    blocked: list[str] = []
    for t in tickets:
        if t.status == "ready":
            region = _code_region(t)
            if region in trigger_regions:
                try:
                    state.transition(t, "blocked")
                    blocked.append(t.id)
                except state.IllegalTransition:
                    pass

    banner = ["[PLAN REVIEW] ≥2 escalations in these code regions:"]
    for region, ids in sorted(trigger_regions.items()):
        banner.append(f"  {region}: {', '.join(sorted(ids))}")
    if blocked:
        banner.append(f"  Blocked dependent tickets: {', '.join(sorted(blocked))}")

    return "\n".join(banner)
