# AgentOps AI — Current State
**Checkpoint date:** 2026-11-23

**Current sprint:** S02 — Database & Authentication (`IN_PROGRESS`)

**Verification:** `PARTIALLY_VERIFIED`

**Current ticket:** AG-003.6 — Review-only S02 implementation handoff (`READY_FOR_TECH_LEAD_REVIEW`)

**Next planned gate:** Tech Lead reviews disabled authentication implementation and resolves release security gates

**Implementation owner:** User controls Mac-local edits, tests, Git and deployment.

> This handoff combines historical user evidence with observed repository inspection and execution on 2026-11-22. VERIFIED means an actual test/log was reviewed; USER_REPORTED means the user confirmed success without full final output. Isolated PoCs are not production auth.

## Current review checkpoint — 2026-11-23

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
See [complete source/test/security review](../sprints/S02_SECURITY_REVIEW.md).


### SEC-10 — Session Rotation Verification (2026-11-23)

**Sprint:** S02 — IN_PROGRESS / PARTIALLY_VERIFIED

**Current ticket:** AG-003.6 — READY_FOR_TECH_LEAD_REVIEW

**Architecture:** ADR-0002 PROPOSED

**Authentication:** IMPLEMENTED_FOR_REVIEW — disabled by default

#### Security remediation

SEC-10 identified an unintended cross-user session revocation
during account switching.

`AuthService.login()` previously revoked the existing browser
session using only its token digest.

The UPDATE now requires:

- Matching `AuthSession.token_digest`.
- Matching `AuthSession.user_id == user.id`.
- `AuthSession.revoked_at IS NULL`.

This preserves an existing session belonging to account A
when account B authenticates using the same browser.

Same-user session rotation continues to revoke the previous
session.

#### Verified PostgreSQL evidence

Date: 2026-11-23

| Check | Result |
|---|---|
| Empty database verification | PASS |
| Alembic upgrade | PASS |
| Alembic downgrade | PASS |
| Alembic second upgrade | PASS |
| Migration lifecycle | PASS |
| PostgreSQL integration | 6 passed in 1.04s |
| Cross-user session isolation | PASS |
| Same-user session rotation | PASS |

The SEC-10 assertions are part of the existing
`test_postgres_session_contract()`.

The PostgreSQL cancellation log originated from an expected
OIDC lock-cancellation regression.

The supplied excerpt confirms pytest PASS but does not include
the final Docker Compose exit code.

#### Current verification boundary

The previous full backend regression:

- 102 passed.
- 6 skipped.
- 0 warnings.
- 16.61 seconds.

This result predates SEC-10 and must be revalidated.

Existing SEC-03 through SEC-09 evidence remains preserved.

Live Google sign-in, production logging collectors, distributed
rate limiting, encryption-key rotation and operator provisioning
remain separate release gates.

#### Git and approval status

- Latest historically observed branch:
  `feat/ag-003-3b-identity-migrations`.
- Latest historically observed HEAD: `69486b8`.
- Newer Git state has not been independently confirmed.
- No new commit or push has been verified.
- Preserve unrelated root `README.md` modifications.
- ADR-0002 remains PROPOSED.
- Sprint S02 remains IN_PROGRESS.
- Authentication stays disabled by default.

#### Exactly one next action

Run the complete backend pytest regression after SEC-10.

If successful, record the exact test result, synchronize final
Sprint documentation and inspect scoped Git changes before
requesting owner approval for ADR-0002 and Sprint closeout.


