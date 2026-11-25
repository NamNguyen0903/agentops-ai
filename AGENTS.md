# AgentOps AI — Active S07 Engineering Policy Amendment

Recorded at: 2026-11-25T15:19:46.940631+00:00.

**S07 Contract v1.0 — OWNER APPROVED.**

Authoritative contract: `docs/sprints/S07.md`.

Immediate authorized package: WP01 documentation only.

> APPROVE S07 CONTRACT v1.0 — Development MVP only. Approve WP01–WP06, AC01–AC36, S07-SG01–S07-SG20, AD07-01–AD07-12 and proposed worker defaults. Preserve all existing security and release restrictions. Dependency manifest changes require separate approval. Authorize WP01 documentation execution only as the immediate next package. Continue FAST-TRACK. Production remains NOT APPROVED.

## Reconciled S06 closure

- S00–S06: CLOSED.
- S06 Contract v1.1, S06-AMEND-001.
- Scope: Offline Development MVP only.
- Official S06 acceptance: 24/24.
- Cumulative delivery CI: 16/16 PASS.
- Implementation PR: #22.
- Final closeout PR: #23.
- Final main CI: 45619735364.
- Last reconciled main: `1414c65df805d9980a84472d6b2ae54d25034f52`.
- Backup stash: `13ab03b82e68364c8f4f022821e12dca5ec7b731`.
- Single canonical workspace: `/Users/namnguyen/agentops-ai`.

S06 binding closure conditions were satisfied according to
the final closure evidence reconciled during S07 startup.
Historical CLOSEOUT_PENDING text remains preserved and does
not reopen S06.

Final closure evidence SHA256:

`d1fea7db66eeaa9a304fda8711cf97b1f4d7e0a5b7c94d48e8173f6b15962c02`

Original S06 v1.0 acceptance ledger remains historical.
Original S06 security ledger remains 13 VERIFIED, 3 PARTIAL.
SG06, SG08 and SG10 remain PARTIAL at S07 startup.
No security gates are waived.


## Effective architecture authority

- ADR-0001: ACCEPTED; preserve modular monolith.
- ADR-0002: ACCEPTED — Development MVP only.
- ADR-0003: ACCEPTED for scoped S07 durable execution development.
- ADR-0004: Existing ACCEPTED scope preserved.
  Application-owned context integration must respect its
  approved graph and agent boundaries.
- ADR-0005: NOT APPROVED.
- ADR-0006: PARTIALLY ACCEPTED, expanded by scoped S07 decisions.
- ADR-0007: PARTIALLY ACCEPTED, expanded by scoped S07 decisions.

Unrelated open decisions are not approved.
Architecture approval is not worker activation authorization.


## Mandatory security and release boundaries

- Production remains NOT APPROVED.
- External execution remains unconditionally denied.
- Authentication remains disabled by default.
- Preserve the strict Authlib security XFAIL.
- No actual provider credentials or live provider API calls.
- No paid inference, paid search or PAYG.
- No shared database migrations.
- No worker activation outside isolated, authorized test scope.
- No real-user authentication, report publication or deployment.
- No security gate waiver.
- Preserve all S02–S06 security and release requirements.
- Dependency manifest and lockfile changes require separate approval.
- Preserve NO_REQUIRED_CHECKS_REPORTED governance limitation.
- CI success does not establish enforced branch protection.
- Retain the governance review obligation for S09.
- Preserve one canonical worktree and the unrelated backup stash.
- No history rewriting, force push, destructive cleanup or bypass.
- Owner controls commits, pushes, merges, deployment and material
  architecture decisions.
- No autonomous repository modifications by the assistant.
- Do not repeat completed local tests without changed source,
  environment or verification scope.
- Mandatory feature/PR and merged-main CI are not waived.

Approval of S07 architecture establishes permitted development
scope, not implemented behavior or production readiness.


## Mandatory successor obligations

| ID | Obligation | Sprint | Status |
| --- | --- | --- | --- |
| D06-01 | Provider interoperability | S08 | OPEN |
| D06-02 | Secure connector verification | S07 | OPEN |
| D06-03 | External execution budgets and deadlines | S07 | OPEN |
| D06-04 | Actual provider usage and cost accounting | S08 | OPEN |
| D06-05 | Real evidence integration | S08 | OPEN |
| D06-06 | Integrated external security acceptance | S08 | OPEN |

### D06-02 acceptance requirements

- Exercise actual DNS, numeric connection, peer verification,
  TLS and HTTP execution path.
- Verify adversarial DNS answers and destination binding.
- Verify certificate trust, hostname mismatch, redirects and cleanup.
- Do not replace the entire connector in correctness tests.
- Preserve unconditional default-deny external authorization.

### D06-03 acceptance requirements

- Integrate acquisition budgets with application-owned execution context.
- Preserve cumulative search, retrieval and retry accounting.
- Enforce operation and running-task deadlines.
- Verify cancellation, timeout and recovery semantics.
- Prevent retry or recovery from resetting applicable budgets.
- Fail closed on incomplete or indeterminate execution.
- Reconcile hard cancellation with verified adapter capabilities.

