# AgentOps AI — Product Requirements Document

**Version:** 0.2
**Status:** Approved for Architecture Design — Implementation Pending
**Owner:** Product Team / AI Engineering
**Sprint:** S00
**Last Updated:** 2026-11-21
**Document:** `docs/product/PRD.md`
**Project:** AgentOps AI — Multi-Agent Market Research Platform

---

## 1. Executive Summary

AgentOps AI is a production-oriented, AI-powered research platform designed to help enterprise market research analysts investigate competitors, products, and market trends.

Users submit research questions through a web interface. The system executes a bounded research workflow using LangGraph, retrieves information from approved public sources, evaluates the available evidence, and generates structured reports with inspectable citations.

The platform aims to reduce manual research effort while improving evidence traceability, repeatability, and operational transparency.

### Product Vision

> Transform a complex research question into a structured, evidence-backed report through a reliable, observable, and secure Agentic AI workflow.

### Core Product Principles

1. **Evidence before conclusions:** Factual findings must be supported by identifiable sources.
2. **Human judgment remains essential:** Reports assist analysts rather than replace their decisions.
3. **Reliability over agent complexity:** Multi-agent orchestration must provide measurable value.
4. **Bounded autonomy:** Model-generated plans cannot override tool permissions, budgets, or execution limits.
5. **Measurable AI quality:** Changes to prompts, models, or graphs require evaluation.
6. **Production-oriented engineering:** The application must be testable, observable, recoverable, and deployable through a controlled release process.

### Intended Technology

| Layer | Proposed Technology |
|---|---|
| Frontend | React, TypeScript |
| Backend | Python, FastAPI |
| Agent Orchestration | LangGraph |
| LLM Integration | LangChain, Amazon Bedrock |
| Database | PostgreSQL |
| ORM / Migrations | SQLAlchemy, Alembic |
| Local Infrastructure | Docker Compose |
| CI/CD | GitHub Actions |
| AWS Runtime | EC2 initially |
| Container Registry | Amazon ECR |
| Logging / Monitoring | Amazon CloudWatch |
| Infrastructure as Code | Terraform, introduced incrementally |

Technology selections describe the initial architectural direction. Exact library versions, AWS resources, identity mechanism, and external integrations must be recorded in Architecture Decision Records before implementation.

---

## 2. Business Problem

Market research analysts must collect and compare information from many public sources before producing reports.

The current manual process commonly involves:

1. Clarifying the research objective.
2. Identifying competitors or relevant market segments.
3. Searching multiple websites.
4. Reading and comparing findings.
5. Checking dates and credibility.
6. Resolving conflicting claims.
7. Producing a coherent report.
8. Recording supporting sources.

### Key Pain Points

| ID | Problem | Business Impact |
|---|---|---|
| BP-001 | Repetitive searching and summarization | High manual effort |
| BP-002 | Important sources may be missed | Incomplete research |
| BP-003 | Unsupported AI-generated claims | Reduced trust |
| BP-004 | Conflicting or outdated sources | Risk of incorrect decisions |
| BP-005 | Poor source traceability | Difficult verification |
| BP-006 | Research steps are difficult to reproduce | Inconsistent results |
| BP-007 | AI execution cost and duration are unpredictable | Operational uncertainty |

### Problem Statement

Enterprise market research analysts need a reliable way to collect, organize, and interpret publicly available information because manual research is time-consuming, difficult to reproduce, and vulnerable to gaps in evidence.

AgentOps AI addresses this through structured research planning, controlled source retrieval, evidence-linked reporting, and transparent execution status.

### Product Constraints

The platform cannot guarantee comprehensive web coverage or factual correctness.

Retrieval success does not imply source accuracy. A structurally valid citation does not necessarily support the associated claim.

---

## 3. Target Users and Personas

### 3.1 Primary Persona — Market Research Analyst

**Responsibilities:**
- Research competitors and market segments.
- Compare products and positioning.
- Identify important trends.
- Produce evidence-backed briefs.

**Needs:**
- Simple research submission.
- Report generation without manually configuring agents.
- Inspectable citations and source dates.
- Transparent uncertainty.
- Searchable research history.

**Success Condition:** The analyst produces an acceptable research brief with lower manual effort while retaining the ability to verify important claims.

### 3.2 Secondary Persona — Product or Strategy Manager

**Responsibilities:**
- Review competitive intelligence.
- Understand market positioning.
- Use findings as input for business decisions.

**Needs:**
- Concise, structured reports.
- Clear distinction between evidence and interpretation.
- Source traceability.
- Explicit limitations and uncertainty.

For the MVP, this persona uses the same individual account model. Shared organizational workspaces are out of scope.

### 3.3 Operational Persona — Platform Operator

**Responsibilities:**
- Configure providers and model access.
- Monitor execution, usage, and errors.
- Investigate incidents.
- Operate releases and recovery procedures.

