"""Private operation-scoped S08 runtime authorization.

No environment switch, public API, worker activation or generic
egress permission is provided.

The separate Owner gate remains unconditionally denied until
an explicitly approved controlled execution mechanism exists.

This is an application trust boundary, not a sandbox against
arbitrary Python code running inside the same process.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Lock
from time import monotonic

from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode

_ACTIVE = ContextVar("s08_private_smoke_activation", default=None)


def deny():
    raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED) from None


def _owner_gate():
    # G04 is not authorized by the current implementation package.
    deny()


@dataclass(frozen=True, slots=True)
class _Activation:
    scope: object
    revoked: Event


class _OwnerPermit:
    """One-use authority owned by the dedicated local smoke runner.

    The private constructor belongs to the trusted application
    process, not a public or cryptographic authentication API.
    """

    __slots__ = ("scope", "_used", "_lock")

    def __init__(self, scope):
        self.scope = scope
        self._used = False
        self._lock = Lock()

    def consume(self, scope):
        with self._lock:
            if self._used or scope is not self.scope:
                deny()
            self._used = True


@contextmanager
def _activate(scope, *, _owner_permit=None):
    """Private activation boundary; not exposed to HTTP callers."""
    if _owner_permit is None:
        _owner_gate()
    elif type(_owner_permit) is not _OwnerPermit:
        deny()

    from agentops_api.services.smoke_scope import SmokeScope
    from agentops_api.services.retrieval_only import RetrievalOnlyScope

    if (
        type(scope) not in (SmokeScope, RetrievalOnlyScope)
        or _ACTIVE.get() is not None
        or not 0 < scope.deadline - monotonic() <= 30.0
    ):
        deny()

    if _owner_permit is not None:
        _owner_permit.consume(scope)

    activation = _Activation(scope, Event())
    token = _ACTIVE.set(activation)

    try:
        yield
    finally:
        # Revocation is shared across copied contexts and threads.
        activation.revoked.set()
        _ACTIVE.reset(token)


def require():
    active = _ACTIVE.get()

    if (
        type(active) is not _Activation
        or active.revoked.is_set()
        or monotonic() >= active.scope.deadline
    ):
        deny()

    return active.scope


def check_identity(handle):
    from agentops_api.services.smoke_scope import handle_identity

    scope = require()

    if handle_identity(handle) != scope.identity:
        deny()

    return scope


def check_operation(handle, kind, request):
    scope = check_identity(handle)
    scope.check(handle, kind, request)
    return scope


def check_binding(handle, grant_id, kind, digest):
    scope = check_identity(handle)

    if kind == "search":
        expected = scope.search_sha256
    elif kind == "retrieval":
        expected = scope.retrieval_sha256
    else:
        deny()

    if (
        grant_id != scope.grant_id
        or type(digest) is not bytes
        or digest != expected
    ):
        deny()

    return scope


def check_grant(handle, grant, kind, request, now, deadline):
    from agentops_api.services.smoke_scope import (
        prepare_scope, proposed_requests,
    )

    from agentops_api.services.retrieval_only import (
        RetrievalOnlyScope, prepare_retrieval_scope,
    )

    scope = check_operation(handle, kind, request)

    if type(scope) is RetrievalOnlyScope:
        current = prepare_retrieval_scope(
            handle, grant, request, now
        )
    else:
        search, retrieval = proposed_requests()
        current = prepare_scope(
            handle, grant, search, retrieval, now
        )

    if (
        current.identity != scope.identity
        or current.grant_id != scope.grant_id
        or current.search_sha256 != scope.search_sha256
        or current.retrieval_sha256 != scope.retrieval_sha256
    ):
        deny()

    remaining = scope.deadline - monotonic()

    if remaining <= 0:
        deny()

    bounded = min(
        deadline, now + timedelta(seconds=remaining)
    )

    if bounded <= now:
        deny()

    return bounded


def check_row(handle, row, kind):
    if (
        row.owner_id != handle.owner_id
        or row.task_id != handle.task_id
        or row.attempt_id != handle.attempt_id
        or row.kind != kind
        or row.acquisition_origin != "live"
    ):
        deny()

    return check_binding(
        handle, row.smoke_grant_id, kind, row.request_sha256
    )


def authorize_network(ticket, kind, url, phase):
    scope = require()

    if kind == "search" and scope.search_sha256 is None:
        deny()

    if kind == "search":
        from agentops_api.services.s06_acquisition import smoke_wire
        return smoke_wire._authorize_network(ticket, url, phase)

    if kind == "retrieval":
        from agentops_api.services.s06_acquisition import controlled_retrieval
        return controlled_retrieval._authorize_network(ticket, url, phase)

    deny()


def read_credential(ticket, request):
    # No secret lookup until a scoped, unconsumed search ticket
    # has been verified against the active operation.
    from agentops_api.services.s06_acquisition import smoke_wire
    from agentops_api.services.s06_acquisition.credentials import (
        TavilyCredential, authorization_header,
    )

    scope = require()

    if scope.search_sha256 is None:
        deny()

    smoke_wire._authorize_credential(ticket, request)

    import os

    credential = TavilyCredential(os.environ.get("TAVILY_API_KEY"))

    # Reuse the existing exact credential format validation.
    authorization_header(credential)

    return credential
