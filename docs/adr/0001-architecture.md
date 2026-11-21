# ADR-0001 — Adopt a Modular Monolith Architecture

| Field | Value |
|---|---|
| ADR ID | ADR-0001 |
| Date | 2026-11-21 |
| Status | Proposed — Awaiting Engineering Approval |
| Sprint | S00 |
| Owner | AI Engineering |
| Related PRD | [PRD v0.2](../product/PRD.md) |
| Architecture | [System Architecture v1.1](../architecture/overview.md) |

## 1. Context

AgentOps AI is a research platform that must support:

- Authenticated users and owner-scoped resources.
- Durable asynchronous research execution.
- Bounded LangGraph orchestration.
- Approved external search and model providers.
- Evidence collection and citation validation.
- Structured report publication.
- Research history and usage accounting.
- Worker failure recovery.
- Controlled AWS staging deployment.

The project is initially developed and operated by a single engineer.

Expected workload, availability requirements and scaling boundaries have not yet been measured.

Adopting independently deployed microservices from the beginning would introduce substantial additional complexity, particularly around authorization, networking, tracing, data consistency, deployment and recovery.

At the same time, long-running research workloads must not block FastAPI request handling.

The architecture must balance implementation simplicity with reliable asynchronous execution and clear boundaries.

## 2. Decision

**Start with a modular monolith that separates API and background worker processes while retaining a shared backend codebase and release artifact.**

### 2.1 Application Organization

Use explicit modules for:

- Identity
- Research
- Execution
- Workflow
- Evidence
- Reporting
- Provider Adapters
- Operations

Modules communicate through application interfaces rather than internal HTTP calls.

Business rules remain in domain and application services, not in API routers or model prompts.

### 2.2 Runtime Processes

Run:

1. A FastAPI process for HTTP requests.
2. A worker process for durable asynchronous research execution.
3. Controlled maintenance responsibilities for recovery and retention.

API and worker share code, persistence models, schemas and versioned artifacts.

They may use different startup commands but must remain release-compatible.

### 2.3 Persistence Authority

PostgreSQL is authoritative for:

- Task ownership and lifecycle.
- Queue eligibility.
- Execution attempts and leases.
- Usage budgets.
- Evidence and provenance.
- Published reports.
- Execution events.
- Deletion metadata.

A task must be committed before the API returns HTTP 202.

The worker must claim work atomically and cannot use in-process FastAPI background tasks as the durability mechanism.

### 2.4 LangGraph Responsibility

LangGraph coordinates:

`Planner → Research → Evidence Validation → Writer → Report Validation`

A bounded Repair Writer step is allowed only after validation failure and subject to the global one-repair limit.

LangGraph does not replace application authorization, durable queue admission, worker leases or transactional publication.

Optional checkpoints may be introduced later for workflow resumption.

### 2.5 Application Security

Tool access, source retrieval policy, task ownership, budgets and final report publication are enforced by application services.

Model-generated instructions cannot change these policies.

External web content is treated as untrusted.

### 2.6 Initial Cloud Deployment

Use Docker Compose locally and initially on a single EC2 instance.

Publish versioned backend artifacts to Amazon ECR.

Use approved Bedrock model access through a provider adapter.

Use CloudWatch for operational visibility.

PostgreSQL initially uses encrypted persistent storage on EC2, together with independently protected backups.

Detailed infrastructure decisions remain pending ADR-0005.

## 3. Alternatives Considered

### Alternative A — Microservices from the Start

Separate identity, research, execution, reporting and evidence into independently deployed services.

**Advantages**
- Independent scaling.
- Independent releases.
- Clear ownership for larger engineering teams.

**Disadvantages**
- More network and deployment complexity.
- Distributed transactions and consistency challenges.
- More complex authorization and tracing.
- Increased operational burden for a single developer.

**Decision:** Not selected for the initial release.

### Alternative B — One FastAPI Process with BackgroundTasks

Run research tasks inside the API process.

**Advantages**
- Minimal infrastructure.
- Easy initial proof of concept.

