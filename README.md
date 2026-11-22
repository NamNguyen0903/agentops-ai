# AgentOps AI

### Evidence-Grounded Agentic Market & Competitor Research Platform

**Production-Oriented AI Engineering Portfolio Project**

AgentOps AI is an AI-powered research platform designed to help market analysts investigate competitors, products, and industry trends through a structured, evidence-grounded research workflow.

The platform is designed to combine **LangGraph-based AI orchestration**, controlled web research, verifiable citations, and a modern full-stack application to produce structured reports that users can inspect and evaluate.

Rather than relying on a single unconstrained LLM response, AgentOps AI is designed around specialized research steps, explicit evidence validation, persistent execution state, and measurable AI quality.

> **Project status (2026-11-22):** S01 scope CLOSED (verification partial); S02 IN_PROGRESS. FastAPI, React/Vite, Docker Compose/PostgreSQL and SQLAlchemy/Alembic infrastructure exist. Backend pytest **31/31 passed**; application database readiness and role checks have observed evidence. Authentication, migration revisions, research agents, AWS deployment and production readiness remain unimplemented/unverified.

---

## 1. Project Overview

Market and competitor research requires collecting information from multiple sources, comparing claims, tracking source credibility, and transforming findings into actionable reports.

Traditional research workflows can be time-consuming and difficult to reproduce. General-purpose AI systems may accelerate analysis, but they can also produce unsupported claims, fabricated citations, or results that are difficult to audit.

AgentOps AI is designed to address these challenges through:

- Structured research planning.

- Controlled external information retrieval.

- Specialized LangGraph workflow components.

- Persistent evidence and source metadata.

- Deterministic citation-reference validation.

- Transparent reporting of uncertainty and limitations.

- Observable, bounded background execution.

- Reproducible AI evaluation.

### Product Objective

Enable users to submit a research question and receive a structured, evidence-backed report while retaining the ability to verify the information used to generate its findings.

### Intended Users

- Market Research Analysts

- Competitive Intelligence Analysts

- Product Managers

- Business Strategy Teams

The initial MVP supports individual authenticated accounts. Shared workspaces and advanced enterprise collaboration are outside its initial scope.

---

## 2. Planned Features

### Research Management

- User authentication and resource ownership.

- Research task creation with optional scope.

- Asynchronous research execution.

- Task status and execution-stage tracking.

- Research history and report viewing.

- Explicit retries and safe failure handling.

### Agentic AI Research

- Structured planning through a Planner component.

- Research execution through approved search and retrieval adapters.

- Evidence normalization and validation.

- Structured report generation through a Writer component.

- Schema and citation-reference validation.

- Bounded repair when generated output is invalid.

- Transparent handling of insufficient evidence.

### Evidence and Reports

- Persistent source metadata.

- Stable evidence identifiers.

- Citation-to-evidence traceability.

- Clear separation of factual findings and model-generated synthesis.

- Source timestamps and limitations.

- Prevention of publication when citation references are invalid.

### Reliability and Operations

- Durable task persistence in PostgreSQL.

- Dedicated background worker process.

- Idempotent task submission.

- Execution deadlines and usage budgets.

- Worker leases and stale-attempt protection.

- Structured logs and operational metrics.

- Containerized environments and CI/CD verification.

These are target capabilities. Their availability must be confirmed through future implementation and testing.

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript | Research dashboard and report viewer |
| Backend | Python, FastAPI | REST API and application services |
| Validation | Pydantic | Typed data and API contracts |
| AI Orchestration | LangGraph | Stateful research workflow |
| LLM Integration | LangChain, Amazon Bedrock | Controlled model inference |
| Database | PostgreSQL | Tasks, evidence, reports and execution records |
| ORM | SQLAlchemy | Persistence and database access |
| Migrations | Alembic | Schema version management |
| Containers | Docker, Docker Compose | Local development and deployment |
| Testing | pytest and supporting tooling | Backend and workflow verification |
| CI/CD | GitHub Actions | Automated tests and releases |
| AWS Runtime | Amazon EC2 | Initial staging environment |
| Container Registry | Amazon ECR | Versioned container images |
| Observability | Amazon CloudWatch | Logs, metrics and monitoring |
| Infrastructure | Terraform (future) | Infrastructure as Code |

Technology choices are based on the current architecture proposal. Exact dependency versions and external providers will be finalized during implementation.

---

## 4. System Architecture

