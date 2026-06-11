from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orc.ticket import Ticket

_WIP_STATUSES = {"in_progress", "escalated"}


@dataclass
class Wave:
    index: int
    tickets: list["Ticket"]
    mode: str  # "parallel" | "sequential"


def _extract_files(body: str) -> set[str]:
    files: set[str] = set()
    for line in body.splitlines():
        m = re.match(r"[-*]?\s*(?:CREATE|MODIFY)\s*:\s*(.+)", line.strip(), re.IGNORECASE)
        if m:
            for part in m.group(1).split(","):
                part = re.sub(r"\s*\(.*\)\s*$", "", part.strip())
                if part:
                    files.add(part)
    return files


def eligible(tickets: list["Ticket"], night: bool, wip_cap: int) -> list["Ticket"]:
    wip = sum(1 for t in tickets if t.status in _WIP_STATUSES)
    if wip >= wip_cap:
        return []

    done_ids = {t.id for t in tickets if t.status == "done"}
    result: list["Ticket"] = []

    for t in tickets:
        if t.status != "ready":
            continue
        if not all(dep in done_ids for dep in t.depends_on):
            continue
        if night and not t.night_batch:
            continue
        result.append(t)

    return sorted(result, key=lambda t: t.id)


def detect_cycles(tickets: list["Ticket"]) -> set[str]:
    id_set = {t.id for t in tickets}

    missing: set[str] = {
        t.id for t in tickets if any(dep not in id_set for dep in t.depends_on)
    }

    dependents: dict[str, list[str]] = {t.id: [] for t in tickets}
    in_degree: dict[str, int] = {t.id: 0 for t in tickets}

    for t in tickets:
        if t.id in missing:
            continue
        for dep in t.depends_on:
            if dep in dependents:
                dependents[dep].append(t.id)
                in_degree[t.id] += 1

    queue: deque[str] = deque(
        tid for tid, deg in in_degree.items() if deg == 0 and tid not in missing
    )
    processed: set[str] = set()

    while queue:
        tid = queue.popleft()
        processed.add(tid)
        for child in dependents[tid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    cyclic = {t.id for t in tickets if t.id not in processed and t.id not in missing}
    return missing | cyclic


def group_waves(eligible_tickets: list["Ticket"]) -> list[Wave]:
    sorted_tickets = sorted(eligible_tickets, key=lambda t: t.id)

    parallel_candidates = [t for t in sorted_tickets if t.parallel_safe is True]
    sequential_tickets = [t for t in sorted_tickets if t.parallel_safe is not True]

    raw_waves: list[tuple[str, list["Ticket"], str]] = []

    current_batch: list["Ticket"] = []
    current_files: set[str] = set()

    for t in parallel_candidates:
        t_files = _extract_files(t.body)
        if current_batch and t_files & current_files:
            raw_waves.append((current_batch[0].id, current_batch, "parallel"))
            current_batch = [t]
            current_files = t_files
        else:
            current_batch.append(t)
            current_files |= t_files

    if current_batch:
        raw_waves.append((current_batch[0].id, current_batch, "parallel"))

    for t in sequential_tickets:
        raw_waves.append((t.id, [t], "sequential"))

    raw_waves.sort(key=lambda w: w[0])
    return [Wave(index=i, tickets=w[1], mode=w[2]) for i, w in enumerate(raw_waves)]
