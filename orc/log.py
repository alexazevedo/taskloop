from __future__ import annotations

import json
from pathlib import Path


def human(msg: str) -> None:
    print(msg, flush=True)


def event(record: dict, log_path: Path | None = None) -> None:
    line = json.dumps(record, default=str)
    if log_path is None:
        log_path = Path("tasks/.orc.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
