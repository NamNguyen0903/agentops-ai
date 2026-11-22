# ADR-0002 — Identity, Database and Authentication Architecture

| Field | Value |
|---|---|
| Status | PROPOSED — READY FOR DECISION |
| Sprint | S02 — Database & Authentication |
| Ticket | AG-003.1 |
| Date | 2026-11-21 (proposal); infrastructure note 2026-11-22 |
| Product baseline | PRD v0.2 |
| Architecture baseline | Overview v1.1 |
| Related decision | ADR-0001 — Proposed |
| Implementation status | Authentication NOT_IMPLEMENTED; PostgreSQL/ORM infrastructure partially implemented (see status note) |
| Verification status | DESIGN_REVIEWED; AG-003.1A isolated PoC runtime VERIFIED |

> This document specifies a proposed authentication architecture. Its approval gate remains open. Independent PostgreSQL/ORM infrastructure has been implemented and partially verified; this does not authorize identity models, auth sessions, or migrations.

## 1. Context

AgentOps AI is an evidence-grounded market and competitor research SaaS built around a FastAPI backend, React/TypeScript frontend and modular-monolith architecture.

Sprint S01 established the application foundation. Sprint S02 introduces PostgreSQL persistence and authentication.

The product requires user authentication, logout, owner-scoped resource access and secure handling of credentials.

The PRD does not mandate a particular authentication provider, local password system, JWT format or cookie transport.

This ADR therefore separates existing requirements from proposed implementation choices.

### 1.1 Source-of-truth hierarchy

1\. PRD v0.2 — Product requirements.

2\. Approved ADRs — Binding architectural decisions.

3\. Architecture overview v1.1 — Existing architectural proposal.

4\. Sprint reports — Implementation scope and acceptance evidence.

5\. Current handoff — Latest recorded implementation checkpoint.

ADR-0001 remains Proposed until explicitly approved.

### 1.2 Existing requirements

| Requirement | Source |
|---|---|
| Authentication and logout | FR-001, US-001 |
| Owner-scoped tasks, reports and evidence | FR-002, PRD §15.1 |
| Reject expired sessions | US-001 |
| Maintained authentication solution | PRD §15.1 |
| Avoid custom cryptography | PRD §15.1 |
| PostgreSQL persistence | PRD §12 |
| Uniqueness, foreign keys and migrations | PRD §12.2 |
| User-scoped idempotency | FR-005 |
| Cross-task evidence isolation | FR-012 |
| Secrets, encryption and least privilege | NFR-006 |
| Deterministic automated testing | NFR-008 |
| Migration compatibility and rollback review | NFR-009 |

### 1.3 New architectural proposals

The following require explicit approval:

- Local password-based accounts for the development MVP.
- Operator-only account provisioning.
- PostgreSQL-backed opaque authentication sessions.
- HttpOnly cookie transport.
- Argon2id password hashing.
- Authentication library selection.
- Identity mapping and session schema.
- CSRF protection strategy.
- Password and session lifecycle policies.
- Exact authentication API contracts.

No public registration, MFA, password recovery or production onboarding capability is assumed.

## 2. Architecture Decision Summary

### Recommended direction

Use PostgreSQL as the authoritative application database and store revocable, opaque authentication sessions server-side.

The browser receives only a random session token in an HttpOnly cookie. The raw token is not stored in PostgreSQL; its cryptographic digest is stored instead.

Protected requests validate the session against PostgreSQL and resolve the authenticated application user.

Authentication and authorization remain separate concerns:

- Authentication establishes the current principal.
- Authorization determines access to specific resources.
- Resource ownership is always enforced on the backend.

### Proposed component choices

| Concern | Preferred choice | Decision status |
|---|---|---|
| Application database | PostgreSQL | Proposed implementation |
| ORM | SQLAlchemy 2.x | Proposed |
| Migration engine | Alembic | Proposed |
| PostgreSQL driver | Psycopg 3 | Proposed; sync/async mode pending |
| User identifier | UUID | Proposed |
| Authentication framework | Stock FastAPI Users + database strategy | **REJECT recommended after PoC**; no replacement approved |
| Browser credential transport | HttpOnly cookie | Proposed |
| Session persistence | PostgreSQL | Proposed |
| Password verification | Maintained Argon2id implementation | Proposed |
| CSRF | Session-bound token and Origin enforcement | Proposed |
| Future external identity | OIDC via maintained client library | Deferred |
| Public registration | Disabled for initial development | Proposed |
| Self-service password recovery | Not implemented initially | Explicit MVP limitation |

