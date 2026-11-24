# AG-003.1B.3 — Authlib OIDC Compatibility PoC

## 2026-11-24 — Stage 2 architecture acceptance

Authlib 1.9.10 has received conditional owner approval
as the Google OIDC protocol client for the Development MVP.

The existing offline verification recorded 56 passed
and 1 strict xfailed on each required PoC target.

Stock PKCE DEBUG exposure remains a known security FAIL.

The application-specific mitigation is bounded to its
verified scope.

Use the matching hash-checked requirements profile.

See docs/adr/0002-authentication.md and
docs/development/PYTHON_DEPENDENCIES.md.

No live Google, staging or production activation is approved.

---

## 2026-11-24 — WP01.1 dependency remediation checkpoint

The offline PoC has been reverified with the final dependency
baseline on macOS ARM64 and Linux AMD64 using Python 3.12.

- Authlib: 1.9.10.
- cryptography: 50.0.2.
- joserfc: 1.8.0.
- setuptools: 84.1.0.
- Each target: 56 passed, 1 strict xfailed.
- Forced XFAIL: expected PKCELogExposure confirmed.
- Advisory audit: both PoC lockfiles passed.

Stock PKCE logging exposure remains a security failure.

For reproducible installation, select the matching lockfile
under this experiment's `requirements/` directory.

Full baseline evidence:
`docs/development/PYTHON_DEPENDENCIES.md`.

No live Google OIDC or production approval is implied.

---

Status: **EXPERIMENTAL / NOT PRODUCTION AUTHENTICATION**.

ADR-0002 remains **PROPOSED**; S02 remains **IN_PROGRESS**.

Recommendation: **ADOPT_CONDITIONALLY** Authlib for the OIDC protocol client,
not its stock state handling as the complete application security boundary.
See [decision report and proposed documentation updates](DECISION_REPORT.md).

## Scope and implementation

The original 26 unit tests remain intact. New `offline_flow.py` and
`test_authlib_flow.py` add 28 cases exercising real `StarletteOAuth2App`
authorization redirects and authorization-code callbacks through an ASGI app.
Authlib makes discovery, token and JWKS requests via httpx2 MockTransport to
an offline synthetic provider. No requests contact Google or any live server.

The provider enforces one-use codes, the configured redirect/client, and PKCE
S256. Synthetic ID tokens are signed with ephemeral RSA keys. Authlib's real
JWKS decoding, signature verification and claim validators run unchanged.
The new flow uses joserfc 1.8.0, installed as an Authlib dependency; existing
JOSE unit fixtures remain unchanged and retain their deprecation warning.

The memory cache, browser-session repository, fake provider and atomic adapter
are test components, not production integration. No ORM models, tables,
migrations, production auth routes, or application-session implementation were
created. Test-only routes use `/experiment/`, not production route contracts.

## Actual inspected Authlib 1.9.10 internals

Inspected installed package sources under `.venv/lib/python3.12/site-packages/`:

- `authlib/integrations/starlette_client/apps.py`: `authorize_redirect` calls
  `save_authorize_data`; `authorize_access_token` reads state, clears it, then
  exchanges the code and validates an ID token when both ID token and saved
  nonce exist. Provider error responses raise before state consumption.
- `authlib/integrations/starlette_client/integration.py`: cache usage requires
  a session marker. Cache `get` and `delete` are separate calls. Session-only
  `get_state_data` returns data without enforcing its saved `exp`; clearing
  expired entries afterward does not retroactively reject the current read.
- `authlib/integrations/base_client/async_openid.py`: obtains discovery/JWKS,
  validates ID-token signature/claims; default callback leeway is 120 seconds.
- `authlib/integrations/base_client/sync_app.py`: restores saved verifier and
  redirect URI; generates PKCE material and logs the verifier at DEBUG.
- `authlib/integrations/httpx_client/_compat.py`: uses installed httpx2.
- `joserfc/_rfc7519/claims.py`: future `iat` raises `InvalidClaimError`.

## State integration findings

`AtomicIntegration` subclasses `StarletteIntegration` using Authlib's framework
integration extension point. It consumes the server-side record atomically in
`get_state_data`; subsequent `clear_state_data` removes the request marker.
The memory consume checks TTL and browser-binding digest under one lock.

Observed comparisons:

1. Session-only stock Authlib accepted a state older than the configured TTL.
2. Stock cache get/delete allowed two concurrent callbacks to exchange codes.
   A barrier forces both reads before either deletion, without arbitrary sleeps.
   Two valid provider codes share one state, so provider code-replay rejection
   cannot mask the client's state-consumption race.
3. The atomic adapter permitted one exchange and rejected the other callback.
4. Replays, expired transactions and wrong-browser callbacks were rejected
   before exchange by the guarded composition.