## 1. Project baseline
| Component | Current state |
|---|---|
| Product | AgentOps AI, evidence-grounded market and competitor research SaaS; PRD v0.2 |
| Architecture | Modular monolith; ADR-0001 `PROPOSED` |
| Frontend/backend | React/TypeScript/Vite + FastAPI |
| Database | PostgreSQL 17 Docker Compose; readiness and least-privilege app role observed |
| ORM | Async SQLAlchemy 2.x/Psycopg 3, `autobegin=False`; AG-003.3A commit `cfab615` historically observed |
| Alembic | Guarded initial revision `0291ce4556fe`; upgrade user-reported PASS on disposable `agentops_migration_test`; four identity tables and 19 constraints observed; production/development migrations not authorized |
| Auth architecture | Google OIDC + Authlib 1.9.10 + FastAPI BFF + PostgreSQL opaque sessions **preferred proposal only** |
| Auth implementation | IMPLEMENTED_FOR_REVIEW — disabled by default; ADR-0002 PROPOSED|
| AI/workers/cloud | Future sprint scope; not implemented/verified |

## 2. Ticket register
| Ticket | Workflow | Evidence / blocker |
|---|---|---|
| S00 | `PENDING_CLOSEOUT` | Documentation signoff outstanding |
| S01 | `CLOSED`, partial verification | PR/merge/browser evidence pending |
| S02 | `IN_PROGRESS` | Identity foundation committed; production authentication, security and integration remain outstanding |
| AG-003.1A | `REPORTED_COMPLETE`, commit USER_REPORTED | FastAPI Users 30 passed, 1 xfailed; SHA/push not supplied |
| AG-003.1B.1 | Design comparison done | Google OIDC preferred over Auth0/Keycloak for MVP; not formal approval |
| AG-003.1B.2/2A | Contract review proposed | API, provisioning, sessions, OIDC state, CSRF; ADR still proposed |
| AG-003.1B.3 | `IN_PROGRESS` | 56 passed, 1 stock-security xfailed; offline integration verified; closeout review pending |
| AG-003.2 | `REPORTED_COMPLETE` | HTTP readiness/role verification observed; persistence marker/commit evidence pending |
| AG-003.3A | `REPORTED_COMPLETE` | Commit `cfab615`, push user-reported; backend regression 31/31 verified |
| AG-003.3B | `REPORTED_COMPLETE — COMMITTED / PUSH_REPORTED` | Commit `bae6fb0`; 39 passed, 1 skipped, 2 warnings; constraint, concurrency, migration lifecycle and permission verification; merge not verified |
| AG-003.4 | `IMPLEMENTED_FOR_REVIEW — activation blocked` | Five endpoints and sessions tested offline/disposable PostgreSQL; no live Google |
| AG-003.5 | `VERIFIED within stated scope` | Dependency, state/session and disable concurrency tests; real-user release gates remain |
| AG-003.6 | `READY_FOR_TECH_LEAD_REVIEW` | 102 backend passes/6 opt-in skips; 6 isolated DB passes; no commit or sprint closure |

## 3. Evidence ledger (2026-11-22)
### Earlier foundation
- AG-003.2: FastAPI `/api/v1/health` and `/api/v1/ready`, proxied Vite readiness returned HTTP 200; DB role verifier passed. Docker recovery user-reported; data-survival marker exact output pending.

- AG-003.3A: Alembic heads/history empty, versions contained only `.gitkeep`, guarded env.py. Earlier backend 31 passed, 1 warning / 6.47 s; AG-003.3A commit `cfab615` observed.

- AG-003.1A: FastAPI Users 15.0.5 / adapter 7.0.0 PoC ran 31 items: **30 passed, 1 expected xfailed, 1 warning, 0.40 s**. Both isolated and backend `pip check` passed; backend regression 31 passed / 1 warning / 6.62 s. Security matrix: AUTH-P03 FAIL (raw token storage boundary), AUTH-P05 NOT_PROVIDED (rolling idle expiry), AUTH-P08 NOT_PROVIDED (Origin/CSRF), AUTH-P09 FAIL (schema and adapter commits), AUTH-P10 UNVERIFIED (security/maintenance review). REJECT **unmodified stock** integration recommended, not an approved replacement.

### AG-003.1B — Google OIDC + Authlib
- User chose Google OIDC for the initial MVP; Tech Lead recommended Authlib + FastAPI BFF, PostgreSQL-backed opaque sessions and internal UUID owners. This is **not** an accepted ADR.

