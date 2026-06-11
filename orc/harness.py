from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orc.config import Config
    from orc.ticket import Ticket

TIMEOUT = -1


def assemble_context(
    ticket: "Ticket",
    repo: Path,
    memory_file: str = "CLAUDE.md",
    prior_errors: str = "",
) -> Path:
    parts: list[str] = []

    memory_path = repo / memory_file
    if memory_path.exists():
        parts.append(memory_path.read_text(encoding="utf-8"))

    parts.append(ticket.body)

    if prior_errors:
        parts.append(f"\n## Previous attempt errors\n\n{prior_errors}\n")

    fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="orc-context-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts))

    return Path(tmp_path)


def dispatch(
    tier: str,
    context_path: Path,
    workdir: Path,
    config: "Config",
) -> tuple[int, str]:
    harness_conf = config.harness.get(tier)
    if not harness_conf:
        raise ValueError(f"No harness configured for tier {tier!r}")

    timeout = config.timeouts.get(tier, 1800)
    cmd = harness_conf.command.replace("{context}", str(context_path)).replace(
        "{workdir}", str(workdir)
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return TIMEOUT, ""
