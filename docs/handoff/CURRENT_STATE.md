# AgentOps AI — Current State

**Date:** 2026-11-23 (Asia/Ho_Chi_Minh)
**Sprint:** S02 — IN_PROGRESS / PARTIAL
**Current ticket:** AG-003.6 — READY_FOR_TECH_LEAD_REVIEW
**Acceptance:** 8/11 existing S02 success criteria verified (72.7%, rounded 73%).
This is not production readiness or test coverage. See the
[acceptance matrix and execution evidence](../sprints/S02_CLOSEOUT.md).

## Baselines and authority

PRD v0.2; architecture v1.1; ADR-0001 and ADR-0002 remain PROPOSED.
Authentication is implemented for review and disabled by default. The preceding closeout task
authorized isolated edits/tests/local commits, but no push, merge, ADR approval or
activation. This follow-up authorizes documentation correction only, without a commit.

## Historical evidence preservation

The complete **402-line** handoff from identity-branch commit
`d2bed54825d83e17efad5b6cde442e8ff470665f` is preserved verbatim in the
[historical handoff archive](S02_HISTORY_2026-11-23.md), with provenance, content hash
and an evidence guide. Its older next actions and Git/approval statements are historical.

The archive retains FastAPI Users AUTH-P failures/gaps, Authlib OIDC-P10 exposure
and forced-XFAIL evidence, owner review-only authorization, SEC-03–07/SEC-10 and
SEC-LOG-04/05 checkpoints, exact historical test results and commit references.
SEC-10's supplied excerpt lacked a final Compose exit code; old 102/6 results
predated that fix. The newer closeout runs below do not retroactively fill that gap.

## Latest evidence

- Backend: 100 passed / 8 skipped on local source and freshly installed Python 3.11.
- PostgreSQL: 7 passed; migration upgrade/downgrade/upgrade and least privilege passed.
- Authlib PoC: 56 passed / 1 xfailed / 1 warning. Stock DEBUG disclosure remains security FAIL.
- Node 22: 17 passed; typecheck/lint/build passed.
- Isolated foundation: health, readiness, frontend/proxy and named-volume restart passed.
- Shared-stack smoke: 3/3 read-only; deployed image equivalence is unverified.
- Backend/PoC pip checks passed; these are not vulnerability audits.
- Missing auth dependency package marker repaired after a fresh-install collection failure.
- Legacy shared Compose test now opt-in; equivalent isolated contention assertions passed.
- New CI workflow has three jobs; remote execution of this branch remains unverified.

## Ticket state

| Ticket | Current outcome |
|---|---|
| AG-003.1 / AG-003.1B | Design reviewed; architecture/security approval BLOCKED on owner |
| AG-003.1A | Historical FastAPI Users PoC; stock approach not adopted |
| AG-003.2 | Local foundation VERIFIED including persistence |
| AG-003.3A / AG-003.3B | ORM/migrations VERIFIED in guarded isolated scope |
| AG-003.4 | IMPLEMENTED_FOR_REVIEW; disabled; activation not authorized |
| AG-003.5 | VERIFIED within offline and isolated PostgreSQL boundaries |
| AG-003.6 | Local closeout package prepared; owner review and Git integration pending |

## Observed Git checkpoint

- Worktree: `/Users/namnguyen/.codex/worktrees/s02-closeout/agentops-ai`.
- Branch: `codex/s02-closeout`; starts at identity branch commit `d2bed54`.
- Last observed verified code commit: `2b677e2`; CI import `5f7d180`.
- Observed HEAD: `0d4dc1f6d2a8aa0fc5c20f4ee399bec89a9d4c26` (closeout documentation).
- This historical-evidence correction is uncommitted; no new test execution is claimed.
- Original worktree remains on `feat/ag-003-3b-identity-migrations`.
- Original modified README and untracked .github content hashes unchanged.
- Last remote observation during the preceding 2026-11-23 closeout: PR #3 OPEN into
  main, two existing checks SUCCESS; PR #4 MERGED into PostgreSQL
  branch at `fa03f27cf986a638f52bdb48ef054478e0e2ddd8` (read-only GitHub evidence).
  Remote status was not refreshed in this documentation-only correction.
- No closeout push/PR/merge. Proposed PR base: identity branch; owner must review full stack.

## Blockers and restrictions

ADR acceptance, conditional auth adoption/security controls and reviewed remote
integration remain incomplete. Live Google, deployed log collectors, key lifecycle,
operator provisioning/disable procedures, retention jobs, distributed abuse protection,
full advisory audit and process-kill/transport failure recovery are not verified.
Multi-tab CSRF proof rotation remains a known limitation. Broader global/indirect
default-privilege review and backup-restore verification remain incomplete. Tested
account-wide revocation does not establish approved operator lifecycle procedures;
configured-handler mitigation does not resolve stock PKCE logging exposure.
No normal development DB migration, production enablement or S03 work occurred.
Stopped isolated test containers/volumes remain; see closeout report for exact names.
Never remove shared resources as cleanup. Root README may contain old status text;
its user-owned changes were intentionally preserved.

## Exactly one next action

**AG-003.6:** Owner/Tech Lead reviews [S02_CLOSEOUT.md](../sprints/S02_CLOSEOUT.md),
resolves acceptance/security gates and authorizes the proposed publication plan.
Do not mark S02 CLOSED before approval and the unchanged sprint criteria are met.