A dedicated operator dashboard is not required for the first usable MVP. Operational visibility may initially be provided through logs, metrics, and documented commands.

---

## 4. Product Goals and Success Metrics

### 4.1 Business Goals

**BG-001:** Reduce analyst time spent assembling evidence-backed briefs.

**BG-002:** Improve the traceability of factual findings.

**BG-003:** Make research workflows repeatable and inspectable.

**BG-004:** Establish measurable AI quality and reliability.

**BG-005:** Control variable inference and search costs.

### 4.2 Initial Success Metrics

All numerical targets below are **initial hypotheses**, not measured results.

| Metric | Proposed Target | Measurement |
|---|---|---|
| Analyst preparation time | 30% lower median time | Paired manual vs assisted tasks |
| Task completion rate | ≥90% | Completed eligible tasks / all eligible tasks |
| Structural citation validity | 100% | Valid citations / all emitted citations |
| Claim groundedness | ≥95% | Supported sampled claims / sampled checkable claims |
| Citation coverage | ≥95% | Cited checkable claims / all checkable claims |
| Report usefulness | ≥80% rated 4/5 or better | Reviewed useful reports / reviewed reports |
| End-to-end latency | p95 ≤240 seconds | Submission to terminal outcome |
| Mean variable cost | ≤USD 0.50 per started task | Estimated provider charges including failures |

### 4.3 Measurement Requirements

- Collect baseline results before claiming improvement.
- Include failed and timed-out tasks in operational statistics.
- Record evaluation dataset version, model version, graph version, prompt version, date, and sample size.
- Separate structural validation from semantic factual assessment.
- Report confidence intervals or uncertainty when supported by the sample.
- Avoid changing release thresholds after observing test results without documenting the decision.

### 4.4 Baselines

The product must compare:

1. **Manual baseline:** Analyst performs the research without AgentOps AI.
2. **Simple AI baseline:** A single model generates a report using a comparable evidence packet.
3. **AgentOps workflow:** The bounded LangGraph research workflow.

For controlled architecture comparisons, all AI approaches should use the same frozen evidence packet. Live retrieval performance must be evaluated separately.

---

## 5. Product Scope and Delivery Milestones

The project uses three release milestones to avoid confusing an early usable product with a production-ready service.

### 5.1 Milestone A — End-to-End MVP

**Objective:** Demonstrate one complete research journey on a local environment.

Required capabilities:

- Sign in using the selected authentication mechanism.
- Submit a research question.
- Persist and display task status.
- Execute planner, research, and writer steps with LangGraph.
- Use one approved search provider.
- Store evidence and source metadata.
- Generate a structured report.
- Reject fabricated or invalid citation references.
- View the completed report.
- Reopen research history.
- Run locally with Docker.
- Pass deterministic API and workflow tests.

This milestone proves feature completeness for the core workflow, not operational readiness for public users.

### 5.2 Milestone B — Controlled AWS Staging

**Objective:** Demonstrate a reliable cloud deployment.

Required capabilities:

- AWS deployment with HTTPS.
- Separate secrets and environment configuration.
- Versioned Docker images.
- Automated CI and deployment checks.
- Persistent PostgreSQL storage.
- Bounded execution with retries and deadlines.
- Task recovery after application or worker interruption.
- Logs, metrics, and traceable execution IDs.
- Owner-scoped authorization tests.
- Backup and restore procedures.
- Initial AI evaluation results.

### 5.3 Milestone C — Production-Oriented Pilot

**Objective:** Support a small, approved group of real users.

Required capabilities:

- Security review and remediation of blocking findings.
- Reliable deletion and retention behavior.
- Tested recovery and rollback procedures.
- Load and failure testing.
- Provider quotas and cost controls.
- AI release gates based on measured results.
- Incident response procedures.
- Operational ownership and documented limitations.
- Product and engineering release approval.

A single-instance AWS deployment may be sufficient for a controlled pilot but does not establish high availability or a production SLA.

---

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | User authentication and logout | Must |
| FR-002 | Owner-scoped access to tasks, reports, and evidence | Must |
| FR-003 | Create research tasks with validated question and optional scope | Must |
| FR-004 | Persist tasks before acknowledging successful submission | Must |
| FR-005 | Idempotent submission using user-scoped request keys | Must |
| FR-006 | Execute research asynchronously | Must |
| FR-007 | Display task status, stage, and safe error information | Must |
| FR-008 | Run Planner, Research, and Writer through LangGraph | Must |
| FR-009 | Restrict external access to approved search/retrieval adapters | Must |
| FR-010 | Store evidence with stable identifiers and provenance | Must |
| FR-011 | Produce schema-valid structured reports | Must |
| FR-012 | Validate citations against evidence belonging to the same task | Must |
| FR-013 | Distinguish factual evidence, synthesis, and uncertainty | Must |
| FR-014 | Provide paginated research history and report viewer | Must |
| FR-015 | Enforce task deadlines, model-call limits, and usage budgets | Must |
| FR-016 | Handle provider failures, malformed responses, and interruptions | Must |
| FR-017 | Allow explicit retry as a new linked task | Should |
| FR-018 | Persist execution events and usage estimates | Must |
| FR-019 | Support authorized deletion and retention cleanup | Pilot |
| FR-020 | Recover queued and interrupted tasks after restart | Staging |