**Important:** FastAPI Users is a conditional candidate, not an unconditional approval. Its maintenance-mode status and integration gaps must pass the dependency review in Section 4.

## 3. Authentication Alternatives

Authentication provider, credential transport and session storage are independent decisions.

| Option | Advantages | Limitations | Decision |
|---|---|---|---|
| FastAPI Users + cookie + database strategy | Documented FastAPI integration, database-backed token strategy, login/logout building blocks | PoC confirms raw token at storage boundary, internal commits, no rolling idle expiry or Origin/CSRF in stock composition | **REJECT unmodified stock integration — recommendation, not ADR acceptance** |
| Authlib + managed OIDC + application session | Established OAuth/OIDC integration, delegates identity-provider password handling | Requires an identity provider, callback integration and separate application session lifecycle | Preferred fallback |
| Custom local authentication using security primitives | Maximum control over schema and behavior | Higher risk of security mistakes and long-term maintenance burden | Not approved as default |
| JWT stored by the React SPA | Simple bearer transport for external API clients | Browser-token exposure, refresh/revocation complexity | Not selected |
| Starlette signed-cookie SessionMiddleware | Small integration surface | Client-side signed session is not equivalent to database-backed revocable opaque sessions | Not selected |
| Archived FastAPI session library | Potentially simple examples | No ongoing project maintenance | Rejected |

### 3.1 Preferred conditional candidate: FastAPI Users

Evaluate the current supported FastAPI Users release with:

- `CookieTransport`.
- `DatabaseStrategy`.
- SQLAlchemy integration.
- UUID user IDs.
- Database token persistence.
- Password verification.
- Current-user dependency injection.
- Logout and database token deletion.

Its documented strategy supports token storage and invalidation, but exact integration with the proposed schema, token-at-rest requirements, session deadlines, CSRF contract and account provisioning must be demonstrated.

**Do not assume that FastAPI Users supplies built-in CSRF protection for this application's cookie-based login/logout flow.**

A working authentication router is not sufficient evidence of complete security compliance.

The implementation review must confirm that the selected configuration supports or safely integrates:

1\. Token hashing or an approved token-at-rest protection mechanism.

2\. Server-enforced absolute expiry.

3\. Server-enforced idle expiry where required.

4\. Account-wide session revocation.

5\. Disabled-account rejection.

6\. Authentication-session rotation.

7\. Origin validation and CSRF protection.

8\. Suitable authentication error handling.

9\. Compatibility with the selected FastAPI, Pydantic, SQLAlchemy and Python versions.

10\. Reasonable maintenance and security-response expectations.

The database strategy and cookie transport being available does not by itself prove that these ten conditions are met.

### 3.2 Maintenance exception

FastAPI Users is currently in maintenance mode.

Before adopting it:

- Pin an approved compatible release.
- Review its maintenance policy and known security issues.
- Review direct and transitive dependencies.
- Confirm that the necessary extension points exist.
- Run a small integration proof of concept.
- Record a migration or replacement strategy.

If maintenance risk or integration complexity is unacceptable, reject this candidate and use a managed OIDC solution rather than improvising an authentication framework.

### 3.3 Fallback: Authlib with OIDC

Authlib is the preferred candidate for standards-based OAuth/OIDC integration.

Under this fallback:

- Authentication occurs through an approved identity provider.
- The backend validates the OIDC response through the selected library.
- The application maps issuer and subject to an internal UUID user.
- AgentOps AI creates its own application session if required.
- PostgreSQL remains authoritative for application users and resource ownership.

Authlib's OAuth/OIDC client support does not imply that it supplies the application's PostgreSQL session store or CSRF policy automatically.

A compatible identity provider, operational costs, test configuration and account-recovery responsibilities must be approved separately.

## 4. Dependency Approval Gate

**This gate blocks implementation of login, logout and session management.**

Before beginning AG-003.4:

- [ ] Select the authentication solution and version range.
- [ ] Verify the supported Python, FastAPI and SQLAlchemy versions.
- [ ] Review maintenance policy and security advisories.
- [ ] Verify cookie and database-token behavior.
- [ ] Verify the token storage format and revocation semantics.
- [ ] Verify supported credential models and user mapping.
- [ ] Define how CSRF protection integrates.
- [ ] Validate absolute and idle expiry behavior.
- [ ] Demonstrate logout and account-wide revocation.
- [ ] Record a fallback if any critical requirement cannot be met.

