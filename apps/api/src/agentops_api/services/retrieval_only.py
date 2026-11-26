"""Owner-approved retrieval-only authority.

No search, credential, public API, worker activation or paid
provider authorization is granted by this module.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID

from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.real_evidence import retrieval_digest
from agentops_api.services.smoke_scope import (
    URL, handle_identity, proposed_requests,
)


def reject():
    raise BudgetRejected("retrieval_only_scope_rejected") from None


@dataclass(frozen=True, slots=True)
class RetrievalOnlyScope:
    identity: tuple
    grant_id: UUID
    retrieval_sha256: bytes
    deadline: float

    @property
    def search_sha256(self):
        return None

    def check(self, handle, kind, request):
        if (
            kind != "retrieval"
            or handle_identity(handle) != self.identity
            or monotonic() >= self.deadline
            or retrieval_digest(request) != self.retrieval_sha256
        ):
            reject()


def _validate_grant(grant, owner, task, request, now):
    approved = proposed_requests()[1]
    digest = retrieval_digest(request)

    if digest != retrieval_digest(approved):
        reject()

    if (
        grant is None
        or type(grant.id) is not UUID
        or grant.id.int == 0
        or grant.owner_id != owner
        or grant.task_id != task
        or grant.grant_kind != "retrieval_only"
        or grant.provider_name != "rfc_editor"
        or grant.endpoint != URL
        or grant.query_sha256 is not None
        or grant.retrieval_url_sha256 != digest
        or type(grant.lock_marker) is not int
        or grant.lock_marker != 0
    ):
        reject()

    for value, expected in (
        (grant.max_search_requests, 0),
        (grant.max_provider_credits, 0),
        (grant.max_retrieval_requests, 1),
    ):
        if type(value) is not int or value != expected:
            reject()

    for value in (now, grant.issued_at, grant.expires_at):
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            reject()

    if not (
        grant.issued_at <= now < grant.expires_at
        <= grant.issued_at + timedelta(minutes=15)
    ):
        reject()

    return digest


def prepare_retrieval_scope(handle, grant, request, now):
    identity = handle_identity(handle)

    digest = _validate_grant(
        grant, identity[0], identity[1], request, now
    )

    return RetrievalOnlyScope(
        identity, grant.id, digest,
        monotonic() + min(
            30.0, (grant.expires_at - now).total_seconds()
        ),
    )


def plan_authorized_retrieval(
    grant, task, rows, request, now, deadline, attempt_id,
):
    from agentops_api.services.smoke_runtime import require
    from agentops_api.services.s06_acquisition.controlled_retrieval import (
        plan_smoke_retrieval,
    )

    scope = require()

    # The original planner retains its verified-search requirement.
    if type(scope) is not RetrievalOnlyScope:
        if getattr(grant, "grant_kind", None) == "retrieval_only":
            reject()

        return plan_smoke_retrieval(
            grant, task, rows, request, now, deadline, attempt_id
        )

    if scope.identity[:3] != (task.owner_id, task.id, attempt_id):
        reject()

    digest = _validate_grant(
        grant, task.owner_id, task.id, request, now
    )

    if grant.id != scope.grant_id or digest != scope.retrieval_sha256:
        reject()

    # One operation for the entire independently approved task.
    # No search lineage is inserted, inferred, copied or fabricated.
    if rows:
        reject()

    deadline = min(deadline, grant.expires_at)

    if deadline <= now or monotonic() >= scope.deadline:
        reject()

    return deadline, {
        "acquisition_origin": "live",
        "provider_name": None,
        "reserved_provider_credits": None,
        "observed_provider_credits": None,
        "smoke_grant_id": grant.id,
        "request_sha256": digest,
    }
