# AgentOps AI — Current State

**Checkpoint date:** 2026-11-22\
**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS`)\
**Verification:** `PARTIALLY_VERIFIED`\
**Current ticket:** AG-003.1B.3 — Authlib OIDC Compatibility PoC (`IN_PROGRESS`)\
**Next planned gate:** AG-003.1B.3 closeout review → explicit architecture decision\
**Implementation owner:** User controls Mac-local edits, tests, Git and deployment.

> This handoff combines historical user evidence with observed repository inspection and execution on 2026-11-22. VERIFIED means an actual test/log was reviewed; USER_REPORTED means the user confirmed success without full final output. Isolated PoCs are not production auth.

## 1. Project baseline

| Component | Current state |
|---|---|
| Product | AgentOps AI, evidence-grounded market and competitor research SaaS; PRD v0.2 |
| Architecture | Modular monolith; ADR-0001 `PROPOSED` |
| Frontend/backend | React/TypeScript/Vite + FastAPI |
| Database | PostgreSQL 17 Docker Compose; readiness and least-privilege app role observed |
| ORM | Async SQLAlchemy 2.x/Psycopg 3, `autobegin=False`; AG-003.3A commit `cfab615` historically observed |
| Alembic | Guarded infrastructure only; no application migration revisions or identity tables |
| Auth architecture | Google OIDC + Authlib 1.9.10 + FastAPI BFF + PostgreSQL opaque sessions **preferred proposal only** |
| Auth implementation | NOT_IMPLEMENTED; ADR-0002 still `PROPOSED` |
| AI/workers/cloud | Future sprint scope; not implemented/verified |

## 2. Ticket register

| Ticket | Workflow | Evidence / blocker |
|---|---|---|
| S00 | `PENDING_CLOSEOUT` | Documentation signoff outstanding |
| S01 | `CLOSED`, partial verification | PR/merge/browser evidence pending |
| S02 | `IN_PROGRESS` | Auth identity and security controls not yet implemented |
| AG-003.1A | `REPORTED_COMPLETE`, commit USER_REPORTED | FastAPI Users 30 passed, 1 xfailed; SHA/push not supplied |
| AG-003.1B.1 | Design comparison done | Google OIDC preferred over Auth0/Keycloak for MVP; not formal approval |
| AG-003.1B.2/2A | Contract review proposed | API, provisioning, sessions, OIDC state, CSRF; ADR still proposed |
| AG-003.1B.3 | `IN_PROGRESS` | 56 passed, 1 stock-security xfailed; offline integration verified; closeout review pending |
| AG-003.2 | `REPORTED_COMPLETE` | HTTP readiness/role verification observed; persistence marker/commit evidence pending |
| AG-003.3A | `REPORTED_COMPLETE` | Commit `cfab615`, push user-reported; backend regression 31/31 verified |
| AG-003.3B | `BLOCKED` | ADR approval, schema/migration role, auth compatibility |
| AG-003.4 | `PLANNED — BLOCKED` | Production login/session/CSRF not implemented |
| AG-003.5 | `PLANNED` | Authorization and security tests pending |
| AG-003.6 | `PLANNED` | Integration, regression, Git and sprint closeout pending |

## 3. Evidence ledger (2026-11-22)

### Earlier foundation

- AG-003.2: FastAPI `/api/v1/health` and `/api/v1/ready`, proxied Vite readiness returned HTTP 200; DB role verifier passed. Docker recovery user-reported; data-survival marker exact output pending.
- AG-003.3A: Alembic heads/history empty, versions contained only `.gitkeep`, guarded env.py. Earlier backend 31 passed, 1 warning / 6.47 s; AG-003.3A commit `cfab615` observed.
- AG-003.1A: FastAPI Users 15.0.5 / adapter 7.0.0 PoC ran 31 items: **30 passed, 1 expected xfailed, 1 warning, 0.40 s**. Both isolated and backend `pip check` passed; backend regression 31 passed / 1 warning / 6.62 s. Security matrix: AUTH-P03 FAIL (raw token storage boundary), AUTH-P05 NOT_PROVIDED (rolling idle expiry), AUTH-P08 NOT_PROVIDED (Origin/CSRF), AUTH-P09 FAIL (schema and adapter commits), AUTH-P10 UNVERIFIED (security/maintenance review). REJECT *unmodified stock* integration recommended, not an approved replacement.

### AG-003.1B — Google OIDC + Authlib

- User chose Google OIDC for the initial MVP; Tech Lead recommended Authlib + FastAPI BFF, PostgreSQL-backed opaque sessions and internal UUID owners. This is **not** an accepted ADR.
- Contract proposed: `GET /api/v1/auth/login/google`, `GET /api/v1/auth/callback/google`, `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`, `POST /api/v1/auth/logout`; `(issuer, sub)` identity, operator-approved provisioning, state/nonce/PKCE S256, short-lived one-time OIDC transaction storage, token digest at rest, 30m rolling idle / 12h absolute timeout, revocation, HttpOnly cookie, CSRF + Origin, explicit DB transactions. No implementation authorized.
- PoC environment observed: Homebrew Python 3.12.9; Authlib 1.9.10, FastAPI 0.165.0, Starlette 1.10.0, SQLAlchemy 2.0.58, httpx2 2.16.2, pytest 9.2.0; `pip check` PASS, OAuth import PASS, `.venv/` ignored by `.gitignore`.
- First PoC pytest output: **25 passed, 1 failed, 1 warning / 0.56 s**; test bug was duplicate `nonce` keyword in `test_p05_rejects_bad_claims[overrides2]`, not a demonstrated Authlib security failure. User reports fix and **26 passed**; full rerun output not supplied.
- Warning in PoC: deprecated `authlib.jose`; upgrade path to `joserfc` to be reviewed.
- Authlib method introspection: `authorize_redirect(request, redirect_uri=None, **kwargs)`, `authorize_access_token(request, **kwargs)`; registered `StarletteOAuth2App` has `save_authorize_data(request, **kwargs)`; no direct `get_state_data`/`clear_state_data`; `framework=StarletteIntegration`, `cache=None`. No inference of atomic state consume.
- Latest backend regression output: **31 passed, 1 Starlette `httpx`/TestClient warning, 6.69 s** (VERIFIED).
- Earlier callback verification gap is superseded by the closeout evidence below; live Google and PostgreSQL-backed authentication remain UNVERIFIED.

## 4. Git checkpoint

- GitHub: https://github.com/NamNguyen0903/agentops-ai
- AG-003.3A commit historically observed: `cfab6154b10299c5f4640afea81e4b88cd452e90`; push USER_REPORTED.
- User later confirmed AG-003.1A commit after staged-file review; **SHA and push output not supplied**. Do not mark remote merge verified.
- Observed 2026-11-22: branch `feat/ag-003-1b-authlib-oidc-poc`, HEAD `c6703e967f36aef38586e8864fbffd0058b28096`. Four tracked documentation files modified; PoC untracked; index empty. Root README edits predate this pass. No commit/push performed. Environments and caches ignored. Remote state not reverified.
- Never stage `.venv/`, `.venv-broken/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/`, `.env.postgres` or secrets. Review scoped staged diff before commit/push.

## 5. Architecture gates and remaining work

1. AG-003.1B.3: Tech Lead reviews completed offline security closeout; advisory and production integration gates remain open.
2. Explicitly approve or revise ADR-0002 and `app` schema/migration role. Until approval, AG-003.3B and AG-003.4 are BLOCKED.
3. AG-003.3B: identity/session models and reviewed Alembic migration with a least-privilege migration role.
4. AG-003.4: Google login/callback, app session, logout, CSRF and fail-closed behavior.
5. AG-003.5: authorization and security tests.
6. AG-003.6: cross-component integration, frontend/backend regression, persistence/recovery, documentation/Git closeout and user signoff.

**One-day acceleration:** a target only; no security gate, negative test, or owner approval is waived.

## 6. Exactly one immediate next action

Tech Lead reviews AG-003.1B.3 closeout and conditional adoption gates. No next implementation ticket is authorized.

## 7. Documentation update rules

Record observed terminal evidence separately from user reports. Update `docs/sprints/S02.md` first, then this handoff and ADR-0002 decision notes. Do not change the ADR status to ACCEPTED without explicit approval, and do not invent Git SHAs, tests, merge or deployment status.

## AG-003.1B.3 security closeout — observed 2026-11-22

Latest execution supersedes earlier 26/54-case checkpoints without altering their
historical evidence: **56 passed, 1 xfailed**, 1 warning, 1.26s (exit 0).
The strict XFAIL is **OIDC-P10 stock security FAIL**. Forced execution yielded
1 failed, 56 deselected, 1 warning, 0.41s (exit 1), confirming the exposure.
Experimental redaction and actual Authlib method delegation tests passed.
Backend: 31 passed, 1 warning, 6.72s (exit 0). Both pip checks found no broken
requirements (exit 0; cache-disabled warnings). No advisory clearance inferred.

See [decision report](../../experiments/auth-authlib-oidc/DECISION_REPORT.md) for
OIDC-P01–P12 classifications, exact leak source, conditional severity and the
proposed PostgreSQL atomic-consumption/concurrency/crash/expiry contract.
The adapter remains memory-only; production multi-worker behavior is UNVERIFIED.
Recommendation ADOPT_CONDITIONALLY; ADR-0002 remains PROPOSED and S02 IN_PROGRESS.
No production auth, identity models, revisions or database changes were made.
