# ADR-0006 — Model and Search Providers

> **Active S06 amendment — S06-AMEND-001:**
> S06 Contract v1.1 is approved for the offline
> Development MVP deliverable only. The approved
> amendment and revised milestone allocation supersede
> conflicting historical S06 scope descriptions.
> Original product requirements, security gates,
> and historical verification remain preserved.
> External execution remains denied.
> Production remains NOT APPROVED.

## S06-AMEND-001 — Approved Contract v1.1

Recorded at: 2026-11-25T12:36:32.255498+00:00.

Status: APPROVED — Development MVP only.

S06 deliverable: Offline Evidence and Citation Foundation.

Authoritative contract and acceptance matrices:
docs/sprints/S06.md.

- Original v1.0 acceptance: 18 VERIFIED, 4 PARTIAL,
  1 PENDING_CI, 1 PENDING_OWNER.
- Effective v1.1 local assessment: 22 VERIFIED,
  1 PENDING_CI, 1 PENDING_OWNER.
- Original security ledger: 13 VERIFIED, 3 PARTIAL.
- Partial security gates: SG06, SG08 and SG10.
- Official final owner acceptance: 0/24, pending closeout.
- Deferred obligations: six, all OPEN.
- Runtime source and tests unchanged.
- Live execution denied.

| ID | Obligation | Original traceability | Receiving milestone | Status |
| --- | --- | --- | --- | --- |
| D06-01 | Provider interoperability | AC05 | S08 | OPEN |
| D06-02 | Secure connector verification | AC07, SG06, SG08 | S07 | OPEN |
| D06-03 | External execution budgets and deadlines | AC09, SG10 | S07 | OPEN |
| D06-04 | Actual provider usage and cost accounting | AC05, AC09, SG10 | S08 | OPEN |
| D06-05 | Real evidence integration | AC05 and real-data obligations of AC11-AC20 | S08 | OPEN |
| D06-06 | Integrated external security acceptance | AC21, SG01-SG16 | S08 | OPEN |

### Mandatory release restrictions

This amendment does not authorize live provider
execution, actual credential access, paid inference,
paid search, PAYG, shared database migrations,
worker activation, real-user authentication,
report publication or production deployment.

External execution remains unconditionally denied
throughout S06 delivery.

All S02-S06 security gates remain mandatory.
SG06, SG08 and SG10 remain PARTIAL in the original
security ledger until successor evidence resolves
their outstanding obligations.

A controlled live smoke test requires separate
explicit authorization after applicable transport,
budget and security prerequisites have been verified.

Routine external execution requires completed
applicable security verification and its own
explicit activation approval.

Preserve the strict Authlib security XFAIL,
approved dependency manifests, canonical worktree
and all prior release restrictions.

Production remains NOT APPROVED.

### ADR-0006 provider and acquisition clarification

Tavily Researcher basic search remains the approved
development adapter selection.

Vendor selection does not authorize live execution.

The current adapter is implemented behind an immutable
default-deny authorization barrier.

Existing isolated verification remains valid within
its actual scope. It is not proof of public network
behavior, live provider compatibility or production
runtime dependency readiness.

D06-02: actual integrated connector security, S07.
D06-03: bounded execution and recovery, S07.
D06-01: provider interoperability and terms, S08.
D06-04: actual provider usage and cost accounting, S08.
D06-05: real evidence integration, S08.
D06-06: integrated security acceptance, S08.

No PAYG, paid subscription, credential retrieval or
live provider request is authorized.

No provider-specific data retention guarantee is
assumed from the selected free plan.

SG06, SG08 and SG10 remain PARTIAL.

#### D06-01 — Provider interoperability

Receiving milestone: S08.

Original traceability: AC05.

Status: OPEN.

Dependencies: D06-02, D06-03.

Acceptance requirements:

- Verify approved provider API and runtime compatibility.
- Verify actual account quota, billing and applicable data handling terms.
- Verify required runtime dependency availability.
- Perform separately authorized bounded provider smoke tests.
- Record sanitized request, response and usage evidence.

Release gate: Separate live-test authorization required.

