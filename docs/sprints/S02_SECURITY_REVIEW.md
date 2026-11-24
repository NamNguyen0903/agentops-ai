# S02 — Final Development MVP Security Review

## 2026-11-24 — Stage 2 architecture acceptance

- Stage 1 dependency/security remediation: COMPLETE LOCALLY.
- Stage 2 architecture and authentication approval: ACCEPTED.
- ADR-0001: ACCEPTED.
- ADR-0002: ACCEPTED — DEVELOPMENT MVP ONLY.
- Authlib 1.9.10: CONDITIONALLY APPROVED.
- Operator-managed provisioning policy: APPROVED.
- Operator runbook: documented with existing integration evidence.
- Authentication: IMPLEMENTED_FOR_REVIEW; disabled by default.
- Live provider and real browser acceptance: deferred release gates.
- Stock PKCE DEBUG disclosure: known security FAIL.
- Production approval: NOT APPROVED.
- Remote CI and reviewed Git incorporation: PENDING.
- Sprint S02: IN_PROGRESS / PARTIAL.
- Current acceptance accounting: 10/11 VERIFIED (90.9%).

The owner explicitly approved the architecture package,
conditional adoption and release-gate boundaries on
2026-11-24, including a separate approval of ADR-0001.

Acceptance criterion 4 is satisfied by the recorded
architecture decisions.

Acceptance criterion 5 is accepted within the owner-approved
Development MVP boundary using the previously verified
offline integration, dependency baseline and scoped security
controls.

This does not establish live Google, deployed browser,
operator CLI or production security acceptance.

Criterion 10 remains PARTIAL until the work is committed,
reviewed and incorporated through the approved Git workflow.

The final sprint sign-off remains a separate closure gate.

Evidence:

- docs/adr/0001-architecture.md
- docs/adr/0002-authentication.md
- docs/development/PYTHON_DEPENDENCIES.md
- docs/development/OPERATOR_PROVISIONING.md

No application tests were rerun for this documentation
checkpoint. Prior verified results remain applicable to
the unchanged application implementation.

### Final Development MVP security disposition

- WP01-01: dependency remediation verified locally.
- WP01-02: stock PKCE logging failure retained;
  bounded application mitigation accepted.
- WP01-03: broader logging/deployment checks remain gates.
- WP01-04: operator policy and minimal development workflow
  accepted; real-user enrollment and operations remain gates.

The clean application lockfile audit is not a universal
security guarantee.

All real-user and production release gates in ADR-0002
remain mandatory.

### Exactly one current next action

Stage 3 — Git Delivery and CI.

Review the complete local change manifest and prepare
explicit staging and commit boundaries.

Do not repeat Stage 1 or Stage 2 without changed inputs
or a newly discovered blocker.

Do not push, merge, change PR bases, rewrite history,
activate authentication or start S03 without the
appropriate owner authorization.

Sprint S02 must remain IN_PROGRESS until criterion 10
and final owner sign-off are satisfied.

---

## 2026-11-24 — WP01.1 dependency remediation checkpoint

- WP01.1 dependency remediation: VERIFIED_LOCALLY.
- Required dependency lockfiles: 9/9.
- Final setuptools baseline: 84.1.0.
- Application lockfile advisory audit: 9/9 passed.
- Backend regression: 100 passed, 8 skipped on each of four targets.
- Offline Authlib PoC: 56 passed, 1 strict xfailed on each
  of two required targets.
- Generator replay and smoke compilation: 4/4 targets passed.
- Docker runtime verification: AMD64 and ARM64 passed.
- Isolated PostgreSQL migration lifecycle: passed.
- PostgreSQL integration: 7 passed.
- Stock Authlib PKCE DEBUG exposure remains a known security FAIL.
- Authentication remains IMPLEMENTED_FOR_REVIEW and disabled by default.
- Remote CI and Git integration remain pending.
- ADR-0002 remains PROPOSED.
- Production approval: NOT APPROVED.
- Sprint S02: IN_PROGRESS / PARTIAL, 8/11 (72.7%).

See `docs/development/PYTHON_DEPENDENCIES.md` for the
dependency policy, lockfile checksums, verification evidence
and residual limitations.

### WP01 security finding disposition

