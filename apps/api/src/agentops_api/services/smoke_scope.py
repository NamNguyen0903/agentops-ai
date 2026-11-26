"""Exact controlled-smoke policy.

This module validates scope; it does not grant live permission.
The existing external authorization barrier remains independent.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID

from agentops_api.agent.s06.contracts import (
    SearchRequest, RetrievalRequest, validate_contract,
)
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.provider_accounting import (
    query_digest, request_digest,
)
from agentops_api.services.real_evidence import retrieval_digest

QUERY = "RFC 9110 HTTP Semantics plain text RFC Editor"
URL = "https://www.rfc-editor.org/rfc/rfc9110.txt"
MAX_RESULTS = 5


def reject():
    raise BudgetRejected("smoke_scope_rejected") from None


def handle_identity(handle):
    values = (
        handle.owner_id,
        handle.task_id,
        handle.attempt_id,
    )

    if any(type(value) is not UUID or value.int == 0
           for value in values):
        reject()

    generation = handle.generation

    if type(generation) is not int or generation < 1:
        reject()

    return (*values, generation)


def proposed_requests():
    return (
        SearchRequest(query=QUERY, max_results=MAX_RESULTS),
        RetrievalRequest(url=URL),
    )


@dataclass(frozen=True, slots=True)
class SmokeScope:
    identity: tuple
    grant_id: UUID
    search_sha256: bytes
    retrieval_sha256: bytes
    deadline: float

    def check(self, handle, kind, request):
        try:
            if (
                handle_identity(handle) != self.identity
                or monotonic() >= self.deadline
            ):
                reject()

            if kind == "search":
                digest = request_digest(request)
                expected = self.search_sha256
            elif kind == "retrieval":
                digest = retrieval_digest(request)
                expected = self.retrieval_sha256
            else:
                reject()

            if digest != expected:
                reject()

        except Exception:
            reject()


def prepare_scope(handle, grant, search, retrieval, now):
    """Prepare a bounded scope from an independently locked grant.

    This is a policy projection, not a grant issuer or wire ticket.
    """
    try:
        identity = handle_identity(handle)
        approved_search, approved_retrieval = proposed_requests()

        search = validate_contract(SearchRequest, search)
        retrieval = validate_contract(RetrievalRequest, retrieval)

        if (
            request_digest(search) != request_digest(approved_search)
            or retrieval_digest(retrieval)
            != retrieval_digest(approved_retrieval)
        ):
            reject()

        if (
            grant is None
            or type(grant.id) is not UUID
            or grant.id.int == 0
            or grant.owner_id != identity[0]
            or grant.task_id != identity[1]
            or grant.provider_name != "tavily"
            or grant.endpoint != "https://api.tavily.com/search"
            or grant.query_sha256 != query_digest(search)
            or grant.retrieval_url_sha256 != retrieval_digest(retrieval)
            or type(grant.lock_marker) is not int
            or grant.lock_marker != 0
        ):
            reject()

        limits = (
            grant.max_search_requests,
            grant.max_provider_credits,
            grant.max_retrieval_requests,
        )

        if any(type(value) is not int or value != 1
               for value in limits):
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

        remaining = min(
            30.0, (grant.expires_at - now).total_seconds()
        )

        return SmokeScope(
            identity=identity,
            grant_id=grant.id,
            search_sha256=request_digest(search),
            retrieval_sha256=retrieval_digest(retrieval),
            deadline=monotonic() + remaining,
        )

    except Exception:
        reject()