#### D06-02 — Secure connector verification

Receiving milestone: S07.

Original traceability: AC07, SG06, SG08.

Status: OPEN.

Dependencies: None within this deferred register.

Acceptance requirements:

- Exercise actual connector through integrated DNS, numeric connection, peer verification, TLS and HTTP.
- Verify adversarial DNS answers and destination binding.
- Verify trust, hostname mismatch, redirects and resource cleanup.
- Do not substitute the entire connector in connector-correctness tests.
- Preserve default-deny external authorization.

Release gate: Required transport security evidence before live smoke authorization.

#### D06-03 — External execution budgets and deadlines

Receiving milestone: S07.

Original traceability: AC09, SG10.

Status: OPEN.

Dependencies: None within this deferred register.

Acceptance requirements:

- Integrate acquisition budgets with application-owned execution context.
- Preserve cumulative search, retrieval and retry accounting.
- Enforce operation and running-task deadlines.
- Document cancellation, timeout and recovery behavior.
- Prevent retries and recovery from resetting applicable budgets.
- Fail closed on incomplete or indeterminate execution.
- Reconcile hard cancellation with verified adapter capabilities and approved execution contract.

Release gate: Required bounded execution evidence before live smoke authorization.

#### D06-04 — Actual provider usage and cost accounting

Receiving milestone: S08.

Original traceability: AC05, AC09, SG10.

Status: OPEN.

Dependencies: D06-01, D06-03.

Acceptance requirements:

- Verify actual provider usage metadata.
- Reconcile provider credits with application-owned accounting.
- Prevent automatic paid usage and unauthorized retries.
- Verify missing or invalid usage handling.

Release gate: No paid subscription or PAYG authorization.

#### D06-05 — Real evidence integration

Receiving milestone: S08.

Original traceability: AC05 and real-data obligations of AC11-AC20.

Status: OPEN.

Dependencies: D06-01, D06-02, D06-03, D06-04.

Acceptance requirements:

- Extend acquisition and evidence contracts for explicitly authorized real evidence.
- Preserve genuine retrieval timestamps, provenance and source identity.
- Prevent synthetic records from being represented as real evidence.
- Verify integrity, scope isolation, deduplication and citation resolution.
- Integrate authorized real evidence into the bounded workflow.
- Verify insufficient evidence behavior and factual grounding through evaluation.

Release gate: Schema and dependency changes require applicable approvals.

#### D06-06 — Integrated external security acceptance

Receiving milestone: S08.

Original traceability: AC21, SG01-SG16.

Status: OPEN.

Dependencies: D06-01, D06-02, D06-03, D06-04, D06-05.

Acceptance requirements:

- Complete all outstanding external security obligations.
- Resolve SG06, SG08 and SG10 with required successor evidence.
- Revalidate all applicable S06 and historical security gates.
- Verify prompt-injection resistance, credential protection, authorization and cross-task isolation.
- Record integrated security evidence and explicit release decisions.

Release gate: Blocks routine external feature release until satisfied.


Date: 2026-11-25.

Status: PARTIALLY ACCEPTED — Development MVP only.

Authority: Owner-approved S06 Contract v1.0,
AD02, AD03, AD04 and AD07.

## Context

S04 and S05 provide verified offline workflow
baselines. S06 needs an application-owned provider
boundary and secure retrieval foundation.

Direct provider access by models would weaken
permission enforcement, reproducibility and
network security.

## Accepted decision

- Typed application-owned search/retrieval interfaces.
- Deterministic test adapters and controlled transports.
- Strict request and response validation.
- External execution disabled by default.
- Application-owned permissions and usage limits.
- Bounded I/O, retries and failure handling.
- Sanitized public errors.

## Network security requirements

Real retrieval, when separately authorized, must:

- Permit only approved public HTTP(S) destinations.
- Reject credentials and prohibited URL schemes.
- Reject private, loopback, link-local, metadata
  and other non-public IPv4/IPv6 destinations.
- Validate all relevant DNS results.
- Prevent DNS rebinding through validated destination
  binding to the actual network connection.
