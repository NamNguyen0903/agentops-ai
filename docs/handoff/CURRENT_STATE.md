# AgentOps AI — Authoritative S09 WP01 checkpoint

**Contract:** S09 v1.0 — OWNER APPROVED.
**Current sprint:** S09.
**Current package:** WP01 — contract preparation.
**Delivery:** NOT EXECUTED.
**Production:** NOT APPROVED.

## Verified predecessor

S00-S08: CLOSED within their respective milestone scopes.

S08-AMEND-002 v1.2:
CLOSED — DEVELOPMENT MVP MILESTONE ONLY.

- Final main: `d79cf18d9ab8d3f47771401fac7b68a9e42f5dbe`.
- Final tree: `06a79c4d65efab8c066d7b18670015cba55be112`.
- Final main CI: 45917540548, 4/4 PASS.
- Amendment PR: #30, MERGED.
- Binding closure gates: 8/8 PASS.
- Final evidence SHA256: `479bc125f045893bdf3d62d9a5e8ad6c5d1c3565d6bbdcf370ad258fcabd27c6`.
- Authlib: 56 PASS, 1 strict XFAIL, 0 XPASS.

Original S08 full-contract acceptance remains OPEN.
Original AC ledger: 26 verified scoped, 6 transferred not passed,
3 partially verified and 1 open.
Original SG ledger: 18 verified scoped, 2 partial.

## Current authority

- S09-G01: OWNER APPROVED.
- WP00: verified discovery and predecessor reconciliation.
- WP01: local documentation preparation authorized.
- WP02-WP06: pending package prerequisites.
- Contract: `docs/sprints/S09.md`.
- ADR: `docs/adr/0005-aws-deployment-architecture.md`.
- Preparation branch: `docs/s09-contract-adr`.
- Preparation base HEAD: `d79cf18d9ab8d3f47771401fac7b68a9e42f5dbe`.

The preparation branch identifies intended local work.
Actual changes and delivery are established by evidence.

## Mandatory open obligations

S09-OB01: real evidence workflow.
S09-OB02: comparable three-arm evaluation.
S09-OB03: integrated external security.
S09-OB04: original obligation reconciliation.

D06-05 and D06-06: OPEN.
Historical S06 SG06/08/10 require successor reconciliation.

Three-arm evaluation: NOT EXECUTED.
Quality metrics: NOT MEASURED.
Cloud deployment: NOT EXECUTED.
Required-check enforcement: NOT VERIFIED.

## Next action

Review WP01 local preparation evidence.
Obtain S09-G02-A for contract Git delivery.

No feature implementation before verified contract delivery
and separately authorized merge with exact main CI.

Preserve the single canonical workspace, protected stash,
original matrices and all security restrictions.

PRODUCTION REMAINS NOT APPROVED.

---

# Retained historical record

The original content below is preserved byte-for-byte.
The active S09 record supersedes conflicting historical
status and authorization statements only.
All nonconflicting requirements remain binding.

---

# Authoritative S08-AMEND-002 milestone record

**Contract:** v1.2.
**Delivery baseline:** verified main `ca6325f276e49cc24168779b82ca0f705972e66e`.
**Historical delivery CI:** 24/24 PASS.
**Milestone closure:** conditional on all eight gates
in `docs/sprints/S08_AMEND_002.md`, section 4.

Once the final amendment delivery evidence verifies
every condition, record S08 as CLOSED — DEVELOPMENT MVP
MILESTONE ONLY. Until then closure is pending.

This is not full original-contract acceptance:
26/36 original AC verified scoped, six transferred
not passed, three partially verified, one open.
18/20 original SG verified scoped; two partial.

S09-OB01 through S09-OB04 are mandatory.
D06-05 and D06-06 remain OPEN.
Original AC36 full acceptance remains OPEN.

S09 NOT STARTED.
PRODUCTION REMAINS NOT APPROVED.

This header supersedes earlier milestone allocation and
administrative status statements only. Historical evidence,
acceptance matrices, security requirements and release
restrictions below remain preserved.

---

# Authoritative S08 v1.1 closeout candidate

**Status:** WP07-A — CLOSEOUT DELIVERY IN PROGRESS.
**Sprint:** NOT CLOSED.
**Production:** NOT APPROVED.

Feature PR #28 merged at `b0aac9f32cd26e02e60b8cf6c67da865f0f35854`.
Exact main CI 45843273499: 4/4 PASS.

G07 Owner-approved scoped acceptance reconciliation:
- Original AC: 26 verified scoped, 6 transferred
  not passed, 3 partial, 1 open.
- Security: 18 verified scoped, 2 partial,
  0 open; no waived security gates.
- D06-01/04 scoped Development MVP closure recorded.
- D06-05/06 remain OPEN.
- S09-OB01/02 remain mandatory; S09 NOT STARTED.
- Full report-quality evaluation remains unmeasured.
- AC36 and outstanding mandatory gates remain pending.

Authoritative reconciliation: `docs/sprints/S08_CLOSEOUT.md`.
Original amendment: `docs/sprints/S08_AMEND_001.md`.

Next: exact docs-only closeout PR CI, then separate G08
review. Final CLOSED status is prohibited until all
applicable final acceptance conditions are satisfied.

The historical checkpoint material below is retained
for traceability and is superseded by this status header.

---

## S08 WP06-B-R03 CI recovery resume

Original feature commit: `23ce5d5ee4da15a31604e1b8927d26446329d682`.
Feature PR: #28.
R02 evidence SHA256: `abc23d1ef990b19635ddc061f3a6913fa58175ee78a39cf8bdff53c48f811f1f`.

Six affected historical S06 provider regression cases passed
in the Docker network-none test run (6 passed in 0.97s).

JUnit export failed after the container stopped. The
original pytest stdout is retained; no JUnit result is
claimed or reconstructed.

Exact test diff and original fixture identities verified.
No local test rerun and no additional runtime modifications.

Mandatory four-job successor feature CI remains required.
Contract v1.1 and S08-AMEND-001 remain effective.
D06-05 and D06-06 remain OPEN.
Mandatory S09 obligations remain unchanged.

