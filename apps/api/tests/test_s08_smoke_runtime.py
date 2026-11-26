"""Offline scoped activation and network-boundary verification.

The Owner gate is replaced ONLY inside explicitly isolated tests.
No PostgreSQL live grant, real credential or network access occurs.
"""

import asyncio
import socket

from contextvars import copy_context
from dataclasses import replace
from datetime import timedelta
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.execution_budget import (
    BudgetRejected, ReservationHandle,
)
from agentops_api.services.smoke_scope import prepare_scope
from agentops_api.services import smoke_runtime as runtime
from agentops_api.services.s06_acquisition import (
    authorization, credentials, smoke_wire,
    controlled_retrieval, pinned_transport, resolver,
)

from tests.test_s08_smoke_scope import fixture


def denied(function, *args, **kwargs):
    with pytest.raises(AcquisitionError) as error:
        function(*args, **kwargs)

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED


def make_scope():
    handle, grant, search, retrieval, now = fixture()
    return (
        prepare_scope(handle, grant, search, retrieval, now),
        handle, grant, search, retrieval, now,
    )


def reservation(handle, now):
    return ReservationHandle(
        reservation_id=uuid4(),
        operation_id=uuid4(),
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        attempt_id=handle.attempt_id,
        generation=handle.generation,
        deadline_at=now + timedelta(seconds=10),
    )


@pytest.fixture
def offline_activation(monkeypatch):
    # All actual socket and DNS boundaries remain disabled.
    def forbidden(*args, **kwargs):
        pytest.fail("Network operation attempted in offline test")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    # This test-only seam does not change the actual Owner gate.
    monkeypatch.setattr(runtime, "_owner_gate", lambda: None)

    values = make_scope()

    with runtime._activate(values[0]):
        yield values


def test_default_deny():
    denied(runtime.require)


def test_owner_gate_cannot_activate_scope():
    scope = make_scope()[0]

    with pytest.raises(AcquisitionError):
        with runtime._activate(scope):
            pytest.fail("Owner gate opened")

    denied(runtime.require)


def test_legacy_apis_remain_disabled(offline_activation):
    scope, handle, grant, search, retrieval, now = offline_activation

    assert runtime.require() is scope
    denied(authorization.require_live_authorization)
    denied(credentials.read_tavily_credential)
    denied(pinned_transport._open_socket, socket.AF_INET, socket.SOCK_STREAM)
    denied(
        resolver.DeadlineResolver(
            Budget(), monotonic() + 5
        ).resolve,
        "api.tavily.com",
    )
    denied(runtime.read_credential, object(), search)


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "attempt_id", "generation",
])
def test_foreign_handle_denied(offline_activation, field):
    scope, handle, grant, search, retrieval, now = offline_activation

    forged = SimpleNamespace(**vars(handle))
    setattr(forged, field, 2 if field == "generation" else uuid4())

    denied(runtime.check_identity, forged)


def test_foreign_grant_denied(offline_activation):
    scope, handle, grant, search, retrieval, now = offline_activation

    grant.id = uuid4()

    denied(
        runtime.check_grant,
        handle, grant, "search", search,
        now, now + timedelta(seconds=10),
    )


def test_foreign_digest_denied(offline_activation):
    scope, handle, grant, search, retrieval, now = offline_activation

    denied(
        runtime.check_binding,
        handle, grant.id, "search", bytes(32),
    )


def test_revocation_survives_context_copy(monkeypatch):
    monkeypatch.setattr(runtime, "_owner_gate", lambda: None)
    scope = make_scope()[0]

    with runtime._activate(scope):
        copied = copy_context()
        assert copied.run(runtime.require) is scope

    denied(copied.run, runtime.require)
    denied(runtime.require)


def test_expired_activation_is_denied(offline_activation, monkeypatch):
    scope = offline_activation[0]
    monkeypatch.setattr(runtime, "monotonic", lambda: scope.deadline)

    denied(runtime.require)


def test_scoped_thread_context(offline_activation):
    scope = offline_activation[0]
    copied = copy_context()
    results = []

    # This test exercises context propagation only. No network.
    def observe():
        results.append(runtime.require() is scope)

    thread = Thread(target=copied.run, args=(observe,))
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert results == [True]


def test_search_ticket_destination_and_replay(offline_activation):
    scope, handle, grant, search, retrieval, now = offline_activation

    ticket = smoke_wire._issue(
        reservation(handle, now),
        grant.id,
        scope.search_sha256,
        monotonic() + 5.0,
        Event(),
    )

    claimant = object()
    endpoint = "https://api.tavily.com/search"

    smoke_wire.claim(ticket, search, claimant)

    denied(
        runtime.authorize_network,
        ticket, "search", "https://example.com/", "dns",
    )

    runtime.authorize_network(ticket, "search", endpoint, "dns")
    denied(runtime.authorize_network, ticket, "search", endpoint, "dns")

    smoke_wire.enter_exchange(ticket, search, claimant)

    runtime.authorize_network(ticket, "search", endpoint, "connect")
    denied(runtime.authorize_network, ticket, "search", endpoint, "connect")


def test_retrieval_ticket_destination_and_replay(offline_activation):
    scope, handle, grant, search, retrieval, now = offline_activation

    ticket = controlled_retrieval._issue(
        reservation(handle, now),
        grant.id,
        scope.retrieval_sha256,
        monotonic() + 5.0,
        Event(),
    )

    controlled_retrieval._advance(
        ticket, retrieval, "ready", "claimed"
    )

    denied(
        runtime.authorize_network,
        ticket, "retrieval", "https://example.com/", "dns",
    )

    runtime.authorize_network(
        ticket, "retrieval", retrieval.url, "dns"
    )

    controlled_retrieval._before_exchange(ticket, retrieval.url)

    runtime.authorize_network(
        ticket, "retrieval", retrieval.url, "connect"
    )

    denied(
        runtime.authorize_network,
        ticket, "retrieval", retrieval.url, "connect",
    )


def test_credential_requires_exact_one_shot_ticket(
    offline_activation, monkeypatch
):
    scope, handle, grant, search, retrieval, now = offline_activation

    monkeypatch.setenv("TAVILY_API_KEY", "offline-test-only")

    ticket = smoke_wire._issue(
        reservation(handle, now),
        grant.id,
        scope.search_sha256,
        monotonic() + 5.0,
        Event(),
    )

    denied(runtime.read_credential, object(), search)

    value = runtime.read_credential(ticket, search)

    assert credentials.authorization_header(value) == (
        "Bearer offline-test-only"
    )
    assert "offline-test-only" not in repr(value)

    denied(runtime.read_credential, ticket, search)
