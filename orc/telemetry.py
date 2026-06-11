from __future__ import annotations

import json
import time
from pathlib import Path


def record(
    repo: Path,
    ticket_id: str,
    tier: str,
    attempt: int,
    seconds: float,
    verify_result: str,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
    ts: float | None = None,
) -> None:
    entry = {
        "ticket_id": ticket_id,
        "tier": tier,
        "attempt": attempt,
        "seconds": round(seconds, 3),
        "verify_result": verify_result,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "ts": ts if ts is not None else time.time(),
    }
    log_path = repo / "tasks" / ".telemetry.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