PRODUCTION REMAINS NOT APPROVED.

---

# Authoritative S08 v1.1 checkpoint

- Amendment: S08-AMEND-001, Owner approved.
- Original v1.0 requirements preserved.
- WP05: scoped technical milestone complete.
- WP06-A: integrated evidence and static feature review complete.
- Next: G05 separate feature delivery authorization.
- Official final acceptance: not yet granted.
- Mandatory S09: outstanding AC22/23 and AC26–29.
- D06-05 and D06-06 remain OPEN.
- AC31, AC33 and applicable security gates remain open
  pending complete reconciliation.
- S09: NOT STARTED.
- Production: NOT APPROVED.

Evidence and traceability:
`docs/sprints/S08_AMEND_001.md`.

# S08 WP05 Evaluation R03

Development MVP only.

Previous successful live evidence: `f03b65e58c30cb1fd2239a720cc8ba2412cc58f53588a1eca5199bf2c5b79e37`.
R02 isolation-check failure: `0f77ceed8e21dbe5e73096249396316fe996773456fa89deb5463f9d2e95f61d`.

Docker network none retained.
Only loopback may be active; inactive tunnel interfaces
do not constitute external network connectivity.
IPv4 and IPv6 non-loopback routes rejected.

Evaluation: GRAPH_COMPONENT_EXECUTION_PASS.
Valid inputs: 40/40.
Graphs returned: 40/40.
Candidate ready: 40/40.
Graph errors: 0/40.

312 previously verified tests preserved.
66/66 synthetic acquisitions preserved.
Actual retrieval and citation PASS preserved.
V1 report retained unchanged.

Three-arm quality benchmark remains unexecuted.
Complete real workflow acceptance remains open.
No mandatory criterion silently waived.

No new external retrieval, Tavily credits, inference,
schema changes, Git delivery or deployment.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05 FINAL FAST-TRACK

Development MVP only.

Accepted previous evidence: `706a1e572ae111619c82853ea4e03a331d67926b50fbc9d3e043cd1d3297a00a`.
Original Tavily search: actual usage of one free credit.
Original G04, G04-B and G04-C remain consumed.

HTTP compatibility: strict ticket-bound HTTP/1.1 chunked
entity decoding. Cumulative 1 MiB body limit, at most
4096 chunks, deadlines, framing checks and default deny
retained. Nonempty trailers and extensions are unsupported.

G04-D retrieval: INDEPENDENT_REAL_RETRIEVAL_PASS.
G04-D consumed: True.
Sanitized diagnostics: [].

Frozen evaluation: FROZEN_COMPONENTS_EXECUTED.
S05 fixture graph completed: 0.
Verified synthetic source acquisitions: 66.

Frozen component runs are not a three-arm quality benchmark.
Manual analyst, single-model and live AgentOps report arms
remain unexecuted. Human quality metrics remain unmeasured.

Independent real retrieval does not establish a complete
real search-to-retrieval workflow.

WP05 quality acceptance remains incomplete until the
mandatory evidence is available. No criteria are silently
waived or reclassified as passed.

D06-01/D06-04/D06-05/D06-06 require final reconciliation.
No additional Tavily request, paid usage, external model
inference, automatic retry, schema change, Git delivery
or deployment.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-G-R02 — G04-C retrieval smoke

Development MVP only.

Accepted R01 evidence: `041236452814886cf0f0244777368914659bfc3a6c308a64853d7fb40c36594a`.
Previously verified actual Tavily credits: 1.

G04-C: OWNER APPROVED and CONSUMED.
Original G04 and G04-B markers remain consumed.

Offline verification: 228 distinct reconciled PASS
identities from prior G2 and R01 executions.
No local test suites rerun.

Observed G04-C status: RETRIEVAL_UNVERIFIED_NO_RETRY.

Sanitized diagnostic events:
[{"code": "INVALID_RESPONSE", "function": "fail", "module": "bounded_http"}, {"code": "INVALID_RESPONSE", "function": "bounded_body", "module": "bounded_http"}, {"code": "INVALID_RESPONSE", "function": "exchange", "module": "bounded_http"}, {"code": "INVALID_RESPONSE", "function": "retrieve_controlled", "module": "controlled_retrieval"}]

This retrieval was independently authorized.
It does not establish end-to-end real search lineage.

No additional Tavily requests, provider credits,
credentials, external inference, automatic retries,
schema changes, Git delivery or deployment.

Mandatory D06 obligations and evaluation remain
subject to evidence-based reconciliation.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-G-R01 — Retrieval diagnostics

Development MVP only.

WP05-G evidence: `2769fd493e406c427c189c7938c04b9f7d005f16b2831eebfe4bbf285f2c2dfd`.
Prior offline preflight: 225/225 PASS.

G04-B live retrieval was indeterminate.
Its one-shot authorization remains consumed.
The historical failure root cause remains unknown.

Added bounded sanitized diagnostics to the disposable
Owner runner only. No HTTP parser, DNS/TLS security,
authorization, schema or application execution policy
was relaxed.

Targeted verification: 5/5 PASS.
New fixture cases: compressed, chunked, truncated.
Targeted JUnit SHA256: `2555a10a263d07a287dd27f0f6062857db3bb60c89ffe2efb06ead1cc5284ad4`.

No new external retrieval, Tavily request, credit,
credential access, automatic retry, dependency change,
Git delivery or deployment.

Independent real retrieval remains NOT VERIFIED.
D06 mandatory obligations remain open.
Evaluation execution remains pending.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-G — Retrieval-only smoke

Development MVP only.

Prior verified Tavily search evidence: `2e317b20571ed9cbb6ba62e3c1052e6a11c06c590b61adc7eb0c35702af549cd`.
Actual Tavily credits in that original execution: 1.
Original G04 search authority remains consumed.

G03-B and G04-B: OWNER APPROVED.
Successor migration: `f9d3106b0802`.
Historical migration `e8c2106a0801` remains unchanged.