**Priority definitions:**

- **Must:** Required for the end-to-end MVP.
- **Should:** Important enhancement, permitted after core MVP if necessary.
- **Staging:** Required before controlled AWS staging acceptance.
- **Pilot:** Required before onboarding real pilot users.

All FR-001 through FR-020 remain part of the overall product requirements. The priority field controls implementation sequencing, not whether a requirement can be silently discarded.

### 6.1 Detailed Acceptance Rules

**FR-003 — Input Validation**
- Empty questions are rejected.
- Questions exceeding configured limits are rejected.
- Optional geography, competitors, category, and time scope are validated.
- Invalid requests create no task.

**FR-005 — Idempotency**
- A client supplies a unique idempotency key per logical submission.
- The key is scoped to the authenticated user.
- Repeating the key with identical input returns the existing task.
- Reusing the key with different input returns a conflict.
- Concurrent identical submissions must not create duplicate tasks.
- Keys must be stored and checked with database-enforced uniqueness.

**FR-012 — Citation Validation**
- Every emitted citation references an evidence ID from the same task.
- Unknown, deleted, or cross-task IDs are rejected.
- Source URLs are derived from stored evidence, not invented by the writer.
- Invalid reports cannot transition a task to `completed`.
- Semantic support remains a separate evaluation concern.

**FR-016 — Failure Handling**
- Retryable errors must be distinguished from terminal errors.
- Retries cannot exceed execution budgets.
- Malformed output triggers at most one bounded repair attempt.
- Failed research must never generate invented evidence.
- Every accepted task must eventually reach a terminal outcome or a documented recoverable state.

---

## 7. User Stories and Acceptance Criteria

### US-001 — Secure Access

**As a market research analyst, I want to sign in so that my research remains private.**

Acceptance criteria:
- Unauthenticated access to protected data is rejected.
- A user can view only their own tasks, reports, and evidence.
- Expired sessions require reauthentication.
- Logout terminates access according to the selected authentication mechanism.
- Known identifiers do not bypass authorization.

### US-002 — Submit Research

**As an analyst, I want to submit a research question so that the system can investigate it.**

Acceptance criteria:
- Valid requests create a persistent queued task.
- The response includes a task identifier and status.
- Invalid questions return field-level validation errors.
- Optional scope is saved and supplied to the workflow.
- Duplicate submissions with the same idempotency key do not create duplicate work.

### US-003 — Track Research Progress

**As an analyst, I want to see research progress so that I understand what is happening.**

Acceptance criteria:
- The interface displays persisted status and current stage.
- Refreshing the browser does not lose task information.
- Failed tasks display actionable, sanitized messages.
- The UI never invents a percentage of work completed.
- Terminal outcomes are visible and distinguishable.

### US-004 — Review Evidence-Backed Reports

**As an analyst, I want to inspect source evidence before trusting a report.**

Acceptance criteria:
- A completed report includes required sections.
- Every citation maps to stored task evidence.
- The user can inspect citation excerpt, URL, and retrieval time.
- Search snippets are not misrepresented as full-page verification.
- Unsupported or uncertain findings are visibly identified.
- Fabricated citation IDs block publication.

### US-005 — Handle Insufficient Evidence

**As an analyst, I want the system to say when information is insufficient.**

Acceptance criteria:
- Tasks with inadequate evidence can end as `insufficient_evidence`.
- The interface explains the evidence gap.
- The system does not fabricate missing sources.
- Available evidence remains inspectable while retained.
- The user can submit a refined question.

### US-006 — Research History and Retry

**As an analyst, I want to revisit or retry previous research.**

Acceptance criteria:
- Research history is paginated and ordered.
- Previously completed reports open without regeneration.
- Retry creates a separate task linked to the original.
- Original reports and usage records remain unchanged.
- Retry receives new execution budgets.

### US-007 — Delete Research

**As an analyst, I want to delete research that I no longer need.**

Acceptance criteria:
- Only the owner can request deletion.
- Deleted tasks immediately become inaccessible.
- Pending work cannot republish deleted content.
- Related records are removed according to the approved retention policy.
- Backup retention limitations are disclosed.

---

## 8. End-to-End User Journey