### Dependency preservation

- D06-01 depends on D06-02 and D06-03.
- D06-04 depends on D06-01 and D06-03.
- D06-05 depends on D06-01 through D06-04.
- D06-06 depends on D06-01 through D06-05.

All six obligations remain OPEN until their actual acceptance
requirements are verified.

Do not silently defer D06-02 or D06-03.
S08 controlled live smoke tests require separate authorization.
S08 integrated external security acceptance remains mandatory.


## Exactly one next action

Review the locally prepared WP01 documentation changes
and their evidence before staging or committing.

WP01 delivery requires Owner-controlled commit, push,
PR review, mandatory CI, merge and merged-main CI.

WP02 must not begin before WP01 delivery is verified.

No runtime implementation or activation is authorized
by the immediate WP01 execution package.


All sections below are retained historical policy. This active S07 amendment supersedes conflicting historical sprint status and scoped authorization statements. Nonconflicting requirements remain mandatory.

---

# AgentOps AI — Active S06 Engineering Policy Amendment

## Authoritative S06 WP05-H closeout

Recorded at: 2026-11-25T12:57:49.675347+00:00.

Contract: v1.1 — S06-AMEND-001.

Status: OWNER_ACCEPTED_CONDITIONAL — CLOSEOUT_PENDING.

Scope: Offline Development MVP only.

This section supersedes conflicting historical S06 status descriptions without rewriting them.

### Acceptance governance

Historical Contract v1.0 remains preserved:

- VERIFIED: 18/24.
- PARTIAL: AC05, AC07, AC09 and AC21.
- PENDING_CI: AC23 at the historical review checkpoint.
- PENDING_OWNER: AC24 at that checkpoint.

This historical ledger is not rewritten to reflect
the amended scope or subsequent delivery.

Effective Contract v1.1 before final closeout delivery:

- VERIFIED: 23/24.
- Owner accepted: AC01-AC23.
- AC24: OWNER_APPROVED_PENDING_CLOSEOUT_CI.
- Final target after verified closure: 24/24.

Security ledger:

- VERIFIED within recorded scope: 13/16.
- PARTIAL: SG06, SG08 and SG10.
- Waived: zero.

The final offline acceptance does not convert
external security obligations into VERIFIED gates.

### Implementation delivery identity

- Contract: v1.1.
- Amendment: S06-AMEND-001.
- Contract PR: #21, delivered.
- Implementation PR: #22, merged.
- Feature commit: 102d273dca8cebaa6e846fa64318212bc4051323
- Previous main: 322dc2878fac60bb1ac871c8b9b4d184812b78d8
- Implementation merged main: 540666dbb9c40df0b500bcd6b143460128e5e3cc
- Verified implementation tree: 750be5b82a36c138b44c08c26d2b7b0dcb775b10
- Feature CI: 45616532423
- Implementation main CI: 45617420446
- Implementation delivery files: 56.
- Merged implementation tree: identical to feature tree.
- Combined implementation CI: 8/8 PASS.
- WP05-G4 evidence SHA256: a6c5a4373ccb08821d97ca093a0c02bb196b59bef1d0270a907805fd32836f5a
- Amendment evidence SHA256: 9d248326493bfffad7bf85dbce7b2681c0f55b98a26a5da0cafd8ac74b325085
- Final Owner approval SHA256: 6dfc2fa4eca0c387af2284038722e691bf73cf54bdbff19aaf3e4b06c405076a

### Work package completion

- WP01: contract and architecture delivered.
- WP02: offline acquisition foundation delivered.
- WP03: synthetic evidence persistence delivered.
- WP04: offline workflow and citations delivered.
- WP05-A/B/C/D/E: integrated verification completed.
- WP05-F: original acceptance review completed.
- WP05-F-R01: approved amendment reconciled.
- WP05-G1/G2/G3: feature delivery and CI completed.
- WP05-G4: implementation merge and main CI completed.
- WP05-H: final Owner approval recorded;
  documentation delivery and final CI pending.

### Binding closure condition

This documentation records final Owner acceptance of
the revised offline S06 deliverable, conditional on
successful closeout delivery.

AC01-AC23 are verified and Owner accepted.

AC24 remains OWNER_APPROVED_PENDING_CLOSEOUT_CI
until ALL of the following conditions are satisfied:

1. The documentation-only closeout PR for branch
   docs/s06-final-closeout passes all four mandatory
   Backend CI jobs on its reviewed head commit.
2. The Project Owner separately authorizes its merge.
3. The closeout PR is merged into main without
   bypassing applicable repository checks.
4. The merge contains only the approved documentation
   scope and preserves the implementation baseline.
5. All four Backend CI jobs pass on the exact merged
   main commit.
6. Local main is synchronized, the working tree is
   clean, and the backup stash and canonical worktree
   remain preserved.