Explicit retrieval-only grants have zero search allowance,
zero provider-credit allowance, one exact RFC 9110 retrieval
and no invented search lineage.

Existing search-bound grants and their verified-search
prerequisite remain in force.

Observed package classification: RETRIEVAL_UNVERIFIED_NO_RETRY.

The independent retrieval does not by itself prove a
complete real search-to-retrieval workflow.

Offline fixture results are not actual provider evidence.
Only verified live settlement can establish real retrieval
and citation persistence.

No additional Tavily request was authorized or made by
the retrieval-only runner. No external model inference,
paid usage, shared migration, Git delivery or deployment.

Mandatory D06 obligations and evaluation remain subject
to final reconciliation.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-F2 — Controlled live smoke

Development MVP only.

G04 Owner approval: `79be6005b3bfe87f303992acf82775f63b38d177c1d7f9a9f2bb7ce91894b95c`.
Verified R03 evidence: `3331f4827adaa48eb2600afae8e96343771f9bb356ebdde2097dee4084dcbfb9`.
Reconciled preflight JUnit: `00c9cae637499879d3b6c5dc04a73c224be562a480ecdbdec739764ab79e9cd6`.

F1: 20/20 reconciled PASS, retained without a test rerun.

Observed F2 classification: SEARCH_VERIFIED_RETRIEVAL_NOT_EXECUTED_NO_RETRY.
G04 one-shot authorization: CONSUMED.
Account usage before: 0.
Account usage after: 1.

Account configuration and credit delta reconciliation
use Owner dashboard attestation.

The disposable runner used the approved exact search
scope and conditional RFC 9110 retrieval scope.

Only observed successful durable operations may count
toward actual provider acceptance. No automatic retry
or alternative destination is authorized.

The disposable environment was cleaned up.
Feature source and dependency manifests remain unchanged.

Mandatory D06 obligations require evidence reconciliation.
Evaluation execution and human review remain pending.

No Git delivery, merge, shared migration or deployment.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-F-R03 — Controlled search accounting recovery

Development MVP only.

G04 Owner approval evidence: `79be6005b3bfe87f303992acf82775f63b38d177c1d7f9a9f2bb7ce91894b95c`.
R01 preflight evidence: `bff94fa645983b48257b152112e8cd3f47fa943afdf23a7844d66ba6c9e01ed6`.
R02 diagnostic evidence: `517f6bdd58cf4f507aa057b49a1094d01d2318be2f4dbfee7d884a2da2824e79`.

R02 identified a duplicate durable reservation.
The controlled search path disabled the Budget observer
but retained the generic ContextVar observer consumed
by the Tavily acquisition decorator.

The fix temporarily clears that generic observer only
around the already-accounted controlled search call.
The previous observer binding is restored in finally.
The dedicated reservation, dispatch, settlement, scope,
wire tickets and authorization checks remain intact.

Corrected source SHA256: `e8c187c105ecc8fdf6421594f702ef7aef08ba520dbb04aee9e533810f73ef44`.

Verification:
- R01 retained unaffected cases: 17/17 PASS.
- R03 previously failed integrated cases: 3/3 PASS.
- Reconciled offline preflight: 20/20 PASS.
- R03 JUnit SHA256: `5bda2125ea81e4e9d4245b3303bb0471aa73c4dfe9e48903057c864211901c6e`.
- Composite JUnit SHA256: `00c9cae637499879d3b6c5dc04a73c224be562a480ecdbdec739764ab79e9cd6`.
- Disposable cleanup: PASS.

The composite report represents two separate executions,
not a single fresh 20-case test run.

The positive integration tests use fixture HTTP content.
They do not represent actual provider usage or real
external evidence.

G04: OWNER APPROVED CONDITIONAL.
Live authorization remains unconsumed.

No real credentials, actual provider calls, paid usage,
dependency changes, new migrations, Git delivery,
merge or deployment occurred.

Next: F2 controlled live smoke in a fresh disposable
environment, with exact source identity and account
configuration revalidated.

D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-E — Scoped runtime integration

Development MVP only.

Prior WP05-D evidence: `1e790de693d53090a3b2a29bf078617a8b307dc4a9d2639a6c451a5891eddd35`.

The private scoped runtime uses a bounded execution context
and shared revocation event. Legacy S06 authorization and
credential entrypoints remain unchanged and denied.

Durable reservations revalidate grant identity, operation
scope, request digest and deadline under existing DB locks.

Live-shaped settlement checks owner/task/attempt, grant,
operation kind and digest.

Controlled credential access requires a valid one-shot
search ticket. DNS and connection authorization require
the matching scoped ticket and destination.

Controlled operation threads inherit the bounded context.
Revocation invalidates copied contexts.

Observed offline verification:
- New runtime cases: 15/15 PASS.
- Targeted regression: 232/232 PASS.
- JUnit SHA256: `936ae9c22672e37ca5dfccf5ef790df43b999357888767d2b1d5257a83f91825`.
- Disposable cleanup: PASS.

The positive authorization fixtures use a test-only Owner
gate seam with socket and DNS failure sentinels.
No actual grant, external request or real credential was used.

The runtime Owner gate remains unconditionally denied.
No global live switch is introduced.

G03: OWNER APPROVED.
G04: NOT AUTHORIZED.

Account dashboard evidence: Researcher Free, 1000 available
credits, PAYG OFF and auto-upgrade OFF at observation time.
Reconfirm these settings immediately before an approved smoke.

The dedicated Owner execution mechanism and positive live
settlement verification remain outstanding.

Frozen evaluation execution and human review remain pending.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Delivery CI retained: 8/24.

No dependency or migration changes, real credentials,
live grants, provider requests, paid usage, Git delivery,
merge or deployment.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-D — Scoped smoke policy

Development MVP only.

Prior WP05-C evidence: `d81101b1393eb46a9073eb4b2117b4080029665c5dc697005e3d09c25253895b`.

## Account preflight

