# AG-003.1B.3 — Authlib security decision report

**Date:** 2026-11-22
**Status:** PROPOSED FOR REVIEW. ADR-0002 remains PROPOSED; S02 remains IN_PROGRESS.
**Recommendation:** ADOPT_CONDITIONALLY Authlib 1.9.10 for OIDC protocol processing only.

## Execution evidence

The original 54 cases are preserved. Three added cases verify the stock logging
security failure, experimental redaction, and delegation to actual Authlib entry
points. Latest run: **56 passed, 1 xfailed**, 1 existing JOSE deprecation warning,
1.26s, exit 0. XFAIL is a security FAIL, not authentication acceptance.
The same regression with `--runxfail` produced **1 failed, 56 deselected**, 0.41s,
exit 1, with a fixed diagnostic and no verifier in displayed output.
Backend regression: **31 passed**, 1 existing TestClient deprecation warning,
6.72s, exit 0. Both `pip check` commands: `No broken requirements found.`, exit 0;
both also warned that the local pip cache was not writable and disabled it.
No packages were installed. Metadata consistency does not establish advisory safety.

## Actual protocol coverage

`offline_flow.py` calls the registered `StarletteOAuth2App.authorize_redirect()`
and `authorize_access_token()`. A new delegating spy test invokes the original
methods and observes one call to each and one token exchange. The actual library
performs discovery, authorization URL creation, PKCE, token exchange and signed
ID-token validation. Only HTTP transport, provider, clock and session/state
persistence are fakes. This is offline library integration, not Google or
production database integration. The fake provider uses token authentication
`none`; confidential-client authentication remains unverified.

## PKCE log exposure and narrow mitigation

Installed Authlib 1.9.10 `integrations/base_client/sync_app.py:285`, in
`_create_oauth2_authorization_url`, eagerly interpolates the verifier into
`log.debug(f"Using code_verifier: {code_verifier!r}")`. The logger is
`authlib.integrations.base_client.sync_app`. DEBUG must be enabled for emission.

This is a sensitive-secret disclosure. A verifier alone is not a bearer token;
exploitation also needs the matching usable code and relevant client conditions.
Exposing it defeats PKCE's additional protection against intercepted codes.
Operational severity is high if authorization material and DEBUG logs are both
accessible to an attacker; no CVSS score, CVE or production incident is asserted.

The experiment's `PKCEVerifierFilter` replaces this known event's message before
handlers receive it, clears format arguments, and preserves level, source,
timestamp and unrelated diagnostics. It is installed on the exact emitting
logger for the regression and removed afterward. Ancestor logger filters would
not protect propagated child events. This is an opt-in demonstration, not a
production logging configuration or universal sanitizer. An upstream message
change requires reassessment. Handler/collector exports, HTTP URL query logs,
headers, exception text, state, codes, tokens and secrets need separate controls.
Never enable locals or raw HTTP body/header logging. Runtime traceback diagnostics
remain enabled; fixture capture is suppressed to avoid displaying synthetic secrets.
The stock observation test and strict-XFAIL security contract remain intact.

## Proposed PostgreSQL state-consumption contract — NOT IMPLEMENTED

The in-process `asyncio.Lock` serializes only coroutines sharing the same store
and event loop. Different workers have independent locks and dictionaries;
restart loses state, and snapshot session writes can overwrite markers. These
fixtures cannot establish distributed atomicity, persistence or crash safety.

Proposed storage: a unique digest of high-entropy state, trusted provider identity,
browser-binding digest, issued/expiry timestamps, encrypted recoverable nonce and
PKCE verifier, and terminal consumption metadata. Never store codes or provider
tokens in logs. Encryption/key access and retention need schema/security approval.
Proposed TTL is 300 seconds, consistent with this fixture; final policy needs approval.

1. Validate callback structure and trusted provider configuration; require a
   server-side browser binding. Begin an explicit short database transaction,
   with bounded connection, lock and statement timeouts and no provider I/O.
2. Lookup the unique state digest and acquire `SELECT ... FOR UPDATE`. After
   acquiring the lock, use database wall-clock time (`clock_timestamp()`) to
   reject `expires_at <= now`; transaction-start time alone is insufficient
   after a lock wait. Reject absent or already-consumed records generically.
