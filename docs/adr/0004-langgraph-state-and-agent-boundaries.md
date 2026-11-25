# ADR-0004 — S06 Scoped Architecture Amendment

Date: 2026-11-25.

Status: ACCEPTED — Development MVP only.

Authority: Owner-approved S06 Contract v1.0.

## Approved extension

AD01, AD06, AD07 and AD08 authorize a separately
versioned S06 workflow for evidence acquisition,
validation and nonpublishable report candidates.

Preserve existing S04 and S05 workflows, typed contracts,
execution guards, tests and historical evidence.

The S06 workflow uses application-owned typed provider
interfaces and evidence provenance contracts.

Retrieved content is untrusted data, never an
authority for policies, permissions, budgets or tools.

The writer receives only validated evidence.
Citation validation is deterministic, task-scoped
and fail-closed.

Unknown, fabricated, deleted, cross-task or
otherwise invalid evidence references must fail.

Insufficient evidence produces an explicit bounded
outcome, not invented citations.

Structural validation does not prove factual
or semantic groundedness.

## Execution boundary

Preserve existing S05 limits in the S05 workflow.
S06 execution limits remain within approved
application-owned budgets and contract ceilings.

No live model provider, external retrieval, persistent
graph checkpointing, durable worker attempts,
task lifecycle transition or report publication
is authorized by this amendment.

Offline graph verification is authorized only after
the relevant work package dependencies pass.

Evidence persistence is separately governed by ADR-0007.
Provider and retrieval policy is governed by ADR-0006.

Graph nodes have no independent database write authority.

Production remains NOT APPROVED.

All sections below retain historical ADR evidence.
This amendment supersedes conflicting historical
S06 restrictions only within its explicit scope.

---

# ADR-0004 — LangGraph State and Agent Boundaries

| Field | Value |
|---|---|
| Status | **ACCEPTED — DEVELOPMENT MVP ONLY** |
| Date | 2026-11-24 |
| Sprint | S04 — Single-agent LangGraph |
| PRD | [PRD v0.2](../product/PRD.md), especially §9 |
| Architecture | [overview v1.1](../architecture/overview.md), especially §8 |
| Related | [ADR-0001](0001-architecture.md), [ADR-0002](0002-authentication.md), [ADR-0003](0003-async-execution-and-recovery.md) |

## Context and decision drivers

The approved modular monolith separates API from future long-running workers. S03 persists and presents tasks but does not execute research. PRD FR-008 requires an eventual bounded Planner → Research → Evidence Validation → Writer → Report Validation pipeline. S04 is only a **single-agent baseline**: its offline fixture must not pretend to satisfy the entire multi-node workflow, evidence or publication requirements. ADR-0003 authorizes PostgreSQL admission only; claiming, leases and crash recovery are not approved. The owner requires no live providers, no real users and no deployment.

## Accepted decision — Development MVP

