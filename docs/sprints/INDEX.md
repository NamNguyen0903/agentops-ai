# AgentOps AI — Authoritative Sprint Roadmap

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

### Approved revised milestone allocation

| Sprint | Deliverable |
| --- | --- |
| S00 | Product planning and architecture — CLOSED |
| S01 | Application foundation — CLOSED |
| S02 | Database and authentication — CLOSED |
| S03 | Research task API and dashboard — CLOSED |
| S04 | LangGraph workflow baseline — CLOSED |
| S05 | Specialized agent nodes — CLOSED |
| S06 | Offline Evidence and Citation Foundation |
| S07 | Worker Reliability and Secure Acquisition |
| S08 | Live Research Integration, Evaluation and Security |
| S09 | CI/CD and AWS Staging Preparation |

The project retains ten planned sprints, S00-S09.
The one-day sprint target is subject to workload
review and is not a completion guarantee.

S07 retains its original reliability, deadline,
recovery and usage-budget objectives, and receives
D06-02 and D06-03.

S08 retains its original evaluation, integration and
security objectives, and receives D06-01, D06-04,
D06-05 and D06-06.

S08 external execution depends on applicable S07
connector and execution verification.

S09 staging readiness depends on applicable S07
and S08 delivery, operational and security evidence.

Deferred obligations are mandatory. They must not
be discarded or further deferred without a recorded
owner-approved amendment.

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

### Current delivery state

S00-S05: CLOSED, historical scope preserved.
S06: IN_PROGRESS, Contract v1.1 effective.
WP05-F-R01: documentation reconciliation completed.
WP05-G: delivery review and authorization required.
WP05-H: final owner acceptance pending.
S07-S09: NOT_STARTED.

This active amendment supersedes historical roadmap
allocation where scope descriptions differ.

No receiving sprint may omit its mandatory deferred
obligations from its approved contract.


## Active roadmap — 2026-11-25, S05 CLOSED; S06 IN_PROGRESS

**Scope:** Development MVP only.

**Production authorization:** NOT APPROVED.

| Sprint | Current status | Evidence / contract |
|---|---|---|
| S00 | FOUNDATION | [S00](S00.md) |
| S01 | CLOSED | [S01](S01.md) |
| S02 | CLOSED — 11/11 accepted | [S02 closeout](S02_CLOSEOUT.md) |
| S03 | CLOSED — 12/12 accepted | [S03 closeout](S03_CLOSEOUT.md) |
| S04 | CLOSED — Development MVP only | [S04 contract](S04.md), [S04 closeout](S04_CLOSEOUT.md) |
| S05 | CLOSED — 16/16 accepted; Development MVP only | [S05 Contract v1.0](S05.md) |
| S06 | IN_PROGRESS — WP02 RECONCILIATION; WP04 OFFLINE VERIFIED | [S06 Contract v1.0](S06.md) |
| S07-S09 | PLANNED | Original roadmap retained below |

S04 final-state synchronization PR #15 is MERGED.

Final S04 main checkpoint:
`104fc173abff205d82025ebcb08eadea8b01f353`.

Final S04 main CI run 45419682711: 4/4 PASS.

S04 is CLOSED. No S04 reopening or additional closeout
delivery is implied.

### S06 — Search, Evidence and Citation Validation

**Status:** IN_PROGRESS — WP02 reconciliation; WP04 offline verified.

**Contract:** [S06 Contract v1.0](S06.md).

Owner approved on 2026-11-25, Development MVP only.

| Work package | Status |
|---|---|
| WP01 — Contract and Architecture | DELIVERED |
| WP02 — Search and Secure Retrieval | ISOLATED_VERIFIED; PARTIAL_ACCEPTANCE_PENDING |
| WP03 — Evidence Persistence and Provenance | VERIFIED_LOCAL |
| WP04 — Evidence-backed Workflow and Citation Validation | VERIFIED_LOCAL_OFFLINE |
| WP05 — Integration, Security, CI and Closeout | PLANNED |

AC01–AC24, SG01–SG16 and scoped AD01–AD08 approved
as the contract baseline, not as completed implementation.

Official acceptance: 0/24.

Search vendor and live external execution require
separate approval.

Production remains NOT APPROVED.

### S05 — Specialized Planner, Research and Writer Nodes

**Status:** CLOSED — DEVELOPMENT MVP ONLY.

Final owner acceptance: 2026-11-25.

| Work package | Status |
|---|---|
| WP01 — Contract and Architecture | DELIVERED; ACCEPTED |
| WP02 — Typed Contracts and Fixture Adapters | DELIVERED; ACCEPTED |
| WP03 — Specialized Workflow Nodes | DELIVERED; ACCEPTED |
| WP04 — Security and Execution Guards | DELIVERED; ACCEPTED |
| WP05 — Integration, CI and Closeout | DELIVERED; ACCEPTED |

Delivered work packages: 5/5.
Accepted criteria: 16/16.

PR #18 and PR #19 are MERGED.

Last verified main implementation and closeout baseline:

9a84d02e0f23958d93a35e64322e95519f8ffe55

Final documentation PR CI: 45571457482, 4/4 PASS.
Final documentation main CI: 45571621625, 4/4 PASS.