Owner dashboard screenshot, 2026-11-26:
Researcher Free, 0 of 1000 credits used,
pay-as-you-go OFF, auto-upgrade OFF.
No upcoming invoice displayed.

This verifies the displayed account configuration,
not API authentication or actual usage.

## Proposed live smoke scope

Provider: Tavily Basic Search.
Query: RFC 9110 HTTP Semantics plain text RFC Editor.
Maximum results: 5.
Retrieval: https://www.rfc-editor.org/rfc/rfc9110.txt.
Maximum search requests: 1.
Maximum credits: 1.
Maximum retrieval requests: 1.
No paid usage, retries or redirects.

The proposed retrieval is conditional on an exact URL
match in validated search results. No alternative URL
may be selected.

## Verification

Scope policy binds owner, task, attempt, generation,
grant identity, exact request digests and expiry.

Controlled graph performs scope checks before acquisition.
Existing unconditional external denial remains intact.

17 new scope tests PASS.
14 affected controlled workflow tests PASS.
31/31 targeted execution PASS.
JUnit SHA256: `fc54a9d149994a14d7390970837b2bec9ba9aaf78ebffec626ccb7faa2188fa9`.

This package is not a complete live activation mechanism.
Propagation into durable grant reservation, credentials,
DNS and socket authority remains required before live I/O.

G03: OWNER APPROVED.
G04: NOT AUTHORIZED.

No live grants, credentials, provider requests, paid usage,
dependency changes, additional migrations, Git delivery,
merge or deployment.

Evaluation execution remains pending.
D06-01, D06-04, D06-05, D06-06 remain mandatory OPEN.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP05-C — Successor CI checkpoint

Development MVP only.

Prior verified evidence: `e8ec9f539a931a7bfab3f93c350964b201d991b20d927bb75a6b031198693267`.

- G03: OWNER APPROVED.
- G04: NOT AUTHORIZED.
- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract delivery CI retained: 8/24.

The existing PostgreSQL CI lifecycle runner now recognizes
the S08 successor head while preserving historical revisions,
catalog checks and privilege assertions.

An explicit S08-to-S07 downgrade/upgrade phase was added.
S08 PostgreSQL integration suites were added to the existing
CI runner. The four GitHub Actions jobs remain unchanged.

Observed local verification:
- Successor lifecycle: PASS.
- S07 execution PostgreSQL regression: 14/14 PASS.
- Schema no-opt-in behavior: 44 intentional skips verified.
- JUnit SHA256: `38d76dfea78f7837bd91974004d604cea6b59d232d2592c30dba72e13544d9ab`.
- Disposable cleanup: PASS.
- Previous 244 S08 package case identities retained.

The opt-out cases are not counted as additional test passes.

Full GitHub CI delivery and successor platform compatibility
remain pending. The local isolated lifecycle check is not a
complete GitHub Actions run.

## G04 readiness

The original unconditional live authorization barrier remains
unchanged. Static authorization call-site inventory completed.

Actual Tavily account plan, remaining free credits, payment
configuration, terms and data handling require verification.

Before an approved live smoke, implement and verify a dedicated
operation-scoped authorization boundary. Never globally enable
legacy live entrypoints.

Proposed smoke maximum: one Basic search, one credit, and at most
one separately approved public HTTPS text retrieval.

No real credentials, live grant, provider request, paid usage,
external inference, shared migration, Git delivery or deployment
occurred in this package.

Frozen dataset SHA256: `6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894`.
Evaluation execution and human review remain pending.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Security acceptance: 0/20.

Next: verified account preflight and dedicated controlled
authorization implementation before G04 execution approval.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP04-D / WP05-B-R01 checkpoint

Development MVP only.

Prior verified evidence: `c2b2a3d8c98d02f847fb622611b26cbe23e4a35b3ad453e7b5e313ee4d61f959`.
Original blocked evidence: `0ca9a350092f1b7849d16fd3c1e1f306e2a63606792f00df7f5753a5acc913c6`.

The original package stopped before mutation because it
expected ten ORM infrastructure tests instead of nine.

R01 verified exact source counts and executed:
- New persistence/security: 7/7 PASS.
- Identity metadata: 7/7 PASS.
- ORM infrastructure: 9/9 PASS.
- Total targeted: 23/23 PASS.
- JUnit SHA256: `85339af8d2f81f9757d1b8bfe6adfabb331e55a7f1d735109704c382c63a7942`.
- Disposable cleanup: PASS.

Positive app-role persistence and citation resolution were
tested using fabricated database fixtures and an expired grant.
Invalid owner/task/attempt handles, deleted tasks and tampered
excerpts were rejected.

Shared capacity of twenty records was exercised in the
real-shaped fixture to synthetic insertion direction.
Deduplication at full capacity was verified.

No actual live acquisition or live settlement was executed.
These tests are not evidence of actual provider usage.

The approved metadata contains twelve tables.
Historical migrations remain unchanged.

G03: OWNER APPROVED.
G04: NOT AUTHORIZED.

Frozen dataset SHA256: `6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894`.
Evaluation execution and human review remain pending.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Security acceptance: 0/20.
Delivery CI retained: 8/24.

No live grants, credentials, provider requests, paid usage,
additional schema or dependency changes, shared migrations,
Git delivery or deployment.

Next: successor CI reconciliation and controlled G04 preflight.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP04-C / WP05-A-R01 checkpoint

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Original evidence SHA256: `334eb97bb67e2657b80a4f6763a1ed9cb2c9403ca59ad98460e404857fb2421d`.
- Retained JUnit SHA256: `b1e287e2df5886a77ceca36449dfc397dd47fcf2757633f82355b111f2544f25`.
- G03: OWNER APPROVED.
- G04: NOT AUTHORIZED.
- Contract delivery CI retained: 8/24.

## Recovery

The original application test execution completed successfully:
176/176 passed in 2.62 seconds, with zero errors, failures or skips.

The original post-test verifier failed because shell quoting
removed Python string delimiters from the suite-name list.

R01 corrects only that assertion, using double-quoted names
and exact reviewed suite counts.