- Contract proposed: `GET /api/v1/auth/login/google`, `GET /api/v1/auth/callback/google`, `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`, `POST /api/v1/auth/logout`; `(issuer, sub)` identity, operator-approved provisioning, state/nonce/PKCE S256, short-lived one-time OIDC transaction storage, token digest at rest, 30m rolling idle / 12h absolute timeout, revocation, HttpOnly cookie, CSRF + Origin, explicit DB transactions. No implementation authorized.

- PoC environment observed: Homebrew Python 3.12.9; Authlib 1.9.10, FastAPI 0.165.0, Starlette 1.10.0, SQLAlchemy 2.0.58, httpx2 2.16.2, pytest 9.2.0; `pip check` PASS, OAuth import PASS, `.venv/` ignored by `.gitignore`.

- First PoC pytest output: **25 passed, 1 failed, 1 warning / 0.56 s**; test bug was duplicate `nonce` keyword in `test_p05_rejects_bad_claims[overrides2]`, not a demonstrated Authlib security failure. User reports fix and **26 passed**; full rerun output not supplied.

- Warning in PoC: deprecated `authlib.jose`; upgrade path to `joserfc` to be reviewed.

- Authlib method introspection: `authorize_redirect(request, redirect_uri=None, **kwargs)`, `authorize_access_token(request, **kwargs)`; registered `StarletteOAuth2App` has `save_authorize_data(request, **kwargs)`; no direct `get_state_data`/`clear_state_data`; `framework=StarletteIntegration`, `cache=None`. No inference of atomic state consume.

- Latest backend regression output: **31 passed, 1 Starlette `httpx`/TestClient warning, 6.69 s** (VERIFIED).

- Earlier callback verification gap is superseded by the closeout evidence below; live Google and PostgreSQL-backed authentication remain UNVERIFIED.

### AG-003.3B — Latest implementation evidence

- Four identity models and guarded Alembic revision `0291ce4556fe` committed as `bae6fb0`.
- PostgreSQL catalog: 19 constraints; seven negative tests PASS (output observed).
- Multi-connection concurrency, transactional DDL rollback, isolated empty → upgrade → downgrade → upgrade PASS (user-reported).
- Runtime DML permission matrix observed: four identity tables allowed, `app.alembic_version` denied.
- Fresh isolated regression of explicit grants/revokes PASS (user-reported); broader global/indirect default-privilege review not exhaustive.
- Final backend: **39 passed, 1 skipped, 2 warnings in 15.41s**. Opt-in DB integration test was skipped; warnings not fully reviewed.
- Branch `feat/ag-003-3b-identity-migrations`; push USER_REPORTED_SUCCESS; merge into `main` NOT_VERIFIED.
- Unrelated root `README.md` remains a preserved uncommitted change as of latest Git report.

## 4. Git checkpoint

- GitHub: https://github.com/NamNguyen0903/agentops-ai
- Historical AG-003.3A commit: `cfab6154b10299c5f4640afea81e4b88cd452e90`; push user-reported.
- AG-003.3B branch: `feat/ag-003-3b-identity-migrations`; latest observed commit: `bae6fb0` (`feat(db): add identity models and controlled migrations (AG-003.3B)`).
- AG-003.3B push user-reported successful; PR/merge to `main` NOT_VERIFIED.
- At last Git check, only root `README.md` remained modified outside the commit. Subsequent documentation updates require a separate scoped commit.
- Never stage `.venv/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/`, `.env.postgres` or secrets; review staged changes before commits.

## 5. Architecture gates and remaining work

1. AG-003.1B: Review Authlib conditional adoption, logging exposure, advisory status and ADR-0002; obtain explicit security/architecture approval.
2. AG-003.4: Implement approved Google OIDC login/callback, PostgreSQL one-time OIDC state, opaque sessions, provisioning, logout and CSRF/Origin checks.
3. AG-003.5: Principal resolution, protected endpoints, authorization and adversarial security tests.
4. AG-003.6: End-to-end auth, regression, persistence/recovery, Git/PR and sprint closeout.