- Revalidate each redirect destination.
- Preserve TLS certificate and hostname verification.
- Prevent proxy or environment configuration from
  bypassing destination security policy.
- Bound duration, response size, decompression,
  redirects, retries and accepted content types.

Fetched content cannot authorize tools or change
policies, credentials, budgets or destinations.

## Alternatives

Direct unguarded provider or HTTP access:
rejected because it bypasses application controls.

Application-owned interfaces with deterministic
verification: accepted for Development MVP.

## Open decisions

- Search vendor selection.
- Vendor API contract and quota.
- Pricing, cost accounting and data retention terms.
- Vendor credentials and secret handling.
- Live external execution and smoke-test authorization.
- Live model, Bedrock region and quota selection.
- Any dependency changes requiring separate review.

A vendor-specific adapter must not be enabled or
treated as approved until these applicable gates
are resolved.

No paid API call or real external retrieval is
authorized by this ADR.

## Verification

WP02 must supply focused contract, transport,
budget, malformed-response and adversarial
security evidence.

WP04 and WP05 must verify integrated enforcement.

ADR acceptance alone does not establish runtime
implementation or network-security verification.

Production remains NOT APPROVED.

## S06 owner-approved provider selection amendment

Date: 2026-11-25.

Status: ACCEPTED — Development MVP implementation only.

The Project Owner explicitly approved:

- Tavily Researcher free plan.
- HTTPX REST adapter without new dependencies.
- Basic search only.
- Secure transport implementation.
- Isolated network security tests.
- External execution disabled by default.
- No paid subscription or PAYG.
- No live API calls without separate approval.
- Preservation of all existing security and release gates.
- Remaining WP02 implementation.

### Implementation restrictions

Vendor selection approval does not authorize live
external network execution.

Production remains NOT APPROVED.

The application owns credentials, permissions, budgets,
destination validation and execution policy.

Search queries must exclude credentials, sensitive
personal information and confidential internal data.

Do not add Tavily SDK dependencies or modify lockfiles.

Before accepting the vendor adapter, verify current
official API contracts, usage limits and applicable
data handling terms.

The free allowance is not a guarantee against charges.
Do not enable billing or automatic paid usage.

Actual secure transport must demonstrate destination
binding, TLS certificate and hostname verification,
redirect validation and bounded response handling.

Offline fixture metadata is not proof of actual
network transport security.

No worker execution, report publication, lifecycle
mutation or production deployment is authorized.

## S06 isolated transport verification checkpoint

Date: 2026-11-25.

- Tavily REST request and response mapping verified
  through HTTPX MockTransport only.
- Numeric IP connection binding verified with
  socket doubles.
- Real TLS certificate and hostname checks verified
  through local Unix socket pairs.
- HTTP parsing and bounded body processing verified
  through local socket pairs with simulated peer metadata.
- Internal socket creation remains fail-closed.
- Latest S06 focused suite: 180 passed.

Remaining obligations:

- Actual vendor execution path and credential boundary.
- Integrated resolver, redirect and pinned transport.
- Production-equivalent socket ownership verification.
- Absolute header and operation deadlines.
- Live execution authorization and applicable smoke tests.

These obligations are not waived by isolated tests.

No live external execution is authorized.
Production remains NOT APPROVED.


## S06 WP02-R-R02 acquisition hardening checkpoint

Date: 2026-11-25.

- New focused security tests: 51 passed.
- Existing acquisition regression: 180 passed.
- Bounded HTTP wire processing implemented.
- Raw response header limit: 16384 bytes.
- Header count limit: 64.
- Body limit: 1048576 bytes.
- Compression and transfer encoding rejected.
- Exclusive socket ownership verified with local socket pairs.
- Fixture DNS answers and redirect targets validated.
- Retry and retrieval budget accounting exercised.
- Remaining operation timeout applied before socket reads.
- Absolute operation deadline checked after socket reads.
- Tavily basic request preparation centralized.
- Existing vendor payload preserved.
- Credential access remains default-deny.
- No real provider request was executed.

This is isolated Development MVP verification only.

