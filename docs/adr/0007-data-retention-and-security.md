# ADR-0007 — Data Retention and Security

Date: 2026-11-25.

Status: PARTIALLY ACCEPTED — Development MVP only.

Authority: Owner-approved S06 Contract v1.0,
AD05, AD06 and AD08.

## Context

S06 requires evidence provenance and persistence
without weakening existing task ownership,
database security or execution boundaries.

## Accepted decision

Implement typed task-scoped evidence records,
stable identifiers, bounded excerpts, acquisition
provenance, validated URLs, UTC retrieval time,
nullable publication time and content integrity metadata.

Derive exact data types, constraints and deduplication
semantics from existing source contracts.

Use PostgreSQL and versioned Alembic migrations.

Evidence access is application-authorized.
Do not trust model-supplied ownership or attempt IDs.

Enforce task and owner isolation and preserve
execution-context isolation.

No cross-task evidence substitution.

Invalid or deleted evidence cannot satisfy
citation validation.

No fabricated source metadata.

Evidence writes must use an explicitly authorized
repository boundary, not direct graph-node writes.

## Database authorization

Schema and repository implementation are approved.
Migration execution and evidence persistence tests
are authorized on isolated disposable PostgreSQL only.

Preserve existing application and migrator role
boundaries and least privilege.

Do not grant schema creation to the application role.

Verify upgrade/downgrade, constraints, unauthorized
access rejection and task isolation.

No shared database migration, data reset,
unrelated lifecycle mutation or worker activation.

## Data handling

Store only bounded content needed for evidence.

Do not persist credentials, hidden chain-of-thought
or complete fetched pages in graph state.

Treat source content as untrusted.

Public errors and logs must not disclose sensitive
data, credentials or internal stack traces.

Content integrity and structural provenance
are not guarantees of factual accuracy.

## Open decisions

- Final retention durations and cleanup schedules.
- Production deletion and restore suppression.
- Encryption and backup operational policies.
- Production audit logging and access policy.
- Shared database migration authorization.
- Durable attempt persistence and publication fencing.
- Report publication and production release.

No full retention implementation is implied by
this scoped ADR acceptance.

## Verification

WP03 must provide evidence schema, migration,
least-privilege and isolation verification.

WP04 must verify citation resolution and
deleted/invalid evidence rejection.

WP05 must provide integrated security evidence.

Production remains NOT APPROVED.
