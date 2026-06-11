from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class BadConfig(Exception):
    pass


@dataclass
class HarnessConfig:
    command: str


@dataclass
class GitHubConfig:
    enabled: bool = False
    repo: str | None = None


@dataclass
class Config:
    repo: str
    wip_cap: int
    night_wallclock_minutes: int
    max_parallel: int
    default_branch: str
    memory_file: str
    timeouts: dict[str, int]
    harness: dict[str, HarnessConfig]
    github: GitHubConfig = field(default_factory=GitHubConfig)


_REQUIRED = {"repo", "wip_cap", "night_wallclock_minutes", "max_parallel", "default_branch", "memory_file"}


def load(path: Path) -> Config:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise BadConfig(f"Config file not found: {path}")
    except tomllib.TOMLDecodeError as e:
        raise BadConfig(f"Config parse error: {e}")

    missing = _REQUIRED - data.keys()
    if missing:
        raise BadConfig(f"Missing required config fields: {', '.join(sorted(missing))}")

    if "timeouts" not in data:
        raise BadConfig("Missing required config section: [timeouts]")
    timeouts_raw = data["timeouts"]
    if not isinstance(timeouts_raw, dict):
        raise BadConfig("[timeouts] must be a table")

    harness_raw = data.get("harness", {})
    harness: dict[str, HarnessConfig] = {}
    for tier, hconf in harness_raw.items():
        if not isinstance(hconf, dict) or "command" not in hconf:
            raise BadConfig(f"[harness.{tier!r}] missing 'command'")
        harness[tier] = HarnessConfig(command=str(hconf["command"]))

    gh_raw = data.get("github", {})
    github = GitHubConfig(
        enabled=bool(gh_raw.get("enabled", False)),
        repo=gh_raw.get("repo"),
    )

    return Config(
        repo=str(data["repo"]),
        wip_cap=int(data["wip_cap"]),
        night_wallclock_minutes=int(data["night_wallclock_minutes"]),
        max_parallel=int(data["max_parallel"]),
        default_branch=str(data["default_branch"]),
        memory_file=str(data["memory_file"]),
        timeouts={k: int(v) for k, v in timeouts_raw.items()},
        harness=harness,
        github=github,
    )