Backend: 1632 passed, 49 historical skips.
Permanent named security tests: 547 passed.
Local backend audit: 64 packages, zero known findings.

All approved security and release gates remain mandatory.

S06 is NEXT — NOT STARTED.
S07-S09 remain PLANNED.

Next action: await separate owner authorization
for Sprint S06 after final status synchronization.

Production remains NOT APPROVED.

### Retained historical S05 checkpoints

The following historical progress records are
retained for traceability. Their earlier pending
statuses and resume instructions are superseded
by the active roadmap above.

WP01 final acceptance and synchronization: COMPLETE.

- PR #16: MERGED.
- PR #17: MERGED.
- Final Main CI 45428619901: 4/4 PASS.
- WP01 required CI job results across four runs: 16/16 PASS.
- Final WP01 main checkpoint:
  `a7f485e3b57e5d898c3a29bf76c4d5c96ae035c1`.

WP02 owner authorization: APPROVED on 2026-11-24.
Authorized criteria: AC03-AC05.

Active branch: `feat/s05-specialized-workflow`.

WP02-01 and WP02-02 are VERIFIED.

WP02-03 typed contracts are VERIFIED_LOCALLY.

WP02-04 validation and immutable context are
VERIFIED_LOCALLY.

WP02-04C2 documentation checkpoint: PASS.

WP02-05 deterministic fixture adapters are
VERIFIED_LOCALLY.

WP02-05C ambiguous replacement marker recovery: PASS.

WP02-05D1 adapter integration verification: PASS.

All three specialized offline fixture adapters
are verified locally.

Adapter integration tests: 32 passed.

WP02-05D2 documentation checkpoint: PASS.

WP02-06 contract and fixture negative tests are
VERIFIED_LOCALLY.

WP02-06A signed-zero integrity tests: 16 passed.
WP02-06B additional contract boundaries: 39 passed.
WP02-06C fixture negative tests: 42 passed.

Consolidated WP02-06 tests: 97 passed.
WP02-06 focused suite: 458 passed.

WP02-06D-R1 documentation diagnostic: PASS.

WP02-06D-R2 documentation checkpoint: PASS.

WP02-07A/B/C/D regression and security verification:
PASS.

WP02-07 is VERIFIED_LOCALLY.

Seven backend and two Authlib hash lockfiles preserved.

SEC-03 and SEC-04 remediated within reproduced cases.

Diagnostic replay: 62 safe rejections, zero findings.

Security tests: 74 passed.
S05 focused tests: 532 passed.
S04 regression: 74 passed.
Combined regression: 606 passed.

Full backend regression:
775 collected, 726 passed, 49 approved opt-in skips.
Zero failures, errors or XFAILs.

WP02-07E initial documentation preparation stopped
before writes on a literal marker assertion.

WP02 main tickets verified locally: 8/8.
WP02 local completion: OWNER ACCEPTED, 2026-11-25.

WP02-07E-R1 execution and evidence review: PASS.

WP02-07E-R2 documentation review: PASS.

WP02-08A-R1 diagnostic: 35/36 checks passed.
WP02-08A-R2 corrected verification: 36/36 PASS.

AC03-AC05 local technical evidence: PASS.

WP02-08A Tech Lead review: ACCEPTED.

WP02-08B initial AC inventory assertion stopped
documentation preparation before repository writes.

WP02-08B-R1 uses section-aware AC validation.
Final documentation review: PASS.

WP02 integrated delivery remains pending PR B.
No official AC03-AC05 acceptance is claimed.

WP03 owner authorization: APPROVED, 2026-11-25.
Authorized criteria: AC06-AC09 only.

WP03-01A baseline: VERIFIED.
WP03-01B1 engineering authorization: VERIFIED.
WP03-01B2 technical design: VERIFIED.
WP03-01B3 final reconciliation: VERIFIED.

WP03-02A interface compatibility: VERIFIED.
WP03-02B Planner implementation: VERIFIED.
WP03-02B-R1 manifest recovery: VERIFIED.
WP03-02C testing and source review: VERIFIED.

Planner unit tests: 34 passed.
Security tests: 74 passed.
S05 focused tests: 566 passed.
S04 regression: 74 passed.
Combined regression: 640 passed.

AC06 Planner component evidence: PASS locally.
Official AC06 acceptance remains PENDING.

WP03-02D documentation review: PASS.

WP03-03A Research implementation: VERIFIED.
WP03-03B testing and source review: VERIFIED.

Research unit tests: 41 passed.
Current S05 focused regression: 607 passed.
Current combined regression: 681 passed.

All six execution exit codes: zero.
Test identities reconciled.

AC07 Research component evidence: PASS locally.
Official AC07 acceptance remains PENDING.

WP03-03C documentation review: PASS.

WP03-04A Evidence implementation: VERIFIED.
WP03-04B testing and source review: VERIFIED.

Evidence unit tests: 65 passed.
Fixture availability cases: 16 passed.
Invalid state cases: 28 passed.
Tampered evidence cases: 11 passed.
Routing revalidation cases: 6 passed.

Current S05 focused regression: 672 passed.
Current combined regression: 746 passed.

All seven execution exit codes: zero.
Test identities reconciled.

Evidence Validation component evidence: PASS locally.
Official AC07-AC09 acceptance remains PENDING.

