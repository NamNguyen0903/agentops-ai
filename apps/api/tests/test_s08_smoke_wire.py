"""Offline wire-authority verification.

Positive authority fixtures exist only in memory and never
execute a real transport or create a PostgreSQL live grant.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic
from uuid import uuid4

import httpx
import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import SearchRequest
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.execution_budget import ReservationHandle
from agentops_api.services.provider_accounting import request_digest
from agentops_api.services.s06_acquisition import (
    smoke_wire,
    provider_transport,
    tavily,
)
from agentops_api.services.s06_acquisition.request_policy import (
    prepare_basic_request,
)


def reservation():
    return ReservationHandle(
        reservation_id=uuid4(),
        operation_id=uuid4(),
        task_id=uuid4(),
        owner_id=uuid4(),
        attempt_id=uuid4(),
        generation=1,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=10),
    )


def denied(function, *args, code=ErrorCode.EXTERNAL_DISABLED, **kwargs):
    with pytest.raises(AcquisitionError) as error:
        function(*args, **kwargs)
    assert error.value.code is code


def fixture_ticket(monkeypatch):
    # Only this module's registry is exercised. Adapter and transport
    # authorization remain disabled, and no provider I/O is performed.
    monkeypatch.setattr(
        smoke_wire, "require_live_authorization", lambda: None
    )

    request = SearchRequest(query="Public market research")
    handle = reservation()
    grant_id = uuid4()
    stopped = Event()
    deadline = monotonic() + 10.0

    ticket = smoke_wire._issue(
        handle, grant_id, request_digest(request), deadline, stopped
    )

    return ticket, request, handle, grant_id, stopped, deadline


def observed():
    return tavily.VerifiedSearchResponse(
        hits=(), credits=1, synthetic=False
    )


def test_ticket_issuance_default_denied():
    request = SearchRequest(query="Public research")

    denied(
        smoke_wire._issue,
        reservation(), uuid4(), request_digest(request),
        monotonic() + 5.0, Event(),
    )


def test_forged_ticket_rejected():
    denied(
        smoke_wire.check_ready,
        smoke_wire._Ticket(),
        SearchRequest(query="Public research"),
    )


@pytest.mark.parametrize("changed", [
    SearchRequest(query="Different query"),
    SearchRequest(query="Public market research", max_results=1),
])
def test_request_substitution_rejected(monkeypatch, changed):
    ticket, request, _, _, _, _ = fixture_ticket(monkeypatch)

    denied(smoke_wire.check_ready, ticket, changed)
    denied(smoke_wire.claim, ticket, changed, object())

    assert smoke_wire.check_ready(ticket, request) > monotonic()


def test_one_shot_wire_and_settlement(monkeypatch):
    ticket, request, handle, grant, _, deadline = fixture_ticket(
        monkeypatch
    )

    claimant = object()

    assert smoke_wire.claim(ticket, request, claimant) == deadline

    denied(smoke_wire.claim, ticket, request, claimant)

    assert smoke_wire.enter_exchange(
        ticket, request, claimant
    ) == deadline

    denied(smoke_wire.enter_exchange, ticket, request, claimant)

    smoke_wire._record(ticket, request, observed())

    assert smoke_wire._settle(ticket, handle) == (
        grant, request_digest(request), 1
    )

    denied(smoke_wire._settle, ticket, handle)


def test_cancellation_revokes_wire_authority(monkeypatch):
    ticket, request, _, _, stopped, _ = fixture_ticket(monkeypatch)

    claimant = object()
    smoke_wire.claim(ticket, request, claimant)
    smoke_wire.enter_exchange(ticket, request, claimant)

    stopped.set()

    denied(smoke_wire.check_exchange, ticket, request, claimant)


def test_expired_ticket_rejected(monkeypatch):
    ticket, request, _, _, _, deadline = fixture_ticket(monkeypatch)

    monkeypatch.setattr(smoke_wire, "monotonic", lambda: deadline)

    denied(
        smoke_wire.check_ready, ticket, request,
        code=ErrorCode.DEADLINE_EXCEEDED,
    )


def test_wrong_transport_claimant_rejected(monkeypatch):
    ticket, request, _, _, _, _ = fixture_ticket(monkeypatch)

    smoke_wire.claim(ticket, request, object())

    denied(smoke_wire.enter_exchange, ticket, request, object())


def test_settlement_before_observation_rejected(monkeypatch):
    ticket, _, handle, _, _, _ = fixture_ticket(monkeypatch)

    denied(smoke_wire._settle, ticket, handle)


def test_receipt_cannot_cross_reservations(monkeypatch):
    ticket, request, handle, _, _, _ = fixture_ticket(monkeypatch)

    claimant = object()
    smoke_wire.claim(ticket, request, claimant)
    smoke_wire.enter_exchange(ticket, request, claimant)
    smoke_wire._record(ticket, request, observed())

    denied(smoke_wire._settle, ticket, reservation())

    assert smoke_wire._settle(ticket, handle)[2] == 1


def test_synthetic_result_cannot_settle_live_ticket(monkeypatch):
    from agentops_api.services.execution_budget import BudgetRejected

    ticket, request, handle, _, _, _ = fixture_ticket(monkeypatch)

    claimant = object()
    smoke_wire.claim(ticket, request, claimant)
    smoke_wire.enter_exchange(ticket, request, claimant)

    with pytest.raises(BudgetRejected):
        smoke_wire._record(
            ticket, request,
            tavily.VerifiedSearchResponse(
                hits=(), credits=1, synthetic=True
            ),
        )

    denied(smoke_wire._settle, ticket, handle)


@pytest.mark.parametrize("boundary", ["request", "exchange"])
def test_transport_without_ticket_denied_before_network(
    monkeypatch, boundary
):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected destination or network access")

    monkeypatch.setattr(
        provider_transport, "require_live_authorization", lambda: None
    )
    monkeypatch.setattr(
        provider_transport, "bind_destination", forbidden
    )
    monkeypatch.setattr(
        provider_transport.pinned, "validated_target", forbidden
    )
    monkeypatch.setattr(
        provider_transport.pinned, "_connect_bound", forbidden
    )

    budget = Budget()
    transport = provider_transport.TavilyPinnedTransport(
        budget, budget.operation_deadline()
    )

    request = SearchRequest(query="Public research")
    body = json.dumps(prepare_basic_request(request)).encode()

    if boundary == "request":
        denied(
            transport.handle_request,
            httpx.Request(
                "POST",
                provider_transport.ENDPOINT,
                content=body,
                headers={"Authorization": "Bearer isolated-test-token"},
            ),
        )
    else:
        denied(
            transport._exchange,
            object(), body, "Bearer isolated-test-token"
        )


def test_adapter_requires_authority_before_credentials(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Credential access forbidden")

    monkeypatch.setattr(
        tavily, "require_live_authorization", lambda: None
    )
    monkeypatch.setattr(
        tavily, "read_tavily_credential", forbidden
    )

    denied(
        tavily.search_live,
        SearchRequest(query="Public research"),
        Budget(),
    )


@pytest.mark.integration
def test_durable_live_entrypoints_remain_disabled():
    from sqlalchemy import select
    from agentops_api.models.execution_context import (
        ResearchOperationReservation,
    )
    from agentops_api.services.durable_execution import DurableExecution
    from agentops_api.services.execution_budget import ExecutionBudgetService
    from tests.test_s07_budget_postgres import database

    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="Public research")

            service = DurableExecution(
                app, isolated_test_scope=True
            )

            with pytest.raises(AcquisitionError) as error:
                await service._search_smoke(handle, request)

            assert error.value.code is ErrorCode.EXTERNAL_DISABLED

            async with app() as session:
                budget = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                before = await budget.snapshot(handle)

                with pytest.raises(AcquisitionError) as error:
                    await budget._begin_smoke_search_wire(
                        handle, reservation(), request, Event()
                    )

                assert error.value.code is ErrorCode.EXTERNAL_DISABLED

                with pytest.raises(AcquisitionError) as error:
                    await budget._complete_smoke_search(
                        handle, reservation(), object()
                    )

                assert error.value.code is ErrorCode.EXTERNAL_DISABLED
                assert await budget.snapshot(handle) == before

            async with admin() as session, session.begin():
                rows = (
                    await session.scalars(
                        select(ResearchOperationReservation).where(
                            ResearchOperationReservation.task_id
                            == handle.task_id
                        )
                    )
                ).all()

                assert rows == []

    asyncio.run(scenario())
