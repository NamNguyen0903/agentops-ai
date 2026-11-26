"""Dormant one-request controlled HTTPS retrieval.

No credentials are involved. No redirects or retries are
permitted by this narrowly scoped smoke adapter.
"""

from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Lock
from time import monotonic
from uuid import UUID
from weakref import WeakKeyDictionary

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import RetrievalRequest
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.network_policy import bind_destination, public_ip
from agentops_api.agent.s06.retrieval import validated_headers, read_body
from agentops_api.agent.s06.transport import TransportResponse
from agentops_api.services.execution_budget import (
    BudgetRejected, ReservationHandle,
)
from agentops_api.services.real_evidence import (
    RealPageObservation, canonical_retrieval_url,
    retrieval_digest, validate_observation,
)

from agentops_api.services.smoke_runtime import require as require_live_authorization
from .resolver import DeadlineResolver


def plan_smoke_retrieval(
    grant, task, rows, request, now, deadline, attempt_id,
):
    digest = retrieval_digest(request)

    if grant is None:
        raise BudgetRejected("smoke_grant_missing")

    if (
        grant.owner_id != task.owner_id
        or grant.task_id != task.id
        or grant.provider_name != "tavily"
        or grant.endpoint != "https://api.tavily.com/search"
        or grant.lock_marker != 0
        or type(grant.max_retrieval_requests) is not int
        or grant.max_retrieval_requests != 1
        or grant.retrieval_url_sha256 != digest
        or not grant.issued_at <= now < grant.expires_at
        or grant.expires_at > grant.issued_at + timedelta(minutes=15)
    ):
        raise BudgetRejected("smoke_scope_rejected")

    live = [
        row for row in rows
        if row.acquisition_origin == "live"
    ]

    for row in live:
        if (
            row.smoke_grant_id != grant.id
            or row.owner_id != task.owner_id
            or row.task_id != task.id
            or row.kind not in {"search", "retrieval"}
        ):
            raise BudgetRejected("provider_accounting_integrity")

    if any(row.kind == "retrieval" for row in live):
        raise BudgetRejected("retrieval_allowance_exhausted")

    if not any(
        row.kind == "search"
        and row.status == "succeeded"
        and row.attempt_id == attempt_id
        and row.provider_name == "tavily"
        and row.observed_provider_credits == 1
        for row in live
    ):
        raise BudgetRejected("verified_search_required")

    deadline = min(deadline, grant.expires_at)

    if deadline <= now:
        raise BudgetRejected("operation_deadline_expired")

    return deadline, {
        "acquisition_origin": "live",
        "provider_name": None,
        "reserved_provider_credits": None,
        "observed_provider_credits": None,
        "smoke_grant_id": grant.id,
        "request_sha256": digest,
    }


class _Ticket:
    pass


@dataclass(slots=True)
class _State:
    reservation: ReservationHandle
    grant_id: UUID
    digest: bytes
    deadline: float
    stopped: Event
    phase: str = "ready"
    page: RealPageObservation | None = None
    dns_used: bool = False
    connect_used: bool = False


_REGISTRY = WeakKeyDictionary()
_LOCK = Lock()


def deny():
    raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED) from None


def _issue(reservation, grant_id, digest, deadline, stopped):
    require_live_authorization()

    if (
        type(reservation) is not ReservationHandle
        or type(grant_id) is not UUID
        or grant_id.int == 0
        or type(digest) is not bytes
        or len(digest) != 32
        or type(deadline) is not float
        or not 0 < deadline - monotonic() <= 15
        or type(stopped) is not Event
        or stopped.is_set()
    ):
        deny()

    ticket = _Ticket()

    with _LOCK:
        _REGISTRY[ticket] = _State(
            reservation, grant_id, digest, deadline, stopped
        )

    return ticket


def _state(ticket):
    if type(ticket) is not _Ticket:
        deny()

    state = _REGISTRY.get(ticket)

    if state is None or state.stopped.is_set():
        deny()

    if monotonic() >= state.deadline:
        raise AcquisitionError(ErrorCode.DEADLINE_EXCEEDED)

    return state


def _advance(ticket, request, before, after):
    require_live_authorization()
    digest = retrieval_digest(request)

    with _LOCK:
        state = _state(ticket)

        if state.digest != digest or state.phase != before:
            deny()

        state.phase = after
        return state.deadline


def _before_exchange(ticket, url):
    return _advance(
        ticket, RetrievalRequest(url=url),
        "claimed", "exchanging",
    )


def _before_send(ticket, url):
    return _advance(
        ticket, RetrievalRequest(url=url),
        "exchanging", "sent",
    )


def _record(ticket, request, page):
    require_live_authorization()
    validate_observation(request, page)

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "sent"
            or state.digest != retrieval_digest(request)
        ):
            deny()

        state.page = page
        state.phase = "observed"


def _settle(ticket, reservation):
    require_live_authorization()

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "observed"
            or state.reservation != reservation
            or type(state.page) is not RealPageObservation
        ):
            deny()

        result = state.grant_id, state.digest, state.page
        del _REGISTRY[ticket]

        return result


def retrieve_controlled(request, budget, *, ticket):
    require_live_authorization()

    if type(budget) is not Budget:
        deny()

    url = canonical_retrieval_url(request)

    deadline = min(
        budget.operation_deadline(),
        _advance(ticket, request, "ready", "claimed"),
    )

    budget.reserve_retrieval(deadline)

    resolver = DeadlineResolver(
        budget, deadline,
        _smoke_kind="retrieval",
        _smoke_ticket=ticket,
        _smoke_url=url,
    )
    target = bind_destination(url, resolver)

    from .bounded_http import exchange

    response = exchange(
        target, budget, deadline,
        _smoke_ticket=ticket,
    )

    budget.check(deadline)

    if (
        type(response) is not TransportResponse
        or type(response.status) is not int
        or response.status != 200
        or public_ip(response.peer_ip) != target.ip
        or response.tls_verified is not True
        or response.tls_hostname != target.destination.host
    ):
        raise AcquisitionError(ErrorCode.INVALID_RESPONSE)

    headers = validated_headers(response)
    content_type, body = read_body(
        response, headers, budget, deadline
    )

    page = RealPageObservation(
        source_url=url,
        retrieved_url=url,
        content_type=content_type,
        body=body,
    )

    _record(ticket, request, page)

def _authorize_network(ticket, url, phase):
    from agentops_api.services.smoke_runtime import check_binding

    require_live_authorization()

    with _LOCK:
        state = _state(ticket)
        check_binding(
            state.reservation, state.grant_id, "retrieval", state.digest
        )

        if retrieval_digest(RetrievalRequest(url=url)) != state.digest:
            deny()

        if phase == "dns":
            if state.phase != "claimed" or state.dns_used:
                deny()
            state.dns_used = True
        elif phase == "connect":
            if (
                state.phase != "exchanging"
                or not state.dns_used
                or state.connect_used
            ):
                deny()
            state.connect_used = True
        else:
            deny()

        return state.deadline