Actual LangGraph Writer bypass was pending
at this historical Evidence checkpoint and was
subsequently verified in WP03-06D.

WP03-04C documentation review: PASS.

WP03-05A Report Validator: VERIFIED.

Historical initial result: 49 passed, 3 failed.
Root cause: UUID_COMPARATOR_INCOMPATIBILITY.
Targeted correction and recovery: VERIFIED.

Original three failed tests recovered.
Eight new UUID regression tests passed.
Report Validator: 60 passed.

WP03-05B Writer implementation: VERIFIED.
WP03-05C node testing: VERIFIED.
WP03-05D combined regression: VERIFIED.

Writer and Report Validation: 61 passed.
Node-level combined regression: 195 passed.

Current S05 focused regression: 793 passed.
Current S04 regression: 74 passed.
Current combined regression: 867 passed.

All previous test identities preserved.
Exactly 61 new Writer test identities.

AC08 component evidence: PASS locally.
Official AC08 acceptance remains PENDING.

Mixed-error security classification requires
hardening before repair activation.

WP03-05E documentation review: PASS.

WP03-06A Outcome implementation: VERIFIED.
WP03-06B Outcome testing: VERIFIED.
Outcome tests: 63 passed.
Terminal component regression: 258 passed.

WP03-06C LangGraph construction: VERIFIED.
WP03-06D actual graph execution: VERIFIED.
Actual LangGraph workflow tests: 35 passed.
Actual Writer bypass: 15 passed.
Graph component regression: 293 passed.

WP03-06E combined regression: VERIFIED.

Latest S05 focused regression: 891 passed.
Latest S04 regression: 74 passed.
Latest combined regression: 965 passed.

Exactly 98 additional test identities.
All previous test identities preserved.

AC09 normal-path orchestration evidence:
PASS locally.

Official AC09 acceptance remains PENDING.

Global repair is not enabled.
SEC05-SEC11 security obligations remain OPEN.

WP03-06F documentation review: PASS.

WP03-07A initial preflight: BLOCKED.
WP03-07A-R1/R1B historical diagnosis: COMPLETE.
WP03-07A-R2 full backend regression: VERIFIED.
WP03-07B acceptance traceability: VERIFIED.

Full backend collected: 1134.
Full backend passed: 1085.
Historical approved skips: 49.
New skips: zero.
Failures and errors: zero.

All 775 historical identities preserved.
All 359 new WP03 identities passed.
All 965 combined regression identities passed.

AC06 primary test accounting: 34.
AC07 primary test accounting: 106.
AC08 primary test accounting: 121.
AC09 primary test accounting: 98.

AC06-AC09 local implementation evidence: PASS.
Official acceptance remains PENDING.

Historical artifact directory and exact skip
reason comparison were corrected without
application changes or weakened gates.

SEC05-SEC11 remain OPEN.

PostgreSQL integration remains NOT_RUN.

WP03-08A initial ledger preparation: BLOCKED.
WP03-08A-R1 ledger diagnosis: PASS.
WP03-08A-R2 documentation review: PASS.
WP03-08B-R2 final technical review: PASS.

WP03 final Project Owner acceptance: APPROVED.
WP03 main tickets accepted locally: 8/8.
WP03 status: LOCAL COMPLETE.

AC06-AC09 local implementation evidence accepted.
Integrated delivery remains pending PR B.

WP03-08C initial documentation sync stopped
before writes on a duplicate authorization marker.

WP03-08C-R1 authorization diagnosis: PASS.
WP03-08C-R2 section-aware documentation recovery.

The full backend result of 726 passed and
49 skipped remains historical WP02 evidence.

Authoritative current authorization — 2026-11-25.

WP03: LOCAL COMPLETE, 8/8.
WP04: AUTHORIZED for AC10-AC14 only.
WP04 implementation: NOT_STARTED.
WP05 remains NOT AUTHORIZED.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official sprint acceptance: 2/16.

AC03-AC09 remain pending integrated delivery.

Actual LangGraph orchestration was implemented
and verified locally in WP03.

Runtime implementation authorization: WP04 ONLY.

SEC05-SEC11 remain OPEN.

All official Sprint Contract security gates
and approved architecture decisions are preserved.

No live model providers, real retrieval, database
writes, lifecycle mutation, worker activation,
publication or production deployment are approved.

Production remains NOT APPROVED.

Historical WP04-01 technical design checkpoint:

WP04-01A baseline: VERIFIED.
WP04-01B design: VERIFIED.
WP04-01C documentation: VERIFIED.
WP04-01D design verification: PASS.

Ten WP04 main tickets are defined in S05.md
section 37.

WP04 main tickets accepted: 1/10.
Runtime implementation remains NOT_STARTED.

GD01-GD12 design review: PASS. Runtime verification remains pending.

Official SG01-SG12 remain unchanged.
SEC05-SEC11 remain OPEN.
AC10-AC14 acceptance remains PENDING.

Repair activation remains disabled pending
the applicable security and execution guards.

### Historical WP04-02 acceptance checkpoint

WP04-02 - Mixed-error security classification:
VERIFIED locally.

SEC05: VERIFIED_LOCAL for the tested component
boundaries. Integrated acceptance remains pending.

WP04 main tickets accepted: 2/10.
Runtime implementation: IN_PROGRESS.

Latest accepted regression baseline:

- Diagnostic replay: 25/25 passed.
- Previously reproduced findings: 16/16 corrected.
- Original controls: 9/9 preserved.
- New permanent SEC05 tests: 46 passed.
- Report Validator: 104 passed.
- Writer: 63 passed.
- Security boundaries: 74 passed.
- S05: 937 passed.
- S04: 74 passed.
- Combined S04/S05: 1011 passed.
- Full backend: 1180 collected, 1131 passed, 49 skipped.
- Historical identities and statuses: 1134 preserved.
- Historical skip identities and reasons: 49 preserved.
- Failures, errors and new skips: zero.

SEC06-SEC11 remain OPEN.
AC10-AC14 integrated acceptance remains pending.
SG01-SG12 remain mandatory and unchanged.

Public workflow repair remains disabled.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

No live providers, real retrieval, database writes,
lifecycle mutation, publication, worker activation
or deployment are authorized.

This checkpoint supersedes earlier WP04 design-only
status and regression baseline statements.


### Historical WP04-03 acceptance checkpoint

WP04-03 - Strict terminal-result integrity:
VERIFIED locally.

SEC05 and SEC06: VERIFIED_LOCAL.
Integrated security acceptance remains pending.

WP04 main tickets accepted: 3/10.
Runtime implementation: IN_PROGRESS.

Latest accepted regression baseline:

- SEC06 diagnostic replay: 54/54 passed.
- Previously reproduced SEC06 findings: 24/24 corrected.
- Public workflow findings: 4/4 corrected.
- Original positive controls: 2/2 preserved.
- Original negative controls: 28/28 preserved.
- New permanent SEC06 tests: 62 passed.
- Previous permanent SEC05 tests: 46 preserved.
- Workflow: 97 passed.
- Outcome: 63 passed.
- Report Validator: 104 passed.
- Writer: 63 passed.
- Security boundaries: 74 passed.
- S05: 999 passed.
- S04: 74 passed.
- Combined S04/S05: 1073 passed.
- Full backend: 1242 collected, 1193 passed, 49 skipped.
- Historical identities and statuses: 1180 preserved.
- Historical skip identities, types and reasons: 49 preserved.
- Failures, errors and new skips: zero.

SEC07-SEC11 remain OPEN.
AC10-AC14 integrated acceptance remains pending.
SG01-SG12 remain mandatory and unchanged.

Public workflow repair remains disabled.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

No live providers, real retrieval, database writes,
lifecycle mutation, publication, worker activation
or deployment are authorized.

This checkpoint supersedes prior WP04 progress
and regression baseline statements.

### Historical WP04-04 acceptance checkpoint

WP04-04 - Safe exception category mapping:
VERIFIED locally.

SEC05, SEC06 and SEC07: VERIFIED_LOCAL.
Integrated security acceptance remains pending.

WP04 main tickets accepted: 4/10.
Runtime implementation: IN_PROGRESS.

Latest accepted regression baseline:

- SEC07 diagnostic replay: 15/15 passed.
- Previously reproduced SEC07 findings: 8/8 corrected.
- Original controls: 7/7 preserved.
- Unauthorized category property reads: zero.
- Raw exception escapes in replay: zero.
- New permanent SEC07 tests: 53 passed.
- Previous SEC05 tests: 46 preserved.
- Previous SEC06 tests: 62 preserved.
- Workflow: 150 passed.
- Outcome: 63 passed.
- Report Validator: 104 passed.
- Writer: 63 passed.
- Security boundaries: 74 passed.
- S05: 1052 passed.
- S04: 74 passed.
- Combined S04/S05: 1126 passed.
- Full backend: 1295 collected, 1246 passed, 49 skipped.
- Historical identities and statuses: 1242 preserved.
- Historical skip identities, types and reasons: 49 preserved.
- Failures, errors and new skips: zero.

SEC08-SEC11 remain OPEN.
AC10-AC14 integrated acceptance remains pending.
SG01-SG12 remain mandatory and unchanged.

Public workflow repair remains disabled.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

No live providers, real retrieval, database writes,
lifecycle mutation, publication, worker activation
or deployment are authorized.

This checkpoint supersedes prior WP04 progress
and regression baseline statements.

### Authoritative WP04-05 acceptance checkpoint

WP04-05 - Exact node update ownership:
VERIFIED locally.

SEC05, SEC06, SEC07 and SEC08: VERIFIED_LOCAL.
Integrated security acceptance remains pending.

WP04 main tickets accepted: 5/10.
Runtime implementation: IN_PROGRESS.

Latest accepted regression baseline:

- Original SEC08 diagnostic replay: 39/39 passed.
- Additional SEC08 diagnostic replay: 17/17 passed.
- Total SEC08 diagnostic replay: 56/56 passed.
- Original reproduced findings: 32/32 corrected.
- Additional reproduced findings: 16/16 corrected.
- Total SEC08 reproduced findings: 48/48 corrected.
- Invalid update downstream calls in replay: zero.
- Invalid payload boundary passes in replay: zero.
- Unsafe public results in replay: zero.
- Original permanent SEC08 tests: 121 passed.
- Additional permanent SEC08 tests: 21 passed.
- Total permanent SEC08 tests: 142 passed.
- Previous SEC05 tests: 46 preserved.
- Previous SEC06 tests: 62 preserved.
- Previous SEC07 tests: 53 preserved.
- Total permanent SEC05-SEC08 tests: 303 passed.
- Workflow: 292 passed.
- Outcome: 63 passed.
- Report Validator: 104 passed.
- Writer: 63 passed.
- Security boundaries: 74 passed.
- S05: 1194 passed.
- S04: 74 passed.
- Combined S04/S05: 1268 passed.
- Full backend: 1437 collected, 1388 passed, 49 skipped.
- Historical identities and statuses: 1416 preserved.
- Historical skip identities, types and reasons: 49 preserved.
- Failures, errors and new skips: zero.

