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