- WP01-01: dependency baseline remediation verified locally.
- WP01-02: stock Authlib PKCE logging failure retained;
  application-specific mitigation remains bounded.
- WP01-03: broader logging and deployment verification remain
  release gates.
- WP01-04: provisioning and live acceptance boundaries require
  explicit owner decisions.

The setuptools findings PYSEC-2026-3447 and
GHSA-xmj3-9gf7-h52w were addressed by upgrading to 84.1.0.

A clean application lockfile audit is not a complete production
security assessment.

The next action is Stage 2: obtain explicit owner decisions
on ADR-0002, conditional Authlib adoption, operator provisioning,
development acceptance boundaries and remaining release gates.

Do not regenerate dependency lockfiles or repeat completed
regression suites without changed inputs or a new blocker.
Do not start S03 or mark S02 complete.

---

Date: 2026-11-23. Verdict: **READY_FOR_TECH_LEAD_REVIEW**, not deployment approval.
ADR-0002: **PROPOSED**. Sprint S02: **IN_PROGRESS**. Authentication remains disabled by default.

## Scope and evidence reconciliation

User-supplied checkpoint: 101 passed/3 skipped/1 warning; adapter 13/13;
auth dependency 6/6; PostgreSQL 3/3 after SEC-06. Those records remain historical.
This pass inspected the actual SEC-03 account revocation service, SEC-04 dependency,
SEC-05 CSRF tests, SEC-06 per-client transport ownership and shared logging-lifespan
changes. It preserved them, then added the account-disable concurrency barrier and
new regression evidence below. Earlier gate-only statements are superseded for
review-only implementation, not for real-user activation.

## Findings and remediation

| ID | Severity | Root cause / scenario | Action and residual risk |
|---|---|---|---|
| SEC-07 | P1 | principal locked AuthSession then read User without locking; disable locks User then revokes sessions. A check could read the previous active account while disable held its account lock. | principal now resolves owner, locks User first, revalidates and locks AuthSession second. Real PostgreSQL tests observe the blocked query and reject read/CSRF/logout after disable commits. Checks ordered before disable may finish; this does not cancel already-authorized in-flight business operations. |
| SEC-08 | P2 | pytest integration marker was unregistered. | Registered marker; final suite has zero warnings. No checks weakened or deselected to hide a warning. |
| SEC-09 | P1 dependency policy | Original cryptography>=44 and implicit joserfc floor permitted older security-affected releases even though installed versions were newer. | Minimums raised to cryptography 50.0.2 and joserfc 1.8.0. Runtime versions unchanged. Full transitive lock/audit remains a release gate. |
| SEC-10 | P2 — Session isolation / account-switching policy | `AuthService.login()` previously revoked `old_token` using only its digest, without restricting revocation to the newly authenticated user. During account switching, a session belonging to account A could be revoked when account B logged in. | The UPDATE now requires matching `token_digest`, matching `user_id` and `revoked_at IS NULL`. Cross-user sessions are preserved; same-user rotation still revokes the old session. PostgreSQL regression PASS. No remote exploit or production incident established. |
| R2-01 | P1 | Missing persisted nonce/PKCE context was rejected only after exchange started. | GoogleOIDC.exchange validates context before any provider I/O; malformed-context regression passes. |
| R2-02 | P0 release gate | Authlib 1.9.10 DEBUG event contains raw verifier; handler-only formatting does not sanitize raw records for later handlers. | Exact upstream logger filter now tested against actual pinned URL builder; safe formatter covers configured handlers. External collectors/later handlers for other events remain outside the guarantee. Stock PoC XFAIL remains security FAIL. |
| R2-03 | P1 | Broad callback error handling returned generic JSON without useful diagnostics. | Allowlisted event/category/frame diagnostics preserve troubleshooting information without exception values, headers or token payloads. |
| R2-04 | P1 | Same-site but cross-origin browser GET could rotate CSRF proof when Origin absent. | Reject Sec-Fetch-Site same-site as well as cross-site; foreign/duplicate Origin rejected. Legacy requests with no Origin/Fetch Metadata rely on SOP. Multi-tab proof rotation remains a documented UX limitation. |
| R2-05 | P2 | Startup/cleanup exceptions could leave logging protection or DB resources unreleased. | Cleanup covered by finally and overlapping lifespan ownership (existing SEC-LOG-04); regressions preserved. |
| R2-06 | P2 | urlsplit defers port validation and strips some control characters. | Invalid ports/control characters rejected during AuthSettings validation. |

