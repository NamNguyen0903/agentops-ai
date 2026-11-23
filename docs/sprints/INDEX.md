# AgentOps AI — Sprint Index

**Version:** 1.5
**Updated:** 2026-11-23
**Latest closed sprint:** S01 — CLOSED (`PARTIALLY_VERIFIED`)
**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS / PARTIAL`)
**Current ticket:** AG-003.6 — Tech Lead / owner security and acceptance review (READY_FOR_TECH_LEAD_REVIEW)
**Product baseline:** PRD v0.2
**Current handoff:** [CURRENT_STATE.md](../handoff/CURRENT_STATE.md)

> Sprint closure means user scope signoff, not proof of full technical verification, remote merge or production readiness. Keep observed evidence distinct from user-reported success.

## Current isolated closeout checkpoint — 2026-11-23

**Resume authority:** Start with [CURRENT_STATE.md](../handoff/CURRENT_STATE.md).
**S02 is NOT DONE; production authentication is NOT APPROVED.** Inspect Git before
changing files. Current branch: `feat/s02-sprint-closeout`; observed HEAD: `cc13f8a`.
The four checkpoint documents and a pre-existing CI-trigger edit remain uncommitted.
This is documentation reconciliation, not new test execution or architecture approval.

**Exactly one recommended next action:** AG-003.6 — conduct the Tech Lead / owner
security and acceptance review using [S02_CLOSEOUT.md](S02_CLOSEOUT.md), recording
explicit decisions on open gates. Do not start S03 or close S02.
Historical run results and prior next actions below describe their original checkpoints;
this resume notice and CURRENT_STATE govern continuation. The complete earlier handoff
is preserved in the [historical archive](../handoff/S02_HISTORY_2026-11-23.md).

**PARTIAL — 8/11 existing acceptance criteria VERIFIED (72.7%, rounded 73%).**
S02 remains IN_PROGRESS; ADR-0002 PROPOSED; auth disabled by default. See
[closeout evidence and exact commands](S02_CLOSEOUT.md) for the denominator,
failures, limits, retained resources and PR plan.

Current observed results: backend **100 passed / 8 skipped** on source Python 3.12
and fresh installed Python 3.11; **7 real PostgreSQL cases passed** with migration
lifecycle; PoC **56 passed / 1 security xfailed**; Node 22 **17 tests**, typecheck,
lint and build passed. Isolated foundation readiness/least privilege/named-volume
restart passed. Shared-stack HTTP smoke passed read-only.

Fixed missing auth-dependency package marker, isolated legacy Compose tests, added
concurrency coverage and expanded CI. At the last GitHub observation, PR #3 was OPEN
with two existing checks SUCCESS; PR #4 was MERGED (`fa03f27`). GitHub status has not
been refreshed in this documentation checkpoint. CI-001 was imported locally. New workflow remote
execution remains UNVERIFIED. Code commit `2b677e2`; current branch `feat/s02-sprint-closeout`
(locally renamed from `codex/s02-closeout`; historical command paths unchanged).
Original README and untracked .github preserved. No push, merge or activation.
Earlier checkpoints below are historical and do not supersede this evidence.

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

## 3. Historical S02 Progress (superseded by closeout checkpoint above)

| Ticket | Workflow | Evidence |
|---|---|---|
| AG-003.1 | DESIGN_REVIEWED — APPROVAL_PENDING | ADR-0002 remains PROPOSED |
| AG-003.1A | REPORTED_COMPLETE | FastAPI Users PoC: 30 passed, 1 xfailed; unmodified stock approach not recommended |
| AG-003.1B | IN_PROGRESS — DECISION_PENDING | Google OIDC/Authlib preferred; 56 passed, 1 security xfailed; formal approval pending |
| AG-003.2 | REPORTED_COMPLETE | PostgreSQL infrastructure and runtime role checks observed; persistence and Git evidence incomplete |
| AG-003.3A | REPORTED_COMPLETE — COMMITTED | Commit `cfab615`; ORM/Alembic infrastructure |
| AG-003.3B | REPORTED_COMPLETE — COMMITTED / PUSH_REPORTED | Commit `bae6fb0`; identity models and guarded migration |
| AG-003.4 | IMPLEMENTED_FOR_REVIEW — ACTIVATION_BLOCKED | Five authentication endpoints, OIDC state, PostgreSQL sessions and CSRF; disabled by default |
| AG-003.5 | PARTIALLY_VERIFIED | Security logging fix verified; session and OIDC security tests pass within tested scope; release gates remain |
| AG-003.6 | READY_FOR_TECH_LEAD_REVIEW — CLOSEOUT_PENDING | Backend baseline 102 passed/6 skipped/0 warnings; PostgreSQL regression after SEC-10: 6 passed in 1.04s; Alembic lifecycle PASS; frontend 17 passed; Git and ADR approval pending |

**Verification boundary:** Six PostgreSQL cases passed separately on a disposable database and were skipped during the default backend run. Offline Google adapter 13/13 and reusable auth dependency 7/7 passed. These results do not establish real Google authentication or production readiness.

**Architecture decision:** ADR-0002 remains PROPOSED. Authentication remains disabled by default. S02 remains IN_PROGRESS.

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

Start with `AGENTS.md` and [CURRENT_STATE.md](../handoff/CURRENT_STATE.md), then
this index and its linked S02 documents. Inspect Git branch/status/HEAD and relevant
diffs before editing. The observed local checkpoint is `cc13f8a` on
`feat/s02-sprint-closeout`, with four modified checkpoint documents and an existing
workflow-trigger edit; do not assume a clean tree. Earlier `bae6fb0`/identity-branch
observations and reported pushes remain historical evidence, not the current resume point.

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


## 8. Historical Resume Point — superseded by CURRENT_STATE

**Checkpoint date:** 2026-11-23.

**Current sprint:** S02 — IN_PROGRESS / PARTIALLY_VERIFIED.

**Current ticket:** AG-003.6 — READY_FOR_TECH_LEAD_REVIEW; closeout pending.

**Architecture:** ADR-0002 PROPOSED; authentication IMPLEMENTED_FOR_REVIEW and disabled by default.

**Latest full backend evidence:** 102 passed, 6 skipped, 0 warnings in 16.61s. This run predates the SEC-10 changes and must be repeated before final closeout.

**Latest PostgreSQL integration:** 6 passed in 1.04s after SEC-10 changes, using disposable PostgreSQL 17. The supplied log confirms pytest PASS; final Compose exit code was not included.

**Google OIDC offline adapter:** 13 passed in 1.18s at the prior verification checkpoint.

**Authentication dependency:** 7 passed in the previous focused test suite.

**Migration lifecycle:** Empty → upgrade → downgrade → upgrade PASS after SEC-10.

**SEC-07:** Account-disable concurrency regression PASS in disposable PostgreSQL.

**SEC-10:** Cross-user session isolation and same-user rotation regression PASS within test_postgres_session_contract.

**SEC-10 policy:** An existing session is revoked during login only when its user_id matches the newly authenticated user. Switching from account A to B does not revoke A's session.

**Latest historically observed branch:** `feat/ag-003-3b-identity-migrations`, HEAD `69486b8`; newer Git state not yet independently confirmed.

**Working tree:** Authentication source, tests and documentation remain uncommitted. Preserve unrelated root `README.md` modifications.

**Next action:** Re-run full backend regression after SEC-10, update S02 security and handoff documentation, review scoped Git changes, then seek explicit ADR-0002 and sprint closeout approval.

**Sprint closeout:** NOT AUTHORIZED. User approval required.

## Historical 2026-11-23 checkpoint

S02 remains IN_PROGRESS. Current gate: AG-003.1B security/architecture approval;
AG-003.4 remains BLOCKED. Independent state-consumption, regression and frontend
checks progressed; production authentication is not implemented. See [S02 evidence](S02.md#2026-11-23-autonomous-execution-checkpoint)
and [current handoff](../handoff/CURRENT_STATE.md). No sprint closeout authorized.

### Final owner-authorized review scope, 2026-11-23

AG-003.4 is now IMPLEMENTED_FOR_REVIEW, disabled by default, following explicit
owner authorization. AG-003.6 handoff is PARTIALLY_COMPLETE_WITH_BLOCKERS; S02
remains IN_PROGRESS. ADR-0002 remains PROPOSED. See the final S02 addendum and
CURRENT_STATE; earlier gate-only checkpoint is historical, not the current status.

## Historical review sequence — superseded by the current closeout checkpoint

## Historical review checkpoint — 2026-11-23

**READY_FOR_TECH_LEAD_REVIEW** for disabled Development MVP implementation; S02
remains IN_PROGRESS and ADR-0002 PROPOSED. Latest observed: backend **102 passed,
6 skipped, zero warnings (16.61s)**; six opt-in PostgreSQL cases **6 passed (1.00s)**
inside successful migration lifecycle; Google adapter + auth dependency **20 passed**
(13+7); frontend **17 passed**, typecheck/lint/build passed. Earlier 101/3/1 and
3-case integration checkpoints below are historical and superseded for current evidence.

SEC-07 locks User before AuthSession and revalidates both; read/CSRF/logout wait
behind account disable and reject after its commit. Existing SEC-03–06 changes
are preserved. The old warning was an unregistered marker, now registered.
No auth activation, normal DB migration, commit or push. Root README unchanged.
See [complete source/test/security review](S02_SECURITY_REVIEW.md).

Exactly one next action: Tech Lead reviews the security package; owner decides ADR revision and activation/closeout permissions.


### SEC-10 verification checkpoint — 2026-11-23

SEC-10 cross-user session isolation remediation has been implemented and reviewed.

The session rotation UPDATE is now restricted to the newly authenticated
user_id, preventing account switching from revoking another user's session.

PostgreSQL regression evidence after SEC-10:
- 6 passed in 1.04s.
- Empty → upgrade → downgrade → upgrade PASS.
- Expected PostgreSQL lock-cancellation event observed.
- Final Docker Compose exit code not supplied in the reviewed excerpt.

The earlier full backend result of 102 passed, 6 skipped and zero warnings
predates SEC-10. Full regression must be repeated before final acceptance.

S02 remains IN_PROGRESS.
ADR-0002 remains PROPOSED.
Authentication remains disabled by default.
No new Git commit, push or merge has been verified.

Next action: complete documentation synchronization and final regression.

## Review checkpoint — 2026-11-23 (post SEC-LOG-05)

### Latest verification

- Full backend regression: **101 passed, 6 skipped in 16.21s**.
- Google OIDC offline regression: **13 passed**.
- SEC-LOG-05 focused regression: **9 passed**.
- Disposable PostgreSQL integration: **6 passed in 1.04s** (last completed run, before SEC-LOG-05 test-only changes).
- Alembic migration lifecycle: **PASS**.

### Sprint status

- S02: **IN_PROGRESS**.
- AG-003.6: **READY_FOR_FINAL_GIT_REVIEW**.
- SEC-06, SEC-07, SEC-10 and SEC-LOG-05: verified within their tested development-review scope.
- ADR-0002: **PROPOSED**.
- Authentication: **disabled by default**.
- Production authentication: **NOT_APPROVED**.

### Exactly one next action

Synchronize `docs/handoff/CURRENT_STATE.md`, then perform final scoped Git review and staging. Preserve unrelated root `README.md` changes.