1. **Graph boundary:** implement a small reusable workflow module inside the existing Python backend package, callable directly from offline tests and later from an explicitly authorized worker. Do **not** call it from ordinary FastAPI request handlers or the S03 submission flow.
2. **Topology:** `START → single_fixture_agent → END`, no dynamic node creation, no tool-calling loop, no implicit retries. This is an intentionally narrower precursor to architecture §8.1; S05 adds the specialized nodes.
3. **Typed state:** explicitly typed/validated input and output, including `task_id`, `attempt_id` (nullable only for offline prototype; never a substitute for future attempt fencing), `question`, `scope`, `plan`, `evidence_ids`, `coverage`, `draft_report`/`result`, `stage`, `repair_used`, `budget_snapshot`, `error_category`, and `versions` for graph/model/prompt/schema. Store no credentials, chain-of-thought, private config or full fetched pages. In S04, absent plan/evidence/draft fields are explicitly empty/null, not fabricated.
4. **Providers and permissions:** inject a deterministic fixture adapter through application code. Graph instructions, returned strings and future retrieved content can never alter allowlisted adapters, approved network destinations, authorization, budget or system configuration. S04 has **no live network-capable tool**.
5. **Result semantics:** return a typed candidate/outcome proposal, not a database transition or published report. A candidate with no evidence cannot be claimed as a valid citation-backed research report. PostgreSQL application services retain task ownership, transition, deletion barrier, fencing and atomic publication authority.
6. **Bounds:** application code owns max steps, deadline, usage counters and output validation. A fixture invocation has finite steps and no model-call or retrieval budget. Future real providers must honor PRD §8.6 limits (8 model calls, 6 searches, 12 retrievals, 20 evidence records, 40k tokens, USD 1.00, 45s model, 15s retrieval, 180s running deadline, 60s queue wait, one eligible retry); these are **initial hypotheses**, not S04 measured guarantees. Never implement unbounded loops. One malformed-output repair globally is deferred until applicable nodes exist.
7. **Failure/validation:** model/fixture output is untrusted. Application-owned schema and policy checks reject malformed state, invalid stage, unexpected fields and unsupported evidence/citation claims. Surface allowlisted error categories, without raw exceptions, prompt content or secrets. Distinguish insufficient evidence from execution failure; graph does not authoritatively mark a task terminal.
8. **Checkpoints:** use **in-memory ephemeral state, no durable LangGraph checkpointer** in S04. No mid-graph recovery claim. If later adopted, checkpoint keys require task+attempt fencing, retention and replay validation by a separate approved decision. LangGraph checkpoints are never the queue or publication record.
9. **Versioning and traceability:** explicit graph, prompt, model/fixture and schema version fields; deterministic fixture inputs and evaluation artifacts tied to versions. No hidden reasoning persisted.

## Alternatives considered

| Option | Advantages | Rejection/deferral reason |
|---|---|---|
| A. Offline single-node LangGraph baseline (**accepted**) | Small, testable seam; enforces state and boundary before providers | Not yet end-to-end research; requires later expansion |
| B. Build complete Planner/Research/Writer now | Closer to FR-008 | Expands beyond S04; raises provider, evidence, recovery approvals |
| C. Plain Python chain without LangGraph | Simpler dependency | Does not validate the intended LangGraph foundation |
| D. LangGraph checkpointer as queue/worker | Built-in workflow snapshots | Violates task/lease/publication authority; ADR-0003 unfinished |
| E. Execute graph during POST HTTP request | Easy integration | Long-running request and commit-before-202 conflicts |

## Security and validation consequences

- **Positive:** clear tool allowlists, typed state, deterministic reproducibility and no accidental external calls during S04 tests.
- **Tradeoff:** no durable execution, no actual report or evidence output, no live cost/latency data, no recovery under process interruption.
- **Threat considerations:** prompt injection in future evidence cannot grant tool permissions; no SSRF exposure now; future search/retrieval must implement DNS/redirect/private-network guards; no arbitrary model-driven network or consequential actions.
- **Testing required:** deterministic fixtures; malformed input/output; unknown tool attempt rejected; budget/step/deadline bounds; safe errors; absence of task DB writes and network use; version consistency. S04 cannot claim semantic groundedness without actual validated evidence.

## Open decision gates

1. Owner accepts or revises topology and explicit single-node interpretation of S04 (full PRD graph remains S05–S06).
2. Owner confirms no checkpointer/no durable worker binding in S04; ADR-0003 stays admission-only.
3. Owner approves exact state contract and outcome nomenclature before code.
4. Library version/security/lockfile compatibility must be reviewed after approval and before dependency installation.
5. Any changed network, auth, publication or lifecycle boundary requires a separate scope/ADR decision.

**Decision status:** ACCEPTED — DEVELOPMENT MVP ONLY. Owner approved 2026-11-24. S04-WP02 implementation permitted after Git diff review; no live providers, real-user activation, release or production authorization.


---

## S05 Architecture Amendment

**Decision date:** 2026-11-24

**Status:** ACCEPTED — DEVELOPMENT MVP ONLY