5. Copied markers with mismatched server-side binding were rejected. The
   fail-closed consume burns that transaction; this availability tradeoff is
   deliberate and must be reviewed before implementing a persistent adapter.

These observations establish extension compatibility only. An asyncio lock
does not prove cross-worker PostgreSQL atomicity, crash safety or durability.
The fixture session snapshots model concurrent requests but are not a session
middleware implementation suitable for production.

## Application controls, not automatic Authlib guarantees

- Durable one-time state consumption with TTL and browser binding; a reviewed
  database transaction/claim design and concurrency tests across connections.
- Require verified OIDC userinfo; stock callback may return OAuth tokens when
  ID token or saved nonce is absent. The fixture application rejects this.
- Explicit expected issuer/audience, a configured algorithm policy and a
  deliberate clock-skew policy. Tests use RS256 and zero leeway with a fixed clock.
- Reject duplicate callback fields and mismatched response `iss`; an absent
  response `iss` is allowed here for provider compatibility. Provider mix-up
  protections and exact Google behavior need separate review.
- Consume provider-denied transactions explicitly; stock error handling does
  not do so. On timeout/token validation failure this adapter fails closed;
  retry starts a new authorization flow rather than reusing consumed state.
- Suppress/redact Authlib DEBUG logs and HTTP query logging. A test confirmed
  the stock DEBUG message contains the PKCE verifier. Generic fixture errors
  are sanitized, but complete deployment logging has not been verified.
- Application sessions, rotation, idle/absolute deadlines, logout/revocation,
  CSRF/Origin, operator provisioning, issuer/subject identity mapping and
  authorization remain application responsibilities.
- Bound storage growth, prune expired rows, limit requests, pin/validate trusted
  discovery endpoints, and define JWKS rotation, outage and retry policy.

Stock signed-cookie session storage is not encryption: keeping verifier/nonce
data server-side avoids relying on signed-cookie confidentiality. The fixture
browser receives an opaque pre-auth handle, not provider tokens or state data.

## OIDC-P01–OIDC-P12 evidence matrix

PASS below is restricted to the named offline observation. Passing a test that
demonstrates a stock gap does not turn that gap into a security PASS.

| ID | Observation and result | Remaining boundary |
|---|---|---|
| P01 | PASS: installed pins, registration, real callback compatibility | Advisory/support review UNVERIFIED |
| P02 | PASS: actual redirect S256; verifier restored at exchange; incorrect verifier rejected by fake provider | Google's enforcement UNVERIFIED |
| P03 | PASS: real flows have distinct state/nonce/challenge; nonce validated | Entropy quality and durable persistence not assessed |
| P04 | PASS: unknown state rejected by Authlib; duplicate/mix-up fields rejected by application | Application checks are not library defaults |
| P05 | PASS: real callback rejects nonce/signature/issuer/audience/expiry/iat/azp failures | JWKS rotation, live TLS and real Google UNVERIFIED; missing identity needs application guard |
| P06 | Stock TTL-on-read FAIL; atomic memory adapter expiry PASS | Persistent TTL enforcement UNVERIFIED |
| P07 | Atomic memory replay rejection PASS; stock denial cleanup NOT_PROVIDED | Durable replay/crash behavior UNVERIFIED |
| P08 | Stock cache atomicity FAIL; atomic memory adapter concurrency PASS | Multi-worker/database atomicity UNVERIFIED |
| P09 | PASS: fake server-session binding rejects another browser and copied marker | Real browser/cookie lifecycle UNVERIFIED |
| P10 | Generic response PASS; stock DEBUG confidentiality FAIL | Deployment log redaction UNVERIFIED |
| P11 | No production ORM changes; application-controlled adapter feasible | Real PostgreSQL transactions NOT_IMPLEMENTED/UNVERIFIED |
| P12 | PASS: existing backend 31 tests; no production code changes | End-to-end deployed authentication UNVERIFIED |

## Executed commands and results

Recorded 2026-11-22T07:59:08Z. Existing environments were reused; no dependencies
were installed or upgraded during this pass.

From `/Users/namnguyen/agentops-ai/experiments/auth-authlib-oidc`:

| Exact command | Exit | Actual result |
|---|---:|---|
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q` (before edits) | 0 | 26 passed, 1 warning in 0.53s |
| `.venv/bin/python -m pip check` | 0 | No broken requirements found. |
| `.venv/bin/python --version` | 0 | Python 3.12.9 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/test_authlib_flow.py -q --show-capture=no` (first integration run) | 1 | 25 passed, 1 failed, 1 warning in 1.00s |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -v` (final code) | 0 | 54 collected; 54 passed, 1 warning in 0.96s |
| `.venv/bin/python -m pip check` (after full run) | 0 | No broken requirements found. |

Initial failure: the new future-iat case expected `InvalidTokenError`, while
actual Authlib/joserfc rejected it with `InvalidClaimError`. Installed source
confirmed that behavior; only the new test's exact exception expectation was
corrected. Rejection assertions remain. Two additional coverage cases were
then added. No existing test assertion was weakened or removed.

From `/Users/namnguyen/agentops-ai/apps/api`:

| Exact command | Exit | Actual result |
|---|---:|---|
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | 0 | 31 passed, 1 warning in 6.75s |
| `.venv/bin/python -m pip check` | 0 | No broken requirements found. |

Warnings: existing PoC `authlib.jose` deprecation; backend httpx TestClient
deprecation. Pip reported an unavailable cache in the restricted environment,
but checks succeeded. A source-read command initially used the wrong working
directory (exit 2), then was corrected; it did not run tests or alter files.

Observed versions: Python 3.12.9; Authlib 1.9.10; FastAPI 0.165.0;
Starlette 1.10.0; SQLAlchemy 2.0.58; httpx2 2.16.2; httpx 0.28.1;
joserfc 1.8.0; cryptography 50.0.2; pytest 9.2.0.

## Determinism and isolation limits

Clock-sensitive integration paths use an injected clock, including the actual
joserfc time source. Concurrency uses a barrier and bounded wait, not sleep-based
timing. Ephemeral cryptographic values vary per run; assertions test invariants,
not exact token bytes. No credentials, keys or tokens are written to evidence.

Socket guards apply to all tests. They are Python guardrails, not an OS sandbox.
MockTransport is the only provider HTTP route and rejects unexpected origins.
Tests suppress captured failure logs and local-variable dumps. Existing unit
fixtures still use random keys; test outcomes do not depend on exact keys.

Unverified: real Google consent, client authentication/secrets, provider account
policy, browser behavior, JWKS rotation, deployment logging, security advisories,
durable state/session storage, race recovery, identity provisioning and migrations.
The fake provider uses token endpoint auth `none`; this does not verify a
confidential Google BFF client. No production-readiness claim is made.

## Git and next decision

Branch: `feat/ag-003-1b-authlib-oidc-poc`.
HEAD: `c6703e967f36aef38586e8864fbffd0058b28096`.
Four tracked documentation files were already modified before this pass and
were preserved. The entire PoC was already untracked. Production diffs are
empty. Root `git diff --check` reports pre-existing Markdown hard-break spaces
in the handoff (exit 2); they were not changed as part of this PoC.

Next action: Tech Lead reviews the conditional adoption recommendation and
proposed documentation updates in DECISION_REPORT.md. ADR-0002 is not approved;
AG-003.3B/AG-003.4 and S02 closeout remain gated. No commit or push performed.

## Security closeout evidence — 2026-11-22

This newer run supersedes the historical 54-case run above. Full reconciled
OIDC-P01–P12 findings and PostgreSQL consumption contract are in
[DECISION_REPORT.md](DECISION_REPORT.md). Stock OIDC-P10 remains FAIL even though
its strict XFAIL allows a green diagnostic suite. Experimental narrow redaction
passes; production logging remains UNVERIFIED.

Commands below were executed from the repository root except the two backend
commands, which were executed from `apps/api`:

| Exact command | Exit | Observed result |
|---|---|---|
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 experiments/auth-authlib-oidc/.venv/bin/python -m pytest experiments/auth-authlib-oidc/tests -q` | 0 | 56 passed, 1 xfailed, 1 warning, 1.26s |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 experiments/auth-authlib-oidc/.venv/bin/python -m pytest experiments/auth-authlib-oidc/tests -q --runxfail -k stock_debug_must_not_disclose_verifier` | 1 | 1 failed, 56 deselected, 1 warning, 0.41s; stock disclosure confirmed |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | 0 | Backend 31 passed, 1 warning, 6.72s |
| `experiments/auth-authlib-oidc/.venv/bin/python -m pip check` | 0 | No broken requirements found; cache disabled warning |
| `.venv/bin/python -m pip check` (backend) | 0 | No broken requirements found; cache disabled warning |
| `git diff --check` | 0 | No diagnostics after handoff trailing-space cleanup |

Changed this closeout: new `src/authlib_oidc_poc/logging_controls.py`; extended
`tests/test_authlib_flow.py`; revised this README and DECISION_REPORT; reconciled
project ADR-0002, S02 and CURRENT_STATE. `offline_flow.py` was inspected without
modification. No production source changes, package installs, Git staging,
commits, pushes or database operations were performed.

Suggested staging scope: the 17 non-ignored PoC source/config/test/document files
and reviewed closeout hunks in the three project documents. Those documents
already contained substantial user edits; inspect the whole diff before staging.
The pre-existing root README changes are separate and were not changed this pass.
Environments/caches are ignored. A targeted source secret scan is only a heuristic,
not proof of absence; synthetic inert credentials and runtime-generated ephemeral
keys are intentional. No private key file is needed. Keep ADR PROPOSED and S02 open.