The candidate may be rejected without changing the approved product requirements.

AG-003.2 PostgreSQL infrastructure can proceed independently after its own configuration is approved. Authentication-specific migrations must follow the chosen identity model and library contract.

## 5. Identity and Database Model

### 5.1 Guiding principles

- Internal application ownership uses `users.id`.
- Authentication identities never serve directly as resource ownership keys.
- Database constraints protect integrity independently of API validation.
- Credential material is isolated from public user representation.
- No research tables are created as part of AG-003.1.

### 5.2 Proposed `users`

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Primary key |
| `is_active` | Boolean | Account enabled state |
| `created_at` | Timestamptz | Creation time |
| `updated_at` | Timestamptz | Last update time |

`users.id` is the stable owner identifier for research tasks in S03.

### 5.3 Proposed `auth_identities`

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID FK | Application user |
| `issuer` | Text | Authentication namespace |
| `subject` | Text | Immutable identity within issuer |
| `created_at` | Timestamptz | Identity creation |

Constraints:

- Unique `(issuer, subject)`.
- Non-null issuer and subject.
- Foreign key to `users.id`.
- Account linking requires a separate verified and approved flow.

**Decision:** Prefer a separate `auth_identities` table from the beginning.

Rationale: A user can later have a local identity and an OIDC identity without changing resource ownership or overloading the `users` table.

This introduces one additional table but avoids an early identity-model migration.

For local identities, use a fixed local issuer and immutable generated subject. Do not use a mutable login email as the subject.

### 5.4 Proposed `local_credentials`

| Field | Type | Purpose |
|---|---|---|
| `user_id` | UUID FK | Credential owner |
| `login_identifier` | Text | Normalized unique login |
| `password_hash` | Text | Encoded password hash |
| `password_changed_at` | Timestamptz | Password change time |

Constraints and rules:

- One local password credential per user initially.
- Unique normalized login identifier enforced in PostgreSQL.
- No plaintext or reversibly encrypted passwords.
- Login identifiers do not establish verified email ownership.
- Password hash parameters and salt are represented by the selected hashing implementation.

The exact ORM structure must remain compatible with the selected authentication library. If the library requires a different user schema, revisit the design before creating migrations.

### 5.5 Proposed `auth_sessions`

This is the logical session contract, not an approved SQLAlchemy model.

| Field | Purpose |
|---|---|
| `id` | Internal session identifier |
| `user_id` | Authenticated user |
| `token_digest` | Digest of high-entropy session token |
| `created_at` | Session creation |
| `last_seen_at` | Qualifying activity |
| `idle_expires_at` | Idle-expiry deadline |
| `absolute_expires_at` | Maximum lifetime |
| `revoked_at` | Optional revocation marker |

Constraints and rules:

- Unique token digest.
- Every authenticated session refers to a user.
- Expiry and revocation are enforced server-side.
- No raw session token is stored in database records or logs.
- Session records persist across API restarts.
- A disabled user must not gain authorization through an existing session.

Session metadata such as device information is deferred until it has a documented product or security purpose.

**Compatibility gate:** The chosen authentication library's database strategy must support this logical contract or an explicitly reviewed equivalent.

Do not implement a parallel custom session framework merely to preserve the proposed table layout.

## 6. Password and Account Policy

This section applies only if local password authentication is approved.

### 6.1 Password storage

Use Argon2id through a maintained implementation.

Proposed initial benchmarking baseline:

- Memory: 19 MiB.
- Iterations: 2.
- Parallelism: 1.

These are starting parameters, not final performance settings.

Benchmark verification cost, memory pressure and concurrency using the actual target container.

The hashing implementation must generate independent salts and support rehashing when the policy changes.

### 6.2 Password acceptance

Proposed development defaults:

- At least 15 characters while MFA is unavailable.
- Bounded maximum input length, provisionally 128 Unicode characters.
- Permit spaces, Unicode, paste and password managers.
- Do not impose arbitrary character-class requirements.
- Do not silently truncate or trim passwords.
- Document and consistently apply any Unicode normalization policy.
- Reject known-compromised passwords using an approved privacy-preserving mechanism.
- Do not require arbitrary periodic password rotation.

Length and normalization choices require library compatibility review.

### 6.3 Credential verification