AgentOps AI follows a proposed **modular monolith architecture** with separate API and background worker processes.

The design aims to preserve clear module boundaries without introducing unnecessary distributed-system complexity during the initial release.

### High-Level Architecture

```mermaid

flowchart TB

    User["Research Analyst"]

    UI["React + TypeScript"]

    API["FastAPI"]

    DB[("PostgreSQL")]

    Worker["Background Research Worker"]

    Graph["LangGraph Workflow"]

    Bedrock["Amazon Bedrock"]

    Search["Approved Web Search Provider"]

    Sources["Public Web Sources"]

    Report["Stored Research Report"]

    User --> UI

    UI -->|"REST API"| API

    API -->|"Persist research task"| DB

    Worker -->|"Claim queued task"| DB

    Worker --> Graph

    Graph -->|"LLM inference"| Bedrock

    Graph -->|"Search queries"| Search

    Graph -->|"Restricted retrieval"| Sources

    Worker -->|"Persist evidence and validated report"| DB

    API -->|"Read saved result"| DB

    API --> Report

    Report --> UI

```

### Architectural Principles

1. **Modular Monolith:** Related business capabilities reside in clearly separated modules within a shared backend codebase.

2. **Asynchronous Execution:** Research tasks are processed outside HTTP request handling.

3. **Durable State:** PostgreSQL is authoritative for application task lifecycle and persisted outputs.

4. **Bounded AI:** Research operations have configurable cost, token, retry, and execution limits.

5. **Evidence Validation:** Invalid or cross-task citation references cannot be published.

6. **Security Boundaries:** Model outputs cannot independently authorize tools or access protected resources.

7. **Testability:** Model and search providers can be replaced by deterministic fixtures during automated testing.

For detailed architecture decisions, see [System Architecture](docs/architecture/overview.md) and [ADR-0001](docs/adr/0001-architecture.md).

---

## 5. LangGraph Research Workflow

The initial workflow is designed as a bounded sequence of specialized components.

```mermaid

flowchart TD

    Start["Research Question"] --> Planner["Planner"]

    Planner --> Research["Research"]

    Research --> Evidence["Evidence Validator"]

    Evidence --> Decision{"Sufficient evidence?"}

    Decision -->|"No"| Insufficient["Insufficient Evidence"]

    Decision -->|"Yes"| Writer["Writer"]

    Writer --> Validator["Report Validator"]

    Validator -->|"Valid"| Publish["Publish Report"]

    Validator -->|"Invalid and repair available"| Repair["Repair Writer"]

    Repair --> Validator

    Validator -->|"Invalid after repair"| Failed["Failed"]

    Publish --> Complete["Completed"]

```

### Planner

Interprets the research question, defines subquestions, identifies assumptions, and produces structured search queries.

### Research

Executes permitted search and retrieval operations while collecting evidence, source metadata, and coverage information.

### Evidence Validator

Checks evidence structure, provenance, references, and whether the collected material is sufficient to continue.

### Writer

Generates a structured report from approved evidence while distinguishing findings, synthesis, and uncertainty.

### Report Validator

Validates report structure and resolves citations against evidence stored for the same research task.

### Repair Writer

Performs at most one authorized corrective generation attempt when the workflow allows it.

The application enforces the repair, token, time, tool-call, and cost limits.

### Expected Report Structure

The planned report includes:

- Executive summary

- Research scope

- Key findings

- Supporting evidence and citations

- Interpretation and implications

- Conflicting information

- Limitations and uncertainty

- Sources and retrieval metadata

**Important:** Structural citation validation verifies that a citation refers to stored evidence. It does not independently prove that the source is accurate or that the cited material semantically supports the claim. Semantic groundedness is evaluated separately.

---

## 6. Repository Structure

The repository is organized as a monorepo.

```text

agentops-ai/

├── apps/

│   ├── api/                    # FastAPI backend

│   └── web/                    # React frontend

│

├── packages/

│   └── agents/

│       ├── graphs/             # LangGraph definitions

│       ├── nodes/              # Workflow components

│       ├── tools/              # Approved tool adapters

│       ├── prompts/            # Versioned prompts

│       └── schemas/            # Typed agent data structures

│

├── tests/

│   ├── unit/

│   ├── integration/

│   └── e2e/

│

├── evaluations/

│   ├── datasets/

│   └── reports/

│

├── infra/

│   ├── docker/

│   └── terraform/

│

├── docs/

│   ├── product/

│   │   └── PRD.md

│   ├── architecture/

│   │   └── overview.md

│   ├── adr/

│   │   └── 0001-architecture.md

│   ├── handoff/

│   │   └── CURRENT_STATE.md

│   └── sprints/

│       ├── INDEX.md

│       └── S00.md

│

├── .github/

│   └── workflows/

│

├── .env.example

├── .gitignore

├── AGENTS.md

└── README.md

```