1. User signs in.
2. User enters a research question and optional scope.
3. Backend validates input and creates a queued task.
4. Worker claims the task.
5. LangGraph Planner creates bounded subquestions.
6. Research step retrieves evidence through approved tools.
7. Evidence is normalized, deduplicated, and persisted.
8. Writer generates a structured report.
9. Report validator verifies schema and citation references.
10. Backend atomically persists the terminal result.
11. Frontend displays the report, citations, and limitations.
12. User can reopen the original task from research history.

### Failure Outcomes

- **Invalid input:** Request rejected before task creation.
- **Insufficient evidence:** Honest explanatory outcome.
- **Provider failure:** Retry within limits or terminal failure.
- **Timeout:** Task enters `timed_out`.
- **Invalid citations:** Report is withheld.
- **Worker interruption:** Task is recovered or safely failed.
- **Deleted task:** No further result publication is permitted.

---

## 9. Agentic AI Workflow Requirements

### 9.1 Initial LangGraph Design

The MVP uses a bounded, stateful workflow:

`Input Validation → Planner → Research → Evidence Validation → Writer → Report Validation → Persistence`

The Planner, Research, and Writer are specialized AI workflow components. They may be implemented as distinct nodes with different prompts, tools, and responsibilities.

This design is **multi-step agent orchestration**, not an unrestricted swarm of autonomous agents.

Additional agents must demonstrate measurable benefits before being introduced.

### 9.2 Planner Responsibilities

- Interpret the question and scope.
- Define bounded subquestions.
- Generate structured search queries.
- Record assumptions and ambiguities.
- Return schema-valid planning output.

The Planner cannot:
- Increase its own budget.
- Modify allowed tools.
- Change system instructions.
- Execute arbitrary external actions.

### 9.3 Research Responsibilities

- Call approved web-search and retrieval adapters.
- Collect source metadata and excerpts.
- Preserve retrieval timestamps.
- Deduplicate sources.
- Identify unavailable or conflicting evidence.
- Treat retrieved content as untrusted.

The Research component must not:
- Execute instructions found in retrieved pages.
- Access internal/private network addresses.
- Generate synthetic evidence to replace missing sources.
- Escalate tool permissions.

### 9.4 Writer Responsibilities

- Produce structured findings.
- Cite stored evidence IDs.
- Separate facts from interpretation.
- Explain limitations and uncertainties.
- Surface material conflicts.
- Abstain when evidence is insufficient.

### 9.5 Deterministic Validation

The application, not the LLM, owns:
- Tool authorization.
- Execution limits.
- Budget accounting.
- Citation ID resolution.
- Task ownership checks.
- State-transition validation.
- Report publication permissions.

A generated answer is not published merely because the model reports confidence.

### 9.6 Graph State Requirements

The workflow must use an explicit, typed state schema containing at least:

- Task identifier
- Research question
- Validated scope
- Structured research plan
- Evidence references
- Report draft or result
- Current stage
- Execution budget counters
- Error category
- Graph/prompt/model version metadata

Avoid storing secrets or unnecessary full source content inside graph state.

---

## 10. Research Task Lifecycle

### 10.1 States

| State | Meaning |
|---|---|
| `queued` | Accepted and waiting for execution |
| `running` | Claimed by an active worker |
| `completed` | Valid report persisted |
| `insufficient_evidence` | No valid supported report could be produced |
| `failed` | Unrecoverable error or exhausted retries |
| `timed_out` | Execution or queue deadline exhausted |

### 10.2 Valid Transitions

- `queued → running`
- `queued → failed`
- `queued → timed_out`
- `running → completed`
- `running → insufficient_evidence`
- `running → failed`
- `running → timed_out`

Terminal states are immutable.

Retry creates a new task, linked to the previous task rather than reopening its terminal state.

### 10.3 Worker Safety

Worker claiming must prevent two workers from owning the same task concurrently.

The design must include:
- Atomic task claiming.
- Lease or heartbeat ownership.
- Attempt identifiers.
- Stale-worker detection.
- Conditional final-state writes.
- Idempotent result publication.

After interruption, an incomplete task may be safely failed rather than resumed from the exact graph node during the MVP. Automatic mid-graph resumption is a later capability.

### 10.4 Deletion Semantics

Deletion is an authorization-protected lifecycle action, not a transition back from a terminal state.

The system must ensure deleted tasks:
- Become inaccessible immediately.
- Cannot be reclaimed by workers.
- Cannot have reports published by delayed results.
- Are cleaned up according to retention rules.

---

## 11. API Contract Requirements

Exact endpoint schemas will be defined during backend design. The MVP must support the following logical contracts.

