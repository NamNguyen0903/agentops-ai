# ADR-0005 — AWS Deployment Architecture

**Status:** ACCEPTED — scoped Development MVP preparation only.
**Authority:** S09 Contract v1.0, AD09-06 through AD09-12.
**Date:** 2026-11-27.
**Production:** NOT APPROVED.

## 1. Context

AgentOps AI retains the Modular Monolith architecture.
The approved initial staging target is a single Linux EC2 host
running Docker Compose, consistent with ADR-0001.

This decision authorizes preparation and applicable local
verification, not actual AWS resource creation or deployment.

## 2. Decision

Prepare the following staging topology:

- HTTPS reverse proxy and React frontend.
- FastAPI backend.
- Separately controlled durable worker process.
- PostgreSQL with encrypted persistent storage.
- Versioned container images in Amazon ECR.
- CloudWatch logging, monitoring and alarms.
- Independently protected encrypted off-host database backups.

The API and worker should reuse the backend image with
separate startup commands and distinct runtime authority.

Existing worker and external execution default-deny
restrictions remain binding.

Bedrock remains a proposed inference target.
This ADR does not approve a specific Bedrock model,
activate an inference provider or authorize paid requests.

## 3. Network and identity boundaries

Expose only necessary HTTPS ingress.
HTTP may be used only for a controlled HTTPS redirect
or explicitly approved certificate provisioning.

Keep PostgreSQL, worker and internal service ports private.

Restrict administrative access, preferably through
AWS-managed session access.

Separate CI deployment authority from application runtime IAM.
Prefer short-lived credentials and instance roles.
No static production credentials in source, images,
prompts, reports or evidence.

Provider credentials are accessible only within their
approved application-owned execution boundaries.

## 4. Artifact and deployment integrity

Use reproducible builds, dependency locks and versioned artifacts.
Deploy using verified immutable image digests.

Preserve applicable dependency, image and secret scans.

Prepare controlled migration, admission, worker drain,
readiness and deployment verification procedures.

Migrations must use the approved migrator identity.
No shared database migration is authorized by this ADR.

Actual artifact publishing and deployment remain
separately authorized operations.

## 5. Persistence and recovery

PostgreSQL storage must survive container replacement.

Persistent disk is not a backup.

Prepare encrypted, access-controlled off-host backups
and a documented restore exercise.

Preserve deletion suppression and retention requirements
during recovery.

Retain previous verified artifacts for rollback.
Do not assume schema downgrade is safe.
Database restore requires explicit recovery authorization.

Actual restore outcomes require actual execution evidence.

## 6. Observability and cost

Prepare sanitized structured logs and operational metrics:

- Request, task and attempt correlation.
- Queue depth and age.
- Completion and failure rates.
- Worker health and expired leases.
- Provider latency, errors and usage.
- Retry, timeout and recovery outcomes.
- Database and disk health.
- Deployment version and artifact identity.

Do not expose credentials or unnecessary research content.
Do not use unbounded task IDs as metric labels.

Prepare CloudWatch alarms and AWS budget alerts.

Budget alerts are not guaranteed spending caps.

Any actual resource usage requires separately approved
account, region, resource configuration and cost limits.

## 7. Alternatives

- ECS and RDS: deferred until operational requirements
  and costs justify managed infrastructure.
- Kubernetes and microservices: not selected for this milestone.
- Single EC2 with Docker Compose: selected for initial
  staging preparation, subject to its limitations.

## 8. Limitations

Single-host failure domain.
No automatic failover.
No multi-AZ database availability.
No guaranteed recovery objective or production SLA.

Local configuration tests do not establish cloud security,
AWS availability, backup durability or operational readiness.

Actual CloudWatch alarms, TLS, IAM behavior, cloud restore
and deployment outcomes require applicable real evidence.

## 9. Release boundary

No new dependency, external provider, AWS resource,
paid usage, worker activation, production authentication,
public report publication or deployment is authorized
solely by this ADR.

Retain all existing security controls and Owner gates.

PRODUCTION REMAINS NOT APPROVED.