**Owner authorization:** APPROVED — S05 Contract v1.0

**Runtime implementation authorization:** NOT AUTHORIZED

**Production authorization:** NOT APPROVED

**Related contract:** [S05 Contract v1.0](../sprints/S05.md)

### Amendment authority

The Project Owner explicitly approved S05 Contract
v1.0 and architecture decisions AD01-AD08 on
2026-11-24.

This amendment extends the accepted S04 architecture
for the specialized S05 offline workflow.

The original S04 decision and its historical evidence
remain intact. Its single-agent graph remains a
supported regression and comparison baseline.

This amendment does not reopen S04 or authorize
production, live providers or worker activation.

### Context

S04 delivered a deterministic single-agent
LangGraph baseline with typed state, execution
guards, validation and a non-publishable result.

S05 extends this foundation toward PRD FR-008
through specialized Planner, Research and Writer
nodes and deterministic validation stages.

Real retrieval, evidence persistence, citation
groundedness and durable worker execution remain
outside the approved S05 scope.

### Accepted S05 decisions

| ID | Architecture decision |
|---|---|
| AD01 | Add a separate agent/s05 package while preserving S04 contracts and behavior. |
| AD02 | Use S05-specific typed contracts and explicit version metadata. |
| AD03 | Implement Planner, Research and Writer nodes with deterministic evidence and report validation stages. |
| AD04 | Use only application-owned deterministic offline fixture adapters. |
| AD05 | Allow at most one globally shared eligible malformed-output repair. |
| AD06 | Enforce bounded execution and a 30-second soft deadline. |
| AD07 | Keep graph state ephemeral and in memory without durable checkpoints. |
| AD08 | Graph outcomes have no persistence, publication or task-transition authority. |

### Graph and module boundaries

The S05 implementation belongs inside the existing
modular monolith backend:

`apps/api/src/agentops_api/agent/s05/`

The existing S04 module remains available without
changing its public contracts or accepted behavior.

The logical S05 workflow is:

Validated Input -> Planner -> Research
-> Evidence Validation -> Writer
-> Report Validation -> Non-publishable Outcome.

Evidence Validation may route to explicit abstention
when available fixture evidence is insufficient.

Planner and Writer may use the same globally bounded
repair allowance for eligible malformed outputs.

All stages may fail closed.

The application owns graph routing and explicit
termination. No dynamic node creation, arbitrary
tool execution, supervisor agent, autonomous agent
swarm or unbounded reflection loop is authorized.

No FastAPI request handler, research submission
service or background worker may invoke the S05
workflow as part of this sprint.

### Typed state and trust boundaries

S05 uses a versioned typed state and separate
input, intermediate output and result contracts.

Application-owned context includes task identity,
attempt identity, validated question and scope,
versions, policy limits and execution counters.

Node and adapter output is untrusted.

Validate node output before allowing it to influence
downstream execution.

Reject unexpected fields, invalid types, invalid
stage transitions and unauthorized context changes.

Application-owned validation must not trust adapter
claims about permissions, budgets, repair usage,
publication or lifecycle status.

Use bounded structured plans, fixture references,
coverage information, structured draft candidates
and sanitized outcome categories.

Do not store credentials, hidden chain-of-thought,
private configuration or unnecessary source content
in graph state.

### Specialized node responsibilities

Planner:

- Interpret the validated research question and scope.
- Produce structured subquestions and search queries.
- Record assumptions and ambiguities.
- Respect the maximum of four subquestions.
- Return schema-valid output without changing policy.

Research:

- Consume a validated research plan.
- Access only approved deterministic offline fixtures.
- Preserve explicit fixture provenance.
- Identify gaps and conflicts in fixture data.
- Never invent evidence to replace missing fixtures.
- Never initiate real network retrieval.

Evidence Validation:

- Validate fixture identity and task association.
- Reject unknown or fabricated fixture references.
- Validate structural coverage information.
- Route insufficient evidence to explicit abstention.
- Do not claim real-world factual groundedness.