**Disadvantages**
- Accepted work may be lost during restarts.
- Long-running workloads compete with HTTP handling.
- Durable claiming and recovery are unresolved.
- Poor alignment with staging reliability requirements.

**Decision:** Rejected for durable research execution.

### Alternative C — External Queue from Day One

Introduce Redis, RabbitMQ or a managed queue immediately.

**Advantages**
- Dedicated queue functionality.
- More flexible worker scaling.
- Potentially improved task dispatch.

**Disadvantages**
- Additional infrastructure.
- More operational and failure modes.
- Need for reliable consistency between database writes and queue publication.
- Database lifecycle, idempotency and publication guards remain necessary.

**Decision:** Deferred until measured needs justify the additional component.

If a broker is introduced, reliable enqueue mechanisms such as a transactional outbox must be evaluated.

### Alternative D — LangGraph Checkpoints as the Durable Queue

Rely solely on workflow checkpoints for scheduling and recovery.

**Advantages**
- State persistence close to graph execution.
- May support node-level resumption later.

**Disadvantages**
- Checkpoints are not user-level admission control.
- They do not inherently enforce ownership or queue capacity.
- Replayed steps may repeat paid external operations.
- Deletion and final publication still require application consistency rules.

**Decision:** Rejected as the sole durable queue.

### Alternative E — ECS and RDS Immediately

Use managed application and database infrastructure for the first release.

**Advantages**
- Better infrastructure separation.
- Additional managed operational capabilities.
- Clearer scaling options.

**Disadvantages**
- Higher initial learning and configuration burden.
- Potential additional cost.
- No measured availability or scaling requirement yet.

**Decision:** Deferred. ECS and RDS remain valid future improvements.

## 4. Benefits

The selected architecture:

- Supports a working MVP without unnecessary infrastructure.
- Separates long-running research from HTTP request handling.
- Makes durable task lifecycle behavior explicit.
- Supports atomic report publication.
- Reduces cross-service communication complexity.
- Allows deterministic provider mocking.
- Retains a clear migration path toward managed services.
- Aligns with PRD delivery milestones.
- Makes operational failure modes easier to understand and test.

## 5. Tradeoffs and Consequences

### 5.1 Coordinated Releases

API and worker share domain contracts and database schema.

Deployments must coordinate compatible versions and migrations.

Separate processes do not imply independent release compatibility.

### 5.2 PostgreSQL as a Critical Dependency

PostgreSQL supports application storage and worker coordination.

Database unavailability may affect APIs, task execution and report access.

Queue transactions must be short. No external network call may hold a database transaction open.

### 5.3 Single-Host Failure Domain

The initial EC2 deployment couples application, worker and database availability to one host.

Backups and restart policies improve recoverability but do not provide high availability.

### 5.4 Limited Mid-Graph Recovery

Interrupted tasks may fail safely instead of resuming at the last LangGraph node.

Explicit retries create new tasks with fresh budgets.

This is permitted by the PRD but may result in repeated external inference costs.

### 5.5 No Exactly-Once External Calls

External model or search calls may complete even after the application times out.

The system cannot guarantee exactly-once execution or exactly-once billing.

The application instead provides:

- Usage reservation.
- Attempt fencing.
- Bounded retries.
- Immutable terminal outcomes.
- Single committed report publication.

### 5.6 Module Discipline

Shared code can become tightly coupled if module boundaries are ignored.

Reviews, typed interfaces and tests must preserve domain ownership.

## 6. Required Failure Behavior

### Worker Lease Expiry During Model Inference

1. Worker A claims task T using execution attempt A1.
2. Worker A reserves usage and calls Bedrock.
3. Worker A stops heartbeating.
4. Its lease expires.
5. Maintenance safely finalizes the task as failed or timed out.
6. The provider response returns late.
7. Worker A attempts a write using expired lease credentials.
8. PostgreSQL/application lifecycle guards reject the write.
9. No report is published from the stale attempt.
10. Usage is conservatively reconciled where permitted.