SEC-07 is a serialization/ordering fix; no previously committed revocation bypass
is claimed to have been exploited. User → session lock ordering matches login and
account disable. It serializes same-user requests briefly and can reduce throughput;
transactions remain bounded and contain no provider network calls.

## Source-grounded security matrix

Paths below are relative to apps/api/src/agentops_api; line ranges describe this checkpoint.
PASS means only the stated observation, never blanket production certification.

| Claim | Source / function / lines | Regression evidence | Status |
|---|---|---|---|
| Persist state before redirect | services/auth.py issue_state 46–51; api/routes/auth.py login 61–74 | test_auth_postgres.py::test_postgres_session_contract | PASS |
| Atomic consume and post-lock expiry | services/oidc_state.py _consume_oidc_state 12–77 | test_oidc_state_postgres.py::test_postgres_state_consumption | PASS independent connections |
| Commit before provider exchange, one callback winner | services/auth.py consume 53–56; api/routes/auth.py callback 77–104 | concurrent API callbacks; provider independently locks consumed row NOWAIT, sees cleared context; exactly one exchange | PASS |
| Browser mismatch burns, replay/expired state rejects | services/oidc_state.py 42–77 | state PostgreSQL regression | PASS |
| Denial/storage errors prevent exchange | api/routes/auth.py callback 77–104 | test_callback_denial_consumes_and_storage_failure_never_exchanges | PASS route fake; real consume separately verified |
| Cancellation/uncertain commit | services/oidc_state.py consume_oidc_state 84–94 | real lock-wait cancellation; injected failure after actual DB commit; replay rejected after commit | PARTIAL: no process kill/network commit-loss fault |
| PKCE/nonce/signature/issuer/audience/expiry | services/google_oidc.py GoogleOIDC 54–105 | test_google_oidc.py actual Authlib with fake signed provider | PASS offline; live Google NOT_TESTED |
| HTTP transport ownership/trust | services/google_oidc.py TrustedGoogleOAuthClient 41–47, TrustedGoogleOAuthApp 49–52, transport 12–36 | 13 adapter cases including closed-transport regression | PASS offline |
| Digest sessions, rotation, expiry, revocation | services/auth.py login 58–71, principal 73–107 | test_postgres_session_contract | PASS PostgreSQL |
| Cross-user session isolation (SEC-10) | `services/auth.py` — `AuthService.login()`; `api/routes/auth.py` — `callback()` | `tests/test_auth_postgres.py::test_postgres_session_contract` — two provisioned users, account switching and same-user rotation | PASS on disposable PostgreSQL; browser account-switching UX not independently tested |
| Account disable versus principal | services/auth.py principal 73–107, disable_user_and_revoke_sessions 108–135 | test_auth_disable_concurrency.py::test_disable_serializes_principal[read/csrf/logout] | PASS observed row-lock wait |
| Authenticated user cannot come from client ID | api/dependencies/auth.py require_principal 8–54 | test_auth_dependency.py (7 cases) | PASS route unit tests; S03 resources not implemented |
| Origin, CSRF, idempotent logout | api/routes/auth.py csrf 116–127, logout 130–143 | auth_review and actual DB session tests | PASS tested cases; browser UX PARTIAL |
| Cookie flags/no-cache/default off | api/routes/auth.py cookie 49–51, finish 40–44; main.py create_app 23–94 | auth_review tests | PASS offline; real proxy/browser NOT_TESTED |
| AEAD and key validation | services/auth.py ContextCipher 24–38; core/auth_config.py AuthSettings | tamper/key/state/binding/version tests | PASS; rotation/deployed key custody NOT_TESTED |
| No secret payload in configured output | core/security_logging.py log_failure 16–29, PKCELogFilter 32–37, SecurityFormatter 40–66 | auth_round2/security_logging/auth_review tests | PARTIAL deployment coverage |
| Overlapping app lifespans | core/security_logging.py acquire 77–113 / release 116–140; main.py lifespan 40–72 | existing SEC-LOG-04 regressions | PASS tested process scope |
| Pool/timeouts | core/orm.py OrmDatabase 67–110 | infrastructure tests; state cancellation test | PARTIAL: pool exhaustion/process death not fault-tested |
| Rate limiting | api/routes/auth.py RateLimit 14–33 | bounded process-local unit test | PASS local scope; distributed NOT_TESTED |
| Operator provisioning | identity mapping rejects absent/inactive rows, services/auth.py login | PostgreSQL unprovisioned login rejection | PARTIAL: no operator UI/CLI or approved runbook |

