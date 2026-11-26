"""Private, one-shot controlled-search wire authority.

Issued only after durable dispatch commits. This registry is not
a security boundary against arbitrary in-process Python execution.
No credentials or network I/O occur here.
"""

from dataclasses import dataclass
from threading import Event, Lock
from time import monotonic
from weakref import WeakKeyDictionary
from uuid import UUID

from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.smoke_runtime import require as require_live_authorization


class _Ticket:
    pass


@dataclass(slots=True)
class _State:
    reservation: object
    grant_id: UUID
    digest: bytes
    deadline: float
    stopped: Event
    phase: str = "ready"
    claimant: object = None
    credits: int | None = None
    credential_used: bool = False
    dns_used: bool = False
    connect_used: bool = False


_REGISTRY = WeakKeyDictionary()
_LOCK = Lock()


def _deny():
    raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED) from None


def _issue(reservation, grant_id, digest, deadline, stopped):
    require_live_authorization()

    from agentops_api.services.execution_budget import ReservationHandle

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
        _deny()

    ticket = _Ticket()

    with _LOCK:
        _REGISTRY[ticket] = _State(
            reservation, grant_id, digest, deadline, stopped
        )

    return ticket


def _state(ticket):
    if type(ticket) is not _Ticket:
        _deny()

    state = _REGISTRY.get(ticket)

    if state is None or state.stopped.is_set():
        _deny()

    if monotonic() >= state.deadline:
        raise AcquisitionError(ErrorCode.DEADLINE_EXCEEDED)

    return state


def _request_digest(request):
    from agentops_api.services.provider_accounting import request_digest
    return request_digest(request)


def check_ready(ticket, request):
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        if state.phase != "ready" or state.digest != digest:
            _deny()

        return state.deadline


def claim(ticket, request, claimant):
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "ready"
            or state.digest != digest
            or claimant is None
        ):
            _deny()

        state.phase = "claimed"
        state.claimant = claimant

        return state.deadline


def enter_exchange(ticket, request, claimant):
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "claimed"
            or state.digest != digest
            or state.claimant is not claimant
        ):
            _deny()

        state.phase = "exchanging"
        return state.deadline


def check_exchange(ticket, request, claimant):
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "exchanging"
            or state.digest != digest
            or state.claimant is not claimant
        ):
            _deny()

        return state.deadline


def _record(ticket, request, result):
    require_live_authorization()

    from agentops_api.services.provider_accounting import (
        observed_provider_credits,
    )

    credits = observed_provider_credits(
        result, expected_origin="live"
    )
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        if state.phase != "exchanging" or state.digest != digest:
            _deny()

        state.credits = credits
        state.phase = "observed"


def _settle(ticket, reservation):
    require_live_authorization()

    with _LOCK:
        state = _state(ticket)

        if (
            state.phase != "observed"
            or state.reservation != reservation
            or type(state.credits) is not int
            or state.credits != 1
        ):
            _deny()

        result = state.grant_id, state.digest, state.credits
        del _REGISTRY[ticket]

        return result

def _authorize_network(ticket, url, phase):
    from agentops_api.services.smoke_runtime import check_binding

    require_live_authorization()

    with _LOCK:
        state = _state(ticket)
        check_binding(
            state.reservation, state.grant_id, "search", state.digest
        )

        if url != "https://api.tavily.com/search":
            _deny()

        if phase == "dns":
            if state.phase != "claimed" or state.dns_used:
                _deny()
            state.dns_used = True
        elif phase == "connect":
            if (
                state.phase != "exchanging"
                or not state.dns_used
                or state.connect_used
            ):
                _deny()
            state.connect_used = True
        else:
            _deny()

        return state.deadline


def _authorize_credential(ticket, request):
    from agentops_api.services.smoke_runtime import check_binding

    require_live_authorization()
    digest = _request_digest(request)

    with _LOCK:
        state = _state(ticket)

        check_binding(
            state.reservation, state.grant_id, "search", state.digest
        )

        if (
            state.phase != "ready"
            or state.digest != digest
            or state.credential_used
        ):
            _deny()

        state.credential_used = True