- Use generic login failure messages.
- Apply rate limits before expensive password verification.
- Use constant-time-safe verification primitives provided by the library.
- Consider a dummy verification path for unknown identifiers.
- Do not run expensive password hashing directly on the async event loop.
- Limit concurrent verification work.
- Do not hold long-lived database locks during password verification.
- Recheck account and credential state before committing a new session.

### 6.4 Account provisioning

Initial development accounts may be provisioned by an authorized operator.

No account credentials or default passwords may appear in migrations, Git, seed data or documentation.

Provisioning must use non-logged secret input and an auditable operator workflow.

Public registration and self-service recovery are not included in this phase.

Before inviting real users, approve an onboarding, recovery and identity-verification policy.

## 7. Session Lifecycle

### 7.1 Token properties

- Generate authentication tokens using a cryptographically secure random generator.
- Proposed entropy: at least 256 bits.
- **Proposed contract (requires explicit approval):** store only a digest of a high-entropy bearer session token; do not persist the raw reusable token. This stricter rule is why stock DatabaseStrategy does not qualify.
- Never expose tokens in URLs, logs or analytics.
- Rotate the token on authentication and privilege changes where applicable.

A high-entropy random session token may be protected with a cryptographic digest. Passwords require adaptive password hashing instead.

### 7.2 Proposed lifetimes

| Setting | Development proposal |
|---|---|
| Idle timeout | 30 minutes |
| Absolute session lifetime | 12 hours |
| Remember me | Disabled |
| Persistent session across server restart | Required |
| Server-side logout revocation | Required |

Idle timeout and absolute expiry must be tested independently.

The absolute lifetime cannot be extended by ordinary activity.

If the chosen library does not natively support an idle timeout, this is a compatibility issue to resolve before promising that behavior.

### 7.3 Cookie policy

For HTTPS deployment:

- `HttpOnly=true`.
- `Secure=true`.
- `SameSite=Lax`.
- `Path=/`.
- No `Domain` attribute.
- Prefer `\\_\\_Host-` cookie naming when its requirements are satisfied.

For loopback-only HTTP development:

- Use an explicitly named development cookie.
- Permit insecure transport only under a development environment setting.
- Reject insecure cookie configuration in staging or production.
- Use a consistent hostname: either `localhost` or `127.0.0.1`.

Cookie security settings must be validated by inspecting actual `Set-Cookie` responses.

### 7.4 Login

Proposed high-level flow:

1\. Client obtains any required CSRF bootstrap state.

2\. Server validates request format and trusted Origin.

3\. Server enforces rate limits.

4\. Authentication library verifies credentials.

5\. Server confirms active account status.

6\. Server invalidates any pre-login authentication context.

7\. Server creates a fresh authenticated session.

8\. Session persistence succeeds before a successful response is returned.

9\. Server sets the authentication cookie.

10\. Client retrieves the current-user representation.

Do not reuse attacker-controlled session identifiers.

### 7.5 Authenticated request

A protected request succeeds only if:

- A valid session credential exists.
- The session is not expired or revoked.
- The associated user is active.
- The requested resource belongs to that user or access is explicitly authorized.

Database unavailability must fail closed.

### 7.6 Logout

Logout is a state-changing operation.

It must:

- Enforce the approved CSRF and Origin rules.
- Invalidate the session server-side.
- Clear the browser cookie.
- Return a sanitized response.
- Be safely repeatable without exposing additional account state.

If server-side revocation cannot be committed, the API must not claim that logout was fully completed.

Password changes, account disablement and recovery events should revoke affected sessions according to an approved policy.

Database backup restoration must not resurrect previously revoked sessions.

## 8. CSRF Protection

Cookie-based authentication requires a deliberate CSRF defense.

**SameSite cookies and CORS do not replace CSRF protection.**

### 8.1 Proposed policy

For state-changing browser requests:

- Validate the `Origin` header against an exact configured allowlist.
- Require the approved CSRF proof.
- Bind CSRF state to the relevant session or pre-authentication context.
- Reject missing, invalid or cross-session tokens.
- Rotate CSRF state when the authenticated session changes.
- Never place CSRF secrets in URLs or logs.

### 8.2 Bootstrap design

Do not automatically create a persistent PostgreSQL pre-authentication session.

First evaluate whether the chosen authentication framework can support a simpler, secure bootstrap approach using a session-bound or correctly authenticated CSRF token.

A pre-authentication database session is permitted only if the selected design requires it and the lifecycle is documented.

