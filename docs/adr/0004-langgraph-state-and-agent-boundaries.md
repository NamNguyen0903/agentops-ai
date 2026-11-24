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