SEC09-SEC11 remain OPEN.
AC10-AC14 integrated acceptance remains pending.
SG01-SG12 remain mandatory and unchanged.

Public workflow repair remains disabled.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

No live providers, real retrieval, database writes,
lifecycle mutation, publication, worker activation
or deployment are authorized.

This checkpoint supersedes prior WP04 progress
and regression baseline statements.


### Authoritative WP04-06 acceptance checkpoint

Date: 2026-11-25.

WP04-06: ACCEPTED LOCAL - DEVELOPMENT MVP ONLY.

SEC05-SEC08: VERIFIED_LOCAL.
SEC09: VERIFIED_LOCAL for invocation accounting,
controller allowance and positive repair eligibility.
Actual public repair verification remains pending
under WP04-07.

SEC10 and SEC11 remain OPEN.

WP04 main tickets accepted: 6/10 (60%).
Runtime implementation: IN_PROGRESS.

Full backend: 1580 collected, 1531 passed, 49 skipped,
zero failures and zero errors.

Historical identities: 1437 preserved.
Historical skip identities, types and reasons: preserved.

SEC09 permanent tests: 143 passed.
SEC05-SEC09 permanent security tests: 446 passed.
Accounting and eligibility diagnostics: 54/54 passed.
Corrected diagnostic finding cases: 18.
Remaining reproduced findings: zero.

Evidence directory:

`/tmp/agentops-s05-wp04-06f.t3EjJ5`

Evidence SHA-256:

`6e1cd1f3c27367fa5756f3eac90fd5a487484aeffb49c4c7ee69aeef9ef060ae`

Full backend JUnit SHA-256:

`748573473136c7e6ce4e2bc312f54d9df19367a33266a69514836d18d09a8b42`

See S05.md section 42 for delivered implementation,
regression evidence and residual limitations.

Public workflow repair remains DISABLED.
WP04-07 is the next authorized ticket.

Local completed work packages: 3/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

Integrated AC10-AC14 acceptance remains pending.
SG01-SG12 remain mandatory and unchanged.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

The WP04-05 and earlier checkpoints are retained
as historical evidence. This WP04-06 checkpoint
supersedes their progress and resume instructions.

### Authoritative WP04 final acceptance checkpoint

Date: 2026-11-25.

WP04: ACCEPTED LOCAL - DEVELOPMENT MVP ONLY.
WP04 tickets: 10/10 completed (100%).

SEC05-SEC11: VERIFIED_LOCAL within tested scopes.

Backend: 1681 collected, 1632 passed, 49 skipped,
zero failures and zero errors.

Prior integration test identities: 1655 preserved.
Historical skip identities and reasons: preserved.
Final named security test inventory: 547.

Public guarded repair: IMPLEMENTED AND VERIFIED_LOCAL.
Global repair allowance: one.
Maximum adapter invocations: four.
Soft deadline: maximum 30 seconds.
Recursion limit: 12.

Evidence directory:

`/tmp/agentops-s05-wp04-final-integration.Vlj7x5`

Final JUnit SHA-256:

`b8c7003bce2821030e68096158abf01a26a245361a9926a9a841e5df24b5447f`

Local completed work packages: 4/5.
Officially delivered work packages: 1/5.
Official Sprint acceptance: 2/16.

Next action: prepare owner-controlled WP02-WP04
feature PR delivery.

WP05 remains NOT AUTHORIZED.
Production remains NOT APPROVED.

Earlier checkpoints remain historical evidence.
See S05.md section 43 for the implementation,
verification evidence and residual limitations.

Next action:

Prepare owner-controlled Git delivery of
WP02-WP04 through the authorized feature PR.

Review the complete feature diff and release gates
before staging, committing or pushing.

WP04 is locally accepted for Development MVP only.
Integrated remote CI and owner approval remain
required before delivery acceptance.

Do not start WP05 without explicit owner authorization.
Production remains NOT APPROVED.

### Current resume authority

Start with [CURRENT_STATE.md](../handoff/CURRENT_STATE.md),
then inspect actual Git evidence.

The PRD, approved ADRs and engineering working
agreement remain authoritative for their respective
product, architecture and engineering decisions.

The original sprint roadmap is retained below without
changing the planned goals of S06-S09.

---

## Historical roadmap archive

All content below is historical. Earlier roadmap
tables, active-sprint headings and pending actions
do not supersede the authoritative roadmap above.

---

# AgentOps AI — Sprint Index

## Authoritative active roadmap — 2026-11-24 (S04 CLOSED; S05 NEXT)