Some directories may currently contain no tracked files. Application modules and infrastructure definitions will be introduced incrementally during implementation.

---

## 7. Research Task Lifecycle

Research tasks follow a controlled state model.

| Status | Description |
|---|---|
| `queued` | Accepted and awaiting execution |
| `running` | Claimed by an active worker |
| `completed` | Valid report successfully persisted |
| `insufficient_evidence` | Research could not establish enough usable evidence |
| `failed` | Unrecoverable execution or validation error |
| `timed_out` | Queue or execution deadline exceeded |

Terminal outcomes are immutable.

An explicit retry creates a new linked task instead of reopening an old terminal task.

The system is designed to protect against duplicate task submission, stale workers, invalid report publication, and deleted-task restoration.

---

## 8. API Design

The proposed backend exposes versioned REST endpoints.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| GET | `/api/v1/ready` | Readiness check |
| POST | `/api/v1/research/tasks` | Submit research |
| GET | `/api/v1/research/tasks` | Research history |
| GET | `/api/v1/research/tasks/{task_id}` | Task status |
| GET | `/api/v1/research/tasks/{task_id}/report` | Stored report |
| GET | `/api/v1/research/tasks/{task_id}/evidence` | Evidence records |
| POST | `/api/v1/research/tasks/{task_id}/retry` | Create linked retry |
| DELETE | `/api/v1/research/tasks/{task_id}` | Request deletion |

Authentication endpoints depend on the mechanism selected in ADR-0002.

A successful research submission is expected to return HTTP `202 Accepted` after the task has been durably stored.

These are proposed API contracts, not currently available endpoints.

---

## 9. AI Evaluation Strategy

AgentOps AI is intended to measure research quality rather than rely solely on subjective demonstrations.

### Evaluation Conditions

The project will compare:

1. **Manual baseline:** Analyst research without AgentOps AI.

2. **Simple AI baseline:** A single model operating on comparable evidence.

3. **AgentOps AI:** The bounded LangGraph research workflow.

### Planned Evaluation Metrics

| Metric | Initial Hypothesis |
|---|---|
| Structural citation validity | 100% |
| Answer groundedness | ≥95% |
| Citation coverage | ≥95% |
| Eligible task completion rate | ≥90% |
| Report usefulness | ≥80% rated at least 4/5 |
| End-to-end latency | p95 ≤240 seconds |
| Estimated variable cost | Mean ≤USD 0.50 per started task |

These targets have not yet been measured.

### Evaluation Practices

- Version evaluation datasets.

- Use deterministic evidence fixtures.

- Maintain held-out test cases.

- Run separate live-provider evaluations.

- Record failures and timeouts.

- Evaluate citation support at claim level.

- Compare prompt, model, and workflow versions.

- Use human review for semantic groundedness.

- Document limitations and uncertainty.

---

## 10. Security and Reliability

### Security Design

The proposed application includes:

- Authenticated, owner-scoped resource access.

- Protected configuration and credentials.

- Server-side tool authorization.

- Strict model-output validation.

- Prompt-injection defenses.

- Restricted public-web retrieval.

- SSRF and redirect protections.

- Safe structured report rendering.

- Sanitized logs and API error messages.

### Reliability Design

The backend is designed to support:

- Durable task admission.

- Idempotent requests.

- Database-backed task claiming.

- Worker leases and heartbeat tracking.

- Conditional writes against stale execution attempts.

- Bounded retries and deadlines.

- Transactional report publication.

- Recovery after worker interruption.

- Persistent usage and error records.

External model and search operations cannot be guaranteed to execute exactly once. Their usage and costs must be accounted for conservatively when outcomes are unknown.

---

## 11. Local Development

### Current Availability (2026-11-22)

The local FastAPI/React/Vite/Docker Compose application has been demonstrated. The PostgreSQL 17 service and API database readiness have been exercised. Backend test suite output: **31 passed, 1 warning in 6.47 seconds** on 2026-11-22. The warning is a Starlette `httpx` TestClient deprecation warning, not a failure.

