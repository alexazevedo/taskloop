from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


class LockHeld(Exception):
    pass


@dataclass
class Lock:
    path: Path

    def release(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire(repo: Path, stale_seconds: int = 14400) -> Lock:
    lock_path = repo / "tasks" / ".orc.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_text())
            pid = int(data["pid"])
            age = time.time() - float(data["timestamp"])
            if _pid_alive(pid) and age < stale_seconds:
                raise LockHeld(
                    f"Lock held by PID {pid} (age {age:.0f}s). "
                    f"Remove {lock_path} if the process is dead."
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # corrupted lock → reclaim

    lock_path.write_text(json.dumps({"pid": os.getpid(), "timestamp": time.time()}))
    return Lock(path=lock_path)


def release(lock: Lock) -> None:
    lock.release()
