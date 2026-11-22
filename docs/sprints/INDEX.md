# AgentOps AI — Sprint Index

**Version:** 1.3  
**Updated:** 2026-11-22  
**Latest closed sprint:** S01 — CLOSED (`PARTIALLY_VERIFIED`)  
**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS`)  
**Current implementation ticket:** AG-003.3A — SQLAlchemy & Alembic Infrastructure  
**Product baseline:** PRD v0.2  
**Current handoff:** [CURRENT_STATE.md](../handoff/CURRENT_STATE.md)

> Sprint closure means user scope signoff, not proof of full technical verification, remote merge or production readiness. Evidence classes are distinguished below.

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

**Scope closed by user signoff:** 2026-11-21. **Verification:** PARTIALLY_VERIFIED; Git merge into `main`: PENDING_EVIDENCE.

| Ticket | Scope | Historical commit |
|---|---|---|
| AG-002.1 | Backend | `48aca5f` |
| AG-002.2 | Frontend | `dee1f9b` |
| AG-002.3 | Compose | `08b027a` |
| AG-002.4 | Integration tests/handoff | `ab8cd01` |

The AG-002.4 branch `feat/ag-002-4-integration-tests` was reported pushed to origin. Final PR merge confirmation and remaining frontend/browser evidence are outstanding. S02 backend tests later reverified existing health behavior; that does not automatically resolve all S01 closeout checks.

## 3. S02 Progress (2026-11-22)

| Ticket | Workflow | Evidence |
|---|---|---|
| AG-003.1 | DESIGN_REVIEWED, approval pending | ADR-0002 still PROPOSED |
| AG-003.2 | REPORTED_COMPLETE | HTTP direct/proxied health/readiness and Postgres role-verifier output observed; outage/recovery user-reported passed; Git SHA/persistence evidence pending |
| AG-003.3A | IN_PROGRESS | **31/31 backend pytest passed**, 1 warning, 6.47s; Alembic discovery empty; SQLAlchemy PostgreSQL integration and S01 smoke user-reported passed |
| AG-003.3B | BLOCKED | Approved identity schema/auth library and migration role required |
| AG-003.4 | PLANNED — BLOCKED | Authentication solution/ADR approval required |
| AG-003.5 | PLANNED | Not started |
| AG-003.6 | PLANNED | Not started |

No migration revisions, identity/authentication models, login/logout endpoints or production deployment are claimed. Alembic migration execution remains disabled in AG-003.3A.

## 4. Status Definitions

| Status | Meaning |
|---|---|
| PLANNED | Scope defined but not started |
| IN_PROGRESS | Work started, not fully accepted |
| REPORTED_COMPLETE | User reports completion; exact evidence may be missing |
| REVIEWED / DESIGN_REVIEWED | Source/design inspected; not equivalent to acceptance |
| VERIFIED | Specific criterion supported by actual observed output |
| REPORTED_PASSED | User confirms check succeeded; output not reviewed |
| PARTIALLY_VERIFIED | Some criteria verified, others open |
| BLOCKED | A named dependency prevents next scope |
| PENDING_CLOSEOUT | Awaiting scope/documentation signoff |
| CLOSED | Scope has explicit user signoff |

Use separate workflow and verification status. Do not claim a sprint is fully verified because its schedule elapsed or tests were generated.

## 5. Sprint Lifecycle

1. **Plan:** confirm objectives, relevant ADRs, acceptance criteria and Git starting point.
2. **Execute:** one ticket at a time; preserve historical evidence and reviewable Git changes.
3. **Review:** collect exact outputs; separate observed and user-reported outcomes; record failures and fixes.
4. **Close out:** update sprint report, handoff and index, reconcile Git PR/merge evidence and obtain user signoff.

## 6. Handoff and Git Consistency

Start a session by reading `AGENTS.md`, [CURRENT_STATE.md](../handoff/CURRENT_STATE.md), this index, [S02.md](S02.md), PRD and relevant ADR. At the latest observed checkpoint, AG-003.3A code and some documents were modified/untracked; current Git branch, HEAD, staged changes and remote status must be checked afresh.

```bash
git branch --show-current
git status -sb
git log -6 --oneline --decorate
git diff --check
```

Do not assume any S02 commit SHA, remote push or merge without supplied Git evidence.

## 7. Documentation Update Rules

- Update `docs/sprints/S02.md` after each ticket with runtime/test evidence, incidents and Git hashes when known.
- Update `docs/handoff/CURRENT_STATE.md` as the concise current checkpoint and next single action.
- Update this index when the sprint or current-ticket state materially changes.
- Update `README.md` when runnable developer setup changes.
- Update ADRs only through an explicit decision; non-decision progress notes must preserve `PROPOSED` status.

## 8. Current Resume Point

**Current sprint:** S02 — IN_PROGRESS.  
**Current ticket:** AG-003.3A — Git/documentation closeout.  
**Next action:** Inspect current branch, working tree, migration revisions and secret handling, then review staged AG-003.3A changes before commit.  
**Blocking architecture:** ADR-0002 is PROPOSED; identity models and auth remain deferred.
