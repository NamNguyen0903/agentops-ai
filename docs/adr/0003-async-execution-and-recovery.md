# S08 G03 — Owner-approved persistence extension

Status: ACCEPTED — DEVELOPMENT MVP ONLY.

Approval authority: AD08-G03-01 through AD08-G03-03.

Accepted WP02-B evidence SHA256:
`a62751e8a47726f41adeb9041f918569f5471a73f230bbfa2912e046426c2143`.

Approved scope:

- Add dedicated provider usage identity and credit fields to
  the existing durable operation ledger.
- Preserve the distinction between synthetic and live observations.
- Introduce durable task-bound controlled smoke grant persistence.
- Derive spent allowance from persistent reservations under a
  transaction lock; do not refund indeterminate execution.
- Grant policy fields remain non-writable by the application role.
- Introduce separate real-evidence persistence linked by
  composite owner/task/attempt/operation lineage.
- Preserve original synthetic evidence table and its constraints.
- Preserve original historical Alembic revisions.
- Execute migrations only on explicitly disposable databases.

Schema foundation does not issue a grant or activate a provider.
Service-level authorization, usage settlement, recovery,
provenance validation and deletion fencing require further tests.

Initial grant schema permits up to six Basic Search requests,
one explicitly scoped retrieval, and a maximum 15-minute
grant lifetime. These are schema ceilings, not live permission.
G04 must set the exact narrower authorized values.

No dependency change, shared migration, live credential use,
paid request, deployment or Git delivery is authorized.

PRODUCTION REMAINS NOT APPROVED.

---

# ADR-0003 — S08 scoped accounting amendment

Date: 2026-11-26.

Status: ACCEPTED — scoped Development MVP additions only.

Authority: S08 Contract v1.0, AD08-05, AD08-06,
AD08-09 and AD08-12.

Preserve all approved S03 and S07 execution decisions.

## Approved S08 scope

- Actual provider usage integrated with durable accounting.
- Application-owned reservations before dispatch.
- Idempotent settlement and duplicate reconciliation.
- Cumulative budgets survive retries and recovery.
- No automatic retry or refund after indeterminate execution.
- Preserve deadlines, leases, fencing and terminal immutability.
- Preserve transactional writes and deletion barriers.
- External execution and routine worker activation remain denied.

Provider calls must remain outside database transactions.
Settlement must not permit stale attempts to publish outcomes.

D06-03 retains isolated closure.
D06-04 remains OPEN until actual accounting evidence is verified.

No new database migration or material architecture change
outside approved scope is authorized by this amendment.

No production or external activation authorization.

---

# Retained historical record

The following original content is preserved verbatim. Nonconflicting requirements remain binding. The active S08 amendment above supersedes conflicting historical sprint-status and authorization statements.

# ADR-0003 — S07 scoped acceptance amendment

Recorded at: 2026-11-25T15:19:46.940631+00:00.

**Status: ACCEPTED — scoped S07 Development MVP.**

Authority: Owner-approved S07 Contract v1.0.

This amendment extends previous admission-only acceptance.

## Durable execution architecture

Preserve the modular monolith and separate API/worker process
boundaries. PostgreSQL is authoritative for task lifecycle,
attempt ownership, recovery and execution accounting.

Do not introduce Redis, Celery, RabbitMQ, Kafka,
Kubernetes or microservices in S07.

Use atomic PostgreSQL claiming with row locking and
FOR UPDATE SKIP LOCKED, coordinated with admission and
global/per-user running limits.

SKIP LOCKED alone is not sufficient for capacity enforcement.
Define consistent lock ordering before implementation.

Each task must have at most one authoritative active attempt.
Attempt identity and monotonically increasing fencing
generation must be durable.

Heartbeats, lease renewal, evidence writes, outcome writes
and lifecycle mutations must verify current ownership.

Expired ownership must be invalidated before recovery.
Stale attempts must not commit results or renew leases.

Recovery is bounded by attempts, deadlines and remaining budgets.
Do not reopen terminal tasks. Preserve deletion barriers.

The existing task statuses remain the baseline:
queued, running, completed, insufficient_evidence, failed, timed_out.

Recovery transition details must remain compatible with the
approved lifecycle, including original start timestamps.
User-visible cancellation state expansion is not authorized
by the cancellation requirement alone.

Database transactions must remain short.
Do not hold a database transaction across external operations.

Durable execution is not a claim of exactly-once remote effects.
Unknown external side effects must fail closed.


## Application-owned execution context