The corrected verifier was extracted from the actual shell
runner argument and replayed against the unchanged original
JUnit artifact.

The replay succeeded and rejected a negative fixture containing
a missing test case.

No application test suite was rerun.
No Docker container was rebuilt or started.
Disposable cleanup from the original execution is retained.

## Evidence security

The shared task-wide evidence limit is implemented in both
repositories. Real evidence and citation lookups refresh ORM
state before validation.

Nine new integrated security cases passed.
All 129 selected historical S06 regression cases passed.
The 38 affected S08 real-evidence/workflow cases passed.

Positive mixed-store capacity, positive live persistence and
stale/deleted real-evidence isolation remain outstanding.

## Evaluation preparation

Dataset: `docs/evaluation/S08_DATASET_V1.json`.
Dataset SHA256: `6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894`.
Protocol: `docs/evaluation/S08_EVALUATION_PROTOCOL.md`.

40 frozen synthetic cases across ten categories.
30 development cases and ten held-out cases.
Fixture hashes and category-specific split verified.

The held-out partition is owner-visible and is not
independently blinded.

Evaluation execution and human review have not occurred.
No quality, latency, cost or baseline superiority is claimed.

## Remaining obligations

WP04-C / WP05-A implementation and local verification:
PASS after R01 verifier reconciliation.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Scoped security acceptance: 0/20.

No dependency, schema or application source change in R01.
No live grants, real credentials, provider requests, paid usage,
shared migrations, Git delivery, merges or deployment.

Next: positive persistence and isolation verification,
successor CI compatibility, scoped G04 preparation.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP04-B — Controlled research workflow

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- WP04-A evidence SHA256: `6a7b3f836d28b16aadcd1ec460b725f5270e2258aeb8d789d6dbc2055e4cfcf6`.
- G03: OWNER APPROVED.
- G04: NOT AUTHORIZED.
- Contract delivery CI retained: 8/24.

## Implementation

A private LangGraph workflow orchestrates the durable controlled
search and retrieval services with fixed application-owned nodes.

Both grant scopes are assessed before dispatch.
The workflow only retrieves the exact approved URL when present
in the validated search results. Snippets cannot select tools,
destinations or additional operations.

The workflow re-reads evidence under current task ownership,
validates persisted citations and returns no publishable report.

A single retrieved source is insufficient for market conclusions.
Unknown publication timestamps remain unknown.

The 30-second cooperative workflow observation bound and
recursion limit 12 remain in force. No tracing, external
model inference, public API or automatic worker activation.

## Observed verification

- New controlled workflow tests: 14/14 PASS.
- JUnit SHA256: `68eb2c3d75c9b5e0123917a9d3f56b9e407f0f55a08d1a6c68d306ff2c435ce1`.
- Disposable cleanup: PASS.
- Previous distinct test cases retained: 214.
- Distinct retained/current case identities: 228.

Positive graph cases use only in-memory service fixtures.
Actual live execution, positive live persistence and provider
billing remain unverified. No grant has been issued.

Historical synthetic workflow, provider boundaries,
migrations and dependencies remain unchanged.

Remaining WP04 obligations include positive persistence,
deletion/attempt isolation and integrated security verification.
Full CI successor compatibility remains pending.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official final acceptance: 0/36.
Scoped security acceptance: 0/20.

No live provider execution, real credentials, paid usage,
shared database migrations, Git delivery or deployment.

Next: WP04 integrated security and evaluation preparation.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP04-A — Real evidence foundation

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract delivery CI retained: 8/24.
- WP03-C evidence SHA256: `d7e2d5863d1e6056796647bb5b780847dacfeb1cb90211c84084978b7c85ce73`.
- G03: OWNER APPROVED.
- G04: NOT AUTHORIZED.

## Implementation

The dormant controlled retrieval path requires a task-bound
grant, an explicitly approved canonical HTTPS URL and prior
settled search in the same attempt.

One retrieval reservation consumes the grant allowance.
No retries, redirects or paid provider invocation are permitted.

The shared bounded connector checks retrieval wire authority
before connection and again before sending the HTTP request.

A separate observation contract rejects synthetic RetrievedPage
objects and accepts only bounded UTF-8 plain text.

Real evidence stores canonical source identity, a normalized
excerpt hash, application-derived source hostname and operation
lineage. Retrieved-at records the database settlement time
after acquisition; it is not a source publication timestamp.

Publication timestamp remains unknown rather than fabricated.

Successful retrieval settlement and evidence insertion are
prepared within one fenced PostgreSQL transaction.

Citation resolution requires current ownership, task/attempt
scope, known evidence identity and successful retrieval lineage.

## Observed verification

- New real-evidence cases: 24/24 PASS.
- Affected S07 PostgreSQL regression: 22/22 PASS.
- Provider accounting: 29/29 PASS.
- Search wire authority: 15/15 PASS.
- Current targeted execution: 90/90 PASS.
- JUnit SHA256: `e69af27857ae208dfbda8b3d885c5ef8b39a11be61189ff9961981a23baba807`.
- Disposable cleanup: PASS.

Positive observations and ticket cases remain offline fixtures.
No actual live grant or positive real-evidence database insertion
has been exercised. The dormant path is not operational approval.

No actual provider usage or website acquisition is claimed.
Workflow integration, positive persistence verification,
account reconciliation and controlled smoke remain pending.

D06-02 and D06-03 retain scoped isolated closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Security acceptance: 0/20.

No additional schema or dependency changes.
No shared migrations, live requests, paid usage,
Git delivery, merge or deployment.

Next: WP04 integrated workflow, provenance and citation security.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP03-C — Controlled search authority checkpoint

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract delivery CI retained: 8/24.
- WP03-B evidence SHA256: `3e8a14eced2794c8076361dfc42e7edf4854c51b7a194861cc6c93a369562d06`.
- G03: OWNER APPROVED.
- G04: NOT AUTHORIZED.

## Implementation

A dormant controlled-search execution path reuses the existing
fenced reservation, bounded daemon thread and cleanup service.