7. Final closure evidence is exported and reconciled.

When these conditions are verified, the effective
acceptance result becomes 24/24 VERIFIED and Owner
accepted under Contract v1.1.

The effective sprint state then becomes:

CLOSED — OFFLINE EVIDENCE AND CITATION FOUNDATION
— DEVELOPMENT MVP ONLY.

Until that point S06 remains CLOSEOUT_PENDING
and S07 remains NOT_STARTED.

The condition is intentionally based on observed
GitHub delivery evidence rather than a prewritten
future commit SHA.

No additional commit or PR is needed solely to
replace this conditional status or record the
closeout commit's own SHA.

### Mandatory S07/S08 successor obligations

| ID | Mandatory obligation | Receiving sprint | Status | Original traceability |
| --- | --- | --- | --- | --- |
| D06-01 | Provider interoperability | S08 | OPEN | AC05 |
| D06-02 | Secure connector verification | S07 | OPEN | AC07, SG06, SG08 |
| D06-03 | External execution budgets and deadlines | S07 | OPEN | AC09, SG10 |
| D06-04 | Actual provider usage and cost accounting | S08 | OPEN | AC05, AC09, SG10 |
| D06-05 | Real evidence integration | S08 | OPEN | AC05 and real-data obligations of AC11-AC20 |
| D06-06 | Integrated external security acceptance | S08 | OPEN | AC21, SG01-SG16 |

All six obligations remain OPEN.

S07 — Worker Reliability and Secure Acquisition
must receive D06-02 and D06-03.

S08 — Live Research Integration, Evaluation and
Security must receive D06-01, D06-04, D06-05
and D06-06.

The original detailed acceptance requirements
and dependency graph remain authoritative in
S06-AMEND-001 in docs/sprints/S06.md.

No receiving sprint may silently discard or
further defer these obligations.

S08 controlled live smoke testing requires
separate explicit approval after applicable
S07 prerequisites have been verified.

Routine external activation requires complete
applicable security acceptance and separate approval.

S09 staging and release readiness remain dependent
on applicable S07 and S08 verification.

### Retained release restrictions

Production remains NOT APPROVED.

External execution remains unconditionally denied.

No actual provider credentials, live provider API,
paid search, paid inference, PAYG, shared database
migration, worker activation, real-user authentication,
report publication or deployment is authorized.

Real evidence coverage remains zero.
S06 workflow and evidence persistence are synthetic-only.
Report candidates remain nonpublishable.

Structural citation validation does not establish
semantic grounding.

Normalized excerpt integrity does not establish
full fetched-page integrity.

Isolated execution identifiers do not establish
durable worker fencing.

Repository scope checks are not database RLS.

Hard cancellation and complete external execution
accounting remain unverified.

HTTPX production runtime dependency availability
requires successor review.

The existing Authlib strict security XFAIL remains.
No production authentication approval is implied.

All S02-S06 security gates remain mandatory.
No original security gate or product requirement
is waived by this closeout.

### Release governance limitations

GitHub reported NO_REQUIRED_CHECKS_REPORTED for
implementation PR #22.

The four mandatory project CI jobs were independently
checked against the approved feature and main SHAs.

This is evidence of observed CI success, not proof
that repository branch protection enforces all
required checks.

Retain this governance limitation in S09 release
readiness review. Verify required status checks,
merge restrictions and applicable branch rules
before production release authorization.

No repository protection setting is changed here.

Retain the previously observed Node.js action runtime
deprecation concern for applicable CI maintenance.

Local vulnerability audits are point-in-time checks,
not complete deployment or infrastructure attestations.

### Exactly one next action

Complete the S06 documentation-only closeout PR
and obtain separate Owner merge approval.

Once the binding closure condition is satisfied,
resume from the prepared S07 handoff.

The current authorization does not extend to
S07 implementation or external runtime activation.

---


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

### Active execution policy

Use the approved v1.1 scope for S06 delivery.

Retain FAST-TRACK execution, single canonical
workspace and existing owner approval boundaries.

Do not reinterpret the original v1.0 PARTIAL
criteria as completed external functionality.

Do not start S07 until S06 v1.1 has been closed
and the S07 contract has been approved.

The S07 contract must include D06-02 and D06-03.
The S08 contract must include D06-01, D06-04,
D06-05 and D06-06.

Do not reopen an independent S06 WP02 package
solely to duplicate completed verification.

Do not repeat local test suites unless affected
source, environment or verification scope changes.

Required feature and merged-main CI are not waived.

Exactly one next action after WP05-F-R01:
owner-controlled WP05-G delivery review.


**Decision date:** 2026-11-25

**Contract:** S06 Contract v1.0 — OWNER APPROVED

**Scope:** Development MVP only

**Production authorization:** NOT APPROVED

## Active authority

This owner-approved S06 amendment supersedes conflicting
S05 execution-mode restrictions, historical sprint
status statements and obsolete ADR status descriptions.

All prior security, testing, evidence, Git and release
requirements remain mandatory.

