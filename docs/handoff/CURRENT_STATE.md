# AgentOps AI — Current State

## Authoritative resume checkpoint — 2026-11-24

- Sprint: **S03 — Research Task API and Dashboard; IN_PROGRESS**.
- Work package: **S03-WP01 — Sprint Contract & Research Persistence; VERIFIED_LOCALLY**.
- S03 acceptance: AC01–AC03 verified locally; AC04–AC12 pending. S03 is NOT CLOSED.
- Previous sprint: **S02 CLOSED, 11/11 accepted**, per owner checkpoint.
- PR #7 merged and final main CI PASS: **owner-reported**, not rechecked on GitHub here.
- ADR-0001 ACCEPTED; ADR-0002 ACCEPTED — DEVELOPMENT MVP ONLY.
- Authentication disabled by default; production and real-user activation NOT APPROVED.

## Git and worktree

- Branch: `feat/s03-research-persistence`.
- Worktree: `/Users/namnguyen/.codex/worktrees/s03-research-persistence/agentops-ai`.
- Base and last observed HEAD before local delivery:
  `7e20e73c32db8287447445d5d48e9331d211ff7c`.
- One successful fetch of origin/main confirmed this exact owner-supplied baseline.
- WP01 changes are local; no push, merge or deployment is authorized.
- The delivery commit cannot record its own final SHA. Inspect Git for the actual
  delivery HEAD; the execution report records it after creation.
- Original repository and S02 worktree were preserved. Do not assume other
  worktrees share this branch or contain these changes.

## Implemented and verified

- Additive ResearchTask migration `83d3b0f10901` after identity `0291ce4556fe`.
- UUID ownership, validated scope, six lifecycle states, timestamps, safe error-code
  shape, owner-scoped idempotency, same-owner retry parent, deletion marker and indexes.
- Caller-owned explicit transactions; owner-scoped reads/keyset history; unique-key
  contention resolves concurrent duplicates without creating two tasks.
- Backend Python 3.12.9 macOS ARM64: **117 passed, 32 skipped**, exit 0.
- Isolated PostgreSQL 17.12/Linux ARM64: **31 passed**, exit 0
  (24 new research cases plus seven existing database regressions).
- Additive upgrade, research-only downgrade preserving S02 identity data,
  upgrade/downgrade-to-base/upgrade, role checks and Alembic metadata check passed.
- The 32 default skips are 31 separately executed PostgreSQL cases and one legacy
  shared-stack case not executed. No skipped case is relabeled as a default-suite pass.
- Both host and isolated runner pip checks passed. No dependency changes.
- Backend lint/type-check tools are not configured; no such PASS is claimed.
- Exact commands, changed paths, first-run observations and limits:
  [S03 report](../sprints/S03.md).

## Boundaries and pending gates

No research routes, worker, providers, reports, frontend changes or shared database
migrations were implemented. S03 tasks may remain queued pending the future worker;
no deadline, recovery, production performance or process-restart claim is made.

ADR-0003 is absent; worker/lease/recovery choices remain open. WP01 uses the
explicitly authorized persistence contract and does not accept those future choices.
WP02 must enforce authenticated ownership, CSRF, admission and sanitized errors,
and commit before HTTP 202. Repository owner filters do not replace authentication.

All [ADR-0002 release gates](../adr/0002-authentication.md) remain mandatory:
live Google, browser acceptance, trusted enrollment, operator audit and deployed
provision/disable, distributed abuse controls, retention/cleanup, encryption key
lifecycle, deployed logging/proxy/TLS/secrets, process-kill/uncertain-commit recovery,
backup/restore, broader dependency/platform and remaining privilege review.
Stock PKCE DEBUG exposure remains **security FAIL**; the existing strict XFAIL
and bounded application mitigation are unchanged. No real credentials or real users.

## Historical evidence

S02 implementation baseline: `76ae5ccccf3d913fba813e8232d8d7e8cb8c9423`.
Its merged PRs #3–#6 and observed CI history remain in
[S02 closeout](../sprints/S02_CLOSEOUT.md) and
[S02 security review](../sprints/S02_SECURITY_REVIEW.md).
The accepted documentation baseline is the newer S03 base above.

Preserved archives: [S02 history](S02_HISTORY_2026-11-23.md) and
[pre-final closeout](S02_PRE_FINAL_CLOSEOUT_2026-11-24.md).
Historical gates and next actions in those files are audit evidence.

## Exactly one next action

**S03-WP02 — Research Task Backend API:** first inspect branch, HEAD, status and the
WP01 commit/diff against this checkpoint; then implement the three core task routes
using the [S03 contract](../sprints/S03.md). Read AGENTS, this handoff, INDEX, S03,
PRD and relevant ADRs before editing. Do not repeat completed S02 audits or WP01
checks without changed inputs, stale evidence or a newly discovered blocker.