A one-shot process-local wire ticket is issued after the durable
dispatch transaction commits. It binds the exact request digest,
reservation, grant identity and conservative monotonic deadline.

The pinned HTTP transport requires this ticket before DNS and
checks its state again before wire send. Generic dispatch remains
unavailable for live reservations.

Credential access remains behind unconditional authorization
and the committed ticket requirement.

The adapter records its validated observation in the one-use
ticket. Settlement checks reservation identity, observed credits,
ownership, attempt fencing and deadline.

No live authorization gate was relaxed or enabled.

## Observed verification

- New wire-authority cases: 15/15 PASS.
- Provider request policy: 39/39 PASS.
- Vendor transport regression: 41/41 PASS.
- Accounting cases: 29/29 PASS.
- S07 PostgreSQL regression: 22/22 PASS.
- Targeted execution: 146/146 PASS.
- JUnit SHA256: `42d11b260a48f1b38f9dd30554baf33897269a88f4c9ebb0f11ffea1c1c71680`.
- Previously verified schema cases: 44/44 retained.
- Distinct retained/current test cases: 190.
- Disposable cleanup: PASS.

Positive wire-ticket cases are in-memory fixtures only.
No actual live grant, remote usage or billing is verified.
The positive live database path remains dormant.
No hard thread termination or remote cancellation is claimed.

D06-02 and D06-03 retain scoped isolated closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Next: WP04 real-evidence provenance, persistence,
retrieval authority and workflow integration.

No dependency or additional schema changes.
No real credentials, live provider requests, paid usage,
shared migrations, Git delivery or deployment.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Security acceptance: 0/20.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP03-B — Atomic provider reservation checkpoint

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract delivery CI retained: 8/24.
- WP03-A evidence SHA256: `9e78e7864e3b3c44497309cbbbdcbf2227a0ca87d496244dc126936eead8ef4d`.
- G03: OWNER APPROVED.
- WP03-B targeted verification: 51/51 PASS.
- Provider accounting cases: 29/29 PASS, including ten new cases.
- Affected S07 PostgreSQL regression: 22/22 PASS.
- JUnit SHA256: `5bbfa29a5a8fcb8748f54932fb99a0e6b3c05bef1a3d7fc031e11891f1a00bc2`.
- Disposable cleanup: PASS.
- Prior 80 provider and 44 schema tests retained without rerun.
- Total distinct retained/current cases: 175.

The provider reservation is bound to its canonical logical
operation identity.

The dormant controlled-smoke reservation path assesses grant
scope and quota under the existing ownership, context, ledger
and grant locks before persisting the reservation.

The existing unconditional live authorization gate is retained.
Generic dispatch and observation reject live reservations.

Origin validation distinguishes synthetic and live observations.
The live-origin positive test is an in-memory fixture, not an
actual provider observation or permission to settle live usage.

Synthetic concurrent reservation, one-shot dispatch, conservative
abandonment and one-use receipt replay rejection were tested.

Actual live grant reservation, live settlement, controlled
wire authority and real evidence integration remain incomplete.
No live grant has been issued or exercised in this package.

G04 remains NOT AUTHORIZED.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official final acceptance: 0/36.
Security acceptance: 0/20.

No dependency or additional schema change.
No shared database migration, paid usage, live provider request,
Git delivery, merge or deployment.

Next: controlled wire authority and real evidence integration.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP02-D / WP03-A — Verified checkpoint

Development MVP only.

- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract PR #27 merged; delivery CI retained 8/24.
- WP02-A: 80/80 provider tests retained.
- WP02-B: Linux aarch64 locked runtime verified.
- WP02-C-R03: 66/66 schema and affected regression tests.
- Retained R03 evidence: `61b8ca3ef8f29e08b3e55f707abf2c75df68b7dcaa5d935c179fc28ecdc836e2`.
- G03: OWNER APPROVED.

## New implementation

Controlled grant scope assessment under existing task ownership
and ledger locks. Assessment is not execution authorization.

The isolated Tavily adapter reserves a dedicated synthetic credit
in the existing durable reservation transaction before dispatch.

Validated observations are bound to one-use receipts and settled
in the existing fenced reconciliation transaction.

Invalid, missing or indeterminate usage fails closed.
Provider reservations are not automatically refunded.

## Observed verification

- New provider accounting tests: 19/19 PASS.
- Affected S07 PostgreSQL regression: 22/22 PASS.
- Targeted execution: 41/41 PASS.
- JUnit SHA256: `0730d725ded72a5e1d43721db6de573b11e8d018e872b62868060c0b525b5c85`.
- Disposable resource cleanup: PASS.
- Prior 80 provider and 44 schema tests were not repeated.
- Full harness now includes all three database test suites.

No actual account quota, billing or usage is verified here.
No actual live grant has been issued.
No live dispatch or real-provider settlement path is enabled.

G04 remains NOT AUTHORIZED.
D06-02 and D06-03 retain scoped isolated closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official acceptance: 0/36.
Scoped security acceptance: 0/20.

Next: controlled live reservation design, trusted settlement,
concurrency/recovery verification and real evidence integration.

No dependencies, historical migrations, shared databases,
Git delivery, paid usage or deployment changed.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP02-C-R03 — Verified schema foundation

Development MVP only.

## Retained verification

- WP01: DELIVERED_VERIFIED.
- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Contract PR #27 merged.
- Delivery CI retained: 8/24.
- WP02-A-R01 provider tests: 80/80 PASS.
- WP02-B Linux aarch64 locked runtime: PASS.
- R01 migration lifecycle and Alembic metadata checks: PASS.
- R01 schema tests: 44/44 PASS.
- R01 evidence SHA256: `b80c5b4ba5179c7d528f52a2f30a0971b351ff426fe305b07b68cf7c2ed9724f`.
- R01 JUnit SHA256: `3151c870988e8b57c4a0e89333417b0820a7f55b6fee7d2432237cb94d84c9b4`.

## Recovery