| Method | Proposed Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Application liveness |
| `GET` | `/api/v1/ready` | Dependency readiness |
| `POST` | `/api/v1/research/tasks` | Submit research |
| `GET` | `/api/v1/research/tasks` | Research history |
| `GET` | `/api/v1/research/tasks/{task_id}` | Task status and metadata |
| `GET` | `/api/v1/research/tasks/{task_id}/report` | Structured report |
| `GET` | `/api/v1/research/tasks/{task_id}/evidence` | Task evidence |
| `POST` | `/api/v1/research/tasks/{task_id}/retry` | Create linked retry |
| `DELETE` | `/api/v1/research/tasks/{task_id}` | Delete research |

Authentication endpoints depend on the selected identity mechanism and must be finalized in an ADR.

### API Design Rules

- Use versioned API routes.
- Use Pydantic schemas for request/response validation.
- Use OpenAPI documentation.
- Return consistent, sanitized errors.
- Enforce authorization server-side.
- Use pagination for collection endpoints.
- Do not expose secrets, provider payloads, or stack traces.
- Use HTTP 202 for accepted asynchronous research submissions.
- Return a task identifier and a URL or documented path for status polling.
- Use an explicit conflict response when an idempotency key is reused with different input.

### Contract Verification

Frontend and backend tests must use compatible schemas. Breaking changes require explicit review and versioning.

---

## 12. Data Model and Persistence

PostgreSQL is the source of truth for research task lifecycle and persistent report data.

### 12.1 Core Entities

**User**
- ID
- Authentication subject
- Account metadata
- Created timestamp

**ResearchTask**
- ID
- Owner ID
- Question
- Scope
- Status
- Current stage
- Idempotency key and request fingerprint
- Retry parent ID
- Created, started, and completed timestamps
- Error category
- Deletion marker

**Execution**
- Task ID
- Attempt ID
- Graph version
- Prompt version
- Model identifier
- Configuration version
- Deadline
- Budget counters
- Usage estimates
- Worker lease metadata

**Evidence**
- ID
- Task ID
- Title
- Source URL
- Retrieved URL
- Excerpt
- Source acquisition method
- Retrieval timestamp
- Publication date, if known
- Content hash

**Report**
- ID
- Task ID
- Schema version
- Summary
- Findings
- Evidence references
- Synthesis
- Limitations
- Generation timestamp

**ExecutionEvent**
- ID
- Task ID
- Attempt ID
- Event type
- Stage
- Timestamp
- Duration
- Sanitized error category

### 12.2 Data Consistency Rules

- Use UTC timestamps.
- Enforce foreign keys and relevant uniqueness constraints.
- Use database transactions for final report publication.
- Ensure citation evidence belongs to the report's task.
- Prevent duplicate task creation using a database uniqueness constraint.
- Do not infer publication dates from retrieval dates.
- Preserve source provenance.
- Use Alembic for schema migrations.
- Do not persist hidden model chain-of-thought.

### 12.3 Initial Retention Hypotheses

| Data Type | Proposed Retention |
|---|---|
| Tasks, reports, evidence | 90 days |
| Operational logs | 30 days |
| Encrypted backups | Up to 30 days |
| Deleted active records | Purged within 24 hours |

These are proposed values requiring security/product approval before real-user onboarding.

Deleted records may remain in backups until backup expiration. Restoration must account for deletion records before data becomes accessible again.

---

## 13. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-001 | Architecture | Modular monolith with explicit module boundaries |
| NFR-002 | API Performance | Target p95 ≤1 second for non-generation endpoints under defined test load |
| NFR-003 | Research Performance | Target p95 ≤240 seconds submission-to-terminal |
| NFR-004 | Durability | Acknowledged tasks and reports survive process restarts |
| NFR-005 | Recovery | Stale running tasks recover or reach a safe terminal state |
| NFR-006 | Security | TLS, least privilege, authorization, protected secrets |
| NFR-007 | Observability | Correlated logs, metrics, stage events, usage and failure categories |
| NFR-008 | Testability | Deterministic tests without live cloud credentials |
| NFR-009 | Deployment | Versioned artifacts, documented migration and deployment workflow |
| NFR-010 | Accessibility | Keyboard navigation, labeled controls, visible focus and status announcements |
| NFR-011 | Maintainability | Track graph, prompt, model and schema versions |
| NFR-012 | Availability | Establish a measured pilot baseline before adopting an SLO |

### 13.1 Reliability Acceptance

- Restarting the API must not erase acknowledged tasks.
- Killing a worker must not leave a task running indefinitely.
- Replayed messages must not publish duplicate reports.
- Failed readiness checks must prevent an unhealthy instance from being treated as ready.
- Deployment rollback must be tested with database schema compatibility.

### 13.2 Performance Acceptance

Initial test conditions:

- 10 authenticated concurrent users.
- Up to 5 active research tasks.
- Defined provider conditions.
- Report p50, p95, failures, queue delays and sample sizes.

Targets remain hypotheses until validated.

---