Public peer metadata is simulated in the new socket-pair
tests. Existing isolated TLS tests remain preserved.

The new wire reader does not establish a complete live
DNS, TLS, provider and credential execution pipeline.

AC05, AC07 and AC09 remain PARTIAL.

Actual live credential injection, real DNS integration,
application wiring and complete provider deadlines are
not verified by this checkpoint.

The retrieval retry policy remains conservative and
bounded, but transient classification requires further
review before live execution.

No full process cancellation guarantee is established.

No security or release gate is waived.

No dependency or migration changes.
No worker activation or publication.

Production remains NOT APPROVED.


## S06 WP02-FINAL execution boundary checkpoint

Date: 2026-11-25.

Local focused verification: 31 passed.
Affected acquisition regression: 231 passed.

Implemented:

- Authorization-guarded Tavily execution path.
- Application-owned credential lookup and redacted repr.
- Shared HTTPX vendor execution and response validation.
- Separate synthetic and external search response metadata.
- Authorization-guarded numeric socket factory.
- Deadline-bounded DNS waiting and single in-flight lookup.
- Shared integrated retrieval execution.
- Existing R02 bounded HTTP reader preserved.

Verification is isolated only.

No real credential lookup or live external request was
performed. Credential tests use synthetic environment data.
Vendor tests substitute HTTPX MockTransport.
Resolver tests substitute getaddrinfo responses.

The real authorization policy remains unchanged and
unconditionally denies external execution.

Important unresolved limitations:

- HTTPX synchronous timeouts and cooperative checks do
  not prove a hard absolute provider operation deadline.
- Timed-out getaddrinfo work cannot be forcibly cancelled.
  Only one outstanding resolver thread is permitted.
- Real integrated DNS, numeric connection, TLS and wire
  behavior still require stronger end-to-end verification.
- Retrieval failure classification is not restricted
  to a proven transient-only exception taxonomy.
- Real retrieved pages cannot enter the synthetic-only
  RetrievedPage and evidence persistence contracts.
- The application workflow remains fixture-only.
- Official vendor compatibility and data handling must
  be verified before external execution authorization.

AC05: implementation advanced; live verification pending.
AC07: implementation advanced; integrated proof pending.
AC09: partial; hard provider deadline not established.

These are not final acceptance claims.

Do not enable live authorization merely because isolated
execution tests have passed.

No dependencies, migrations, workers or publication
were changed or enabled.

Production remains NOT APPROVED.


## S06 WP05-AB-R01 integrated verification checkpoint

Date: 2026-11-25.

Recovery context:

The initial WP05-A/B run passed all 22 new security
tests but failed two historical ORM metadata assertions.

Initial backend result:
2110 passed, 75 skipped, 2 failed.

The initial transaction restored the 48-file baseline.

Recovery corrections:

- test_identity_models.py:
  test_model_import_registers_only_expected_tables.
- test_orm_infrastructure.py:
  test_metadata_registers_approved_identity_models.

Both expected table inventories now include the
approved app.research_evidence table.

The original strict set equality assertions remain
unchanged. AST comparison verifies that exactly one
approved table literal was added to each test function.

No schema or migration change was required.

Restored WP05-A implementation:

- Fixed-origin HTTPX transport for Tavily.
- Shared DNS, numeric connection, TLS and bounded
  response processing under a common operation deadline.
- Provider redirects and automatic POST retries denied.
- Explicit transient retrieval failure classification.
- DNS acquisition errors preserved.
- Internal retrieval authorization enforced.
- Integrated local TLS and HTTP verification.

Verified recovery results:

- ORM regression correction: 2 passed.
- Final security focused tests: 22 passed.
- Full backend regression: 2112 passed.
- Skipped: 75.
- Failed: zero.
- Xfailed: zero.
- Xpassed: zero.
- Dependency consistency: PASS.

Skip reconciliation:

- Historical opt-in integration skips: 49.
- S06 disposable PostgreSQL skips: 26.
- No new unexplained skip count.

The 26 S06 skipped database cases are not counted as
passed in the full backend result. They must be run
using the disposable PostgreSQL harness in WP05-C.