- R02 evidence SHA256: `fae97d1151adf3e1ac7a82f3fff9efe36a7bb6e553474fef40e46d9961282026`.
- R02 corrected the exact S07 revision assertion.
- R02 runner stopped because the image build loop reused MODE.
- R03 isolated the immutable schema-test mode from build mode.
- Full verification remains the default harness mode.
- R03 regression-only execution: 22/22 PASS.
- Regression JUnit SHA256: `72887ca13b2c1028daf2561d5f12d71b1b77e34d4152f9dd9d29722ae9e97d42`.
- Zero regression failures, errors or skips.
- Disposable Docker cleanup: PASS.
- Combined schema verification: 66/66 PASS across R01 and R03.
- Combined targeted and schema verification: 146/146 PASS
  across distinct work-package executions.
- No rerun of the prior 44 schema or 80 provider tests.

Schema foundation is verified within the executed test scope.
Full CI successor compatibility remains pending.

G03 remains OWNER APPROVED.
G04 remains NOT AUTHORIZED.

Controlled authorization service, durable provider-credit
accounting, recovery and real evidence integration remain pending.

D06-02 and D06-03 retain isolated scoped closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Technical acceptance retained: 3/36.
Official final acceptance: 0/36.
Security acceptance: 0/20.

No live grant issuance, credentials, provider requests,
paid usage, dependency changes, shared migrations,
Git delivery or deployment.

Next action: WP02-D / WP03 durable authorization and accounting.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP02-C — G03 schema checkpoint

S08 Contract v1.0 — Development MVP only.

- WP00: VERIFIED.
- WP01: DELIVERED_VERIFIED.
- Contract PR #27: MERGED.
- Contract PR CI: 45796194218, 4/4 PASS.
- Contract main CI: 45797026991, 4/4 PASS.
- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Technical acceptance retained: 3/36.
- Delivery CI retained: 8/24.
- WP02-A-R01 targeted tests: 80/80 PASS.
- WP02-B locked runtime: PASS, Linux aarch64.
- G03: OWNER APPROVED.

## Current package

WP02-C adds schema foundation for durable provider credits,
controlled authorization persistence and separate real evidence.

Migration revision: `e8c2106a0801`.
Previous revision: `d8b3105f0804`.

Schema and migration acceptance remains pending actual
disposable PostgreSQL execution evidence.

WP03 service integration remains pending.
WP04 evidence service and workflow integration remain pending.
Actual account quota and billing remain unverified.
No live grant is issued. G04 remains NOT AUTHORIZED.

D06-02 and D06-03 retain isolated scoped closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

No local rerun of the prior 80 tests.
No dependency manifest changes.
No shared database migration or Git delivery.
No real credentials, live requests, paid usage or deployment.

Official acceptance: 0/36.
Scoped security acceptance: 0/20.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP02-B active checkpoint

S08 Contract v1.0 — Development MVP only.

## Retained verified delivery

- WP00: VERIFIED.
- WP01: DELIVERED_VERIFIED.
- Contract PR #27: MERGED.
- Contract PR CI 45796194218: 4/4 PASS.
- Contract main CI 45797026991: 4/4 PASS.
- Base main: `e570b31fdee439c10579694201c2f44a88107547`.
- Technical acceptance retained: AC01–AC03, 3/36.
- Cumulative delivery CI: 8/24.

## WP02-A-R01 retained verification

- Evidence SHA256: `3a52fd607967c7cbf02312427d65e8da82d6096d6a81869f986691f1abe97322`.
- JUnit SHA256: `ecaf1c779aeac6d323729372e808b4daa2284bde6e65276aa14aa978372e2e0f`.
- New S08 request policy tests: 39/39 PASS.
- Existing affected S06 vendor tests: 41/41 PASS.
- Total: 80 PASS; zero failures, errors or skips.
- No repeated execution of those test suites in WP02-B.

## WP02-B observed runtime compatibility

- Three runtime locks contain HTTPX 0.28.1 and HTTPX2 2.16.2.
- Actual application Dockerfile build passed.
- Docker architecture: aarch64.
- Runtime image ID: `sha256:32a13695f9b8572d580ec1f97d42e538dd9a4189241cc61bf1346c789f876486`.
- Build-context manifest SHA256: `8ad49d756553c49f9c7dcc2e9567c9fdd46a61de946ff2d3132f5adbcfdc057d`.
- Locked runtime imports passed.
- Non-root and network-disabled smoke passed.
- Isolated mock adapter passed.
- Default-deny live authorization passed.
- Disposable image removed.
- Runtime execution on every supported architecture is not claimed.
- No dependency manifest or lockfile change.

## G03 material schema boundary

The existing operation ledger stores model tokens and monetary
cost but has no dedicated provider-credit accounting fields.

Existing research evidence is constrained to synthetic-only
fixture retrieval.

Proposed S08 schema direction, NOT YET AUTHORIZED:

1. Add provider identity and dedicated reserved/observed credit
   accounting to durable operation settlement.
2. Keep synthetic observations distinct from actual provider usage.
3. Bind provider usage to the existing owner/task/attempt/operation
   authority, preserving transaction, deadline and retry restrictions.
4. Use a narrowly scoped durable controlled-smoke allowance to
   prevent repeat dispatch or allowance reset across recovery.
5. Support real evidence with explicit provenance and an
   attempt-bound acquisition relationship.
6. Preserve synthetic fixture restrictions and historical records.
7. Use forward-only new Alembic revisions for implementation,
   with downgrade verification restricted to disposable databases.
8. Verify migration, grants, constraints, isolation, recovery
   and affected regressions before technical acceptance.

This is a proposed architecture scope, not applied DDL.
Separate G03 approval and exact implementation review are required.

## Remaining WP02 obligations

Actual account quota, billing status and applicable account terms
remain unverified. Controlled live authorization remains pending.
No live credentials or provider interoperability claim.

AC04, AC06 and AC08 have supporting offline/runtime evidence.
Final criterion reconciliation remains pending.
AC05, AC07 and AC09 remain incomplete.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

