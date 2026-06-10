from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orc.ticket import Ticket

logger = logging.getLogger(__name__)

LEGAL: dict[str, set[str]] = {
    "ready": {"in_progress", "blocked", "failed"},
    "in_progress": {"done", "escalated", "ready", "failed"},
    "blocked": {"ready", "failed"},
    "escalated": {"done", "ready", "failed"},
    "done": {"failed"},
    "failed": set(),
}

_TERMINALS = {"done", "failed"}


class IllegalTransition(Exception):
    pass


def transition(ticket: Ticket, to: str) -> None:
    from orc.ticket import write_frontmatter

    frm = ticket.status
    allowed = LEGAL.get(frm, set())

    if to not in allowed:
        raise IllegalTransition(
            f"Illegal transition {frm!r} -> {to!r} for ticket {ticket.id!r}"
        )

    logger.info("ticket %s: %s -> %s", ticket.id, frm, to)
    ticket.status = to
    write_frontmatter(ticket)
