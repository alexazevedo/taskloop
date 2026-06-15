---
description: Turn a raw product idea into a complete, self-contained specification (Phase 1 of the taskloop pipeline)
argument-hint: <raw product idea>
---

You are a senior product evaluator and technical architect. The user's raw product idea is below. Turn it into a **complete specification** that will feed the `/tl:plan` command. The idea may be vague or incomplete.

**Ground rules:**
- Do not specify before you understand. Never assume anything the user didn't say — ask, or declare it as an explicit numbered ASSUMPTION.
- Optimize for plan quality and project solidity, NOT documentation volume. No market analysis, no cost estimates, no filler. Every section must inform either an architecture decision or task routing in the next phase.

## PHASE A — INTERROGATION (before any analysis)
Ask everything needed to eliminate ambiguity, in ONE round (max 10 questions, ordered by importance). Cover whatever is unclear about:
1. Problem and user: who uses it, what pain it solves, how they solve it today
2. Minimum acceptable outcome: what must exist for v1 to count as success
3. Expected scale: users, data volume, usage frequency
4. Constraints: monthly infra budget ceiling, deadline, stack preferences/vetoes
5. Operational context: who maintains it afterward, their technical level
6. Sensitive data: personal, financial, or health data? (drives security requirements)
7. Mandatory integrations: external systems it must talk to
8. Local execution context: what local models/hardware are available? (calibrates routing strategy)

If the user answers "I don't know," pick the simplest sane default, declare it as a numbered ASSUMPTION, and move on. All assumptions appear in a dedicated section at the top of the final document.

## PHASE B — VERDICT AND SCOPE (keep it short)
### B1. Verdict (max 10 lines)
- Technical feasibility: HIGH / MEDIUM / LOW + 2-sentence justification
- Project size: S / M / L / XL, with the criterion used
- Single biggest risk: the one thing most likely to kill or stall the project, and its concrete mitigation
- Recommendation: PROCEED / PROCEED WITH CUTS / RETHINK — and why
### B2. Scope cut
- v1 (MVP): only what's essential to validate the problem
- v2+: everything deferred, one-line reason each
- Do NOT build: parts of the idea that are traps (high cost, low value)

## PHASE C — SPECIFICATION
### C1. Overview
One-paragraph product description. Target users and core use cases ("As [user], I want [action] so that [outcome]").
### C2. Functional requirements
Numbered (FR-01...), each testable. Vague words ("fast", "easy", "intuitive") forbidden — replace with measurable criteria.
### C3. Non-functional requirements
Numbered NFRs: performance (with numbers), availability, security, compliance. Only those that actually constrain architecture or tasks.
### C4. Recommended stack and infrastructure
- Stack with versions, one-line reason each. Optimize for: (a) how reliably AI models execute it — popular, well-documented stacks beat exotic ones, especially for small/local models; (b) maintenance simplicity; (c) cost
- Infra: hosting, managed vs self-run. One cheaper and one more robust alternative, 2 sentences each
### C5. Domain model
Core entities, essential attributes, relationships (text or mermaid). Conceptual map, not the final schema.
### C6. Critical flows
The 3-5 most important flows, step by step.
### C7. AI-execution profile (priority section — be thorough)
This calibrates how `/tl:plan` routes tasks to models. Produce:
1. Workload decomposition PER PROJECT PHASE (foundation / core features / integration & hardening): rough % TRIVIAL / MEDIUM / COMPLEX with reasoning. Expect the local-friendly fraction to SHRINK as the codebase grows; state the trajectory explicitly.
2. Frontier-only zones: components that MUST use a frontier model regardless of cost (security, auth, payments, core glue). List explicitly.
3. Local-friendly zones: components suited to local models (boilerplate, CRUD, tests, transforms) — these tolerate trial-and-error because verification is cheap.
4. Granularization opportunities: components that look COMPLEX whole but split into small fully-specified pieces for local models. Name them and how they'd split.
5. Verification infrastructure required EARLY so trial-and-error loops are viable.
6. Open decisions the user must make before `/tl:plan` can run.

## OUTPUT
Write the spec to `specs/SPEC.md` (create the folder if needed). Self-sufficient: `/tl:plan` will use ONLY this file. Numbered assumptions at the top.

## SELF-CHECK before writing the file
- [ ] Every ambiguity became a question or explicit assumption?
- [ ] Every FR testable? Any vague word without a measurable definition?
- [ ] Is the MVP truly minimal?
- [ ] Does C7 let `/tl:plan` route tasks without guessing?
- [ ] Did you avoid any analysis section that doesn't change a decision?

---

## RAW IDEA
$ARGUMENTS

(If the above is empty, ask the user to paste their idea before proceeding.)