3. Mark the locked pending record terminal consumed and clear stored secret
   material. Validate expiry and constant-time binding comparison under this
   lock; return decrypted transaction data only when both are valid. Commit
   the terminal write even on expired/binding-mismatch records. This matches
   the fixture's burn-on-mismatch policy; attackers who know a state can cause
   denial of service. Missing session markers are rejected before consumption.
4. Only after confirmed commit may the winning callback exchange its code.
   A concurrent callback waits within its timeout, then observes consumed state
   and performs no exchange. No automatic retries after an uncertain commit.
5. Crash before commit rolls back; another callback may consume the record if
   still valid. Crash after commit, exchange timeout, or unknown commit outcome
   requires a fresh login. Never restore state or reclaim via a lease. A provider
   exchange and local commit cannot be made one atomic transaction. This is
   at-most-one authorized exchange attempt, not exactly-once login success.
6. Provider denial should consume a valid transaction as well. Expired and
   consumed tombstones can be cleaned asynchronously under an approved retention
   policy; cleanup is not the expiry enforcement mechanism. Session creation
   after verified identity is a separate reviewed transaction, not implemented.

Required future PostgreSQL tests: independent connections/processes racing on
one state, waiting past expiry, mismatch consumption, rollback before commit,
process termination before/after commit, lost commit acknowledgement, lock
and statement timeouts, cleanup racing with consumption, restart persistence,
and no provider I/O while a transaction is open. No such tests or migrations
were implemented in this closeout. DDL/role approval remains a separate gate.

## Reconciled verification matrix

PASS below is limited to the named offline observation. Every production
requirement remains UNVERIFIED; no aggregate production acceptance is implied.

| ID | Stock / library finding | Experimental result | Production |
|---|---|---|---|
| OIDC-P01 | Pinned imports and dependency constraints compatible; advisories UNVERIFIED | PASS imports and pip check | UNVERIFIED maintenance/advisories |
| OIDC-P02 | Real S256 redirect/exchange supported | PASS positive and verifier mismatch | UNVERIFIED Google client configuration |
| OIDC-P03 | State, nonce and challenge generated | PASS distinct independent flows | UNVERIFIED deployed storage |
| OIDC-P04 | Unknown state rejected; duplicate/mix-up boundary needs app controls | PASS rejection before exchange | UNVERIFIED callback policy |
| OIDC-P05 | Signature/issuer/audience/expiry/nonce checked when ID token and nonce exist; missing identity is not fail-closed by itself | PASS negative claims and application identity gate | UNVERIFIED live keys/rotation/identity |
| OIDC-P06 | FAIL session-only expiry enforcement on read | PASS memory expiry boundary | UNVERIFIED database expiry |
| OIDC-P07 | Sequential success consumes state; provider-denial cleanup NOT_PROVIDED | PASS replay and denial consumption | UNVERIFIED durable failure handling |
| OIDC-P08 | FAIL cache get/delete atomicity; two exchanges observed | PASS one winner using memory consume | UNVERIFIED multiple workers/crashes |
| OIDC-P09 | Session marker provided, durable browser sessions NOT_PROVIDED | PASS fake browser binding including copied marker | UNVERIFIED browser/session security |
| OIDC-P10 | FAIL verifier DEBUG disclosure, strict XFAIL | PASS narrow filter and generic callback errors | UNVERIFIED all logging/export paths |
| OIDC-P11 | Application DB integration NOT_PROVIDED | No ORM identity integration implemented | UNVERIFIED schema/transactions |
| OIDC-P12 | Library compatibility alone is insufficient | PASS 31 backend regressions; experiment isolation | UNVERIFIED production authentication |

## Decision gates and next action

Keep ADOPT_CONDITIONALLY: approve the durable state contract, dependency/advisory
review, trusted discovery/JWKS network policy, confidential-client configuration,
full logging policy and app-owned sessions/CSRF/logout/provisioning/authorization
before production implementation. Python networking monkeypatches are guardrails,
not an OS sandbox. No live Google calls or production credentials were used.

Project ADR, sprint and handoff now carry this evidence; earlier 26/54-case
runs remain historical. Next action: Tech Lead reviews AG-003.1B.3 closeout and
conditional adoption gates. Do not infer approval for another ticket.