A later retry must use a new task and execution attempt.

This behavior requires a PostgreSQL integration test and a deterministic late-provider-response test.

### Duplicate Submissions

Concurrent submissions using the same user and idempotency key must not create multiple tasks.

Database uniqueness and request fingerprint comparison enforce this rule.

### Deletion During Execution

Deletion invalidates publication rights.

A delayed worker cannot republish deleted content or create new evidence under the deleted task.

### Invalid Citations

Reports containing missing, fabricated or cross-task evidence IDs cannot become completed reports.

Validation must occur again inside the publication transaction.

## 7. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Duplicate work | Idempotency and atomic claiming |
| Stale worker writes | Attempt IDs, leases and conditional publication |
| Invalid reports | Schema and citation validation |
| Cross-user access | Owner-scoped repositories and composite constraints |
| Lost tasks | Durable queued state and recovery sweeps |
| Unbounded model costs | Budget reservation and call limits |
| Provider uncertainty | Conservative accounting |
| Prompt injection | Application-enforced tool permissions |
| SSRF | Restricted retrieval and DNS/redirect validation |
| Host failure | Off-host backups and restore tests |
| Unsafe migrations | Compatible schema evolution and release review |
| Deleted data restoration | Independent deletion tombstone records |
| Excessive coupling | Explicit module boundaries and code reviews |

## 8. Conditions for Reconsideration

Revisit this decision when:

- Independent engineering teams require separate releases.
- API/worker coupling repeatedly delays delivery.
- PostgreSQL queue contention causes measured performance failures.
- Workload requires independently scaled worker fleets.
- Availability objectives cannot tolerate a single host.
- Regulatory or security requirements demand stronger isolation.
- Recovery objectives require managed database or orchestration services.
- A particular module has a demonstrated scaling bottleneck.

Infrastructure may be upgraded incrementally.

Moving PostgreSQL to RDS or workers to ECS does not automatically require microservices.

## 9. Verification Requirements

This decision is considered successfully implemented only when:

- API and worker can run as separate processes.
- Both use compatible backend versions.
- HTTP 202 is returned only after durable task persistence.
- Concurrent claims do not execute the same task simultaneously.
- Stale attempts cannot publish results.
- Invalid citations cannot be published.
- Worker interruptions reach safe terminal outcomes.
- Deterministic workflow tests require no paid provider calls.
- The application runs locally through Docker Compose.
- Staging deployment and rollback behavior are verified separately.

The ADR itself does not establish that any of these tests have passed.

## 10. Related Requirements

| PRD Requirement | Relationship |
|---|---|
| FR-001–FR-003 | Authentication, ownership and request validation |
| FR-004–FR-007 | Durable task creation and status |
| FR-008–FR-013 | LangGraph workflow, evidence and reports |
| FR-014 | Persistent history |
| FR-015–FR-018 | Budgets, error handling and usage |
| FR-019–FR-020 | Deletion and recovery |
| NFR-001 | Modular Monolith architecture |
| NFR-002–NFR-003 | Performance requirements |
| NFR-004–NFR-005 | Durability and recovery |
| NFR-006–NFR-008 | Security, observability and testing |
| NFR-009 | Versioned deployment |
| NFR-010 | Accessible UI |
| NFR-011 | Versioned workflow configuration |
| NFR-012 | Availability requirements |

## 11. Follow-up ADRs

| ADR | Pending Decision |
|---|---|
| ADR-0002 | Authentication and Session Strategy |
| ADR-0003 | Durable Execution and Recovery |
| ADR-0004 | LangGraph State and Agent Boundaries |
| ADR-0005 | AWS Deployment Architecture |
| ADR-0006 | LLM and Search Provider Selection |
| ADR-0007 | Security, Retention and Deletion |

## 12. Decision Status

**Status: Proposed — Awaiting Engineering Approval**

This ADR recommends the modular monolith approach and supplies the rationale and constraints for implementation.

It does not establish that dependent ADRs have been approved, that features have been implemented, or that the system is production-ready.