The authoritative S06 contract is:

`docs/sprints/S06.md`

## S06 execution mode

FAST-TRACK, owner-operated local execution.

ChatGPT performs Tech Lead, architecture, development,
AI engineering, security, QA, DevOps, project planning,
implementation generation and evidence review.

The Project Owner performs local command execution,
file application, tests, commits, pushes, PR creation
and merges, and retains architecture and release control.

Group related tickets into large work packages.
Use complete Terminal blocks where practical.
Only one active authorized work package at a time.

Do not request routine implementation approvals.
Separate authorization is required for new architecture,
scope, live providers and release boundary changes.

No autonomous repository edits or Git actions by an
assistant are authorized under this manual workflow.

## Active ADR baseline

| ADR | Status |
|---|---|
| ADR-0001 | ACCEPTED |
| ADR-0002 | ACCEPTED — Development MVP only |
| ADR-0003 | PARTIALLY ACCEPTED — admission only |
| ADR-0004 | ACCEPTED — including scoped S06 amendment |
| ADR-0005 | NOT APPROVED |
| ADR-0006 | PARTIALLY ACCEPTED — offline interfaces and retrieval policy |
| ADR-0007 | PARTIALLY ACCEPTED — scoped evidence security |

ADR-0003 does not authorize durable claiming, attempts,
leases, fencing or recovery.

ADR-0006 does not authorize a search vendor, external
network execution or live model inference.

ADR-0007 authorizes evidence persistence implementation
and migration verification on disposable PostgreSQL only.

## Security and operational controls

- Preserve one canonical worktree.
- Preserve the unrelated backup stash.
- Preserve approved dependency lockfiles.
- Authentication disabled by default.
- Preserve strict Authlib security XFAIL.
- Preserve S02–S05 security and release gates.
- Enforce S06 SG01–SG16.
- No destructive Git cleanup or force pushes.
- No unauthorized shared database mutations.
- No worker activation or task lifecycle changes.
- No report publication or deployment.
- Do not invent execution evidence.

The owner approved S06 WP01–WP05, AC01–AC24,
SG01–SG16 and scoped AD01–AD08.

WP01 is the immediate authorized package.
Later packages must respect dependencies, verified
acceptance evidence and unresolved approval gates.

S05 remains CLOSED. S06 does not reopen S05.

All sections below are retained historical policy.
Their nonconflicting requirements remain mandatory.

---

# AgentOps AI — Active Engineering Policy Amendment

**Amendment:** S05 final owner acceptance and closure

**Decision date:** 2026-11-25

**Owner approval:** S05 Contract v1.0

**Scope:** Development MVP only

**Production authorization:** NOT APPROVED

## 1. Active policy authority

This owner-approved amendment updates the execution
mode and architecture baseline for Sprint S05.

It supersedes conflicting execution-mode permissions
and obsolete ADR status descriptions in the retained
engineering working agreement below.

All other engineering, security, testing, Git,
documentation and release requirements remain mandatory.

The original agreement is retained for historical
traceability and continues to apply wherever it does
not conflict with this amendment.

## 2. Current architecture baseline

| Decision | Active status |
|---|---|
| ADR-0001 | ACCEPTED |
| ADR-0002 | ACCEPTED — Development MVP only |
| ADR-0003 | PARTIALLY ACCEPTED — admission only |
| ADR-0004 | ACCEPTED — Development MVP only, including S05 amendment |
| ADR-0005 | NOT APPROVED |
| ADR-0006 | NOT APPROVED |
| ADR-0007 | NOT APPROVED |

Authoritative S05 contract:

`docs/sprints/S05.md`

The S05 architecture amendment is recorded in:

`docs/adr/0004-langgraph-state-and-agent-boundaries.md`

ADR-0003 does not authorize worker claiming,
execution attempts, leases, fencing or recovery.

ADR-0004 does not authorize live providers,
real retrieval, report publication or production.

## 3. S05 manual execution policy

The Project Owner retains direct operational control
of the canonical repository.

ChatGPT performs the following responsibilities:

- Senior Tech Lead and Software Architect.
- Work package and ticket specification.
- Implementation content generation.
- Test and verification command generation.
- Source, documentation and evidence review.
- QA assessment and scoped failure analysis.
- Checkpoint and documentation update instructions.

The Project Owner performs:

- Local repository file changes.
- Terminal and Git command execution.
- Local test execution.
- Explicit staging and commits.
- Pushes and pull request creation.
- Pull request merges.
- Scope and architecture approvals.
- Sprint acceptance and release decisions.

Codex may assist with producing reviewable code or
technical suggestions when explicitly requested.

Direct autonomous Codex edits, command execution
and commits are not authorized under the active
S05 manual execution policy.

This amendment does not establish a permanent
execution mode for future sprints. A future change
requires an explicit owner decision.

No AI assistant may independently claim that a
local command, test, commit, push or merge succeeded
without supporting evidence.

## 4. Sequential execution and Git controls

