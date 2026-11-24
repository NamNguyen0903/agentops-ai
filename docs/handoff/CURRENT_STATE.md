# AgentOps AI — Current State

## Authoritative resume checkpoint

- Date: 2026-11-24 (Asia/Ho_Chi_Minh).
- Last accepted sprint: S02 — Database & Authentication.
- Final acceptance: 11/11 VERIFIED (100%).
- Owner final sign-off: APPROVED.
- Sprint closure: effective when this documentation
  closeout is incorporated into main and its CI passes.
- Next sprint: S03 — planning pending.
- Production deployment: NOT APPROVED.
- Real-user authentication activation: NOT APPROVED.
- Authentication remains disabled by default.

## Start here in the next session

Read these files in order:

1. AGENTS.md
2. docs/handoff/CURRENT_STATE.md
3. docs/sprints/INDEX.md
4. docs/product/PRD.md
5. docs/architecture/overview.md
6. docs/adr/0001-architecture.md
7. docs/adr/0002-authentication.md
8. The actual S03 sprint specification.

Inspect current Git status, branch, HEAD and remote main.

Confirm that the final S02 documentation closeout was
merged and its main CI completed successfully.

Do not repeat completed S02 implementation, dependency
generation or regression work without changed inputs
or a newly discovered blocker.

## Accepted architecture

- Modular monolith with separate API and worker processes.
- FastAPI, React TypeScript and PostgreSQL.
- Async SQLAlchemy, Psycopg and Alembic.
- Google OIDC through conditionally approved Authlib.
- PostgreSQL-backed opaque application sessions.
- Operator-managed account provisioning.
- No public signup or local password implementation in S02.
- ADR-0001 ACCEPTED.
- ADR-0002 ACCEPTED — DEVELOPMENT MVP ONLY.

## Git checkpoint

The fully integrated and CI-verified S02 implementation
baseline is:

76ae5ccccf3d913fba813e8232d8d7e8cb8c9423

Merged implementation PRs:

- PR #4: backend CI foundation.
- PR #6: security and S02 closeout implementation.
- PR #5: identity and authentication.
- PR #3: final integration into main.

Final implementation main CI:

https://github.com/NamNguyen0903/agentops-ai/actions/runs/45311767623

The final documentation integration commit will be
newer than this implementation baseline.

Read GitHub and Git state for its actual identity.
Do not treat the implementation baseline as the
permanent latest HEAD.

Existing local worktrees may remain on historical
branches. Do not assume they are synchronized.

## Evidence and documentation

- docs/sprints/S02.md
- docs/sprints/S02_CLOSEOUT.md
- docs/sprints/S02_SECURITY_REVIEW.md
- docs/development/PYTHON_DEPENDENCIES.md
- docs/development/OPERATOR_PROVISIONING.md
- docs/adr/0001-architecture.md
- docs/adr/0002-authentication.md
- docs/handoff/S02_HISTORY_2026-11-23.md
- docs/handoff/S02_PRE_FINAL_CLOSEOUT_2026-11-24.md

The archived handoffs contain historical Git state,
approval gates and next actions.

They are audit evidence, not current execution instructions.

## Mandatory security boundaries

The owner accepted Development MVP only.

Stock Authlib PKCE DEBUG disclosure remains a known
security FAIL with a bounded application mitigation.

Live Google OIDC, real browser acceptance, trusted
identity enrollment, operator access/auditing,
distributed throttling, retention, key rotation,
production logging, TLS, secret management, recovery,
backup restoration and broader security review remain
mandatory release gates.

Consult the full ADR-0002 gate list.

No real-user activation, staging deployment or
production deployment has been authorized.

## Engineering workflow

Preserve unrelated user changes and existing worktrees.

Use explicit staging boundaries.

Do not use git add ., force push, destructive reset,
history rewrite or uncontrolled resource cleanup.

Keep the sprint tracker, ADRs, verification evidence
and CURRENT_STATE synchronized at meaningful checkpoints.

## Exactly one next action

After verifying the final S02 documentation PR and its
main CI, begin S03 planning from the actual sprint
specification.

Identify the first S03 ticket and its acceptance criteria.

Create an appropriate feature branch from current main
using an isolated clean worktree if needed.

Do not implement unapproved scope.

Do not activate production authentication.