Strict Authlib XFAIL and ADR-0002 scope remain binding.
Worker activation remains disabled by default.
No live execution, paid usage, deployment or Git delivery.

Official acceptance: 0/36.
Security acceptance: 0/20.
Technical acceptance retained: 3/36.

Next action: reconcile WP02-B and approve the narrow G03
schema scope before material database changes.

PRODUCTION REMAINS NOT APPROVED.

---

# S08 WP02-A-R01 active checkpoint

S08 Contract v1.0 — Development MVP only.

- WP00: VERIFIED.
- WP01: DELIVERED_VERIFIED.
- Contract PR #27: MERGED.
- Contract PR CI 45796194218: 4/4 PASS.
- Contract main CI 45797026991: 4/4 PASS.
- Main baseline: `e570b31fdee439c10579694201c2f44a88107547`.
- Technical acceptance: AC01–AC03, 3/36.
- Delivery CI: 8/24.
- WP02-A initial execution stopped before mutation because
  its expected credentials.py SHA256 was truncated.
- R01 uses the original reviewed source snapshot identity.
- No integrity gate is waived.

## WP02-A-R01 implementation scope

Shared application-owned Basic Search request policy.
Validate exact provider body before DNS and wire exchange.
Preserve unconditional live authorization denial.
Preserve original credential handling and pinned connector.

Public provider compatibility sources for review:

- https://docs.tavily.com/documentation/api-reference/endpoint/search
- https://docs.tavily.com/documentation/api-credits
- https://www.tavily.com/pricing
- https://www.tavily.com/terms

Actual account quota, billing and live interoperability
remain unverified.

Targeted runtime results require execution evidence.
Locked runtime compatibility remains pending.
AC04–AC09 require further verification.

D06-02 and D06-03 retain isolated Development MVP closure.
D06-01, D06-04, D06-05 and D06-06 remain mandatory OPEN.

ADR-0002 Development MVP authentication scope preserved.
Worker activation disabled by default.
Strict Authlib XFAIL retained.

No dependency or schema change.
No live credentials, paid usage or external activation.
No Git delivery or deployment.

Official acceptance: 0/36.
Security acceptance: 0/20.

Next action: reconcile targeted runtime and inspect
durable accounting and evidence persistence for WP02/WP03.

PRODUCTION REMAINS NOT APPROVED.

---

# AgentOps AI — S08 active checkpoint

**Date:** 2026-11-26

**Contract:** S08 Contract v1.0 — OWNER APPROVED.

**Sprint status:** IN_PROGRESS — DEVELOPMENT MVP ONLY.

**Current work package:** WP01 contract documentation.

**Production:** NOT APPROVED.

## Last verified starting checkpoint

- S00–S07: CLOSED.
- S07 official acceptance: 36/36.
- S07 scoped security gates: 20/20.
- S07 delivery CI: 16/16 PASS.
- S07 feature PR #25 and closeout PR #26: MERGED.
- Starting main HEAD: `99c220233a296dcaf6a007865d1a1e52d854602c`.
- Final S07 main CI: 45793307007.
- S07 final evidence SHA256 reference: `2a6de4fc0c308a65537469bcb14d781b379470608addf346901cfc5d6ecd2b96`.
- WP00: 36/36 checkpoint checks PASS.
- Protected stash: `13ab03b82e68364c8f4f022821e12dca5ec7b731`.
- Workspace: `/Users/namnguyen/agentops-ai`.
- WP01 target branch: `docs/s08-contract-adr`.

Previous checkpoint history remains available in the
starting main commit and `docs/sprints/S07_CLOSEOUT.md`.

No future commit or CI identity is asserted.

## Current S08 work status

| Package | Deliverable | Status |
| --- | --- | --- |
| WP00 | Checkpoint and contract discovery | VERIFIED — 36/36 checks |
| WP01 | Contract, ADR and documentation delivery | IN_PROGRESS — delivery pending |
| WP02 | Provider compatibility and controlled authorization | PLANNED |
| WP03 | Actual usage and cost accounting | PLANNED |
| WP04 | Real evidence and workflow integration | PLANNED |
| WP05 | Live smoke, AI evaluation and security acceptance | PLANNED — separate live gate |
| WP06 | Integrated verification and feature delivery | PLANNED |
| WP07 | Final acceptance and sprint closeout | PLANNED |

Official acceptance: 0/36 pending final acceptance.
Scoped S08 security verification: 0/20.

G01 Owner approval is recorded in `docs/sprints/S08.md`.

## Mandatory obligations

| ID | Obligation | Dependencies | Status |
| --- | --- | --- | --- |
| D06-01 | Provider interoperability | D06-02, D06-03 | OPEN |
| D06-02 | Secure connector verification | None | CLOSED_VERIFIED_ISOLATED_DEVELOPMENT_MVP |
| D06-03 | Execution budgets and deadlines | None | CLOSED_VERIFIED_ISOLATED_DEVELOPMENT_MVP |
| D06-04 | Actual provider usage and cost accounting | D06-01, D06-03 | OPEN |
| D06-05 | Real evidence integration | D06-01 through D06-04 | OPEN |
| D06-06 | Integrated external security acceptance | D06-01 through D06-05 | OPEN |

## Current constraints

- Preserve isolated closure of D06-02 and D06-03.
- Actual provider and real-evidence verification remains pending.
- Default-deny external execution.
- No live credentials or live smoke execution without G04.
- No paid usage, routine external activation or deployment.
- Worker activation remains disabled by default.
- Preserve existing Development MVP authentication under ADR-0002
  and its approved restrictions; strict Authlib XFAIL retained.
- No real-user authentication; production authentication remains
  NOT APPROVED.
- Dependency changes and material unapproved schema/architecture
  changes require separate approval.
- All prior security gates and governance limitations remain binding.

## Exactly one next action

Review WP01 local documentation evidence and obtain
G02 Owner authorization for contract documentation delivery.

WP01 delivery and merged-main CI must pass before WP02 begins.

No Git delivery or merge has been authorized by G01.

PRODUCTION REMAINS NOT APPROVED.