- Use exactly one canonical local worktree.
- Canonical path: /Users/namnguyen/agentops-ai.
- Preserve existing unrelated changes and stashes.
- Work on one authorized work package at a time.
- Issue one immediate ticket action at a time.
- Review submitted evidence before proceeding.
- Declare exact target file scope before changes.
- Stage reviewed paths explicitly.
- Do not use destructive cleanup or force pushes.
- The owner controls all commits and remote delivery.
- Record observed SHAs and actual CI evidence.
- Never invent future commit IDs or test outcomes.

The existing backup stash must be preserved.

## 5. Current S05 authorization boundary

Sprint S05 is CLOSED for Development MVP only.

On 2026-11-25, the Project Owner explicitly
accepted AC01-AC16 and WP01-WP05.

PR #18 and final documentation PR #19 are merged.
Their recorded required CI gates have passed.

The final status synchronization is documentation-only.

S05 Contract v1.0, AD01-AD08, ND01-ND12 and
SG01-SG12 remain unchanged.

No additional runtime implementation is authorized.

No live model providers, real search providers,
database migrations, worker activation, report
publication or production deployment are authorized.

Authentication remains disabled by default.

Preserve the strict Authlib security XFAIL,
all existing dependency lockfiles and all
S02/S03 security and release gates.

Sprint S06 is NEXT but NOT STARTED.

A separate explicit owner authorization is required
before beginning S06 or expanding architecture scope.

Production remains NOT APPROVED.

## 6. Documentation and evidence policy

The active resume checkpoint is:

`docs/handoff/CURRENT_STATE.md`

The authoritative sprint roadmap is:

`docs/sprints/INDEX.md`

Historical sections do not supersede an explicitly
identified current checkpoint.

At ticket acceptance, record the actual evidence,
remaining limitations and the single next action.

Do not equate owner approval, generated source
or documentation review with verified runtime behavior.

---

## Retained engineering working agreement

The original agreement follows unchanged.

Its conflicting execution-mode provisions and obsolete
ADR status descriptions are superseded by the active
S05 amendment above. Its remaining requirements
continue to apply.

---

# AgentOps AI — Engineering Working Agreement

## Mandatory Single Local Worktree Policy

Effective from Sprint S03, by owner authorization.

This policy supersedes previous workspace instructions
that permit isolated worktrees or temporary repository clones.

- Canonical directory: `/Users/namnguyen/agentops-ai`.
- All development must use Local execution mode.
- Edit, test and commit directly in the canonical directory.
- Do not create additional Git worktrees or temporary clones
  without explicit owner approval.
- Use standard Git feature branches.
- Preserve unrelated local changes and existing Git stashes.
- Report a blocker if the canonical directory is unsafe.
- Continue autonomous execution by large work packages.
- Update sprint documentation and handoff proactively.
- Do not repeat completed verification without changed inputs.
- Preserve all S02 security controls and release gates.
- Preserve existing owner approval boundaries.
- Authentication remains disabled by default.
- Production approval and deployment remain prohibited.

**Version:** 1.2
**Status:** Owner-authorized local execution workflow from S03
**Project:** AgentOps AI
**Last updated:** 2026-11-24

## 1. Project Overview

AgentOps AI is a production-oriented market and competitor research platform.

Users submit research questions and receive structured, evidence-backed reports generated through a bounded LangGraph workflow.

### Technology Baseline

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- Frontend: React, TypeScript
- Database: PostgreSQL
- AI orchestration: LangGraph
- AI workflow: Planner, Research, Evidence Validator, Writer, Report Validator
- LLM integration: Amazon Bedrock through an application-owned adapter
- Local development: Docker Compose
- CI/CD: GitHub Actions
- Initial cloud target: AWS EC2, ECR, Bedrock, CloudWatch
- Architecture: Modular monolith with separate API and worker processes

Production-oriented is an engineering objective, not a claim of verified production readiness.

## 2. Authoritative Documents

Read documents in this order when decisions conflict:

| Document | Authority |
|---|---|
| `docs/product/PRD.md` | Product scope, requirements, acceptance criteria |
| Approved ADRs | Accepted architecture decisions |
| `docs/architecture/overview.md` | Proposed or approved system design |
| `AGENTS.md` | Engineering workflow and collaboration rules |
| `docs/handoff/CURRENT_STATE.md` | Current project checkpoint |
| `docs/sprints/INDEX.md` | Sprint status and roadmap |
| `docs/sprints/SXX.md` | Historical evidence for an individual sprint |

Current expected baselines:

- PRD: v0.2
- Architecture overview: v1.1
- ADR-0001: Accepted
- ADR-0002: Accepted — Development MVP only; mandatory release gates retained
- ADR-0003 through ADR-0007: Open decisions

An ADR marked Proposed is not an approved architecture decision.

Do not silently change product requirements to fit generated code.

## 3. Roles and Authority

### User — Developer and Repository Owner