Bootstrap responses must be non-cacheable and must not grant authenticated privileges.

### 8.3 Browser boundary

The React application should call the backend through same-origin `/api` paths.

Do not enable wildcard credentialed CORS.

If frontend and backend are deployed on different origins, review cookie scope, CORS, CSRF and proxy configuration before enabling cross-origin credentials.

## 9. Authorization

Authentication establishes a principal; it does not automatically authorize access.

The application principal exposes the internal UUID user ID and minimal necessary account state.

It never exposes password hashes, session digests or secret tokens.

### Future resource ownership

For S03:

- Resource ownership derives from the authenticated principal.
- Clients cannot assign arbitrary `owner_id`.
- Task queries are owner-scoped.
- Report and evidence queries are scoped through owned tasks.
- Retry-parent ownership is checked.
- Idempotency keys are scoped to the authenticated user.
- Inaccessible resources return consistent sanitized errors.
- Authorization must occur in application services and persistence queries, not only in route guards.

Two-user negative tests are required before claiming owner isolation works.

## 10. Authentication API Contract Boundaries

The following capabilities are required, but exact route paths and schemas remain subject to review:

- Authentication/CSRF bootstrap.
- Login.
- Current-user inspection.
- Logout.

### Proposed HTTP behavior

| HTTP status | Meaning |
|---|---|
| `401` | Missing or invalid authentication, expired session, generic invalid credentials |
| `403` | CSRF or Origin rejection |
| `404` | Resource inaccessible to the principal |
| `422` | Invalid request structure |
| `429` | Rate limit reached |
| `503` | Required authentication or database dependency unavailable |

Credential values must never be echoed in validation errors.

Authentication responses should use `Cache-Control: no-store`.

Exact routes, request bodies, error objects and OpenAPI contracts require review before implementation.

## 11. PostgreSQL and Migration Strategy

### 11.1 Database configuration

- PostgreSQL is authoritative for application persistence.
- SQLAlchemy 2.x is the proposed ORM.
- Alembic manages schema history.
- Psycopg 3 is the proposed driver.
- Synchronization mode and connection-pool configuration require approval.
- Application runtime uses a non-superuser database role.
- Migration permissions are separate from normal application permissions.
- Credentials are provided through protected runtime configuration.
- Development, test, staging and production databases are isolated.

### 11.2 Migration principles

- Maintain one reviewed migration history.
- Do not use application startup `create_all` as migration management.
- Do not run implicit migrations on service startup.
- Review every generated migration.
- Prefer additive schema changes.
- Explicitly review destructive changes and rollback compatibility.
- Never create accounts with embedded credentials in migrations.

### 11.3 Health endpoints

Keep `/api/v1/health` as a dependency-independent liveness endpoint.

Introduce a separate readiness mechanism for database/schema compatibility when that capability is implemented.

### 11.4 Testing

Use actual PostgreSQL for:

- Database uniqueness and foreign-key constraints.
- Transaction behavior.
- Migration upgrade verification.
- Session persistence.
- Concurrent account-state changes.
- Revocation behavior.

SQLite does not replace PostgreSQL integration evidence for these requirements.

## 12. Security Controls and Threat Model

| Threat | Required response |
|---|---|
| Credential stuffing | Shared rate limiting, bounded verification capacity |
| Account enumeration | Generic login errors and timing-aware verification |
| Session theft | Secure cookie attributes, token rotation, revocation |
| Session fixation | New session after authentication |
| CSRF | Origin validation plus CSRF proof |
| XSS | React escaping, safe report rendering, CSP |
| Broken object-level authorization | Owner-scoped queries and negative tests |
| Credential leakage | Log redaction, secret isolation |
| Database outage | Fail-closed authorization |
| Disabled account reuse | Check account state on protected requests |
| Backup session resurrection | Session invalidation policy after restore |
| Dependency compromise | Version review, vulnerability monitoring, maintenance policy |

Rate limiting must work across all relevant application processes.

A process-local counter is not sufficient evidence for multi-process deployment.

Trusted forwarded headers must be restricted to known proxies.

## 13. MVP Versus Pilot Requirements

### Development MVP

- Operator-provisioned accounts.
- No public signup.
- No self-service password recovery.
- Single browser authentication mechanism.
- PostgreSQL-backed application data.
- CSRF protection.
- Protected backend routes.
- Automated security regression tests.

### Before Real-User Pilot

Require separate review of:

- Onboarding and identity verification.
- Credential recovery.
- MFA requirements.
- Email ownership verification, if email is used.
- Account deletion and retention.
- Observability and incident response.
- Security of the deployed identity provider or local authentication service.
- Load testing and rate-limit coordination.
- Backup restoration and session invalidation.
- HTTPS termination, proxies and cookie policy.

These requirements are not silently included in the S02 development MVP.

## 14. Unresolved Decisions and Approval Gates

| ID | Decision | Status | Required before |
|---|---|---|---|
| DEC-001 | Accept ADR-0001 modular monolith baseline | PENDING | Dependent architecture work |
| DEC-002 | Approve database-backed session direction | PENDING | Session implementation |
| DEC-003 | Approve authentication solution and supported versions | BLOCKING | AG-003.4 |
| DEC-004 | Approve `users` + `auth_identities` design | PENDING | Identity migrations |
| DEC-005 | Approve operator-provisioned account policy | PENDING | Account provisioning |
| DEC-006 | Approve CSRF bootstrap implementation | PENDING | Login/logout |
| DEC-007 | Approve cookie and expiry policies | PENDING | Session implementation |
| DEC-008 | Approve authentication API contracts | PENDING | Authentication routes |
| DEC-009 | Approve PostgreSQL and SQLAlchemy integration mode | PENDING | AG-003.2/003.3 |
| DEC-010 | Approve rate-limit and session cleanup ownership | PENDING | Real-user exposure |

A direction can be accepted while some implementation details remain blocked, but the dependent tickets must not proceed past their relevant gates.

## 15. AG-003.1 Acceptance Criteria

This is an architecture and documentation ticket. No runtime implementation is included.

- [x] Separate PRD requirements from new proposals.
- [x] Compare authentication and session alternatives.
- [x] Identify a conditional maintained-library candidate.
- [x] Document maintenance and integration risks.
- [x] Propose identity, credentials and session models.
- [x] Define password, cookie and session security requirements.
- [x] Define CSRF and Origin controls.
- [x] Define authorization boundaries.
- [x] Define PostgreSQL and migration strategy.
- [x] Document MVP limitations and pilot requirements.
- [x] Record decision gates and unresolved items.
- [ ] Tech Lead/user approves or revises the decisions.
- [ ] Selected library compatibility is validated.
- [ ] User saves the document at its intended repository path.
- [ ] Git commit and remote status are confirmed.
- [ ] Sprint and handoff documentation are updated.

Checklist items marked complete above indicate **design coverage in this draft**, not user acceptance or executable verification.

## 16. Future Verification Matrix

The following tests must be implemented during the relevant tickets:

| Area | Required tests |
|---|---|
| Identity | Unique issuer/subject; stable UUID ownership |
| Credentials | Correct password, wrong password, unknown account, disabled account |
| Hashing | Argon2id verification and parameter upgrade |
| Sessions | Persistence, expiry, revocation, rotation, logout |
| CSRF | Missing token, wrong token, cross-session token, untrusted Origin |
| Cookies | Development and HTTPS security attributes |
| Authorization | Two-user access denial and owner-scoped queries |
| Database | Unique constraints, FKs, transaction rollback |
| Migrations | Upgrade, compatibility and rollback review |
| Failure handling | Database unavailable, sanitized errors |
| Security | No credential/token leakage in logs |
| Integration | Browser login/logout and protected route behavior |

No tests listed here have been executed as part of AG-003.1.

## 17. Decision Record

**Current decision:** PROPOSED — READY FOR REVIEW.

**Recommended implementation direction:**

1\. PostgreSQL as authoritative persistence.

2\. Internal UUID users with separate identity mapping.

3\. Opaque, server-revocable browser sessions.

4\. HttpOnly cookie transport with CSRF protection.

5\. FastAPI Users as a conditional implementation candidate.

6\. Authlib with managed OIDC as the fallback.

7\. No custom authentication framework without separate security approval.

**Approval limitation:** The selected authentication library must pass its compatibility and maintenance gate before implementation.

**AG-003.2 may begin only after its independent database configuration decisions are approved.**

**AG-003.4 remains blocked until the authentication solution, session behavior, CSRF integration and API contracts are approved.**

## 18. Handoff

After review:

1\. Record which decisions were approved.

2\. Preserve unresolved decisions as explicit blockers.

3\. Save the ADR under `docs/adr/0002-authentication.md`.

