# orc — ticket orchestrator

Stateless batch CLI that executes AI coding tickets against a single git repository.

## Install

```bash
uv tool install .          # installs `orc` globally
# or for development:
uv sync && uv run orc --help
```

## Quick start

```bash
# copy and edit config
cp orchestrator.toml.example orchestrator.toml

# check ticket status
orc status --repo /path/to/repo

# day run (dispatch eligible tickets)
orc run --repo /path/to/repo --config orchestrator.toml

# dry run (print plan, no dispatch)
orc run --dry-run --repo /path/to/repo --config orchestrator.toml

# night run
orc run --night --repo /path/to/repo --config orchestrator.toml
```

## Config (`orchestrator.toml`)

```toml
repo = "."                       # target repo; --repo overrides
wip_cap = 5                      # max escalated+in_progress tickets
night_wallclock_minutes = 360    # budget for night runs
max_parallel = 3
default_branch = "main"
memory_file = "CLAUDE.md"

[timeouts]
API-MID = 1800

[harness."API-MID"]
command = "claude -p --model claude-sonnet-4-6 --dangerously-skip-permissions --cwd {workdir} < {context}"

[github]
enabled = true
repo = "owner/name"
```

## Ticket contract

Each `tasks/T-*.md` file has a YAML front-matter block followed by an immutable body:

```markdown
---
id: T-001
title: "Short description"
status: ready            # ready | blocked | in_progress | done | escalated | failed
depends_on: [T-000]      # list of prerequisite ticket ids
tier: API-MID            # matches a [harness."TIER"] key
retry_budget: 3
escalate_to: API-FRONTIER
branch: task/T-001
night_batch: false
parallel_safe: false
verify:
  - uv run pytest tests/test_foo.py -q
  - uv run ruff check src/foo.py
---

# Task body (immutable)

...spec for the AI agent...
```

## CLI commands

| Command | Description |
|---------|-------------|
| `orc run [--night] [--dry-run]` | Run eligible tickets |
| `orc status` | Print ticket table and WIP count |
| `orc sync` | Flush `.sync-queue` to GitHub |
| `orc unblock T-XXX` | blocked/escalated → ready |
| `orc done T-XXX` | escalated → done (after manual fix) |

## Daily / nightly workflow

**Day:** run `orc run` manually or via CI. Eligible = `status==ready` AND all deps `done`.

**Night:** set `night_batch: true` on long-running tickets. Schedule `orc run --night`; it respects `night_wallclock_minutes`.

**Escalation:** when a ticket exhausts its retry budget, `status` becomes `escalated` and a report is written to `tasks/reports/`. Human reviews, fixes, then runs `orc unblock T-XXX` to retry or `orc done T-XXX` to accept.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check orc tests
```

See `docs/scheduling.md` for launchd/cron setup.