Starting with S03, the owner authorizes Codex to inspect and edit the active work
package, run development commands and tests, repair scoped failures, update
documentation, create feature branches and make reviewed scoped local commits.
This supersedes the previous manual-copy-only execution policy. The owner retains:

- Authority over pushes, remote repositories, merges and release actions.
- Manages credentials and cloud resources.
- Approves changes to scope and architecture.
- Approves deployment and sprint closeout.

### ChatGPT — Tech Lead

ChatGPT:

- Reads available project context.
- Defines reviewable work packages and their acceptance boundaries.
- Defines acceptance criteria.
- Provides precise Terminal and Git commands.
- Creates technical instructions for Codex.
- Reviews submitted code, documents and test results.
- Identifies bugs, design risks and missing evidence.
- Determines the next action.
- Prepares handoff updates from verified or clearly attributed information.

ChatGPT must not claim that a command succeeded without supporting evidence.

### Codex — AI Coding Assistant

Codex:

- Implements authorized local work packages directly, including code and documents.
- Identifies the destination path for each artifact.
- Provides related tests and verification instructions.
- Runs scoped checks and repairs failures based on observed evidence.
- Explains design changes and dependencies.
- Prepares documentation and handoff updates.

Codex must not:

- Modify unrelated work or cross the active work package boundary.
- Push or merge without explicit owner authorization.
- Approve architecture, security release gates or sprint closure on behalf of the owner.
- Use destructive cleanup, history rewriting, force push, `git add .`,
  `git reset --hard` or `git clean`.
- Provision AWS resources.
- Deploy applications.
- Invent test results or Git state.

Use isolated disposable resources for destructive migration tests. Never migrate,
reset or delete shared development data as a test setup shortcut. Authentication
remains disabled by default; no live Google, real-user activation or deployment
is authorized by the local workflow. Stop affected work at material unapproved
architecture decisions or security-boundary changes; continue independent work.

## 4. Mandatory Session Startup

At the start of every new ChatGPT or Codex session:

1. Read this `AGENTS.md`.
2. Read `docs/handoff/CURRENT_STATE.md`.
3. Read `docs/sprints/INDEX.md`.
4. Read the latest active sprint report.
5. Read relevant PRD, architecture and ADR sections.
6. Inspect actual Git status, branch, HEAD, worktrees and relevant diffs.
7. Reconcile any differences between Git and the handoff.
8. Confirm the current work package and one immediate action.

### Git Checkpoint Reconciliation

Compare the available Git state against:

- Recorded branch.
- Last observed commit SHA.
- Working tree state.
- Evidence timestamp.
- Expected artifact versions.

If Git state differs from the recorded checkpoint:

- Do not automatically assume an error.
- Do not overwrite existing work.
- Inspect relevant changes or ask the user to provide a sanitized diff.
- Determine whether the handoff is older than the repository.
- Record the discrepancy before proceeding.

An unknown checkpoint is not proof that the working tree is clean.

### Missing Context

If essential information is unavailable:

- Identify the exact missing artifact or evidence.
- Do not invent its contents.
- Continue only work that does not depend on it.
- Prefer one focused request over asking the user to repeat the entire project history.

## 5. Ticket Execution Workflow

Work on exactly one authorized work package at a time. Tickets may be grouped
inside that package; do not stop for routine implementation choices.

Each ticket must specify:

- Ticket ID.
- Objective.
- Dependencies.
- In-scope work.
- Out-of-scope work.
- Exact target file paths.
- Acceptance criteria.
- Verification commands.
- Required evidence.
- Exactly one next ticket.

### Standard Workflow

1. ChatGPT/owner assigns a work package.
2. ChatGPT supplies a prompt or implementation specification.
3. Codex inspects actual sources and preserves unrelated changes.
4. Codex implements the authorized scope in the canonical local directory on a feature branch.
5. Codex runs applicable verification using the accepted dependency baseline.
6. Codex repairs scoped failures and reruns affected checks without weakening tests.
7. Codex reviews the diff, security boundaries and actual execution evidence.
8. Codex updates sprint and handoff records with results and unresolved limits.
9. If authorized package gates pass, Codex stages explicit reviewed paths and
   creates a local commit. A blocker must remain documented, not hidden by a commit.
10. The owner retains architecture decisions, remote delivery and sprint sign-off.

Do not expand a small ticket into unrelated features.

Do not proceed to another ticket while a blocking acceptance criterion remains unresolved unless the user explicitly approves deferral.

## 6. Standard Status Definitions

| Status | Definition |
|---|---|
| `PLANNED` | Defined but not started |
| `IN_PROGRESS` | Started; acceptance incomplete |
| `REPORTED_COMPLETE` | User reports completion; supporting verification is pending |
| `REVIEWED` | Specified artifact or evidence has received documented review |
| `VERIFIED` | Acceptance criteria are supported by supplied inspection or execution evidence |
| `BLOCKED` | A named dependency prevents progress |

### Verification Fields

Use separate fields where necessary:

- `Work status`
- `Review status`
- `Verification status`
- `Evidence source`