4\. Update the S02 sprint report.

5\. Update the Sprint Index.

6\. Update the current handoff using actual Git state.

7\. Commit reviewed documentation on the AG-003.1 feature branch.

8\. Start only the next approved ticket.

Do not report authentication, PostgreSQL models, migrations or security tests as implemented merely because this ADR exists.

## 19. Infrastructure Progress Note — 2026-11-22 (Non-decision)

This section records observed work without changing the ADR approval status.

- AG-003.2: PostgreSQL 17 Compose runtime, readiness checks and application-role restrictions; direct HTTP and role-verification output reviewed. Outage/recovery user-reported passed. Completion SHA not independently observed.
- AG-003.3A: Async SQLAlchemy + Psycopg 3 infrastructure, explicit transactions, Alembic scaffolding and proposed `app` schema. Backend pytest: **31 passed, 1 warning**, 2026-11-22. PostgreSQL read transaction and S01 smoke user-reported passed.
- No authentication tables, authentication API, session runtime or migration revisions have been authorized by this ADR.
- Proposed future migration principal: `agentops_migrator`, schema owner for `app`, with least-privilege grants for runtime principal `agentops_app`. Provisioning, exact privileges, version-table location and operational procedures require explicit approval before online migrations.
- Existing `alembic/env.py` is intentionally a temporary execution guard for AG-003.3A, not a completed online-migration configuration.

**Decision status remains `PROPOSED — READY FOR DECISION`.** This note is not architecture approval. The substantive authentication options and unresolved approval checklist above remain unchanged.

---

## 20. AG-003.1A — FastAPI Users Compatibility PoC (2026-11-22; Non-decision)

**Decision status:** ADR-0002 remains **PROPOSED — READY FOR DECISION**. This section records experimental evidence and a *recommendation*, not formal adoption of an alternative.

**Candidate examined:** FastAPI Users `15.0.5` with `fastapi-users-db-sqlalchemy` `7.0.0` in an isolated experiment. The actual saved PoC code is under `experiments/auth-fastapi-users/`; it does not alter production FastAPI, database schema or Alembic.

**Execution evidence (user-provided terminal outputs):** Python `3.12.9`, pytest `9.2.0`, **31 collected, 30 passed, 1 xfailed, 1 warning (0.40 s)**; experiment `pip check` and backend `pip check` both reported **No broken requirements found**; backend regression **31 passed, 1 warning (6.62 s)**. The strict XFAIL in AUTH-P03 is evidence of a violated contract, not security compliance.

| Contract | Finding | Interpretation |
|---|---|---|
| Token at rest (AUTH-P03) | **FAIL** | Stock strategy passes the raw reusable bearer token to persistence adapter |
| Absolute and idle expiry (AUTH-P05) | **NOT_PROVIDED overall** | Stock absolute cutoff works in fake storage; rolling idle expiry not provided |
| CSRF/Origin (AUTH-P08) | **NOT_PROVIDED** | CookieTransport does not enforce application Origin or CSRF proof |
| Schema and transaction (AUTH-P09) | **FAIL** | Stock user/token layout differs; stock adapters commit internally, conflicting with application-owned transaction policy |
| Maintenance/dependency (AUTH-P10) | **UNVERIFIED overall** | Runtime pins and `pip check` passed; advisory review / risk acceptance pending |

The following narrow observations passed: imports and mapped models, strategy token lifecycle with a memory fake, individual token revocation, disabled-user rejection, and configured cookie response attributes. None establish PostgreSQL persistence, browser CSRF protection, secure password login or a production authentication system. The isolated experiment also emitted a non-blocking Starlette/httpx deprecation warning.

**Recommendation:** **REJECT unmodified stock FastAPI Users integration against the current proposed session and transaction contracts.** Do not silently weaken token-at-rest, idle expiry, CSRF or transaction requirements to make stock integration pass. This recommendation does not reject all extensibility options and does not approve Authlib/OIDC.

**AG-003.1B (next decision):** Evaluate and approve an alternative authentication mechanism, provider if applicable, application session ownership, token storage protection, session expiration/revocation, CSRF policy, account provisioning, and compatibility with `users`/`auth_identities`/credential models. Approve the migration role/schema separately before AG-003.3B; AG-003.4 remains blocked until those gates close.

**Git evidence:** Experiment commit and push not yet supplied. AG-003.3A infrastructure commit `cfab615` was observed in Git log; its push was user-reported.