## 14. AI Evaluation and Quality Assurance

### 14.1 Evaluation Dataset

Create an initial versioned dataset of approximately 40 research questions, including:

- Competitor comparisons
- Product positioning
- Market trends
- Ambiguous requests
- Sparse evidence
- Conflicting sources
- False premises
- Inaccessible sources
- Temporal questions
- Prompt-injection cases

Maintain a held-out subset that is not used for prompt tuning.

### 14.2 Evaluation Conditions

Compare:

1. Manual analyst baseline.
2. Simple single-model baseline.
3. AgentOps AI bounded research workflow.

Keep model, source packet, task instructions, and output expectations comparable when isolating differences in orchestration.

### 14.3 Core Metrics

**Structural Citation Validity**

`valid citations / all emitted citations`

A citation is structurally valid only when its evidence reference exists and belongs to the current task.

**Citation Coverage**

`checkable factual claims with citations / all checkable factual claims`

Requires a defined annotation rubric.

**Groundedness**

`checkable claims supported by cited evidence / all sampled checkable claims`

Requires semantic judgment of the cited evidence, including dates, numbers, and scope.

**Task Completion Rate**

`eligible tasks completed successfully / all eligible submitted tasks`

Failures and timeouts remain in the denominator.

**Report Usefulness**

`reports rated at least 4/5 / reviewed reports`

**Task Cost**

Track estimated provider charges for every started task, including failures and retries.

**Task Latency**

Measure from task submission to terminal outcome, including queue time.

### 14.4 Evaluation Method

- Use frozen provider fixtures for reproducible tests.
- Maintain separate live-provider evaluation.
- Use human review for semantic quality.
- Use LLM-based graders only as supporting evidence until calibrated.
- Record evaluator disagreements.
- Preserve representative failures.
- Version prompts, datasets, and configurations.
- Compare against baseline before promoting an AI workflow change.

### 14.5 Initial AI Release Gates

Proposed targets:

- 100% structural citation validity.
- ≥95% groundedness on reviewed factual claims.
- ≥90% completion rate on eligible tasks.
- No fabricated citation accepted by validation.
- No observed unauthorized tool execution in defined security tests.
- No cross-user information disclosure in defined authorization tests.

These gates are initial hypotheses. Final thresholds must be reviewed after baseline measurements.

Passing these checks does not guarantee factual correctness or production readiness.

---

## 15. Security and Responsible AI Requirements

### 15.1 Authentication and Authorization

- Use a maintained authentication solution.
- Avoid custom cryptographic implementations.
- Enforce resource ownership at the API and data access layers.
- Validate session expiry and logout.
- Prevent cross-user evidence access.
- Apply rate limits and submission quotas.

### 15.2 Prompt Injection

All external information is untrusted, including:
- Search snippets
- Web page content
- Titles
- Metadata
- User-controlled source descriptions

Required protections:

- Keep model instructions separate from retrieved data.
- Validate tool names and arguments against strict schemas.
- Enforce authorization outside the model.
- Never accept retrieved text as permission to change budgets or access credentials.
- Avoid exposing secrets in model context.
- Test malicious instructions embedded in sources.
- Sanitize frontend-rendered content.

Prompt wording alone is not a security boundary.

### 15.3 Network and Tool Safety

The retrieval system must:
- Permit only approved public HTTP(S) destinations.
- Reject loopback, private, link-local and cloud metadata destinations.
- Revalidate resolved addresses and redirects.
- Limit content type, size, and retrieval time.
- Avoid arbitrary browser automation or code execution.
- Respect source access restrictions and provider terms.
- Prevent model-generated destinations from bypassing access policy.

### 15.4 Privacy and Secrets

- Use protected runtime secret configuration.
- Exclude credentials and research content from default logs.
- Minimize confidential data sent to external providers.
- Review provider data-processing and retention settings.
- Encrypt traffic and persisted data using approved infrastructure controls.
- Document credential rotation and incident response procedures.

### 15.5 Human Oversight

Research reports are decision-support artifacts.

The system must disclose:
- Uncertainty
- Missing evidence
- Conflicting sources
- Retrieval dates
- Unverified assumptions
- Scope limitations

No autonomous purchasing, messaging, account modification, or other consequential external actions are permitted in the MVP.

---

## 16. Cost, Resource and Execution Budgets

The following proposed defaults are configurable and require validation.

| Control | Initial Default |
|---|---|
| Question length | 4,000 characters |
| Optional scope length | 2,000 characters |
| Planned subquestions | Maximum 4 |
| Model invocations | Maximum 8 |
| Search calls | Maximum 6 |
| Page retrieval calls | Maximum 12 |
| Evidence records | Maximum 20 |
| Total model tokens | Maximum 40,000 |
| Estimated variable cost ceiling | USD 1.00 per task |
| Model timeout | 45 seconds |
| Search/retrieval timeout | 15 seconds |
| Running-task deadline | 180 seconds |
| Maximum queue wait | 60 seconds |
| Retry per eligible operation | Maximum 1 |
| Concurrent running tasks | 5 |
| Per-user running tasks | 1 |
| Pending queue capacity | 50 |