Examples:

- User completed a command but output was not supplied: `REPORTED_COMPLETE`, verification `PENDING_EVIDENCE`.
- ChatGPT reviewed an uploaded Markdown document: `REVIEWED`, local save `UNCONFIRMED`.
- User provided output proving a requested local check passed: `VERIFIED` for that specific criterion.

Do not use `VERIFIED` as a blanket claim of application correctness.

`REPORTED_COMPLETE` must not cause previous work to be repeated automatically.

## 7. One-Day Sprint Policy

One sprint represents one planned working day.

This is a planning cadence, not a guaranteed calendar deadline.

### Sprint Start

- Confirm the sprint objective.
- Review unresolved carried-over work.
- Select one ticket.
- Define acceptance and evidence requirements.

### Sprint Execution

- Complete tickets sequentially.
- Keep changes reviewable.
- Record important decisions.
- Preserve failed checks and unresolved issues.
- Do not silently reduce product requirements.

### Sprint Closeout

A sprint can close when:

1. Accepted work has documented outcomes.
2. Required reviews are complete.
3. Applicable checks have evidence.
4. Deferred tasks are explicitly recorded.
5. The current Git state is documented.
6. The sprint report is updated.
7. The handoff identifies one next action.
8. The user approves closeout.

Unfinished work may be carried forward without inventing success.

## 8. Manual-Copy Output Rules (When Explicitly Requested)

Direct local execution is the S03 default. These rules apply only to requests
that explicitly require proposals or manual application instead.

For every generated file:

1. State the exact destination path.
2. State whether it is a new file or full replacement.
3. Return complete copyable content.
4. Do not silently omit unchanged sections from a full replacement.
5. Place instructions outside the file content.
6. Provide applicable verification commands.
7. Wait for user confirmation before claiming a local save.

Use correctly nested Markdown fences when generating Markdown that contains code fences.

For small fixes, provide clearly identified replacement sections when safer than rewriting large files.

Do not require the user to copy unrelated files repeatedly.

## 9. Architecture Rules

- Preserve the modular monolith.
- Separate API requests from long-running research execution.
- Keep PostgreSQL authoritative for task lifecycle.
- Use durable asynchronous task claiming.
- Use explicit execution attempts and leases.
- Enforce idempotency at the database boundary.
- Keep external network calls outside database transactions.
- Use conditional writes to reject stale attempts.
- Publish reports transactionally.
- Do not reopen terminal tasks.
- Treat deletion as an access and publication barrier.
- Do not treat LangGraph checkpoints as a replacement for the task queue.
- Do not add microservices, Kubernetes or extra agents without justification.

Pending architecture decisions must be resolved before their dependent implementation choices are finalized.

## 10. Coding Standards

### Python and FastAPI

- Use explicit type annotations.
- Use Pydantic for request and response contracts.
- Separate routes, services, domain logic and persistence.
- Use dependency injection for providers and external dependencies.
- Keep functions small and focused.
- Handle failures explicitly.
- Do not expose stack traces in public API errors.
- Never execute long-running research inside a normal HTTP request.
- Use project-configured formatting, linting and type-checking tools.

### SQLAlchemy and Alembic

- Use explicit transactions.
- Enforce ownership and important constraints.
- Create migrations for schema changes.
- Test locking behavior with PostgreSQL.
- Review destructive migrations carefully.
- Document rollback compatibility.

### LangGraph and AI

- Use typed state.
- Use bounded graphs and explicit termination.
- Validate structured model output.
- Keep tool permissions outside model control.
- Enforce token, cost, retry and timeout budgets.
- Persist evidence with provenance.
- Reject fabricated citations.
- Distinguish structural citation checks from factual groundedness.
- Do not persist hidden chain-of-thought.
- Version prompts, graphs and model configurations.
- Use deterministic mock providers in ordinary tests.

### React and TypeScript

- Use typed API contracts.
- Handle loading, empty, error and terminal states.
- Use accessible form controls.
- Render reports safely.
- Never execute model-generated HTML or scripts.
- Do not fabricate progress percentages.
- Do not expose backend secrets in frontend configuration.
- Viewing a stored report must not regenerate it.

## 11. Security Requirements

### Authentication and Authorization

- Use a maintained authentication mechanism.
- Never trust a client-supplied owner ID.
- Verify resource ownership on the server.
- Test cross-user access.
- Protect session expiry and logout behavior.

### LLM and Tool Safety

- Treat all retrieved content as untrusted.
- Use approved provider adapters.
- Validate generated tool arguments.
- Prevent external content from changing policies or budgets.
- Do not allow autonomous consequential external actions.

### SSRF and Retrieval

- Restrict retrieval to permitted public HTTP(S) destinations.
- Reject prohibited private, loopback, link-local and metadata addresses.
- Validate resolved DNS addresses and redirects.
- Prevent DNS-rebinding bypasses.
- Bound retrieval duration, size and content type.

### Secrets and Privacy

