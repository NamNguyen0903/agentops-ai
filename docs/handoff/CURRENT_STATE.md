# AgentOps AI — Current State

## Authoritative resume checkpoint — 2026-11-24

- Sprint: S03 — Research Task API and Dashboard.
- Sprint status: IN_PROGRESS.
- WP01: VERIFIED_LOCALLY and committed.
- WP02: VERIFIED_LOCALLY and committed.
- WP03: VERIFIED_LOCALLY; delivery commit pending.
- AC01–AC10: VERIFIED_LOCALLY.
- AC11–AC12: PENDING.
- S03 cumulative acceptance: 10/12 (83.3%).
- Next work package: S03-WP04 — Integration, CI & Closeout.
- Previous sprint: S02 CLOSED, 11/11, Development MVP only.

## Workspace and Git

- Canonical directory: /Users/namnguyen/agentops-ai.
- Execution mode: Local only.
- Worktree count: 1.
- Branch: feat/s03-research-persistence.
- S02 base: 7e20e73c32db8287447445d5d48e9331d211ff7c.
- WP01 implementation: 40f017e.
- WP02 delivery: bac326cdf64679ef8a01c7ea5450d15a8c05ef7b.
- Inspect actual Git HEAD for WP03 delivery commit.
- Preserve existing backup stash.
- No push, merge or deployment authorization.

## Verified implementation

- Research task persistence and owner-scoped repository.
- PostgreSQL queue_control admission locking.
- Three authenticated research API endpoints.
- Commit-before-202 and idempotency.
- Session, CSRF and Origin validation.
- Research frontend form, history, detail and polling.
- Same-origin API client and runtime response validation.
- No fabricated AI progress or report generation.

## Verification evidence

- Native backend: 124 passed, 46 skipped.
- Disposable PostgreSQL: 45 passed.
- Migration lifecycle and metadata parity: PASS.
- Frontend: 39 passed, 0 failed.
- TypeScript typecheck: PASS.
- ESLint: PASS.
- Frontend build: PASS.
- Backend and dependency manifests unchanged: PASS.
- One legacy shared Compose test remains unexecuted.
- Full browser/API/PostgreSQL integration: PENDING.
- Full runtime-role HTTP acceptance: PENDING.
- Remote S03 CI: NOT_RUN.

Detailed evidence: [S03 report](../sprints/S03.md).

## Architecture and security boundaries

- ADR-0001: ACCEPTED.
- ADR-0002: ACCEPTED — DEVELOPMENT MVP ONLY.
- ADR-0003: PARTIALLY ACCEPTED — admission only.
- Authentication remains disabled by default.
- Stock Authlib PKCE DEBUG security FAIL remains open.
- Existing strict XFAIL and bounded mitigation retained.
- All S02 release gates remain mandatory.
- Worker execution, leases, recovery and reports are deferred.
- No real Google login, real users or live AI providers.
- Production approval: NOT APPROVED.
- S03 owner closeout: PENDING.

## Historical evidence

- [S02 closeout](../sprints/S02_CLOSEOUT.md).
- [S02 security review](../sprints/S02_SECURITY_REVIEW.md).
- [S03 report](../sprints/S03.md).

## Exactly one next action

After observing the WP03 delivery commit, execute S03-WP04:
Integration, CI & Closeout for AC11–AC12.

Use the canonical local directory only.
Preserve prior verification evidence.
Do not repeat completed checks without changed inputs,
unless required by the integration acceptance gate.
