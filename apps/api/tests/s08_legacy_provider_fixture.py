
"""S08 compatibility for historical isolated S06 provider tests.

This module is test-only. It issues in-memory fixture tickets,
not database grants or actual Owner authorizations.

Existing MockTransport and local TLS fixtures remain responsible
for their original response, certificate and deadline assertions.
No public network connection is permitted.
"""

import ipaddress
import socket

from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest

from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.execution_budget import ReservationHandle
from agentops_api.services.provider_accounting import request_digest
from agentops_api.services.smoke_scope import SmokeScope
from agentops_api.services import smoke_runtime as runtime

from agentops_api.services.s06_acquisition import (
    pinned_transport as pinned,
    provider_transport,
    smoke_wire,
    tavily,
)

from agentops_api.services.s06_acquisition.request_policy import (
    validate_basic_wire_request,
)

_ORIGINAL_SOCKET = socket.socket
_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CONNECT_EX = socket.socket.connect_ex
_ORIGINAL_DNS = socket.getaddrinfo

_ORIGINAL_BOUND = pinned._connect_bound
_ORIGINAL_OPEN = pinned._open_socket
_ORIGINAL_RESOLVER = provider_transport.DeadlineResolver


def _assert_disabled():
    with pytest.raises(AcquisitionError) as error:
        runtime.require()

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED


def _check_loopback(address):
    assert isinstance(address, tuple), "Non-IP connection denied"
    assert ipaddress.ip_address(address[0]).is_loopback, (
        "Public network connection forbidden in S06 fixture"
    )


def _connect(sock, address):
    _check_loopback(address)
    return _ORIGINAL_CONNECT(sock, address)


def _connect_ex(sock, address):
    _check_loopback(address)
    return _ORIGINAL_CONNECT_EX(sock, address)


def mock_exchange(transport, handler, request):
    """Retain the original HTTPX mock and advance its fixture ticket."""
    checked = validate_basic_wire_request(request.content)

    smoke_wire.claim(
        transport._wire_ticket,
        checked,
        transport._claimant,
    )

    smoke_wire.enter_exchange(
        transport._wire_ticket,
        checked,
        transport._claimant,
    )

    return handler(request)


class _SocketProxy:
    """Adapt an existing legacy socket fixture, not production code."""

    def __init__(self, original, factory):
        self._original = original
        self.socket = factory

    def __getattr__(self, name):
        return getattr(self._original, name)


def fixture_search(monkeypatch, request, budget):
    _assert_disabled()

    now = datetime.now(timezone.utc)

    handle = ReservationHandle(
        reservation_id=uuid4(),
        operation_id=uuid4(),
        owner_id=uuid4(),
        task_id=uuid4(),
        attempt_id=uuid4(),
        generation=1,
        deadline_at=now + timedelta(seconds=15),
    )

    grant_id = uuid4()
    digest = request_digest(request)

    scope = SmokeScope(
        identity=(
            handle.owner_id,
            handle.task_id,
            handle.attempt_id,
            handle.generation,
        ),
        grant_id=grant_id,
        search_sha256=digest,
        retrieval_sha256=bytes(32),
        deadline=monotonic() + 20.0,
    )

    with monkeypatch.context() as patch:
        # Preserve the original historical fixture seams.
        legacy_bound = pinned._connect_bound
        legacy_open = pinned._open_socket
        legacy_resolver = provider_transport.DeadlineResolver
        legacy_dns = socket.getaddrinfo

        # Even a broken fixture must never connect publicly.
        patch.setattr(
            _ORIGINAL_SOCKET, "connect", _connect
        )
        patch.setattr(
            _ORIGINAL_SOCKET, "connect_ex", _connect_ex
        )

        def isolated_dns(host, *args, **kwargs):
            if legacy_dns is _ORIGINAL_DNS:
                # No real DNS for the provider hostname.
                assert ipaddress.ip_address(host).is_loopback
            else:
                assert host in {"api.tavily.com", "127.0.0.1", "::1"}

            return legacy_dns(host, *args, **kwargs)

        patch.setattr(socket, "getaddrinfo", isolated_dns)

        # Activate only this fixture's private scope.
        patch.setattr(runtime, "_owner_gate", lambda: None)

        for module in (
            tavily,
            provider_transport,
            smoke_wire,
        ):
            patch.setattr(
                module,
                "require_live_authorization",
                runtime.require,
            )

        # Existing tests may substitute the old resolver
        # constructor. Adapt only that already-installed fixture.
        if legacy_resolver is not _ORIGINAL_RESOLVER:
            def scoped_resolver(
                budget, deadline, *,
                _smoke_kind, _smoke_ticket, _smoke_url
            ):
                assert _smoke_kind == "search"
                runtime.authorize_network(
                    _smoke_ticket, "search", _smoke_url, "dns"
                )
                return legacy_resolver(budget, deadline)

            patch.setattr(
                provider_transport,
                "DeadlineResolver",
                scoped_resolver,
            )

        # The historical TLS fixture may replace the entire
        # connector or just its socket-opening seam.
        if legacy_bound is not _ORIGINAL_BOUND:
            def scoped_bound(
                target, budget, deadline, *,
                _smoke_kind=None, _smoke_ticket=None
            ):
                assert _smoke_kind == "search"

                runtime.authorize_network(
                    _smoke_ticket,
                    "search",
                    target.destination.url,
                    "connect",
                )

                return legacy_bound(
                    target, budget, deadline
                )

            patch.setattr(pinned, "_connect_bound", scoped_bound)

        elif legacy_open is not _ORIGINAL_OPEN:
            patch.setattr(
                pinned,
                "socket",
                _SocketProxy(pinned.socket, legacy_open),
            )

        # Retain the existing synthetic credential, never a
        # real provider key.
        import os
        token = os.environ.get("TAVILY_API_KEY", "")
        assert token.startswith(("synthetic", "fixture", "test"))

        with runtime._activate(scope):
            ticket = smoke_wire._issue(
                handle,
                grant_id,
                digest,
                monotonic() + 10.0,
                Event(),
            )

            result = tavily.search_live(
                request,
                budget,
                _wire_ticket=ticket,
            )

            assert smoke_wire._settle(ticket, handle) == (
                grant_id, digest, 1
            )

        _assert_disabled()

        return result