- Never commit credentials, access tokens, passwords or private keys.
- Never put secrets in examples, prompts or logs.
- Redact sensitive command output before sharing.
- Use least-privilege cloud permissions.
- Do not assume compliance certification or production readiness.

## 12. Testing and Evidence Standards

Generate relevant tests alongside implementation.

Codex executes applicable tests for the authorized work package. User-reported
results retain attribution when their outputs have not been independently inspected.

Applicable checks may include:

- Formatting and linting.
- Type checks.
- Unit tests.
- PostgreSQL integration tests.
- Deterministic LangGraph tests.
- API and frontend contract tests.
- Security tests.
- AI evaluation.
- Docker startup tests.
- Deployment and recovery tests.

Ordinary deterministic tests must not require live provider credentials or paid inference.

### Evidence Record

For each relevant check, record:

- Ticket ID.
- Date and environment.
- Exact command, when available.
- Sanitized output.
- Exit code, when available.
- Artifact or version checked.
- Result.
- Remaining limitations.
- Evidence source.

Do not fabricate missing details.

A suggested command is not an executed command.

## 13. Git Workflow

Codex may inspect Git, create feature branches, and create scoped local commits
under the owner-authorized work package. Push, merge and remote changes require
explicit authorization; they are not implied by local commit permission.

### Initial Baseline

Sprint S00 may create the first reviewed baseline commit on `main`.

Before committing:

- Inspect `git status`.
- Review the proposed staging set.
- Check for secrets and unrelated files.
- Review staged changes.
- Run applicable checks.

### Subsequent Work

After the first baseline:

- Use feature branches.
- Keep commits small and scoped.
- Review diffs before committing.
- Prefer review before merging into `main`.
- Never force push.
- Never commit `.env`, credentials or generated secret files.
- Preserve unrelated local work.
- Do not claim a push succeeded without evidence.

### Commit SHA Recording

A commit cannot truthfully contain a record of its own final SHA.

Therefore:

1. Commit the reviewed code and documentation.
2. Observe the actual commit SHA.
3. Update handoff documentation to record that SHA.
4. Commit the handoff update separately if needed.
5. Record the latest observed checkpoint without inventing future SHAs.

`Last verified commit` means the last commit whose SHA and relevant evidence were observed, not necessarily the current HEAD.

## 14. Handoff Protocol

### Current State File

`docs/handoff/CURRENT_STATE.md` must remain concise.

It contains:

- Current sprint and ticket.
- Product and architecture baselines.
- Current ticket statuses.
- Last observed Git checkpoint.
- Critical blockers.
- Open decisions.
- Exactly one immediate next action.

Do not duplicate full sprint history.

### Sprint Report

`docs/sprints/SXX.md` contains:

- Historical ticket outcomes.
- Files changed.
- Commands and results.
- Review decisions.
- Failures and resolutions.
- Deferred work.
- Sprint acceptance.
- Git and release evidence.
- Signoff.

### Sprint Index

Update `docs/sprints/INDEX.md` when:

- A sprint starts or closes.
- Sprint status changes.
- A sprint report is created.
- Planned scope is formally revised.

### Update Frequency

- After material progress: prepare a short handoff update when needed.
- After ticket completion: record the outcome in the sprint report.
- At session end: ensure the resume point remains accurate.
- At sprint closeout: finalize the report, index and handoff.

Do not rewrite historical reports unnecessarily.

## 15. End-of-Session Report Template

### Session

- Date:
- Sprint:
- Ticket:
- Objective:
- Outcome:
- Status:

### Artifacts

| Path | Change | Saved by | Review / verification |
|---|---|---|---|
| Exact path | Description | Codex / User / Unknown | Result |

### Evidence

| Check | Command or source | Result | Limitation |
|---|---|---|---|
| Check name | Actual supplied evidence | Result | Unverified details |

### Decisions

- Decisions:
- Pending ADRs:
- Open questions:

### Git Checkpoint

- Branch:
- Last observed HEAD:
- Last verified commit:
- Working tree:
- Remote:
- Evidence timestamp:

### Continuity

- Current blocker:
- Exactly one next ticket:
- Immediate first action:
- Handoff saved: Confirmed / Unknown

## 16. Interrupted Session Recovery

When resuming:

1. Read the mandatory project documents.
2. Identify the last recorded checkpoint.
3. Compare it with current Git evidence.
4. Review differences before modifying code.
5. Confirm which changes were actually saved and inspect their diff.
6. Preserve unrelated work.
7. Resume the unfinished ticket.
8. Recheck only stale or missing acceptance evidence.

If the project state cannot be established safely, stop destructive operations and request the specific missing evidence.

Never assume a command succeeded because it was previously suggested.

## 17. Final Engineering Rule

**Evidence determines completion. The owner controls scope, architecture, remote
delivery, sprint sign-off and release authorization. ChatGPT directs and reviews.
Codex executes authorized local work packages. Git preserves project history.**

Every session must end with one unambiguous next action.