Current verified HTTP contracts:

- `GET http://127.0.0.1:8000/api/v1/health` → HTTP 200, `{"status":"ok","service":"agentops-api"}`.
- `GET http://127.0.0.1:8000/api/v1/ready` → HTTP 200, `{"status":"ready","checks":{"database":"ok"}}`, when PostgreSQL was healthy.
- `GET http://127.0.0.1:5173/api/v1/ready` → HTTP 200 through Vite proxy.

Authentication and research-task endpoints are **not implemented**. Readiness checks database connectivity, not an approved schema version.

### Environment Configuration

A private local `.env.postgres` is used with `docker compose --env-file .env.postgres`. Use `postgres.env.example` (where present) as a variable guide, and generate strong, distinct bootstrap and application credentials. **Do not commit `.env.postgres`** or paste its values into documentation, screenshots or logs. The database is not exposed through a host port by default.

### Start and Inspect Services

From repository root:

```bash
docker compose --env-file .env.postgres config --quiet
docker compose --env-file .env.postgres up -d --build
docker compose --env-file .env.postgres ps
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/ready
curl -i http://127.0.0.1:5173/api/v1/ready
```

To verify existing PostgreSQL runtime-role checks:

```bash
docker compose --env-file .env.postgres exec -T db bash /opt/agentops/verify-app.sh
```

To stop services **without deleting persistent data**:

```bash
docker compose --env-file .env.postgres stop
```

Do not run `docker compose down -v` unless you intentionally want to destroy local database data.

### Backend Tests and Alembic Discovery

```bash
cd apps/api
python -m pip install -e '.[dev]'
python -m pytest -v
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
```

At the AG-003.3A checkpoint, Alembic has no revision files; `heads`/`history` correctly return no migration history. `alembic/env.py` temporarily refuses migration execution until schema, role and authorization are approved. **Do not run** `alembic revision --autogenerate`, `alembic upgrade head` or `alembic stamp head` as setup steps now.

### Integration Smoke

With services running, from repository root:

```bash
python3 scripts/test_integration.py
```

The user reported this smoke check and a SQLAlchemy read-only PostgreSQL transaction passed on 2026-11-22; the exact recent output was not archived in the documentation.

See [S02 report](docs/sprints/S02.md) and [CURRENT_STATE](docs/handoff/CURRENT_STATE.md) for detailed evidence and blockers.

## 12. AWS Deployment Strategy

The initial cloud architecture targets a controlled AWS staging environment.

### Proposed AWS Services

| Service | Responsibility |
|---|---|
| Amazon EC2 | Initial container runtime |
| Amazon ECR | Versioned Docker image registry |
| Amazon Bedrock | Approved LLM inference |
| Amazon CloudWatch | Logs, metrics and operational alarms |
| Encrypted off-host storage | Database backup retention |

The initial staging topology proposes a single EC2 instance running separate application and worker processes with PostgreSQL on persistent encrypted storage.

This deployment model has a single-host failure domain and does not provide automatic failover or a high-availability SLA.

Future infrastructure may include Amazon RDS, ECS, and Terraform-managed deployments when engineering and operational requirements justify them.

---

## 13. Engineering Workflow

Development follows a human-controlled, ticket-based process.

### Responsibilities

| Role | Responsibility |
|---|---|
| Developer | Creates files, runs commands, tests, reviews, commits and deploys |
| ChatGPT | Tech Lead, technical guidance, architecture and code review |
| Codex | Generates code, tests and documentation for manual copying |

Codex does not directly modify repository files, run Terminal commands, commit, push, or deploy under the project's working agreement.

### Session Startup

At the beginning of a new development session:

1. Read [AGENTS.md](AGENTS.md).

2. Read [CURRENT_STATE.md](docs/handoff/CURRENT_STATE.md).

3. Read [Sprint Index](docs/sprints/INDEX.md).

4. Review the active sprint report.

5. Consult the PRD and relevant ADRs.

6. Verify the current Git state before continuing.

### Development Principles

- Work on one small ticket at a time.

- Review generated changes before accepting them.

- Use real test evidence rather than assumed success.

- Preserve unrelated work.

- Record unresolved issues.

- Update the sprint report and handoff.

- Commit and push only after review.

---

## 14. Development Roadmap

Each sprint represents one planned working day. Unfinished work is carried forward explicitly rather than silently marked complete.

