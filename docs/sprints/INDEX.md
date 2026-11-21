# AgentOps AI — Sprint Index

**Version:** 1.1
**Updated:** 2026-11-21
**Current sprint:** S00
**Sprint status:** IN_PROGRESS
**Current ticket:** AG-001.5
**Product baseline:** PRD v0.2

**Current handoff:** [CURRENT_STATE.md](../handoff/CURRENT_STATE.md)

## 1. Sprint Roadmap

Each sprint represents one planned working day.

The schedule is a planning target, not a guarantee that all planned scope will be completed within one calendar day.

| Sprint | Goal | Status | Report |
|---|---|---|---|
| S00 | PRD, architecture, engineering rules, Git foundation | IN_PROGRESS | [S00.md](S00.md) |
| S01 | FastAPI, React and Docker project foundation | PLANNED | Not created |
| S02 | PostgreSQL, authentication and migrations | PLANNED | Not created |
| S03 | Research task API and dashboard | PLANNED | Not created |
| S04 | Single-agent LangGraph baseline | PLANNED | Not created |
| S05 | Planner, Research and Writer workflow nodes | PLANNED | Not created |
| S06 | Search provider, evidence and citation validation | PLANNED | Not created |
| S07 | Worker reliability, deadlines and usage budgets | PLANNED | Not created |
| S08 | AI evaluation, security and integration testing | PLANNED | Not created |
| S09 | CI/CD and AWS staging preparation | PLANNED | Not created |

Future reports must only be linked when the corresponding files exist.

The milestone plan remains subject to acceptance evidence and explicitly approved scope changes.

AWS staging preparation in S09 does not imply successful deployment.

## 2. Standard Status Definitions

| Status | Meaning |
|---|---|
| `PLANNED` | Work is defined but not started |
| `IN_PROGRESS` | Work has started; acceptance remains incomplete |
| `REPORTED_COMPLETE` | User reports completion; supporting verification is pending |
| `REVIEWED` | Specified content or evidence received documented review |
| `VERIFIED` | Acceptance criteria supported by inspection or execution evidence |
| `BLOCKED` | A named dependency prevents the required next action |

For tickets, review status and verification status may be recorded separately.

A sprint is not closed merely because its planned day has ended.

Sprint closeout additionally requires recorded acceptance and user signoff.

## 3. Sprint Lifecycle

### Planning

- Confirm objective and scope.
- Identify dependencies.
- Select the first ticket.
- Define acceptance criteria.

### Execution

- Work on one ticket at a time.
- Keep changes reviewable.
- Record failures and important decisions.
- Carry over incomplete work explicitly.

### Review

- Compare outputs against acceptance criteria.
- Inspect supplied test and Git evidence.
- Separate generated content from verified local artifacts.
- Record unresolved issues.

### Closeout

- Complete the sprint report.
- Record actual Git evidence.
- Record deferred scope.
- Update the current handoff.
- Update this index.
- Identify one next ticket.
- Obtain user approval.

## 4. Handoff and Git Consistency

At the beginning of a new session:

1. Read `AGENTS.md`.
2. Read [CURRENT_STATE.md](../handoff/CURRENT_STATE.md).
3. Read this index.
4. Read the current sprint report.
5. Read relevant PRD and ADR sections.
6. Reconcile recorded Git state with current user-supplied evidence.

If the handoff appears stale:

- Inspect the difference.
- Do not overwrite uncommitted work.
- Do not invent missing information.
- Update the checkpoint from evidence before continuing.

## 5. Incomplete Sprint Work

If acceptance criteria are not met:

- Keep the ticket open or mark it BLOCKED.
- Record the missing evidence.
- Identify the next required action.
- Carry scope to another sprint only with an explicit decision.
- Do not treat a generated document or unexecuted command as completed implementation.

## 6. Current Resume Point

**Current sprint:** S00 — IN_PROGRESS.

**Current ticket:** AG-001.5 — Engineering Rules and Sprint Handoff.

**Immediate action:** Save and review the revised four documentation files.

**Next ticket:** AG-001.6 — Initial Git Commit, GitHub Push & Sprint S00 Closeout.

**First AG-001.6 action:** Inspect the real Git branch, status, HEAD and remote configuration before staging or committing.

Do not begin S01 until S00 has been closed with recorded acceptance and user signoff.