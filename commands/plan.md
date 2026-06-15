---
description: Turn a specification into a multi-model execution plan with routed, self-contained tickets (Phase 2 of the taskloop pipeline)
argument-hint: [path to spec, default specs/SPEC.md]
---

You are the chief architect and planner. Input: the specification produced by `/tl:spec` (path in $ARGUMENTS, default `specs/SPEC.md` — read it now). Output: a **complete, self-contained execution plan** to be executed by AI models of varying capability, from small local models to frontier models, with no access to this conversation and no ability to ask questions.

**Fundamental rule: eliminate every implicit decision.** If a task allows two interpretations, the plan has failed.
**Routing rule: every task gets an explicit model-routing verdict** (Stage 4). This is the primary deliverable.

## STAGE 0 — INPUT VALIDATION
Read the spec. If any "Open decisions" remain unresolved or anything needed is missing, stop and ask now — executors cannot ask later.

## STAGE 1 — ARCHITECTURE DECISIONS (document ALL)
For each: Decision / Reason / Implication for executors. Mandatory coverage: architectural pattern + layers; COMPLETE directory tree with each folder's purpose; data model with exact field names/types/relations (literal SQL/schema); API contracts (method, route, literal request/response JSON, error codes); auth (exact mechanism, where validated, format); error handling (single format, log format, levels); ALL environment variables (exact names + example values); DB migration strategy; naming conventions. No executor may make an architectural decision.

## STAGE 2 — INFRASTRUCTURE & ENVIRONMENT
Local setup step by step (literal commands in order); complete infra files written into the plan (Dockerfile, compose, CI YAML, IaC); pinned versions of ALL deps (literal dependency file); exact commands to run/test/lint/build/deploy. Verification infrastructure (tests/lint/CI) must be among the EARLIEST tasks — it's the precondition for routing to local models with retry budgets.

## STAGE 3 — TASK DECOMPOSITION
Break into atomic tasks (1 task = 1 verifiable unit, ideally 1 small PR). Use EXACTLY this format per task:

```
### TASK [ID] — [Title]
**Complexity:** TRIVIAL | MEDIUM | COMPLEX
**Depends on:** [IDs or "none"]   **Blocks:** [IDs or "none"]
**Criticality:** BLOCKER | PARALLEL | LEAF
**Routing verdict:** [apply Stage 4 matrix]
- Model tier: LOCAL-S | LOCAL-L | API-CHEAP | API-MID | API-FRONTIER
- Retry budget: [N attempts before escalation]
- Escalation path: [tier it escalates to]
- Night-batch eligible: YES | NO  [YES only if: LOCAL tier; PARALLEL/LEAF; automated verification; parallel-safe; non-destructive]
**Granularization note:** [if a COMPLEX task was split into TRIVIAL subtasks for local execution, say so + reference subtask IDs; if splittable but not split, justify]
**Self-contained context:** [2-4 sentences — what this does and why; executor hasn't read the rest]
**Files:** CREATE / MODIFY / DO NOT TOUCH (exact paths)
**Specification:** step-by-step; include LITERALLY: function signatures with types, interfaces/schemas/DTOs, data structures, SQL, pseudocode for non-obvious logic. Executor fills implementation, never design. LOCAL tiers: keep required context SHORT.
**Mandatory edge cases:** each one + exact expected behavior
**Prohibitions:** no out-of-scope refactors; no deps beyond listed; no changing defined contracts; [task-specific]
**Acceptance criteria (command-verifiable):** `[command]` → `[expected output]`; named tests pass; lint clean. Never "should work correctly." These are the loop's exit condition.
**Tests:** TEST AUTHORSHIP RULE — for LOCAL-S/LOCAL-L tasks, tests are NOT written by the executor: write them HERE (frontier model) as literal committed test code, BEFORE implementation. The ticket then says "Implement against the existing tests in <path>; modifying any test file is prohibited." This eliminates test-gaming by construction. For API-MID/FRONTIER, the executor may write tests (TDD), subject to the review gate.
**On failure:** after retry budget exhausted, STOP. Do not improvise. Write a failure report (attempts, literal errors, hypothesis), set status escalated, stop.
```