Application state handling deliberately uses create_authorization_url, fetch_access_token
and parse_id_token with the application database boundary. It does not rely on
StarletteIntegration's default get/delete store or a memory cache for cross-worker
safety. The separate PoC tests stock authorize_redirect/authorize_access_token.

## Final test evidence and commands

| Check | Actual command / cwd | Observed result / exit |
|---|---|---|
| Backend | apps/api: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q --tb=short` | 102 passed, 6 skipped, 0 warnings, 16.61s; 0 |
| Adapter + auth dependency | root: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 apps/api/.venv/bin/python -m pytest apps/api/tests/test_auth_dependency.py apps/api/tests/test_google_oidc.py -q --tb=short` | 20 passed (7 dependency + 13 adapter), 1.38s; 0 |
| Migration lifecycle + PostgreSQL | root: command below | Empty→upgrade→downgrade→upgrade PASS; role assertions PASS; 6 passed, 1.00s; 0 |
| Authlib PoC, earlier this review | experiments/auth-authlib-oidc: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q` | 56 passed, 1 xfailed, 1 deprecation warning, 1.07s; 0; stock security FAIL |
| Frontend | apps/web: `npm run typecheck && npm run lint && npm run test && npm run build` | 17 tests/2 files, 1.30s; all commands exit 0; build 585ms |
| Dependencies | root: `apps/api/.venv/bin/python -m pip check` and `experiments/auth-authlib-oidc/.venv/bin/python -m pip check` | Both no broken requirements; 0; pip cache-disabled warnings |
| Shell | root: `sh -n apps/api/tests/migration_lifecycle/run.sh` | 0 |
| Whitespace | root: `git diff --check` | no diagnostics; 0 |

```sh
docker compose -p agentops-s02-final-review -f apps/api/tests/migration_lifecycle/compose.yaml up --abort-on-container-exit --exit-code-from runner
docker compose -p agentops-s02-final-review -f apps/api/tests/migration_lifecycle/compose.yaml down
```

The six opt-in cases remain SKIPPED in the default suite and all six passed in the
isolated database run. Cancellation produces an expected PostgreSQL cancelled-query
log, not a test failure. The existing standalone concurrency test uses the disposable
agentops_migration_test database with rollback-only writes. Normal agentops was not
modified. No revision/model/normal Compose changes were needed.

Backend Python 3.12.2; PoC 3.12.9; isolated Linux arm64 PostgreSQL 17.12/Python 3.12.
An attempted no-build-isolation editable install failed (missing setuptools, exit 2).
Normal build-isolated `apps/api/.venv/bin/python -m pip install --no-deps -e apps/api`
succeeded (exit 0); no runtime dependency upgrades occurred. The earlier fixture/path
failures remain recorded in S02 historical checkpoints; this final regression passed.


### SEC-10 — Post-fix PostgreSQL verification (2026-11-23)

**Scope:** Session isolation and account-switching behavior.

**Implementation:**
- `apps/api/src/agentops_api/services/auth.py`
- `apps/api/tests/test_auth_postgres.py`

**Change:** The old-session revocation UPDATE is restricted to
the newly authenticated user ID, the matching token digest,
and sessions that have not previously been revoked.

**PostgreSQL regression scenarios:**

| Scenario | Expected behavior | Result |
|---|---|---|
| Account A logs in | A receives an active session | PASS |
| Account B logs in with A's old token | A's session remains valid | PASS |
| Account B receives a new session | B's session resolves to B | PASS |
| Account B logs in again with B's token | B's previous session is revoked | PASS |
| Account A after B's session rotation | A's original session remains valid | PASS |

**Observed disposable PostgreSQL execution:**

| Check | Result |
|---|---|
| Empty database | PASS |
| Alembic upgrade | PASS |
| Alembic downgrade | PASS |
| Alembic second upgrade | PASS |
| Migration lifecycle | PASS |
| PostgreSQL integration suite | 6 passed in 1.04s |
| Expected lock-cancellation log | Observed; no test failure |

The SEC-10 assertions were added to the existing
`test_postgres_session_contract()` rather than a separate
test function. Therefore, the suite still contains six
PostgreSQL test cases.

The provided terminal excerpt confirms all six pytest cases
passed. The final Docker Compose exit code was not included
in the excerpt.

**Previous full backend baseline:**
102 passed, 6 skipped, 0 warnings in 16.61s.
This baseline predates SEC-10 and must not be represented
as a post-fix full-suite result.

**Verification classification:**
SEC-10 — VERIFIED_FOR_DEVELOPMENT_REVIEW.

**Residual limitations:**
- Real-browser account switching has not been tested.
- Live Google authentication has not been verified.
- Account switching replaces the browser cookie but does
  not invalidate another user's session in PostgreSQL.
- Production deployment and authentication activation
  remain outside the approved scope.

**Required follow-up:**
Run the full backend regression after SEC-10 and review
the final Git diff before owner approval.

## Dependency assessment — 2026-11-23

Observed versions: Authlib 1.9.10, joserfc 1.8.0, cryptography 50.0.2, httpx2/httpcore2
2.16.2, Starlette 1.10.0, FastAPI 0.165.0, SQLAlchemy 2.0.58, Psycopg 3.3.9.
Authlib's changelog documents security fixes through 1.9.10. Selected primary-source
advisories were checked, not an exhaustive graph audit:

- Authlib fixes: https://docs.authlib.org/en/stable/upgrades/changelog.html
- joserfc issuer-claim typing: https://github.com/authlib/joserfc/security/advisories/GHSA-r74j-q665-7rpj — fixed 1.7.3; installed 1.8.0 is newer.
- joserfc key-type confusion: https://github.com/authlib/joserfc/security/advisories/GHSA-vvgp-wfq3-pjxj — patched-version field 1.7.7; installed 1.8.0 is newer; application restricts RS256.
- cryptography wheel OpenSSL: https://github.com/pyca/cryptography/security/advisories/GHSA-537c-gmf6-5ccf — patched wheels 48.0.1; installed 50.0.2 is newer. Source-build OpenSSL needs separate assessment.
- Starlette Host validation: https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr — fixed 1.0.1; installed 1.10.0 is newer.

No claim of zero vulnerabilities. Unreviewed advisories, complete transitive graph,
reproducible locking and deployed TLS/logging configuration remain release gates.

## Acceptance and gate classification

| Area | Development MVP review | Staging / real-user gate |
|---|---|---|
| Atomic state and account-disable ordering | Verified in disposable PostgreSQL | Process-kill/network-commit faults still untested |
| Sessions and reusable principal dependency | Ready for source review | S03 ownership enforcement must use dependency, never request owner ID |
| Single-process rate limit | Acceptable proposed local-only limitation | Distributed or gateway abuse controls before internet exposure |
| Multi-tab CSRF rotation | Stale proof safely rejected; refetch/retry UX limitation | Approve/test browser UX; no relaxation of validation |
| Single encryption key | Acceptable for isolated synthetic testing; replacing key invalidates pending login | Secret custody, rotation/rollback and backup policy before real users |
| Logging | Tested handlers and upstream verifier filter | Approve complete handler/collector/proxy config before enabling outside tests |
| Live Google | Not needed for offline code review | Required before claiming real Google sign-in acceptance, including local real-credential use |
| Cleanup/retention | Disposable tests cleaned; no production scheduler | Define state/session retention and cleanup before sustained real-user operation |
| Operator lifecycle | Disable/revoke service verified | Provisioning/reactivation runbook and permissions need approval |
| Architecture / Git / closeout | Code can be reviewed now | Owner approves ADR and activation; no automatic commit or sprint closure |

No remaining demonstrated P0/P1 code defect is being intentionally waived for the
review-only scope. This is not proof of absence. Activation approvals remain open.
Reverse proxy must trust only configured proxy hops, reject spoofed forwarding/Host,
use correct HTTPS origin, and avoid logging queries/cookies. Those deployment
controls were not configured or tested in this pass.

## Decision package

1. Authlib 1.9.10: suitable for CONDITIONAL adoption as protocol client with app-owned state/session controls; not stock turnkey authentication.
2. PostgreSQL state store: safe to submit for review based on independent connection and callback evidence; no exactly-once claim.
3. Local development: synthetic/disposable review is supported. Do not enable real Google credentials or normal DB migrations without explicit approval.
4. Staging: not yet approved; logging, proxy/TLS, secrets, live-provider validation and abuse controls remain gates.
5. Real users: not yet safe to authorize deployment from this evidence alone.
6. ADR recommendation: **REVISE**, incorporating lock ordering and explicit local-versus-release gates; keep status PROPOSED until owner decision.
7. S02 verdict: **READY_FOR_TECH_LEAD_REVIEW**, not CLOSED/DONE.

**SEC-10 review decision:** The cross-user session revocation
finding is resolved within disposable PostgreSQL regression
scope. Same-user rotation remains supported. Authentication
activation and production/browser acceptance are not implied.

**Post-SEC-10 acceptance:** Final backend regression and scoped
Git review remain pending. ADR-0002 stays PROPOSED and
Sprint S02 stays IN_PROGRESS.
Next action: Tech Lead reviews this package and owner decides ADR revisions, local
activation scope and explicit carry-forward of staging gates before sprint closeout.

## Git and changed files

Branch: feat/ag-003-3b-identity-migrations.
Initial/final HEAD: 69486b88ffd1a9e25ee13d4d1bcac9e997d26fae.
No branch changes, staging, commits, pushes, merges, PRs or activation.
Root README verified byte-for-byte unchanged against the review-start SHA-256 snapshot.

Latest focused changes: services/auth.py (lock ordering), test_auth_disable_concurrency.py
(new), test_auth_dependency.py (client-ID spoofing regression), pyproject.toml
(marker registration and reviewed dependency floors), migration_lifecycle/run.sh
(include concurrency tests), and the four requested documents. Earlier Round 2 fixes
and user SEC-03–06 work are preserved in the full uncommitted working tree.

## Security review checkpoint — 2026-11-23 (post SEC-LOG-05)

### Verification evidence

- Full backend regression: **101 passed, 6 skipped in 16.21s**.
- Google OIDC offline regression: **13 passed**.
- SEC-LOG-05 focused regression (`test_auth_round2.py`): **9 passed**.
- Disposable PostgreSQL integration (latest completed run): **6 passed in 1.04s**, performed before SEC-LOG-05 test-only changes.
- PostgreSQL migration lifecycle: **PASS**.

### Security review decisions

- **SEC-06:** Verified for development review; independent trusted OAuth HTTP transports.
- **SEC-07:** Verified with PostgreSQL concurrency regression.
- **SEC-10:** Verified with PostgreSQL cross-user session isolation regression.
- **SEC-LOG-05:** Verified for development review. Removed the placeholder overlapping-lifespan test and strengthened the real regression to assert formatter restoration after both application lifespans stop.
- **Authentication routes, session/CSRF enforcement, OIDC state consumption:** Source reviewed; acceptable for development review within tested boundaries.

### Remaining release gates

- ADR-0002 remains **PROPOSED**.
- Authentication remains **disabled by default**.
- Live Google OIDC and browser acceptance tests are not complete.
- External logging collectors and distributed rate limiting are not verified.
- Deployment security, secrets/key rotation, and operational failure scenarios require separate acceptance.

**Decision:** `READY_FOR_FINAL_GIT_REVIEW`, not production release approval.

## Isolated S02 closeout follow-up — 2026-11-23

ADR-0002 remains PROPOSED; auth disabled by default. Conditional adoption has not
become approval. Fresh installed-package verification found and repaired a missing
`api/dependencies/__init__.py`; source-path tests alone had masked package omission.
Current backend result is 100 passed / 8 skipped; seven opt-in PostgreSQL cases
passed separately. Stock Authlib DEBUG disclosure remains security FAIL despite
the expected xfail. No auth/schema policy change, production rollout or remote
integration is implied. Owner approval and deployment security gates remain open.
See [S02 closeout evidence](../sprints/S02_CLOSEOUT.md) for execution, failures and
acceptance accounting; older test totals above remain historical checkpoints.