Provider documentation review:

https://docs.tavily.com/documentation/api-reference/endpoint/search

The implementation uses the fixed Tavily search
endpoint, bearer authentication, basic search and
include_usage.

Live response compatibility, account-specific billing,
quota configuration and applicable data handling terms
remain separate verification obligations.

No paid subscription or PAYG activation is authorized.

Remaining technical limitations:

- Public peer IP and DNS answer metadata are simulated.
- Integrated TLS tests replace the connection seam.
- OS getaddrinfo cancellation is not guaranteed.
- No hard real-time process cancellation claim.
- No real provider response was obtained.
- Application workflow remains fixture-only.
- Real evidence persistence remains disabled.

AC05, AC07 and AC09 have additional implementation
and isolated verification evidence. Formal acceptance
remains pending reconciliation with the approved
S06 contract.

Next: WP05-C/D/E disposable PostgreSQL lifecycle,
dependency vulnerability review, security gate review
and frontend verification.

No live provider execution, shared database mutation,
worker activation, report publication or deployment.

Production remains NOT APPROVED.


## S06 WP05-DE-R01 verification checkpoint

Verified at: 2026-11-25T12:22:40.166781+00:00.

Overall status: PARTIAL_BLOCKED.
Development MVP only.

Owner authorization:

An independent environment for pip-audit 2.10.1 is
approved. Application dependency changes, lockfile
changes and backend pip remediation are not approved
by this audit-tool authorization.

Prior verified results retained without re-execution:

- Backend: 2112 passed, 75 skipped, zero failed.
- Historical disposable PostgreSQL: 48 passed.
- S06 evidence PostgreSQL: 17 passed.
- S06 workflow PostgreSQL: 9 passed.
- S06 disposable PostgreSQL: 26/26 passed.
- Total disposable PostgreSQL: 74 passed.
- Migration lifecycle and disposable cleanup: PASS.

WP05-C: VERIFIED_LOCAL.
WP05-D: PARTIAL_BLOCKED.
WP05-E: VERIFIED_LOCAL.

Actual recovery results:

- AUDIT_TOOL_ENVIRONMENT: PASS.
- BACKEND_VULNERABILITY_GATE: BLOCKED.
- AUTHLIB_COMPATIBILITY_GATE: PASS.
- HISTORICAL_SECURITY_GATE: PASS.
- FRONTEND_DEPENDENCY_GATE: PASS.
- FRONTEND_VULNERABILITY_GATE: PASS.
- FRONTEND_TYPECHECK: PASS.
- FRONTEND_ESLINT: PASS.
- FRONTEND_REGRESSION: PASS.
- FRONTEND_BUILD: PASS.

Backend pip version: 24.0.
Backend pip was not changed by this recovery.

Audit tool environment created: False.
Audit findings are recorded in the exported JSON
evidence. No automatic fixes were applied.

Blockers:

- BACKEND_VULNERABILITY_GATE: 12 known findings; owner remediation decision required

No backend regression or PostgreSQL lifecycle was
repeated. Historical security source and authorization
policy remain unchanged.

Application dependency manifests and lockfiles
remain unchanged.

Real provider compatibility remains unverified.
Real evidence coverage remains zero.
Application workflow remains fixture-only.
Hard process cancellation is not established.

Dependency audit results apply only to the audited
package inventories and the advisory data returned
at verification time.

Next action:

Review recorded blockers and obtain any required owner remediation approval. Repeat only affected verification gates.

Formal S06 acceptance remains pending.
No live provider execution, shared database migration,
worker activation, report publication or deployment.

Production remains NOT APPROVED.


## S06 WP05-D-R02 dependency remediation checkpoint

Verified at: 2026-11-25T12:26:51.600150+00:00.

Status: VERIFIED_LOCAL - Development MVP only.

Owner authorization:

Upgrade backend virtualenv pip from 24.0 to 26.2.
No application dependency, lockfile, global Python
or Conda environment change is authorized.

Remediation results:

- Previous backend pip: 24.0.
- Installed backend pip: 26.2.
- Changed installed distribution: pip only.
- Other external distributions unchanged: 63.
- Editable application distribution unchanged.
- Backend pip check: PASS.
- External packages audited: 64.
- Audit skipped packages: zero.
- Previous reported vulnerability entries: 12.
- Previous unique advisory IDs: six.
- Current known vulnerability findings: zero.
- Audit SHA256: 2f6646439b747b2ebc6248518eb90fba3f66c221d273382ec31ee8e394dd1e3a.

The six previously reported pip advisory IDs were
reconciled by a fresh audit of the full external
package inventory, without excluding pip.

The local audit is point-in-time evidence. It does
not establish vulnerability-free deployment images
or production infrastructure.

Prior verification evidence retained:

- Backend regression: 2112 passed, 75 skipped.
- Backend failures: zero.
- Disposable PostgreSQL: 74 passed.
- S06 evidence and workflow PostgreSQL: 26/26 passed.
- Migration lifecycle and cleanup: PASS.
- Authlib compatibility: 56 passed, one required
  security XFAIL, zero XPASS.
- Frontend regression: 39 passed across four files.
- Frontend typecheck, lint and build: PASS.
- Frontend vulnerability audit: zero findings.
- Historical security source preservation: PASS.

No test suite was repeated in this remediation.
No backend source, tests or dependency manifests
were modified.

WP05-C: VERIFIED_LOCAL.
WP05-D: VERIFIED_LOCAL.
WP05-E: VERIFIED_LOCAL.

The previously recorded local dependency audit
blocker has been remediated.

Next: WP05-F acceptance reconciliation of AC01-AC24
and SG01-SG16 before owner-controlled feature PR.

AC05, AC07 and AC09 must be reconciled according
to the actual isolated verification scope.

Real provider compatibility remains unverified.
Real evidence coverage remains zero.
Application workflow remains fixture-only.
Hard process cancellation is not established.

The authorization policy remains default-deny.

No live provider execution, shared database mutation,
worker activation, report publication or deployment.

Official sprint acceptance and required CI remain
pending.

Production remains NOT APPROVED.

## S06 WP05-F provider acceptance review

Status: PARTIAL - external execution denied.

AC05, AC07, AC09 and AC21 remain PARTIAL.
SG06, SG08 and SG10 remain PARTIAL.

### Unresolved contractual obligations

AC05:
The approved vendor-specific adapter exists and is
verified with isolated infrastructure. Live provider
compatibility, actual account quota/billing settings,
and integration of real evidence into the application
workflow are not established.

AC07:
DNS all-answer validation, numeric binding, redirects
and TLS safeguards have isolated verification.
Integrated local TLS tests substitute the connection
seam. They do not establish full actual connector-chain
security from DNS to the connected peer and TLS.

AC09:
Search/retrieval counters, shared transient retry,
bounded socket operations and deadline propagation
have local verification. Actual external usage and
end-to-end provider limits are not fully verified.
OS DNS lookup cancellation and hard process
interruption are not established.

Contract v1.0 explicitly distinguishes cooperative
deadlines from hard interruption. Lack of hard
cancellation alone is not a newly imposed acceptance
criterion. Adapter capability and live execution
approval remain separate obligations.

AC21:
Cannot be fully verified while SG06, SG08 and SG10
retain partial security evidence.

Additional retained limitations:

- Real evidence coverage remains zero.
- Evidence storage and writer contracts remain
  synthetic-only.
- Content integrity means normalized excerpt hash,
  not full fetched-page integrity.
- Citation validation is structural, not proof of
  semantic factual grounding.
- Execution IDs are not durable worker fencing.
- Repository isolation is application-owned, not
  a database row-level security guarantee.
- Local dependency audit does not cover all images,
  deployment infrastructure or OS components.
- HTTPX dependency availability for a production
  runtime still requires appropriate review.
- No production authentication approval.
- Existing strict Authlib security XFAIL retained.
- Historical legacy shared-Compose test remains
  separately opt-in and was not activated.

No ADR decision is expanded or superseded by this review.
No external execution or production approval.