## STAGE 4 — ROUTING DECISION MATRIX
Tiers: LOCAL-S (~7-14B, pattern-following, short context); LOCAL-L (~32-70B, solid logic with full spec); API-CHEAP (Haiku-class); API-MID (Sonnet-class); API-FRONTIER (Opus/Fable-class, judgment/architecture/security).
Rules (priority order):
1. Frontier-only zone (spec C7.2) → API-FRONTIER always, no cost exceptions.
2. BLOCKER → route UP one tier from complexity, retry budget = 1 (stalled critical path costs more than tokens). TRIVIAL blocker → API-CHEAP min; MEDIUM → API-MID min; COMPLEX → API-FRONTIER.
3. COMPLEX + not granularizable → API-FRONTIER (or API-MID if plan covers nearly all judgment), retry 1-2.
4. COMPLEX + granularizable → SPLIT into TRIVIAL/MEDIUM subtasks, route pieces individually. Splitting preferred over routing up when pieces become fully specifiable.
5. PARALLEL/LEAF + TRIVIAL + automated verification → LOCAL-S, retry 3-5 (trial-and-error OK; failure cheap and auto-detected).
6. PARALLEL/LEAF + MEDIUM + automated verification → LOCAL-L or API-CHEAP, retry 2-3.
7. No automated verification possible → never LOCAL; min API-MID.
8. Test authorship: a task may route to LOCAL only if its tests are pre-authored at emission (Stage 6). If pre-authoring isn't feasible, it doesn't qualify for LOCAL.
Escalation ladder: LOCAL-S → LOCAL-L → API-CHEAP → API-MID → API-FRONTIER. On budget exhaustion, escalate one step with the failure report in context. Two escalations on one task = stop, flag for human review.

## STAGE 5 — ORCHESTRATION
1. Dependency graph + critical path. 2. Routing table (task → criticality → complexity → tier → retry → escalation → night-batch → review level) — the execution loop consumes this. 3. Night-batch queue grouped into waves with zero file overlap (each wave runs concurrently in separate worktrees). 4. Priority order (BLOCKERs first by unblock count, then PARALLEL, then LEAF). 5. Checkpoints + what to verify (commands). 6. Final integration checklist (build, all tests, e2e smoke, lint) with expected outputs. 7. Known risks where executors tend to fail here, with preventive instruction.

## STAGE 6 — TICKET EMISSION (progressive — never the whole project at once)
Architecture (1-2) and the full task list with dependencies (3) cover the whole project, but detailed tickets are emitted ONE WAVE at a time (~1-2 weeks of work, or up to the next checkpoint). Later tasks stay as one-line graph entries. Subsequent waves are emitted by `/tl:plan` re-run in a Stage 9 replanning session. Reason: plans never survive contact with execution; tickets written months ahead are waste.
Emit each wave task as `tasks/T-XXX.md` with YAML front-matter (id, title, status, complexity, criticality, tier, retry_budget, escalate_to, depends_on, parallel_safe, night_batch, review, github_issue: null, branch, verify: [commands]) then the full task body. Ticket rules:
- Self-contained minus shared memory: load the memory file (Stage 7) + ONE ticket. Never reference the plan; never repeat what the memory file states. Copy only task-specific contracts.
- Context budget by tier: LOCAL-S tickets keep essentials in the first ~150 lines.
- Imperative voice, no hedging. The verify commands ARE the definition of done.
- Failure protocol in every ticket: after retry_budget, write tasks/reports/T-XXX-failure.md, set status escalated, stop.
### 6.1 GitHub mirror (one-way) — emit a `sync-tickets` spec: files → GitHub only (never back); create one Issue per ticket (labels from front-matter), update labels on status change, post failure reports as comments, PRs `closes #N`; on gh failure append to tasks/.sync-queue and flush next run; never block execution; Issue bodies immutable.