| Sprint | Status | Evidence / contract |
|---|---|---|
| S01 | CLOSED | Historical sprint record |
| S02 | CLOSED, 11/11 | [S02 closeout](S02_CLOSEOUT.md) |
| S03 | CLOSED, 12/12 | PR #8 / #9 MERGED, main CI PASS; [S03 closeout](S03_CLOSEOUT.md) |
| S04 — Single-agent LangGraph | **CLOSED; WP01–WP04 DELIVERED — DEVELOPMENT MVP ONLY** | [S04 approved contract](S04.md), [ADR-0004 ACCEPTED — Development MVP only](../adr/0004-langgraph-state-and-agent-boundaries.md) |
| S05–S09 | PLANNED | Historical roadmap below; no implementation implied |

Owner approved S04 contract and ADR-0004 on 2026-11-24 for Development MVP; WP01/WP02 verified and merged via PR #10, merge `151af7e`, main CI `45377051431` PASS; WP03 delivered via PR #12, merge f4b1625, main CI 45402438307 PASS; WP04 DELIVERED; AC09 and AC10 accepted for Development MVP; PR #14 MERGED and post-merge main CI 45417693955 PASS; S04 CLOSED. All S02/S03 security gates continue; production NOT APPROVED. Single canonical worktree and backup stash preserved. The sections after the following divider are **historical snapshots** (including earlier 'current' headings and pending actions) and do not supersede this active roadmap or [CURRENT_STATE](../handoff/CURRENT_STATE.md).

### S04 final closeout checkpoint

- Date: 2026-11-24.
- Sprint S04: CLOSED — Development MVP only.
- WP01–WP04: DELIVERED.
- AC01–AC10: accepted within Development MVP scope.
- Closeout PR #14: MERGED.
- PR CI run 45417304467: 4/4 PASS.
- Post-merge main CI run 45417693955: 4/4 PASS.
- S05: NEXT; not started or approved by this checkpoint.
- Production authorization: NOT APPROVED.

---

# AgentOps AI — Sprint Index

## Current roadmap — 2026-11-24, S03-WP03

Start with [CURRENT_STATE.md](../handoff/CURRENT_STATE.md), then inspect actual Git.
S02 is CLOSED, 11/11 accepted by the owner; PR #7 merge/final main CI are
owner-reported. Remote main was fetched once and matches
`7e20e73c32db8287447445d5d48e9331d211ff7c`.

| Sprint | Current status | Report |
|---|---|---|
| S02 — Database & Authentication | CLOSED — Development MVP only | [S02](S02.md) |
| S03 — Research Task API and Dashboard | IN_PROGRESS; WP01–WP03 VERIFIED_LOCALLY; AC01–AC10 verified, AC11–AC12 pending | [S03](S03.md) |
| S04–S09 | PLANNED; existing roadmap goals retained | Reports not yet created |

Exactly one next work package: **S03-WP04 — Integration, CI & Closeout**.
Branch: `feat/s03-research-persistence`; see the handoff for its worktree and
observed Git checkpoint. No push, merge, deployment or S03 closeout is implied.
ADR-0002 remains ACCEPTED — DEVELOPMENT MVP ONLY; authentication stays disabled
by default. Stock PKCE logging remains security FAIL. All release gates remain.

Everything below is historical checkpoint evidence, including older tables and
next actions. It does not override this current roadmap or CURRENT_STATE.

## 2026-11-24 — Final owner acceptance and S02 closeout

### Current sprint roadmap

| Sprint | Current disposition |
|---|---|
| S02 — Database & Authentication | CLOSED upon final documentation incorporation; 11/11 |
| S03 | NEXT — planning pending |

| S02 Stage | Status |
|---|---|
| Dependency and security remediation | COMPLETE |
| Architecture and authentication approval | COMPLETE |
| Git delivery and CI | COMPLETE |
| Final sprint closeout | Owner-approved; effective upon incorporation |

All previous S02 progress percentages and pending
approval notes below are historical.

Earlier sprint closure issues are not silently changed
by this S02-specific closeout.

### Official sprint disposition

- Sprint: S02 — Database & Authentication.
- Final acceptance: 11/11 VERIFIED (100%).
- Scope: Development MVP only.
- Owner final sign-off: APPROVED.
- Stage 1: COMPLETE.
- Stage 2: COMPLETE.
- Stage 3: COMPLETE.
- Stage 4: owner-approved; effective upon successful
  incorporation of this documentation closeout.
- Final sprint status after incorporation: CLOSED.
- Production deployment: NOT APPROVED.
- Real-user activation: NOT APPROVED.

### Owner authorization

On 2026-11-24, the project owner explicitly approved:

- Final acceptance of all eleven S02 success criteria
  within the Development MVP scope.
- Closure of Sprint S02.
- Retention of all mandatory real-user release gates.
- Final documentation commit, push, pull request and
  integration subject to successful CI.

Production authorization was explicitly withheld.

### Accepted architecture

- ADR-0001: ACCEPTED.
- ADR-0002: ACCEPTED — DEVELOPMENT MVP ONLY.
- Authlib 1.9.10: CONDITIONALLY APPROVED.
- Authentication: implemented within the review scope,
  disabled by default.

### Final local verification evidence

