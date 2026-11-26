# ADR-0007 — S08 scoped real evidence and security amendment

Date: 2026-11-26.

Status: PARTIALLY ACCEPTED — scoped Development MVP additions.

Authority: S08 Contract v1.0, AD08-03, AD08-07,
AD08-09, AD08-10, AD08-11 and AD08-12.

## Approved scope

- Explicit real/synthetic evidence distinction.
- Genuine retrieval timestamps and provenance.
- Source identity, integrity and deduplication.
- Owner/task/attempt isolation and fenced persistence.
- Preserve deletion barriers and stale-attempt rejection.
- Reject fabricated, unknown, deleted and cross-task citations.
- Treat provider output and retrieved content as untrusted.
- Preserve credential protection and sanitized logs/errors.
- Separate fixture evaluation from actual external evaluation.
- Keep report candidates nonpublishable.

Do not imply normalized excerpt integrity proves full fetched-page
integrity unless the complete integrity boundary is verified.

Application-level repository scope checks are not database RLS.

No provider-specific retention guarantee is assumed.
Do not send confidential internal data, secrets or sensitive
personal information to external providers.

D06-05 and D06-06 remain OPEN pending actual evidence.
Historical S06 SG06, SG08 and SG10 require proper reconciliation.

Preserve all historical authorization, security, retention,
deletion and release restrictions.

Material schema changes require applicable approval.
Shared database migration remains prohibited.

No routine external activation, real-user authentication,
report publication or production deployment.

Production remains NOT APPROVED.

---

# Retained historical record

The following original content is preserved verbatim. Nonconflicting requirements remain binding. The active S08 amendment above supersedes conflicting historical sprint-status and authorization statements.

# ADR-0007 — S07 scoped acceptance amendment

Recorded at: 2026-11-25T15:19:46.940631+00:00.

**Status: PARTIALLY ACCEPTED — expanded S07 scope.**

Authority: Owner-approved S07 Contract v1.0.

AD07-10: attempt-fenced evidence and outcome handling.

## Attempt-fenced evidence security

Preserve owner/task isolation, synthetic-only evidence
constraints, evidence integrity and existing citation validation.

An isolated execution UUID alone is not durable fencing.

Integrate evidence and outcome handling with authoritative
attempt ownership, fencing generation, lease validity,
task deadline and deletion barriers.

Stale attempts must not insert newly authoritative evidence
or produce accepted outcomes.

Existing S06 offline evidence behavior must not be silently
removed or converted into worker execution.

Use explicitly authorized disposable PostgreSQL verification.
No shared database migration.

All report candidates remain nonpublishable.
Do not claim semantic grounding or real evidence verification
from structural citation tests.

Existing repository scope checks are not database RLS.


No unrelated retention or deletion policy expansion.

Implementation and verification remain pending.

Production remains NOT APPROVED.

Previous ADR content remains preserved below.

---

# ADR-0007 — Data Retention and Security

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

### ADR-0007 evidence and security clarification

S06 evidence storage and citation verification remain
synthetic-only.

Normalized excerpt hashes are integrity metadata,
not proof of full fetched-page integrity.

Stable evidence identifiers and application-owned
scope checks are not durable worker fencing or
database row-level security.

Actual provider data retention, real evidence
provenance and applicable deletion/retention behavior
remain subject to the approved successor contracts.

D06-05 receives real evidence integration obligations.
D06-06 receives integrated external security review.

Original data retention and security requirements
remain unchanged.

No real evidence schema activation, unauthorized
retention cleanup, shared database mutation or
publication is authorized by this amendment.


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


## S06 WP03 evidence persistence verification

Date: 2026-11-25.

Status: Development MVP — locally verified.

Revision: b6e0326a7103.

- Evidence IDs are deterministic and scoped by
  owner, task, execution and normalized excerpt identity.
- SHA-256 covers the retained excerpt, not the full
  original page or source authenticity.
- Composite foreign key protects task ownership.
- Application role receives SELECT and INSERT only.
- Runtime evidence UPDATE, DELETE, TRUNCATE and DDL
  are not authorized.
- Evidence remains synthetic-only.
- Publication timestamp remains unknown.
- Maximum retained excerpt is 4096 characters.
- Maximum evidence admission is 20 records/task,
  across execution contexts.
- Repository transactions use READ COMMITTED and
  serialize admission with the parent task lock.
- Soft-deleted tasks are rejected at repository boundaries.
- Execution context must originate from the application.

This is repository-level scoping, not database RLS.

A trusted runtime role with direct SQL access is not
equivalent to an untrusted application user.

No durable worker execution fencing, retention purge,
real evidence acquisition or publication is authorized.

Verified only against disposable PostgreSQL.

Production remains NOT APPROVED.