### Budget Enforcement

- Retries consume the same global task budgets.
- A call must not start if its budget is exhausted.
- Per-call timeout cannot exceed the remaining task deadline.
- Estimate token usage and costs before dispatch.
- Reconcile estimates with provider usage when available.
- Reject unknown model pricing rather than assuming free usage.
- Report estimated costs separately from actual cloud billing.
- Handle budget exhaustion through a safe terminal outcome.

### Cost Management on AWS

Before enabling paid AWS resources:

- Establish a monthly budget.
- Configure cost alerts.
- Review EC2, storage, network, Bedrock, search, and logging charges.
- Apply request limits.
- Document shutdown and cleanup procedures.
- Avoid always-on GPU instances for the initial system.

Budgets and alerts improve visibility but must not be treated as guaranteed hard spending caps.

---

## 17. AWS Deployment and Operations Requirements

### 17.1 Initial Deployment Architecture

The first AWS implementation targets:

- EC2 Linux instance
- Dockerized FastAPI application
- Separate background worker process
- React frontend
- PostgreSQL persistence
- Amazon ECR
- Amazon Bedrock
- CloudWatch
- HTTPS reverse proxy
- GitHub Actions CI/CD

The exact deployment topology will be finalized through an ADR.

A single EC2 deployment can support an initial demonstration, but it is a single point of failure.

### 17.2 Environment Separation

The project must distinguish:

- Local development
- Automated testing
- AWS staging
- Approved production/pilot environment

Environment-specific configuration, credentials, database data, and deployment permissions must be separated.

### 17.3 CI/CD Requirements

The pipeline must support:

1. Formatting and linting.
2. Type checks where configured.
3. Unit tests.
4. PostgreSQL integration tests.
5. Deterministic LangGraph tests.
6. Security scanning.
7. Docker build verification.
8. Versioned image publishing.
9. Staging deployment.
10. Post-deployment smoke tests.
11. Controlled production promotion.

AI-specific changes must additionally run applicable evaluation regressions.

### 17.4 Observability Requirements

Track:

- Request and task IDs.
- Workflow stage transitions.
- Tool-call counts.
- Provider errors.
- Token usage.
- Estimated costs.
- Queue latency.
- Task duration.
- Timeout and retry counts.
- Worker failures.
- Deployment version.

Logs must exclude secrets and raw research content by default.

### 17.5 Recovery and Release Requirements

Before pilot approval:

- Test application rollback.
- Validate database migration compatibility.
- Verify backup restoration.
- Document incident response.
- Demonstrate recovery from worker interruption.
- Confirm monitoring and alerting behavior.
- Review outstanding security findings.

---

## 18. Risks, Dependencies and Decisions

### 18.1 Project Risks

| ID | Risk | Mitigation |
|---|---|---|
| R-001 | Hallucinated factual claims | Evidence validation and evaluation |
| R-002 | Fabricated citations | Deterministic citation resolution |
| R-003 | Prompt injection | External tool authorization and security tests |
| R-004 | Unsafe URL retrieval | SSRF protections and destination validation |
| R-005 | Excessive LLM costs | Bounded budgets and provider usage tracking |
| R-006 | Worker crashes | Durable task state and recovery rules |
| R-007 | Data leakage | Owner-scoped access and sanitized logging |
| R-008 | Outdated sources | Provenance and date tracking |
| R-009 | Evaluation overfitting | Held-out and live evaluation sets |
| R-010 | AWS cost overruns | Budgets, alerts, limits and resource cleanup |
| R-011 | Insufficient source coverage | Appropriate abstention and transparent limitations |
| R-012 | Overly complex architecture | Modular monolith and measured agent expansion |

### 18.2 External Dependencies

- Amazon Bedrock model availability and permissions.
- Approved web-search provider.
- Public source availability.
- PostgreSQL runtime.
- AWS account and deployment permissions.
- Human reviewers for semantic AI evaluation.
- Domain and HTTPS configuration, if public access is enabled.

### 18.3 Architecture Decisions to Finalize

The following must be resolved during architecture design:

**ADR-001 — Modular Monolith Architecture**

Why the initial product uses a modular monolith instead of microservices.

**ADR-002 — Authentication Strategy**

Identity provider or maintained authentication library, including session/logout semantics.

**ADR-003 — Async Task Execution and Recovery**

Worker, queue, task claiming, state persistence, and restart recovery.

**ADR-004 — LangGraph State and Agent Boundaries**

