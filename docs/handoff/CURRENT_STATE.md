# AgentOps AI — Current State

## Authoritative resume checkpoint — 2026-11-24

- Sprint: S03 — Research Task API and Dashboard; IN_PROGRESS.
- WP01: VERIFIED_LOCALLY.
- WP02: VERIFIED_LOCALLY; local delivery pending commit.
- AC01–AC08: VERIFIED_LOCALLY.
- AC09–AC12: PENDING.
- Cumulative S03 acceptance: 8/12 (66.7%).
- Next package: S03-WP03 — Research Dashboard.
- Previous sprint: S02 CLOSED, 11/11, Development MVP only.

## Workspace and Git

- Canonical directory: /Users/namnguyen/agentops-ai.
- Execution mode: Local only.
- Worktree count: 1.
- Branch: feat/s03-research-persistence.
- S02 base: 7e20e73c32db8287447445d5d48e9331d211ff7c.
- WP01 implementation: 40f017e.
- Last observed pre-delivery HEAD: 360a6b9.
- Inspect actual Git HEAD after WP02 commit.
- Preserve the existing backup stash.
- No push, merge or deployment authorization.

## Verified implementation

- ResearchTask persistence and owner-scoped repository.
- queue_control singleton admission locking.
- Three core research task API routes.
- Explicit commit before HTTP 202.
- Idempotency, pagination, authentication and CSRF.
- Six registered application tables.
- Native backend: 124 passed, 46 skipped.
- Disposable PostgreSQL: 45 passed, Compose exit 0.
- Migration lifecycle and metadata parity passed.
- Disposable resources removed.

Detailed evidence: [S03 report](../sprints/S03.md).

## Architecture and security boundaries

- ADR-0001: ACCEPTED.
- ADR-0002: ACCEPTED — DEVELOPMENT MVP ONLY.
- ADR-0003: PARTIALLY ACCEPTED — admission only.
- Worker claiming, leases and recovery remain open.
- Authentication remains disabled by default.
- Stock Authlib PKCE DEBUG exposure remains security FAIL.
- Existing strict XFAIL and bounded mitigation retained.
- All ADR-0002 release gates remain mandatory.
- Full runtime-role HTTP acceptance remains unverified.
- No live Google or real-user activation.
- Production approval: NOT APPROVED.
- Remote S03 CI: NOT_RUN.
- S03 owner closeout: PENDING.

## Historical evidence

- [S02 closeout](../sprints/S02_CLOSEOUT.md).
- [S02 security review](../sprints/S02_SECURITY_REVIEW.md).
- [S02 history](S02_HISTORY_2026-11-23.md).
- [S02 pre-final closeout](S02_PRE_FINAL_CLOSEOUT_2026-11-24.md).
- [S03 report](../sprints/S03.md).

## Exactly one next action

After observing the WP02 local delivery commit, start S03-WP03.
Inspect the existing frontend and implement the Research Dashboard
against the verified API for AC09–AC10.

Keep all development in the canonical local directory.
Do not repeat completed checks without changed inputs.
