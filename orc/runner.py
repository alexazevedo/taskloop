from __future__ import annotations

import logging
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from orc import escalation as escalation_mod
from orc import github as github_mod
from orc import harness as harness_mod
from orc import locking
from orc import state
from orc import telemetry as telemetry_mod
from orc import ticket as ticket_mod
from orc import verify as verify_mod
from orc import worktree as worktree_mod
from orc.eligibility import detect_cycles, eligible, group_waves
from orc.log import human

if TYPE_CHECKING:
    from orc.config import Config

logger = logging.getLogger(__name__)

_WIP_STATUSES = {"in_progress", "escalated"}


def _load_tickets(repo: Path) -> list[ticket_mod.Ticket]:
    tasks_dir = repo / "tasks"
    if not tasks_dir.exists():
        return []
    tickets: list[ticket_mod.Ticket] = []
    for p in sorted(tasks_dir.glob("T-*.md")):
        try:
            tickets.append(ticket_mod.parse(p))
        except ticket_mod.MalformedTicket as e:
            human(f"[warn] skipping malformed ticket: {e}")
    return tickets


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + cmd, capture_output=True, text=True, cwd=cwd)


def _commit_and_push(wt_path: Path, ticket: ticket_mod.Ticket, attempt: int) -> bool:
    _git(["add", "-A"], wt_path)
    diff = _git(["diff", "--cached", "--quiet"], wt_path)
    if diff.returncode == 0:
        human(f"[{ticket.id}] no changes to commit; treating as success")
    else:
        msg = f"orc: {ticket.id} pass (attempt {attempt})"
        result = _git(["commit", "-m", msg], wt_path)
        if result.returncode != 0:
            logger.error("commit failed for %s: %s", ticket.id, result.stderr)
            return False

    result = _git(["push", "origin", ticket.branch], wt_path)
    if result.returncode != 0:
        logger.error("push failed for %s: %s", ticket.id, result.stderr)
        return False

    return True


def _run_ticket(ticket: ticket_mod.Ticket, repo: Path, config: "Config") -> None:
    # Re-read ticket in case it was blocked by plan_review_check between wave build and execution
    try:
        ticket = ticket_mod.parse(ticket.path)
    except ticket_mod.MalformedTicket:
        pass

    if ticket.status != "ready":
        human(f"[{ticket.id}] skipping: status={ticket.status!r}")
        return

    tier = str(ticket.tier) if ticket.tier else "API-MID"
    retry_budget = ticket.retry_budget if ticket.retry_budget else 3

    try:
        wt_path = worktree_mod.ensure(repo, str(ticket.branch), base_branch=config.default_branch)
        worktree_mod.reset(wt_path)
    except Exception as e:
        human(f"[error] {ticket.id}: worktree setup failed: {e}")
        state.transition(ticket, "ready")
        return

    state.transition(ticket, "in_progress")

    attempts: list[dict] = []
    prior_errors = ""

    for n in range(1, retry_budget + 1):
        human(f"[{ticket.id}] attempt {n}/{retry_budget} (tier={tier})")

        start = time.time()
        ctx_path = harness_mod.assemble_context(
            ticket, repo,
            memory_file=config.memory_file,
            prior_errors=prior_errors,
        )

        try:
            exit_code, harness_output = harness_mod.dispatch(tier, ctx_path, wt_path, config)
        finally:
            ctx_path.unlink(missing_ok=True)

        if exit_code == harness_mod.TIMEOUT:
            elapsed = time.time() - start
            outcome = "timeout"
            verify_ok = False
            verify_output = "[harness timed out]"
        else:
            verify_ok, verify_output = verify_mod.run(
                ticket.verify, wt_path,
                timeout=config.timeouts.get(tier, 1800),
            )
            elapsed = time.time() - start
            outcome = "pass" if verify_ok else "fail"

        telemetry_mod.record(
            repo=repo,
            ticket_id=ticket.id,
            tier=tier,
            attempt=n,
            seconds=elapsed,
            verify_result=outcome,
        )
        attempts.append({"n": n, "outcome": outcome, "verify_output": verify_output})

        if verify_ok:
            if _commit_and_push(wt_path, ticket, n):
                state.transition(ticket, "done")
                github_mod.mirror("update_labels", ticket, config, repo)
                human(f"[{ticket.id}] done after {n} attempt(s)")
                return
            prior_errors = "commit/push failed"
        else:
            prior_errors = verify_output

    escalation_mod.write_report(ticket, attempts)
    state.transition(ticket, "escalated")
    github_mod.mirror("comment", ticket, config, repo)
    human(f"[{ticket.id}] escalated after {retry_budget} attempt(s)")


def run(repo: Path, night: bool, config: "Config") -> None:
    lock = locking.acquire(repo)

    try:
        tickets = _load_tickets(repo)

        # Crash recovery: reset any in_progress to ready
        for t in tickets:
            if t.status == "in_progress":
                human(f"[recovery] resetting {t.id} from in_progress to ready")
                wt = worktree_mod.path(repo, str(t.branch))
                if wt.exists():
                    shutil.rmtree(wt, ignore_errors=True)
                state.transition(t, "ready")
        worktree_mod.prune(repo)

        github_mod.flush(repo, config)

        tickets = _load_tickets(repo)

        bad_ids = detect_cycles(tickets)
        if bad_ids:
            human(f"[warn] skipping tickets with cycles/missing deps: {sorted(bad_ids)}")

        waves = group_waves(eligible(tickets, night=night, wip_cap=config.wip_cap))

        if not waves:
            human("No eligible tickets.")
            return

        for wave in waves:
            tickets = _load_tickets(repo)
            wip = sum(1 for t in tickets if t.status in _WIP_STATUSES)
            if wip >= config.wip_cap:
                human(
                    f"WIP cap reached ({wip}/{config.wip_cap}); "
                    "drain the queue before more work is pulled."
                )
                break

            if wave.mode == "parallel":
                with ThreadPoolExecutor(max_workers=config.max_parallel) as pool:
                    futs = {
                        pool.submit(_run_ticket, t, repo, config): t
                        for t in wave.tickets
                    }
                    for fut in as_completed(futs):
                        try:
                            fut.result()
                        except Exception as e:
                            human(f"[error] unexpected failure: {e}")
            else:
                for t in wave.tickets:
                    _run_ticket(t, repo, config)

            tickets = _load_tickets(repo)
            banner = escalation_mod.plan_review_check(tickets)
            if banner:
                human(banner)

        tickets = _load_tickets(repo)
        done = sum(1 for t in tickets if t.status == "done")
        escalated = sum(1 for t in tickets if t.status == "escalated")
        human(f"\nSummary: {done} done, {escalated} escalated.")

    finally:
        locking.release(lock)