Writer:

- Produce a structured offline report candidate.
- Use only allowed validated fixture references.
- Distinguish fixture findings, synthesis and uncertainty.
- Explain evidence limitations and conflicts.
- Never claim that the candidate is a published report.

Report Validation:

- Validate the candidate schema.
- Reject fabricated, unknown or cross-task references.
- Enforce non-publication semantics.
- Return only an application-validated outcome proposal.

### Application-owned execution policy

| Control | S05 approved policy |
|---|---|
| Maximum subquestions | 4 |
| Global repair allowance | Maximum 1 |
| Specialized adapter invocations | Maximum 4 |
| Initial LangGraph recursion limit | 12 |
| Soft execution deadline | 30 seconds |
| Live model calls | 0 |
| Live search calls | 0 |
| Live retrieval calls | 0 |
| Live provider tokens | 0 |
| Paid inference cost | USD 0 |
| Durable checkpoints | 0 |
| Publication permission | False |

The recursion limit of 12 is an approved initial
engineering value, not a measured execution guarantee.

Actual LangGraph integration tests must establish
that the approved routes terminate within bounds.

Graph recursion limits and specialized adapter
invocation counters are separate controls.

The application checks the deadline at entry,
before and after each node and repair invocation,
and before accepting the final outcome.

A caller may shorten but cannot extend the
application-owned deadline.

The 30-second deadline is soft. It does not forcibly
interrupt a blocked node.

### Global repair decision

Planner and Writer share one global allowance for
eligible malformed-output repair.

A repair consumes the same global execution budgets.

If the Planner consumes the allowance, the Writer
cannot receive an additional repair.

Repeated malformed output fails closed.

No implicit retries are authorized.

Security violations, unauthorized context mutation,
unknown or cross-task references and expired
deadlines fail closed without repair.

Insufficient evidence is an abstention condition,
not permission to fabricate evidence or retry.

The application owns the repair counter and
eligibility decisions.

### Security boundaries

The S05 workflow has no authority to:

- Access live model or search providers.
- Perform network or DNS operations.
- Perform database operations.
- Call research persistence or lifecycle services.
- Change authorization or tool permissions.
- Modify application-owned budgets.
- Persist or publish report candidates.
- Transition ResearchTask lifecycle states.
- Activate workers or durable recovery.
- Activate live authentication or real users.

All candidates remain non-publishable.

Fixture content remains untrusted even when loaded
from an approved deterministic adapter.

Existing S02 and S03 security controls, the
authentication-disabled default and the strict
Authlib security XFAIL remain mandatory.

### Validation and verification requirements

Required evidence includes:

- Deterministic fixture and structured contract tests.
- Actual LangGraph topology and termination tests.
- Strict input and output validation tests.
- Immutable context and stage transition tests.
- Unknown and cross-task fixture reference rejection.
- Global repair exhaustion tests.
- Deadline and invocation limit tests.
- Sanitized exception, traceback and log tests.
- Network, DNS, database and research layer guards.
- Recursive forbidden-import verification.
- S04 regression and full backend regression.
- Dependency compatibility and security audit evidence.
- Required PR and post-merge main CI results.

Negative tests must begin with valid baseline data,
mutate the intended field and verify the relevant
failure category.

Security tests must cover normal, failure,
abstention and eligible repair paths.

Downstream execution must be prevented following
a boundary failure where applicable.

Passing these tests does not establish complete
OS-level network or database isolation.

### Alternatives and tradeoffs

The selected design preserves S04 and adds a
separately versioned S05 package.

Directly replacing the S04 contracts was rejected
for S05 because of regression risk and loss of a
stable single-agent baseline.

The separate package may introduce limited
duplication. Shared abstractions should be considered
only when justified by actual implementation needs
and without silently changing accepted S04 behavior.

Adding live providers, durable checkpoints, new
agents or worker execution would exceed the
approved incremental scope.

