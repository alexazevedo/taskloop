from __future__ import annotations

import subprocess
from pathlib import Path


def run(commands: list[str], workdir: Path, timeout: int) -> tuple[bool, str]:
    if not commands:
        return True, ""

    parts: list[str] = []
    ok = True

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
            )
            parts.append(result.stdout + result.stderr)
            if result.returncode != 0:
                ok = False
        except subprocess.TimeoutExpired:
            parts.append(f"[TIMEOUT after {timeout}s]\n")
            ok = False

    return ok, "".join(parts)