Typed state, graph nodes, allowed tools, validation, and checkpoint strategy.

**ADR-005 — AWS Deployment Architecture**

EC2, database location, secrets, networking, ECR, monitoring, and release flow.

**ADR-006 — LLM and Search Provider Selection**

Bedrock model, region, quotas, cost characteristics, search provider, and retrieval policy.

**ADR-007 — Security and Data Retention**

Retention, encryption, deletion, backups, and audit logging.

No pending ADR should be silently treated as an implemented technical decision.

---

## 19. Definition of Done and Roadmap

### 19.1 Milestone A — MVP Definition of Done

- [ ] User authentication and owner-scoped authorization work.
- [ ] A user can submit a valid research question.
- [ ] A research task is persisted before acknowledgment.
- [ ] LangGraph executes the core bounded workflow.
- [ ] Approved search tools return evidence with provenance.
- [ ] Invalid citations cannot be published.
- [ ] A structured report can be viewed in the frontend.
- [ ] Research history persists across restarts.
- [ ] Core API and graph tests pass.
- [ ] Local Docker startup is documented and verified.

### 19.2 Milestone B — AWS Staging Definition of Done

- [ ] Versioned Docker image is built and published.
- [ ] CI pipeline passes required software/security checks.
- [ ] Application deploys successfully to AWS staging.
- [ ] HTTPS is configured.
- [ ] Runtime secrets are protected.
- [ ] Database migrations are versioned and verified.
- [ ] Task timeouts and budget limits are enforced.
- [ ] Worker interruption recovery is tested.
- [ ] Health and readiness endpoints pass.
- [ ] Logs and operational metrics are available.
- [ ] Rollback and database restore procedures are exercised.

### 19.3 Milestone C — Controlled Pilot Definition of Done

- [ ] Cross-user authorization tests pass.
- [ ] Prompt-injection and unsafe retrieval tests pass.
- [ ] Retention cleanup and deletion are verified.
- [ ] AI evaluation results are recorded and reviewed.
- [ ] Release gates are met or formally revised.
- [ ] Performance and failure tests are completed.
- [ ] Blocking security risks are remediated or explicitly assessed for the pilot.
- [ ] Incident runbook is approved.
- [ ] Data handling and provider terms are reviewed.
- [ ] Product and Engineering approve pilot release.

### 19.4 Future Roadmap

**Phase 1 — Improve Evidence Quality**
- More robust source selection.
- Improved contradiction handling.
- Expanded evaluation datasets.
- Better source freshness tracking.

**Phase 2 — Advanced Agentic AI**
- Dedicated verification agent.
- Conditional research replanning.
- Human-in-the-loop approval.
- More sophisticated recovery and checkpointing.
- Measured multi-agent versus single-agent experiments.

**Phase 3 — Enterprise Capabilities**
- Shared workspaces.
- Team roles and permissions.
- Private document retrieval.
- Report export and collaboration.
- Scheduled research workflows.

**Phase 4 — Advanced MLOps and Cloud**
- ML experiment tracking.
- Model and prompt release registry.
- Automated AI quality regression gates.
- Infrastructure as Code.
- ECS/RDS migration if justified.
- Advanced monitoring and deployment strategies.

### 19.5 Sprint S00 Acceptance

Sprint S00 product planning is complete when:

- [ ] PRD is reviewed and approved.
- [ ] Architecture overview is documented.
- [ ] Required architecture decisions and unresolved questions are recorded.
- [ ] `AGENTS.md` is created.
- [ ] Initial engineering backlog is defined.
- [ ] Sprint report and handoff files are updated.
- [ ] Documentation is committed to Git.
- [ ] The next sprint has an unambiguous starting point.

---

## Appendix A — Initial Sprint Roadmap

| Sprint | Planned Deliverable |
|---|---|
| S00 | Product requirements, architecture, engineering rules |
| S01 | FastAPI, React, Docker project foundation |
| S02 | PostgreSQL, authentication, migrations |
| S03 | Research task API and dashboard |
| S04 | LangGraph workflow baseline |
| S05 | Specialized planner, research and writer nodes |
| S06 | Search integration and evidence validation |
| S07 | Worker reliability and bounded execution |
| S08 | AI evaluation and security testing |
| S09 | CI/CD and AWS staging preparation |

One sprint corresponds to one planned working day. Scope may move to the following sprint when acceptance criteria are not met.

Sprint reports must record actual verified accomplishments rather than automatically marking all planned work as completed.

## Appendix B — Document Governance

The PRD is the authoritative product requirements reference.

Engineering design documents and ADRs define implementation decisions but must not silently contradict the PRD.

Any material change to scope, user access, data retention, security, evaluation thresholds, or external action permissions requires documented product and engineering review.

**Document status:** Approved as a planning baseline for architecture work. Implementation and production readiness remain unverified.