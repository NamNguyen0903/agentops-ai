# AgentOps AI — Current State

**Checkpoint date:** 2026-11-22
**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS`)
**Verification status:** `PARTIALLY_VERIFIED`
**Current ticket:** AG-003.1A — FastAPI Users Compatibility PoC (`REPORTED_COMPLETE`, pending documentation/Git closeout)
**Next planned ticket:** AG-003.1B — Authentication Architecture Selection
**Implementation owner:** User controls local edits, tests, Git and deployment.

> This handoff records conversation evidence, not a live inspection of the repository. `VERIFIED` refers to reviewed terminal output; `USER_REPORTED` identifies success without complete direct output. An isolated diagnostic PoC is not production authentication.

## 1. Project Baseline

| Component | Current state |
|---|---|
| Product | AgentOps AI, evidence-grounded market/competitor research; PRD v0.2 |
| Architecture | Modular monolith; ADR-0001 `PROPOSED` |
| Backend/front end | FastAPI + React/TypeScript/Vite; S01 scope closed, partial evidence outstanding |
| PostgreSQL | PostgreSQL 17 through Docker Compose; runtime readiness and role permissions observed |
| ORM | SQLAlchemy 2.x + async Psycopg 3; `autobegin=False`; AG-003.3A commit `cfab615` |
| Alembic | Infrastructure-only guarded environment; no revision or application identity tables |
| Authentication | NOT_IMPLEMENTED; ADR-0002 `PROPOSED`; unmodified FastAPI Users stock integration REJECT recommended by PoC |
| AI/worker/cloud | Planned for later sprints; not implemented/verified |

## 2. Sprint and Ticket Status

| Scope | Workflow | Evidence / blockers |
|---|---|---|
| S00 | `PENDING_CLOSEOUT` | Documentation signoff pending |
| S01 | `CLOSED` | `PARTIALLY_VERIFIED`; PR/merge and remaining regression/browser evidence outstanding |
| S02 | `IN_PROGRESS` | `PARTIALLY_VERIFIED` |
| AG-003.1 | `DESIGN_REVIEWED` | ADR-0002 proposed; final authentication decision pending |
| AG-003.1A | `REPORTED_COMPLETE` — Git closeout pending | Isolated PoC 30 passed, 1 xfailed; both `pip check` passed; backend 31 passed |
| AG-003.1B | `NOT_STARTED — NEXT` | Select and approve auth/session/identity architecture |
| AG-003.2 | `REPORTED_COMPLETE` | Readiness and least-privilege role checks observed; persistence marker and dedicated SHA pending |
| AG-003.3A | `REPORTED_COMPLETE` | Commit `cfab615` observed in Git; push user-reported; backend 31/31 |
| AG-003.3B | `BLOCKED` | Approved identity schema, compatible auth design and migration role/schema required |
| AG-003.4 | `PLANNED — BLOCKED` | Auth and session implementation decision pending |
| AG-003.5 | `PLANNED` | Authorization and security tests not started |
| AG-003.6 | `PLANNED` | Integration tests and sprint closeout not started |

## 3. Latest Execution Evidence (2026-11-22)

### AG-003.1A — Isolated FastAPI Users PoC

- Experiment location: `experiments/auth-fastapi-users/`; real FastAPI Users 15.0.5 and SQLAlchemy adapter 7.0.0 exercised against isolated fakes and mock DB I/O.
- Runtime: **Python 3.12.9, pytest 9.2.0, 31 collected, 30 passed, 1 xfailed, 1 warning in 0.40 s**. Complete terminal output reviewed.
- PoC `.venv/bin/python -m pip check`: **No broken requirements found** (observed).
- Backend `.venv/bin/python -m pip check`: **No broken requirements found** (observed).
- Backend regression: **31 passed, 1 warning, 6.62 s** (observed).
- Both suites warned about Starlette `httpx` TestClient deprecation. Tests did not fail.
- The original Python environment creation failed with `ensurepip` and segmentation faults due to mixed environment paths; subsequent isolated Homebrew Python 3.12.9 test run passed.

| Requirement | Result | Meaning |
|---|---|---|
| AUTH-P01 | PASS | Isolated import and mapping |
| AUTH-P02 | PASS | Strategy lifecycle with memory storage |
| AUTH-P03 | **FAIL** | Raw token passed to storage adapter; strict `XFAIL` in pytest |
| AUTH-P04 | PASS | Per-token revocation |
| AUTH-P05 | **NOT_PROVIDED** | Rolling idle expiry absent; absolute-time cutoff observed |
| AUTH-P06 | PASS | Disabled user rejection |
| AUTH-P07 | PASS | TestClient cookie header attributes |
| AUTH-P08 | **NOT_PROVIDED** | Stock CookieTransport does not enforce Origin/CSRF |
| AUTH-P09 | **FAIL** | Stock identity schema/adapter-owned commits incompatible with proposed contracts |
| AUTH-P10 | **UNVERIFIED** overall | Installed versions and `pip check` pass; security advisory and maintenance-risk acceptance pending |

**Tech Lead recommendation:** REJECT **unmodified stock** FastAPI Users integration for the current ADR proposal. This is not approval of Authlib/OIDC or of any alternative design. No production login, migrations or database user tables were created by the PoC. Browser/real-DB behavior unverified.

### Earlier evidence and historical failures

- AG-003.2: `/api/v1/ready` and `/api/v1/health` HTTP 200 observed; Vite readiness proxy observed; role verification passed. Database outage/recovery and persistence were user-reported, with some exact evidence missing.
- AG-003.3A: Alembic `heads`/`history` empty, versions contains only `.gitkeep`, `env.py` guarded; prior pytest **31 passed, 1 warning, 6.47 s**. SQLAlchemy PostgreSQL read transaction and S01 smoke user-reported.
- Historical issues resolved: missing readiness route module, missing Alembic `script.py.mako`, initially empty `alembic/env.py`.

## 4. Git Checkpoint and Safety

**Repository:** https://github.com/NamNguyen0903/agentops-ai
**Observed branch:** `feat/ag-003-3-sqlalchemy-alembic`
**Observed AG-003.3A HEAD:** `cfab6154b10299c5f4640afea81e4b88cd452e90`
**AG-003.3A push:** USER_REPORTED_SUCCESS; remote-tracking ref at HEAD observed by Codex; no direct GitHub PR/merge confirmation.
**Latest reported working tree:** `M docs/sprints/S02.md`, `?? docs/adr/0002-authentication.md`, `?? experiments/`. The latter contains PoC source *and generated artifacts*. Refresh before Git writes.
**AG-003.1A PoC commit / push:** PENDING_EVIDENCE.
**S01 merge to `main`:** PENDING_EVIDENCE.

Never stage `.venv/`, `.venv-broken/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/`, `.env.postgres` or other local secrets. Review `.gitignore` and `git diff --cached` first.

## 5. Architecture Gates

- ADR-0001 remains `PROPOSED`; ADR-0002 remains `PROPOSED — READY FOR DECISION`.
- Stock FastAPI Users with DatabaseStrategy and default SQLAlchemy adapters is **not recommended**: raw token persistence, adapter-controlled commits, incompatible stock schema, no rolling idle expiry, and no built-in Origin/CSRF enforcement.
- AG-003.1B must select and approve a maintained authentication solution, identity mapping, session contract and compatibility approach. OIDC via Authlib is only a candidate; it does not automatically solve app sessions/CSRF.
- `app` schema ownership and separate `agentops_migrator` must be approved and provisioned before identity migrations.
- AG-003.3B and AG-003.4 remain blocked until dependent design approvals.

## 6. Outstanding Work

- [ ] Review generated PoC artifacts and `.gitignore`; stage source/docs only, commit, push, and record SHA.
- [ ] Save/review ADR-0002 in Git without claiming it has been accepted.
- [ ] AG-003.1B authentication architecture decision and documented approval.
- [ ] AG-003.3B identity models, constraints, migration role, initial revision and PostgreSQL tests.
- [ ] AG-003.4 login/current-user/logout, session expiry/revocation, Origin and CSRF controls.
- [ ] AG-003.5 authorization and security regression tests.
- [ ] AG-003.6 end-to-end S02 integration, Git/PR/merge evidence and user closeout signoff.
- [ ] Reconcile earlier S01 and AG-003.2 evidence carryovers separately.

## 7. Exactly One Immediate Next Action

Review the current working tree and ignore rules before committing the PoC:

```bash
cd /Users/namnguyen/agentops-ai
git status --short --untracked-files=all
git check-ignore -v experiments/auth-fastapi-users/.venv/ experiments/auth-fastapi-users/.venv-broken/ experiments/auth-fastapi-users/.pytest_cache/ experiments/auth-fastapi-users/agentops_auth_fastapi_users_poc.egg-info/ || true
git diff --check
```

Do not delete untracked ADR-0002 or overwrite other uncommitted work. After PoC Git closeout, start AG-003.1B architecture review.

## 8. Documentation Update Rules

Record actual test outputs separately from reported successes; never invent Git SHA, merge status or approval. Update `docs/sprints/S02.md` first, then this handoff, and update `docs/sprints/INDEX.md` when sprint status changes. Do not mark ADR-0002 `ACCEPTED` without an explicit architecture decision.
