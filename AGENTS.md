# AgentOps AI — Engineering Working Agreement

**Version:** 1.1
**Status:** Proposed for adoption
**Project:** AgentOps AI
**Last updated:** 2026-11-21

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
- ADR-0001: Proposed, pending formal approval
- ADR-0002 through ADR-0007: Open decisions

An ADR marked Proposed is not an approved architecture decision.

Do not silently change product requirements to fit generated code.

## 3. Roles and Authority

### User — Developer and Repository Owner

The user alone:

- Creates, modifies and deletes local repository files.
- Copies generated code and documentation into the project.
- Runs Terminal, Git, Docker, database and test commands.
- Creates GitHub branches and repositories.
- Commits, pushes and merges changes.
- Manages credentials and cloud resources.
- Approves changes to scope and architecture.
- Approves deployment and sprint closeout.

### ChatGPT — Tech Lead

ChatGPT:

- Reads available project context.
- Breaks work into small, reviewable tickets.
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

- Generates complete, copyable code and documents.
- Identifies the destination path for each artifact.
- Provides related tests and verification instructions.
- Proposes fixes from user-supplied error output.
- Explains design changes and dependencies.
- Prepares documentation and handoff updates.

Codex must not:

- Modify or delete repository files.
- Execute commands or tests.
- Apply patches automatically.
- Commit, push or merge.
- Provision AWS resources.
- Deploy applications.
- Invent test results or Git state.

Read-only inspection of explicitly provided files is allowed when authorized by the user. It does not authorize modification or execution.

## 4. Mandatory Session Startup

At the start of every new ChatGPT or Codex session:

1. Read this `AGENTS.md`.
2. Read `docs/handoff/CURRENT_STATE.md`.
3. Read `docs/sprints/INDEX.md`.
4. Read the latest active sprint report.
5. Read relevant PRD, architecture and ADR sections.
6. Review user-supplied Git state.
7. Reconcile any differences between Git and the handoff.
8. Confirm the current ticket and one immediate action.

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

Work on exactly one ticket at a time.

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

1. ChatGPT assigns a ticket.
2. ChatGPT supplies a prompt or implementation specification.
3. Codex generates content.
4. The user manually copies content into the project.
5. ChatGPT supplies verification commands.
6. The user runs checks and shares relevant output.
7. ChatGPT reviews findings.
8. Failures are fixed and rechecked.
9. The user performs Git actions when authorized by the workflow.
10. Sprint and handoff records are updated.

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

## 8. Manual-Copy Output Rules

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

The user executes them.

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

The user alone performs Git actions.

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

| Path | Change | Saved by user | Review / verification |
|---|---|---|---|
| Exact path | Description | Confirmed / Unknown | Result |

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
5. Confirm which generated files were actually saved.
6. Preserve unrelated work.
7. Resume the unfinished ticket.
8. Recheck only stale or missing acceptance evidence.

If the project state cannot be established safely, stop destructive operations and request the specific missing evidence.

Never assume a command succeeded because it was previously suggested.

## 17. Final Engineering Rule

**Evidence determines completion. The user controls execution. ChatGPT directs and reviews. Codex generates implementation content. Git preserves the project history.**

Every session must end with one unambiguous next action.