S02 remains IN_PROGRESS. Historical PoC success is not production authentication verification.

## 6. Exactly one immediate next action

Review `docs/adr/0002-authentication.md` and `experiments/auth-authlib-oidc/DECISION_REPORT.md`, resolve the known security gates, and record an explicit architecture decision before starting AG-003.4.

Preserve the unrelated root `README.md` edits.

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

The Authlib PoC did not change production auth; separate AG-003.3B identity models and migration were subsequently committed.

## Latest observed execution — 2026-11-23

AG-003.1B remains IN_PROGRESS; AG-003.4 is BLOCKED on explicit decision approval.
Actual PostgreSQL state-service evidence: independent-connection one-winner consume,
replay/binding/expiry, lock-wait expiry and rollback passed in a disposable project.
Full backend 51 passed/2 skipped (the two opt-in cases separately passed); Authlib
56 passed/1 security xfailed; frontend 17 passed plus typecheck/lint/build; both pip
checks and 3/3 smoke checks passed. See S02 checkpoint for commands and limitations.
Stock PKCE logging remains security FAIL; new formatter is opt-in, not deployed.
Encryption/key policy, session APIs/CSRF and live Google remain unverified.
HEAD 69486b88ffd1a9e25ee13d4d1bcac9e997d26fae on feat/ag-003-3b-identity-migrations;
no commit/staging/push. Root README preserved; existing ADR/state-service edits retained.
Next action remains AG-003.1B owner decision-package review, not automatic AG-003.4.

## Final review-only checkpoint — 2026-11-23

Supersedes the gate-only checkpoint above: owner authorized review-only APIs while
keeping ADR PROPOSED. Five auth routes, AES-GCM OIDC context, existing DB-backed
sessions, CSRF/logout, trusted Google adapter and startup logging protection are
implemented but disabled by default. Full backend: 77 passed/3 skipped, 16.25s;
three opt-in database tests separately passed in 0.64s, including API→DB workflow.
Frontend 17 passed/typecheck/lint/build, PoC 56 passed/1 security xfailed, both pip
checks and 3/3 smoke passed. See final S02 addendum for scope/failures/commands.
No migrations changed, no normal agentops writes, no commit/push. HEAD unchanged.
Remaining: approval, real Google, full advisory/key-management/collector review,
distributed abuse controls, process-crash and normal-stack recovery verification.
Exactly one next action: Tech Lead reviews implementation and remaining release gates.
## 2026-11-23 — Latest Verified Checkpoint (AG-003.6)

**Sprint:** S02 — IN_PROGRESS / PARTIALLY_VERIFIED

**ADR-0002:** PROPOSED — approval pending

**Current ticket:** AG-003.6 — PostgreSQL integration verified; security and sprint closeout pending

**Authentication:** IMPLEMENTED_FOR_REVIEW — disabled by default

### Verified execution evidence

| Check | Result |
|---|---|
| Backend regression | 94 passed, 3 skipped, 1 warning, 16.32s |
| Google OIDC adapter offline | 12 passed, 1.14s |
| Disposable PostgreSQL integration | 3 passed, 1 warning, 0.69s |
| Alembic lifecycle | Empty → upgrade → downgrade → upgrade PASS |
| PostgreSQL privileges | Runtime identity-table DML and Alembic restrictions PASS |
| SEC-LOG-04 | Overlapping lifespan fix verified by regression tests |
| Shell syntax | PASS |
| Git whitespace | PASS |
| Disposable Docker cleanup | PASS |

The three opt-in PostgreSQL tests passed separately and remain skipped in the default backend regression run.

SEC-03 account-wide session revocation: PostgreSQL regression PASS (3 integration tests, 0.76s); disable/reactivate does not restore revoked sessions. Operator lifecycle and concurrency hardening remain open.

