# AgentOps AI — Sprint Index

**Version:** 1.4
**Updated:** 2026-11-22
**Latest closed sprint:** S01 — CLOSED (`PARTIALLY_VERIFIED`)
**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS`)
**Current implementation ticket:** AG-003.1B — ADR-0002 Security & Architecture Approval
**Product baseline:** PRD v0.2
**Current handoff:** [CURRENT_STATE.md](../handoff/CURRENT_STATE.md)

> Sprint closure means user scope signoff, not proof of full technical verification, remote merge or production readiness. Keep observed evidence distinct from user-reported success.

## 1. Sprint Roadmap

| Sprint | Goal | Workflow status | Report |
|---|---|---|---|
| S00 | PRD, architecture, engineering rules, Git foundation | PENDING_CLOSEOUT | [S00.md](S00.md) |
| S01 | FastAPI, React, TypeScript, Docker Compose and integration tests | CLOSED — PARTIALLY_VERIFIED | [S01.md](S01.md) |
| S02 | PostgreSQL, authentication and migrations | IN_PROGRESS — PARTIALLY_VERIFIED | [S02.md](S02.md) |
| S03 | Research task API and dashboard | PLANNED | Not created |
| S04 | Single-agent LangGraph baseline | PLANNED | Not created |
| S05 | Planner, Research and Writer workflow nodes | PLANNED | Not created |
| S06 | Search provider, evidence and citation validation | PLANNED | Not created |
| S07 | Worker reliability, deadlines and usage budgets | PLANNED | Not created |
| S08 | AI evaluation, security and integration testing | PLANNED | Not created |
| S09 | CI/CD and AWS staging preparation | PLANNED | Not created |

The sprint schedule is a planning target, not a guarantee. Do not link future reports until created.

## 2. S01 Closeout Summary (Historical)

**Scope closed by user signoff:** 2026-11-21. **Verification:** PARTIALLY_VERIFIED; merge into `main`: PENDING_EVIDENCE.

| Ticket | Scope | Historical commit |
|---|---|---|
| AG-002.1 | Backend | `48aca5f` |
| AG-002.2 | Frontend | `dee1f9b` |
| AG-002.3 | Compose | `08b027a` |
| AG-002.4 | Integration tests/handoff | `ab8cd01` |

The AG-002.4 branch was reported pushed. Final merge confirmation and remaining frontend/browser evidence are outstanding.

## 3. S02 Progress (2026-11-22)

| Ticket | Workflow | Evidence |
|---|---|---|
| AG-003.1 | DESIGN_REVIEWED — APPROVAL_PENDING | ADR-0002 remains PROPOSED |
| AG-003.1A | REPORTED_COMPLETE | FastAPI Users PoC: 30 passed, 1 xfailed; unmodified stock approach not recommended |
| AG-003.1B | IN_PROGRESS — DECISION_PENDING | Google OIDC/Authlib preferred; PoC 56 passed, 1 xfailed (known stock security failure); security gates and ADR approval pending |
| AG-003.2 | REPORTED_COMPLETE | HTTP health/readiness and Postgres role checks observed; persistence/merge evidence incomplete |
| AG-003.3A | REPORTED_COMPLETE — COMMITTED | Commit `cfab615`; 31 backend tests PASS; push user-reported |
| AG-003.3B | REPORTED_COMPLETE — COMMITTED / PUSH_REPORTED | Commit `bae6fb0`; 39 passed, 1 skipped, 2 warnings; constraints, concurrency, rollback, migration lifecycle and permission checks; merge not verified |
| AG-003.4 | PLANNED — BLOCKED | Authentication implementation requires explicit security/ADR approval |
| AG-003.5 | PLANNED | Authorization/security tests not started |
| AG-003.6 | PLANNED | Cross-component integration and sprint closeout not started |

AG-003.3B created four identity models and a guarded initial migration for disposable PostgreSQL verification. Production login/logout, session controls and deployment are **not** implemented or authorized by this database milestone alone. AG-003.3B tests include one skipped opt-in integration test; the 2 warnings have not been fully classified.

## 4. Status Definitions

| Status | Meaning |
|---|---|
| PLANNED | Scope defined but not started |
| IN_PROGRESS | Work started, not fully accepted |
| REPORTED_COMPLETE | User reports completion; exact evidence may be missing |
| REVIEWED / DESIGN_REVIEWED | Source/design inspected; not equivalent to acceptance |
| VERIFIED | Specific criterion supported by observed output |
| REPORTED_PASSED | User confirms check succeeded; output not reviewed |
| PARTIALLY_VERIFIED | Some criteria verified, others open |
| BLOCKED | A named dependency prevents next scope |
| PENDING_CLOSEOUT | Awaiting scope/documentation signoff |
| CLOSED | Scope has explicit user signoff |

Use separate workflow and verification status. Do not claim the sprint is fully verified because scheduled work or individual tests were completed.

## 5. Sprint Lifecycle

1. **Plan:** Confirm objectives, ADRs, acceptance criteria and Git starting point.
2. **Execute:** Implement one ticket at a time; preserve historical evidence and Git changes.
3. **Review:** Collect exact output, separate observed and user-reported outcomes, document fixes.
4. **Close out:** Synchronize sprint report, handoff and index; review Git/PR/merge evidence and obtain user signoff.

## 6. Handoff and Git Consistency

Start a new session with `AGENTS.md`, [CURRENT_STATE.md](../handoff/CURRENT_STATE.md), this index, [S02.md](S02.md), PRD and relevant ADRs. AG-003.3B commit `bae6fb0` was observed on branch `feat/ag-003-3b-identity-migrations`, with push reported successful. The root `README.md` was the only uncommitted working-tree change at the last checkpoint; later documentation edits are not part of that commit until separately committed.

```bash
git branch --show-current
git status -sb
git log -6 --oneline --decorate
git diff --check
```

Do not assume a PR merge or remote state without evidence.

## 7. Documentation Update Rules

- Update `docs/sprints/S02.md` after each ticket with runtime/test evidence, incidents and Git hashes when known.
- Update `docs/handoff/CURRENT_STATE.md` with the latest Git checkpoint, blocker and next single action.
- Update this index when the sprint/current-ticket state materially changes.
- Update `README.md` only when developer setup or usage instructions change.
- Update ADRs only through an explicit decision; progress notes must preserve `PROPOSED` until accepted.

## 8. Current Resume Point

**Current sprint:** S02 — IN_PROGRESS / PARTIALLY_VERIFIED.
**Current ticket:** AG-003.1B — ADR-0002 Security & Architecture Approval.
**Previous ticket:** AG-003.3B — commit `bae6fb0`, push user-reported, merge not verified.
**Latest observed branch:** `feat/ag-003-3b-identity-migrations`.
**Working tree:** Unrelated root `README.md` modified at last Git check.
**Verification:** 39 backend tests passed, 1 skipped, 2 warnings; isolated migration lifecycle and runtime privilege checks PASS per user, with selected output directly reviewed.
**Next action:** Review `docs/adr/0002-authentication.md` and the Authlib PoC decision report; resolve security gates and obtain explicit approval before AG-003.4.
**Architecture:** ADR-0002 remains PROPOSED; production authentication NOT_IMPLEMENTED.
