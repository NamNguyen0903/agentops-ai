# AgentOps AI — Sprint Index

**Version:** 1.2
**Updated:** 2026-11-21
**Latest sprint:** S01 — CLOSED
**Verification status:** PARTIALLY_VERIFIED
**Current implementation ticket:** None
**Next planned sprint:** S02 — Database & Authentication
**Product baseline:** PRD v0.2

**Current handoff:** [CURRENT_STATE.md](../handoff/CURRENT_STATE.md)

> Sprint closure means the planned scope received user signoff. It does not automatically establish full technical verification, Git merge completion or production readiness.

## 1. Sprint Roadmap

Each sprint represents one planned working day. The schedule is a planning target, not a guarantee of completion within a calendar day.

| Sprint | Goal | Status | Report |
|---|---|---|---|
| S00 | PRD, architecture, engineering rules, Git foundation | PENDING_CLOSEOUT | [S00.md](S00.md) |
| S01 | FastAPI, React, TypeScript, Docker Compose and integration tests | CLOSED — PARTIALLY_VERIFIED | [S01.md](S01.md) |
| S02 | PostgreSQL, authentication and migrations | PLANNED | Not created |
| S03 | Research task API and dashboard | PLANNED | Not created |
| S04 | Single-agent LangGraph baseline | PLANNED | Not created |
| S05 | Planner, Research and Writer workflow nodes | PLANNED | Not created |
| S06 | Search provider, evidence and citation validation | PLANNED | Not created |
| S07 | Worker reliability, deadlines and usage budgets | PLANNED | Not created |
| S08 | AI evaluation, security and integration testing | PLANNED | Not created |
| S09 | CI/CD and AWS staging preparation | PLANNED | Not created |

Future sprint reports must only be linked when their files exist. The roadmap remains subject to acceptance evidence and approved scope changes.

## 2. Sprint S01 Closeout Summary

**Closeout date:** 2026-11-21
**Scope status:** CLOSED — User signoff received
**Technical verification:** PARTIALLY_VERIFIED
**Git merge into `main`:** PENDING_EVIDENCE

| Ticket | Description | Commit |
|---|---|---|
| AG-002.1 | FastAPI Backend Foundation | `48aca5f` |
| AG-002.2 | React + TypeScript Frontend | `dee1f9b` |
| AG-002.3 | Docker Compose Foundation | `08b027a` |
| AG-002.4 | Integration Tests & Sprint Handoff | `ab8cd01` |

### Confirmed Git Evidence

- AG-002.4 was committed as `ab8cd01`.
- Branch `feat/ag-002-4-integration-tests` was successfully pushed to `origin`.
- Local HEAD and the remote-tracking branch were observed at the same commit.
- The supplied `git status -sb` showed no outstanding local file changes at that checkpoint.
- The known commit sequence includes all four S01 tickets.

### Confirmed Runtime Evidence

- FastAPI returned HTTP 200 with the expected health JSON.
- React/Vite frontend returned HTTP 200.
- Vite API proxy returned HTTP 200 with the expected backend JSON.
- Docker Compose reported both API and Web containers healthy.

### Outstanding Verification

- Final backend pytest output.
- Final frontend regression-test and build outputs.
- Exact AG-002.4 unittest and integration-test outputs.
- Docker restart, recovery, shutdown and rebuild evidence.
- Browser rendering and responsive UI review.
- Pull request review and merge into `main`.

These items remain open. Do not interpret Sprint scope closure as full technical verification.

## 3. Standard Status Definitions

| Status | Meaning |
|---|---|
| `PLANNED` | Work is defined but not started |
| `IN_PROGRESS` | Work has started; acceptance remains incomplete |
| `REPORTED_COMPLETE` | User reports completion; exact verification evidence may still be pending |
| `REVIEWED` | Specified source or documentation has been reviewed |
| `VERIFIED` | A specific criterion is supported by observed execution or inspection evidence |
| `PARTIALLY_VERIFIED` | Some criteria are verified while others remain unresolved |
| `BLOCKED` | A named dependency prevents the required next action |
| `PENDING_CLOSEOUT` | Implementation or documentation signoff is not fully recorded |
| `CLOSED` | Sprint scope received explicit user signoff |

Ticket workflow status and verification evidence must be recorded separately where appropriate.

A sprint is not closed merely because its planned day has ended.

## 4. Sprint Lifecycle

### Planning

- Confirm the objective, scope and dependencies.
- Review relevant PRD and ADR sections.
- Select the first ticket.
- Define acceptance criteria.

### Execution

- Work on one ticket at a time.
- Keep Git changes reviewable.
- Run applicable checks.
- Record important decisions and failures.
- Carry over incomplete work explicitly.

### Review

- Compare actual outputs against acceptance criteria.
- Inspect test, Git and runtime evidence.
- Distinguish generated code from verified implementation.
- Record unresolved issues.

### Closeout

- Complete the sprint report.
- Record actual commits and verification evidence.
- Record deferred scope.
- Update the current handoff.
- Update this Sprint Index.
- Obtain user signoff.
- Identify one next action.

## 5. Handoff and Git Consistency

At the beginning of a new session:

1. Read `AGENTS.md`.
2. Read [CURRENT_STATE.md](../handoff/CURRENT_STATE.md).
3. Read this Sprint Index.
4. Read the current or most recently completed Sprint report.
5. Read relevant PRD and ADR sections.
6. Reconcile the recorded branch, HEAD, working tree and remote against fresh Git evidence.

Do not assume that committed code has been merged into `main`.

Do not overwrite uncommitted work or invent missing verification evidence.

## 6. Documentation Update Rules

After each ticket:

- Update `docs/sprints/SXX.md` with implementation status, actual tests, issues and commit evidence.
- Update `docs/handoff/CURRENT_STATE.md` with the latest verified checkpoint and immediate next action.
- Update this Sprint Index when a sprint begins, changes status or closes.
- Update `README.md` when developer setup or user-facing usage instructions materially change.
- Update ADRs only through an explicit architecture decision or approval process.

The user performs all local file edits, tests, Git actions and deployments.

## 7. Current Resume Point

**Latest completed scope:** Sprint S01 — Project Foundation.

**Current implementation ticket:** None.

**Current repository milestone:** AG-002.4 commit `ab8cd01` was pushed on branch `feat/ag-002-4-integration-tests`.

**Immediate action:** Review and merge the Sprint S01 pull request into `main`, subject to required review and checks.

**Pull request base:** `main`
**Pull request compare:** `feat/ag-002-4-integration-tests`

After the merge:

1. Verify the updated `main` branch and Git history.
2. Record PR and merge evidence in `S01.md` and `CURRENT_STATE.md`.
3. Resolve remaining S01 evidence carryover.
4. Review authentication and database architecture decisions.
5. Plan Sprint S02 before creating its first implementation branch.

**Next planned sprint:** S02 — Database & Authentication.

Do not record S02 as `IN_PROGRESS` until work actually begins. Do not mark S01 `FULLY_VERIFIED` until its remaining acceptance evidence has been reviewed.