### Dependencies and release restrictions

Keep the existing LangGraph 1.2.24 dependency
baseline and all seven backend dependency lockfiles.

No dependency changes, Docker runtime changes or
CI workflow changes are authorized without
separate owner approval.

ADR-0001 remains accepted.

ADR-0002 remains accepted for Development MVP only,
with all existing security and release restrictions.

ADR-0003 remains partially accepted for admission
only. Worker claiming, attempts, leases, fencing,
recovery and publication remain deferred.

This amendment does not approve ADR-0005,
ADR-0006 or ADR-0007.

### Limitations and deferred work

S05 does not establish real retrieval, persistent
evidence, semantic citation groundedness, live
model quality, hard timeouts, OS-level sandboxing,
worker recovery or production readiness.

Real retrieval and evidence integration remain
future sprint work.

Durable execution and recovery require separate
architecture approval before implementation.

No production deployment or real-user activation
is approved.

### Delivery and authorization

Owner approval of this amendment records the
architecture decision only.

Documentation review and WP01 delivery gates
must complete before runtime work can begin.

A separate owner authorization is required for
the next implementation work package.

AC02 delivery verification remains pending until
the reviewed amendment and WP01 delivery evidence
are accepted.

Current authorized work: WP01 documentation only.

Runtime implementation: NOT AUTHORIZED.

Production authorization: NOT APPROVED.


### S05 WP01 delivery verification

The owner-approved architecture amendment was
reviewed and delivered through merged PR #16.

Verified documentation commit:

`c0cc22a9cb2294c6a2f5e12632579d4e5dbfe19a`

Verified merge checkpoint:

`cae5d35bdfb955866560c763fb41c5714e60c41d`

- PR CI 45425694993: 4/4 PASS.
- Post-merge main CI 45426129070: 4/4 PASS.
- Reviewed architecture amendment preserved.
- AC02 technical delivery verification: PASS.

This section records subsequent delivery evidence
and supersedes the earlier pending AC02 delivery
verification description.

Final WP01 checkpoint synchronization remains subject
to its own documentation delivery verification.

No AD01-AD08 decision is changed.

Runtime implementation remains NOT AUTHORIZED
until separate explicit owner approval.

Production remains NOT APPROVED.


### S05 WP01 final acceptance and WP02 authorization

Date: 2026-11-24.

Final synchronization PR #17 is MERGED.

- PR CI 45428102016: 4/4 PASS.
- Final Main CI 45428619901: 4/4 PASS.
- Final main checkpoint:
  `a7f485e3b57e5d898c3a29bf76c4d5c96ae035c1`.
- WP01: DELIVERED.
- AC01-AC02: ACCEPTED.

The Project Owner explicitly accepted WP01 and
authorized WP02 only, covering AC03-AC05.

This later authorization supersedes earlier WP01-only
execution restrictions for the authorized WP02 scope.

The S05 package may implement typed contracts,
strict validation, immutable context and deterministic
offline fixture adapters.

No architecture decision AD01-AD08 is changed.

The approved execution limits remain unchanged.

WP03-WP05 remain NOT AUTHORIZED.

No live providers, real evidence persistence,
worker activation or report publication are authorized.

Production remains NOT APPROVED.


### S05 WP02 local acceptance and WP03 authorization

Date: 2026-11-25.

The Project Owner explicitly accepted:

- WP02 local completion: 8/8 main tickets.
- AC03-AC05 local technical evidence.
- WP03 implementation authorization: AC06-AC09 only.
- Development MVP scope.

WP02 integrated delivery remains pending PR B.
Official sprint acceptance remains 2/16.

This subsequent authorization supersedes earlier
WP02-only implementation restrictions for WP03.

AD01-AD08, the approved topology, execution limits
and security boundaries remain unchanged.

WP04-WP05 remain NOT AUTHORIZED.

No live providers, real retrieval, lifecycle mutation,
publication, worker activation or production deployment
are authorized.

Production remains NOT APPROVED.