SEC-04 reusable auth dependency: 6/6 unit-level regression tests PASS. SEC-05 CSRF rotation: PostgreSQL integration 3/3 PASS (0.73s). Multi-tab CSRF behavior remains a known limitation. SEC-06 HTTP transport lifecycle review pending.

### Remaining blockers

- Formal architecture approval of ADR-0002.
- CSRF rotation and multi-tab behavior review.
- Operator account lifecycle and account-wide session revocation.
- Authentication key rotation and secret distribution.
- Security logging coverage beyond startup-configured handlers.
- Distributed rate limiting.
- Complete dependency advisory and HTTP transport lifecycle review.
- Real Google sign-in and deployment checks.
- Git commit, push and PR/merge verification.

### Git and safety

The latest historically observed branch is `feat/ag-003-3b-identity-migrations`, with HEAD `69486b8`. No newer commit or branch state has been confirmed.

Authentication source, tests and recent runner changes remain uncommitted at this checkpoint.

Preserve unrelated root `README.md` changes. Do not stage unrelated files or use `git add .`.

### Exactly one next action

Reconcile `docs/sprints/INDEX.md` and the S02 Ticket Register, then conduct final security closeout and targeted Git staging review.

Do not change ADR-0002 to ACCEPTED or Sprint S02 to CLOSED without explicit approval.

### 2026-11-23 — S02 Security Review Checkpoint (SEC-03 to SEC-06)

**Current status:** S02 IN_PROGRESS; ADR-0002 PROPOSED; authentication disabled by default.

**Verified evidence:**
- SEC-03: Account-wide session revocation — PostgreSQL integration PASS.
- SEC-04: Reusable authentication dependency — 6/6 tests PASS.
- SEC-05: CSRF rotation and stale-proof rejection — PostgreSQL integration PASS.
- SEC-06: Google OIDC transport lifecycle remediation — 13/13 tests PASS.
- Full backend regression: 101 passed, 3 skipped, 1 warning in 16.42s.

**Remaining work:**
- Re-run disposable PostgreSQL integration after the SEC-06 changes.
- Classify outstanding security and deployment risks.
- Review the remaining pytest warning.
- Complete ADR-0002 decision and S02 acceptance gates with explicit approval.
- Verify Git changes, preserve unrelated README modifications, then commit and push only approved S02 files.

**Next step:** Continue S02 closeout security blocker classification. Do not enable authentication or mark the sprint DONE.

## Current checkpoint — 2026-11-23 (post SEC-LOG-05)

### Verified evidence

- Full backend regression: **101 passed, 6 skipped in 16.21s**.
- Google OIDC offline regression: **13 passed**.
- SEC-LOG-05 focused regression: **9 passed**.
- Disposable PostgreSQL integration: **6 passed in 1.04s** (latest completed run, before SEC-LOG-05 test-only changes).
- Alembic migration lifecycle: **PASS**.

### Security review status

- SEC-06: Google OIDC transport lifecycle verified offline.
- SEC-07: PostgreSQL account-disable concurrency verified.
- SEC-10: PostgreSQL cross-user session isolation verified.
- SEC-LOG-05: Placeholder test removed; real overlapping-lifespan test strengthened with formatter restoration assertion.
- Authentication routes, session/CSRF enforcement and OIDC state consumption reviewed for Development MVP.

### Project status

- Branch: `feat/ag-003-3b-identity-migrations`.
- Sprint S02: **IN_PROGRESS**.
- AG-003.6: **READY_FOR_FINAL_GIT_REVIEW**.
- ADR-0002: **PROPOSED**.
- Authentication: **disabled by default**.
- Production authentication: **NOT_APPROVED**.
- No new commit, push or merge verified.
- Preserve unrelated root `README.md` changes.

### Exactly one next action

Perform final scoped Git review. Review changed and untracked S02 files, confirm documentation consistency and security-sensitive content, then prepare an explicit staging allowlist. Do not stage the root `README.md` or commit before Tech Lead review.