| Verification | Result |
|---|---|
| Backend regression | 100 passed, 8 skipped on each of four targets |
| Offline Authlib PoC | 56 passed, 1 strict xfailed on each of two targets |
| PostgreSQL integration | 7 passed |
| PostgreSQL migration lifecycle | Upgrade/downgrade/upgrade passed |
| Docker runtime | AMD64 and ARM64 passed |
| Application dependency lockfiles | 9/9 verified |
| Generator replay and smoke compilation | 4/4 targets passed |
| Application dependency advisory audit | 9/9 profiles passed |

The eight backend skips include seven explicitly gated
PostgreSQL cases, which passed separately, and one legacy
shared-stack case that was intentionally not executed.

The stock Authlib PKCE DEBUG logging exposure remains a
known security FAIL, preserved as strict XFAIL.

The application-specific logging mitigation remains
bounded to its verified scope.

### Git integration evidence

| Pull request | Disposition | Merge commit |
|---|---|---|
| PR #4 | MERGED | fa03f27 |
| PR #6 | MERGED | 44fee92 |
| PR #5 | MERGED | 77cc5f5 |
| PR #3 | MERGED | 76ae5cc |

The CI workflow conflict was resolved in commit 8245d31.

The resolved source tree was verified identical to the
previously tested identity source tree.

The original identity PR package-discovery failure was
resolved by incorporating the existing closeout fix.
No historical failure is erased from the audit trail.

Verified S02 implementation baseline on main:

76ae5ccccf3d913fba813e8232d8d7e8cb8c9423

### Remote CI evidence

| Workflow run | Event/scope | Result |
|---|---|---|
| 45310607000 | Historical identity PR | FAIL; superseded by corrected integration |
| 45310595391 | Closeout push | PASS |
| 45310612883 | Closeout PR | PASS |
| 45310877756 | Identity push after PR #6 | PASS |
| 45311489190 | Identity integration push | PASS |
| 45311491764 | Identity integration PR | PASS |
| 45311610079 | Foundation push | PASS |
| 45311616131 | Foundation PR | PASS |
| 45311767623 | Integrated main push | PASS |

The final implementation baseline on main passed:

- Backend Tests.
- PostgreSQL Lifecycle and Auth.
- Offline Authlib Compatibility.

CI evidence:

https://github.com/NamNguyen0903/agentops-ai/actions/runs/45311767623

The final documentation-only PR must also pass CI
and be incorporated into main before closure is effective.

Its integration SHA and workflow evidence are recorded
by GitHub and the final execution report.

No new application code or local regression execution
is included in this documentation-only checkpoint.

### Next sprint

S03 is the next sprint to plan after this closeout
is incorporated and its final main CI passes.

Start from docs/handoff/CURRENT_STATE.md.

Read AGENTS.md, PRD v0.2, architecture v1.1, the sprint
index and the actual S03 specification before making
changes.

Do not invent S03 scope or silently carry forward
release gates as completed work.

No S03 implementation was started during S02 closure.

---

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

### Current execution roadmap

| Stage | Status |
|---|---|
| Stage 1 — Dependency and security | COMPLETE LOCALLY |
| Stage 2 — Architecture approval | COMPLETE |
| Stage 3 — Git delivery and CI | NEXT |
| Stage 4 — Final closeout | PENDING |

S03 remains blocked on final S02 closeout.

CURRENT_STATE.md remains the authoritative resume source.

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

### Current S02 roadmap

1. Dependency and security remediation: complete locally.
2. Architecture and authentication approval: next.
3. Git delivery and CI: pending.
4. Final sprint closeout: pending.

The official resume source remains
`docs/handoff/CURRENT_STATE.md`.

The next action is Stage 2: obtain explicit owner decisions
on ADR-0002, conditional Authlib adoption, operator provisioning,
development acceptance boundaries and remaining release gates.

Do not regenerate dependency lockfiles or repeat completed
regression suites without changed inputs or a new blocker.
Do not start S03 or mark S02 complete.

---

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


### S03-WP04 local integration checkpoint

- WP01–WP03: VERIFIED_LOCALLY and committed.
- WP04 local runtime/browser integration: VERIFIED.
- AC01–AC10 verified; AC11 remote CI pending; AC12 pending.
- Sprint S03 remains IN_PROGRESS, 10/12 formal acceptance.
- Next: scoped WP04 local delivery commit and owner-authorized remote CI.
- Production approval: NOT APPROVED.


### S03 remote CI and closeout checkpoint — 2026-11-24

- S03: IN_PROGRESS; CLOSEOUT_PREPARED.
- WP01–WP04 implementation and integration: VERIFIED.
- AC01–AC11: VERIFIED.
- AC12: OWNER_APPROVED; FINAL_DELIVERY_PENDING.
- Formal acceptance: 11/12 (91.7%).
- PR #8.
- Verified source: f414786.
- Remote push CI: 45345545692, PASS.
- Remote PR CI: 45345553676, PASS.
- Main CI: PENDING.
- Production approval: NOT APPROVED.
- Next: final closeout commit, PR CI and merge verification.
- S04 remains pending S03 closure.

See [S03_CLOSEOUT.md](S03_CLOSEOUT.md).

## Owner sign-off — 2026-11-24

- Decision: APPROVED.
- Approver: Project Owner.
- Scope: Development MVP only.
- Owner statement:

  "Tôi đồng ý nghiệm thu Sprint S03 trong phạm vi
  Development MVP, giữ nguyên các release gates
  và cho phép hoàn tất closeout."