Integrate acquisition accounting with durable task and attempt
authority, not with model-owned state or fresh per-attempt counters.

Reserve applicable capacity before dispatch:

1. Validate task, attempt, fencing generation and lease.
2. Validate task and operation deadlines.
3. Validate remaining cumulative budget.
4. Persist reservation transactionally.
5. Commit before executing the operation.
6. Execute outside the database transaction.
7. Record outcome with current ownership verification.

Conservatively retain consumed/reserved capacity across crashes.
Do not automatically refund uncertain dispatch reservations.
Do not retry an operation with indeterminate execution status.

Count retries toward all applicable cumulative ceilings.
Recovery cannot reset task budgets or running deadlines.

Use authoritative durable deadline timestamps and appropriately
bounded local monotonic timing. Lease renewal does not extend
the task deadline.

Maintain the distinction between caller timeout,
cooperative cancellation, local termination and remote effects.

Evaluate isolated process execution where synchronous adapters
lack reliable interruption capabilities. A specific isolation
implementation is not selected merely by this evaluation.

Cancelling a future or coroutine does not prove that its
underlying synchronous operation has stopped.

Fail closed when completion, cancellation or execution state
cannot be established. Never claim hard cancellation without
verified adapter capabilities.

Actual provider billing and usage reconciliation remain D06-04.
Only deterministic model/token/estimated-cost verification
is authorized in S07.


## Approved execution limits

| Control | Limit |
| --- | --- |
| Global concurrent running tasks | 5 |
| Per-user running tasks | 1 |
| Pending queue capacity | 50 |
| Queue wait deadline | 60 seconds |
| Running-task deadline | 180 seconds |
| Search calls | 6 |
| Retrieval calls | 12 |
| Search/retrieval operation deadline | 15 seconds |
| Retry per eligible operation | 1 |
| Model invocation product ceiling | 8 |
| Model token product ceiling | 40000 |
| Model operation timeout | 45 seconds |
| Estimated variable cost product ceiling | USD 1.00 |
| Evidence records | 20 |
| Redirects | 3 |
| Retrieved body size | 1 MiB |

Preserve the stricter existing S05 workflow limits:
four adapter invocations, one globally shared repair allowance,
recursion limit twelve and 30-second cooperative soft deadline.

Product ceilings do not grant permission for paid usage.

### Approved worker defaults

| Control | Value |
| --- | --- |
| Lease duration | 30 seconds |
| Heartbeat interval | 10 seconds |
| Idle polling interval | 1 second |
| Recovery inspection interval | 5 seconds |
| Maximum execution attempts | 2, including initial attempt |

These are approved initial defaults, not benchmark results.
Recovery cannot extend the running-task deadline or reset budgets.


AD07-01 through AD07-08 and AD07-12 apply within their approved S07 scope.

Detailed execution schema, SQL predicates and adapter capabilities must be reviewed during the applicable implementation packages.

No runtime activation, shared migration or publication.

Production remains NOT APPROVED.

Previous ADR content remains preserved below.

---

# ADR-0003 — Async Execution and Recovery

## Status

PARTIALLY ACCEPTED — S03 Development MVP admission only.

Owner authorization: 2026-11-24.

## Accepted decision: research admission

- PostgreSQL is authoritative for queued research tasks.
- Use a singleton app.queue_control coordination record.
- Serialize admission decisions with SELECT FOR UPDATE.
- Resolve idempotency replay before enforcing queue capacity.
- Default pending queue capacity: 50, configurable.
- Count non-deleted queued tasks.
- Commit before returning HTTP 202.
- Fail closed when coordination or database access fails.
- Runtime role receives SELECT and UPDATE on queue_control.
- No new dependency or external queue infrastructure.

## Deferred decisions

Worker claiming, execution attempts, leases, heartbeats,
stale-worker recovery, deadlines and result publication remain open.

Future claiming must coordinate consistently with admission.

## Approval boundary

This decision does not authorize production, real-user activation,
live Google OIDC, worker implementation or deployment.

All ADR-0002 mandatory release gates remain unchanged.


## Local admission verification — 2026-11-24

- Native backend: 124 passed, 46 skipped.
- Disposable PostgreSQL: 45 passed.
- Queue singleton and concurrent admission verified.
- Queue-only downgrade/upgrade passed.
- Runtime role SELECT/UPDATE grants verified.
- Full runtime-role HTTP acceptance remains open.
- Compose exit code: 0.

Status remains PARTIALLY ACCEPTED — admission only.
No worker, recovery or production approval is implied.