## STAGE 7 — AGENT MEMORY & SKILLS (before execution)
### 7.1 CLAUDE.md + identical AGENTS.md, max 150 lines (~1500 tokens). Every line re-paid each session — include only invariants ≥30% of tasks need: project one-liner + compressed directory map; exact run/test/lint/build commands; the 5-10 naming/style rules that matter; error+log format (once); global prohibitions; the failure protocol. Overflow belongs in a skill or ticket.
### 7.2 Project skills (optional): for a pattern in 3+ tasks, emit skills/<name>/SKILL.md — one pattern, ≤80 lines, built around a literal worked example. Never a skill used by <3 tasks.
### 7.3 Loading matrix: Claude Code auto-loads CLAUDE.md + skills; Codex auto-loads AGENTS.md; local harnesses (Pi) — the orchestrator MUST prepend the memory file + referenced skill. LOCAL-S: memory + skill + ticket must fit the short-context budget.

## STAGE 8 — REVIEW GATES (QA beyond automated checks)
Verify commands are the FIRST QA layer and already gate every task. LLM review is a SECOND layer, proportional to risk, never uniform (review is read-only/single-pass, far cheaper than generation — "cheap writes, strong reviews" is encouraged; reviewing everything is waste). Assign each task a review level:
- none — TRIVIAL + LOCAL/API-CHEAP where verify fully covers acceptance. Verify passing = mergeable.
- sampled — night-batch tasks: no per-task review; ONE morning triage session (strong model, diff-only) reviews the whole night's output for scope creep, prohibited changes, test-gaming. Per diff: merge or open a fix ticket.
- standard — MEDIUM: one review pass (API-CHEAP/MID) of the diff vs ticket: contract conformance, edge cases, prohibitions.
- frontier — COMPLEX, BLOCKER, frontier-only zones: API-FRONTIER review in a FRESH session (never the writing session): design conformance, integration boundaries, failure modes.
- security — auth/payments/input handling: frontier + explicit checklist (injection, authz bypass, secrets, unsafe deserialization, missing rate limits).
Rules: reviewer context = ticket + diff + memory (not the whole codebase); reviewer NEVER fixes — output is APPROVE or numbered findings that become fix tickets routed by Stage 4; NO persistent persona agents (a review is a ticket type with a checklist prompt); sampled/standard prompts must explicitly check for test-gaming.

## STAGE 9 — WAVE CYCLE
### 9.1 End-of-wave replanning: emit the next wave only after a frontier replanning session consuming failure reports + telemetry (9.2) + the diff between planned and actual (interfaces changed, tasks split, assumptions broken). Update Stage 1 decisions, adjust remaining tasks, recalibrate the matrix with evidence, then emit.
### 9.2 Telemetry (orchestrator behavior): log per ticket to tasks/.telemetry.jsonl — id, complexity, initial→final tier, attempts per tier, wall-clock, token cost, verify outcome, review verdict. Budgets are hypotheses in wave 1, data-driven from wave 2.
### 9.3 Plan-review trigger: 2+ escalations in the same code region or touching the same Stage 1 decision = the PLAN is the suspect, not the executors. Pause dependent tickets in that region until replanning resolves it.
### 9.4 WIP limit: cap items awaiting human decision (escalated + pending frontier/security reviews + triage). Default 5. At cap, stop pulling new tickets (including night-batch) until the queue drains.

## SELF-CHECK before delivering
- [ ] Every task executable without asking any question? Every cross-task contract literal (nothing "TBD")?
- [ ] Every file path absolute from repo root? Every dependency version pinned?
- [ ] Every acceptance criterion a command with verifiable output?
- [ ] Tickets emitted ONLY for the current wave; later tasks one-line graph entries?
- [ ] Every task has a routing verdict (tier, retry, escalation, night-batch) + a review level?
- [ ] Every BLOCKER routed up (rule 2)? Every frontier-only zone → API-FRONTIER? Every COMPLEX either justified non-splittable or split?
- [ ] No LOCAL-tier task without automated verification? Every LOCAL ticket points to pre-authored, committed tests (modification prohibited)?
- [ ] No night-batch task destructive or sharing files within a wave?
- [ ] Memory file ≤150 lines, only ≥30%-of-tasks invariants? Every skill backed by 3+ tasks + a worked example? LOCAL-S tickets within short-context budget?
- [ ] Telemetry fields, WIP cap, plan-review trigger defined for the orchestrator? No over-reviewing (no frontier review on verified trivial work)?
- [ ] Any vague word ("appropriate", "as needed", "robustly") undefined? Replace it.

---

## SPEC PATH
$ARGUMENTS
(If empty, read specs/SPEC.md.)