- Implementation and verification: ACCEPTED.
- Existing release gates: PRESERVED.
- Production approval: NOT APPROVED.
- Closeout execution: AUTHORIZED.
- Final closeout commit CI: PENDING.
- Pull request merge: PENDING.
- Main CI verification: PENDING.
- Sprint closure: PENDING final delivery verification.


## Latest authoritative roadmap checkpoint — 2026-11-24

- S02: CLOSED, 11/11 VERIFIED.
- S03: CLOSED, 12/12 VERIFIED.
- S03 owner sign-off: APPROVED.
- S03 delivery PR: #8, MERGED.
- S03 main delivery commit: f533857b.
- S03 main CI: 45346656444, PASS.
- S04: NEXT — Single-agent LangGraph.
- S04 implementation: NOT_STARTED.
- Production approval: NOT APPROVED.
- All previous release gates remain mandatory.

Final S03 documentation synchronization is required
before S04 implementation.

References:
- [S03 sprint](S03.md)
- [S03 closeout](S03_CLOSEOUT.md)


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

## S06 WP05-F acceptance reconciliation

Reviewed at: 2026-11-25T12:30:47.011733+00:00.

Status: REVIEWED_LOCAL - OWNER DECISION REQUIRED.
Scope: Development MVP only.

Authority: owner-approved S06 Contract v1.0 and
provider selection amendment. The original acceptance
and security requirements remain unchanged.

Evidence baseline: WP05-D-R02.
Evidence SHA256: 59b1ff6708678ceb1875731a938bc1cbf07f1a593f9d907963bcb74d44803400.

### Technical acceptance assessment

- VERIFIED: 18/24.
- PARTIAL: 4/24.
- PENDING_CI: 1/24.
- PENDING_OWNER: 1/24.
- Technical readiness: 75 percent.
- Official owner acceptance: 0/24.

### Security assessment

- VERIFIED: 13/16.
- PARTIAL: 3/16.
- Partial security gates: SG06, SG08 and SG10.

VERIFIED is a scoped technical assessment, not
an owner signoff or certification of production
security.

All prior S02-S05 security gates remain mandatory.

WP01: DELIVERED.
WP02: VERIFIED_LOCAL_PARTIAL.
WP03: VERIFIED_LOCAL within synthetic evidence scope.
WP04: VERIFIED_LOCAL_OFFLINE.
WP05-A/B/C/D/E: VERIFIED_LOCAL.
WP05-F: REVIEWED_LOCAL; OWNER DECISION PENDING.
WP05-G/H: PENDING.

### Prior integrated verification

- Backend: 2112 passed, 75 skipped, zero failed.
- Disposable PostgreSQL: 74 passed.
- S06 PostgreSQL integration: 26/26 passed.
- Offline Authlib: 56 passed, one security XFAIL.
- Frontend: 39 passed, typecheck/lint/build PASS.
- Backend pip 26.2; other distributions unchanged.
- Backend audit: 64 packages, zero findings.
- Frontend audit: zero findings.
- Application dependency manifests unchanged.
- External authorization barrier unchanged.
- No test suites repeated in WP05-F.

The preceding figures are retained observed evidence,
not newly executed tests.

No criteria or security gates are waived.

### Feature delivery requirements

The proposed feature branch remains:

feat/s06-search-evidence-citations

Base main: 322dc2878fac60bb1ac871c8b9b4d184812b78d8.

Following an authorized owner scope decision,
prepare a PR against main with the reviewed file scope
and accurately disclosed partial acceptance status.

Required CI job evidence:

- Backend Tests.
- PostgreSQL Lifecycle and Auth.
- Frontend Tests and Build.
- Offline Authlib Compatibility.

Require all four job results on the feature PR and
on the merged main commit. Verify the exact commit
SHA associated with each run.

If repository branch protection is absent or required
checks are not configured, disclose that limitation.
Do not treat missing governance as a passed check.

Merging a partial feature milestone does not
automatically close S06 or authorize S07.

Production remains NOT APPROVED.

Full acceptance and security matrices: [S06 Contract and WP05-F review](S06.md).

### Owner decision required before feature delivery

Recommended decision A: approve delivery of the
current default-disabled offline implementation
as a partial S06 milestone.

This does not close Sprint S06, waive any criterion,
authorize live execution, or establish production
readiness. AC05, AC07, AC09 and AC21 remain PARTIAL.
SG06, SG08 and SG10 remain PARTIAL.

Alternative decision B: retain the current scope and
require the missing proof and implementation before
feature delivery. Any live smoke test requires separate
explicit authorization, credential handling and cost review.

Alternative decision C: approve a formal contract
amendment that defines the offline deliverable,
relocates remaining external-execution obligations
to an explicitly authorized future milestone, and
preserves all security gates as prerequisites for
external activation.

Decision C requires a separate recorded amendment,
named deferred requirements and a revised acceptance
baseline. This checkpoint does not apply that amendment.

Until an explicit owner decision is recorded:

- Do not stage, commit, push or merge.
- Do not mark S06 CLOSED.
- Do not start S07.
- Do not count PARTIAL items as VERIFIED.
- Keep external execution unconditionally denied.