| Sprint | Planned Goal | Status |
|---|---|---|
| S00 | PRD, architecture, repository and engineering rules | PENDING_CLOSEOUT |
| S01 | FastAPI, React and Docker foundation | CLOSED — PARTIALLY_VERIFIED |
| S02 | PostgreSQL, authentication and migrations | IN_PROGRESS — PARTIALLY_VERIFIED |
| S03 | Research task APIs and dashboard | Planned |
| S04 | Single-agent LangGraph baseline | Planned |
| S05 | Specialized planner, research and writer nodes | Planned |
| S06 | Web search, evidence storage and citations | Planned |
| S07 | Worker reliability, deadlines and budgets | Planned |
| S08 | AI evaluation and security testing | Planned |
| S09 | CI/CD and AWS staging preparation | Planned |

The full roadmap and sprint statuses are maintained in [Sprint Index](docs/sprints/INDEX.md).

### Future Enhancements

Potential post-MVP capabilities include:

- Additional specialized AI agents.

- Human-in-the-loop research approval.

- Private document retrieval and RAG.

- Research collaboration and shared workspaces.

- Scheduled market monitoring.

- Report export and annotations.

- Advanced evaluation dashboards.

- More sophisticated model routing.

- Managed AWS infrastructure and improved availability.

These capabilities are outside the initial MVP unless explicitly approved through product planning.

---

## 15. Project Documentation

| Document | Purpose |
|---|---|
| [Product Requirements Document](docs/product/PRD.md) | Product scope and acceptance criteria |
| [System Architecture](docs/architecture/overview.md) | Architecture and technical boundaries |
| [ADR-0001 — Modular Monolith](docs/adr/0001-architecture.md) | Initial architectural decision proposal |
| [Engineering Working Agreement](AGENTS.md) | Coding rules and collaboration process |
| [Current Project State](docs/handoff/CURRENT_STATE.md) | Active ticket and resume checkpoint |
| [Sprint Index](docs/sprints/INDEX.md) | Roadmap and sprint history |
| [Sprint S00 Report](docs/sprints/S00.md) | Product planning and foundation work |
| [Sprint S01 Report](docs/sprints/S01.md) | Closed S01 scope, verification carryover |
| [Sprint S02 Report](docs/sprints/S02.md) | Active database/ORM/authentication sprint evidence |
| [ADR-0002 — Authentication](docs/adr/0002-authentication.md) | Proposed identity and session decisions; approval pending |

### Decision Records

The following architectural decisions remain pending:

- [ADR-0002 — Authentication Strategy](docs/adr/0002-authentication.md) — PROPOSED (reviewed; approval pending)

- ADR-0003 — Async Execution and Recovery

- ADR-0004 — LangGraph State and Agent Boundaries

- ADR-0005 — AWS Deployment

- ADR-0006 — Model and Search Provider Selection

- ADR-0007 — Security and Data Retention

Pending decisions should not be represented as approved or implemented.

---

## 16. Contributing and Project Governance

This project currently follows a developer-controlled contribution workflow.

Future contributions should:

- Follow `AGENTS.md`.

- Reference an existing ticket.

- Preserve PRD and ADR consistency.

- Include appropriate tests.

- Avoid unrelated changes.

- Provide reproducible verification instructions.

- Use a reviewed feature branch after the initial repository baseline.

- Update relevant documentation when behavior changes.

Contribution guidelines may be expanded if additional collaborators join the project.

---

## 17. Project Limitations

**Status update (2026-11-22):** Backend app, PostgreSQL readiness and ORM infrastructure are implemented with partial verification; the restrictions below about AI agents, authentication, production deployment, cloud and CI/CD remain in force unless later evidence says otherwise.

At the current S02 checkpoint:

- The backend and frontend have been observed serving local HTTP responses, but complete browser/production verification is pending.

- Authentication is not implemented.

- Live search and Bedrock integrations are not verified.

- AI quality results have not been measured.

- Docker-based API/Web/PostgreSQL startup has been observed locally; production deployment and recovery hardening are not verified.

- CI/CD has not been verified.

- AWS deployment has not been verified.

- Production availability and security claims have not been established.

This repository documents the intended engineering approach and will be updated with verified implementation evidence as development proceeds.

---

## 18. License

No open-source license has been selected.

Unless a license is added, no license to use, modify, or distribute this project is granted by default.

---

**AgentOps AI — Building evidence-grounded AI research workflows with measurable quality, controlled autonomy, and production-oriented engineering.**
