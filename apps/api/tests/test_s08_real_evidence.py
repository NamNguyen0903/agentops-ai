"""Offline real-evidence policy and provenance verification.

No actual live grants, provider credentials or external
retrieval requests are created by these tests.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import RetrievalRequest, RetrievedPage
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.execution_budget import (
    BudgetRejected, ReservationHandle, ExecutionBudgetService,
)
from agentops_api.services.durable_execution import DurableExecution
from agentops_api.services.real_evidence import (
    RealPageObservation, build_values, validate_stored,
    validate_observation, retrieval_digest, resolve_real_citations,
)
from agentops_api.services.s06_acquisition import controlled_retrieval as wire


URL = "https://example.com/research"
REQUEST = RetrievalRequest(url=URL)


def fixtures():
    now = datetime.now(timezone.utc)

    handle = SimpleNamespace(
        owner_id=uuid4(),
        task_id=uuid4(),
        attempt_id=uuid4(),
    )

    operation = SimpleNamespace(
        id=uuid4(),
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        attempt_id=handle.attempt_id,
        kind="retrieval",
        acquisition_origin="live",
        status="succeeded",
        request_sha256=retrieval_digest(REQUEST),
        smoke_grant_id=uuid4(),
        dispatched_at=now - timedelta(seconds=1),
        resolved_at=now,
        deadline_at=now + timedelta(seconds=1),
    )

    page = RealPageObservation(
        URL, URL, "text/plain",
        b"Public research fixture.  Example evidence.",
    )

    return handle, operation, page, now


def test_real_record_projection_and_integrity():
    handle, operation, page, now = fixtures()

    values = build_values(
        handle, operation, REQUEST, page, now
    )

    assert values["acquisition_origin"] == "live"
    assert values["published_at"] is None
    assert values["retrieved_at"] == now
    assert values["excerpt"] == "Public research fixture. Example evidence."

    assert validate_stored(
        handle, SimpleNamespace(**values), operation
    ) == values["id"]

    assert build_values(
        handle, operation, REQUEST, page, now
    )["id"] == values["id"]


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "attempt_id",
    "content_hash", "source_identity_sha256",
    "excerpt", "published_at", "retrieved_at",
])
def test_modified_record_rejected(field):
    handle, operation, page, now = fixtures()

    values = build_values(handle, operation, REQUEST, page, now)

    bad = {
        "owner_id": uuid4(),
        "task_id": uuid4(),
        "attempt_id": uuid4(),
        "content_hash": bytes(32),
        "source_identity_sha256": bytes(32),
        "excerpt": "Fabricated statement",
        "published_at": now,
        "retrieved_at": now + timedelta(seconds=1),
    }

    values[field] = bad[field]

    with pytest.raises(BudgetRejected):
        validate_stored(
            handle, SimpleNamespace(**values), operation
        )


@pytest.mark.parametrize("body", [
    b"", b"\xff", b"\x00", b"x" * 1048577,
])
def test_invalid_content_rejected(body):
    with pytest.raises(BudgetRejected):
        validate_observation(
            REQUEST,
            RealPageObservation(URL, URL, "text/plain", body),
        )


def test_synthetic_page_cannot_enter_real_evidence():
    page = RetrievedPage(
        source_url=URL,
        retrieved_url=URL,
        content_type="text/plain",
        body=b"fixture",
        synthetic=True,
    )

    with pytest.raises(BudgetRejected):
        validate_observation(REQUEST, page)


def test_redirect_and_html_rejected():
    for page in (
        RealPageObservation(
            URL, "https://example.org/other",
            "text/plain", b"text",
        ),
        RealPageObservation(
            URL, URL, "text/html", b"<p>text</p>",
        ),
    ):
        with pytest.raises(BudgetRejected):
            validate_observation(REQUEST, page)


def grant_fixture():
    handle, operation, page, now = fixtures()

    task = SimpleNamespace(
        id=handle.task_id, owner_id=handle.owner_id
    )

    grant = SimpleNamespace(
        id=operation.smoke_grant_id,
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        provider_name="tavily",
        endpoint="https://api.tavily.com/search",
        lock_marker=0,
        max_retrieval_requests=1,
        retrieval_url_sha256=retrieval_digest(REQUEST),
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(seconds=10),
    )

    search = SimpleNamespace(
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        attempt_id=handle.attempt_id,
        acquisition_origin="live",
        smoke_grant_id=grant.id,
        kind="search",
        status="succeeded",
        provider_name="tavily",
        observed_provider_credits=1,
    )

    return handle, task, grant, search, now


def test_scoped_retrieval_plan():
    handle, task, grant, search, now = grant_fixture()

    deadline, fields = wire.plan_smoke_retrieval(
        grant, task, (search,), REQUEST, now,
        now + timedelta(seconds=15), handle.attempt_id,
    )

    assert deadline == grant.expires_at
    assert fields["request_sha256"] == retrieval_digest(REQUEST)
    assert fields["smoke_grant_id"] == grant.id
    assert fields["reserved_provider_credits"] is None


@pytest.mark.parametrize("case", [
    "missing_search", "wrong_attempt", "wrong_url",
    "expired", "allowance_consumed",
])
def test_retrieval_scope_fails_closed(case):
    handle, task, grant, search, now = grant_fixture()
    rows = [search]

    if case == "missing_search":
        rows = []
    elif case == "wrong_attempt":
        search.attempt_id = uuid4()
    elif case == "wrong_url":
        grant.retrieval_url_sha256 = bytes(32)
    elif case == "expired":
        grant.expires_at = now
    elif case == "allowance_consumed":
        rows.append(SimpleNamespace(
            owner_id=handle.owner_id,
            task_id=handle.task_id,
            acquisition_origin="live",
            smoke_grant_id=grant.id,
            kind="retrieval",
        ))

    with pytest.raises(BudgetRejected):
        wire.plan_smoke_retrieval(
            grant, task, tuple(rows), REQUEST, now,
            now + timedelta(seconds=15), handle.attempt_id,
        )


def test_ticket_lifecycle_offline(monkeypatch):
    # Registry-only simulation: no real grant or HTTP exchange.
    monkeypatch.setattr(
        wire, "require_live_authorization", lambda: None
    )

    handle, operation, page, now = fixtures()

    reservation = ReservationHandle(
        reservation_id=operation.id,
        operation_id=uuid4(),
        task_id=handle.task_id,
        owner_id=handle.owner_id,
        attempt_id=handle.attempt_id,
        generation=1,
        deadline_at=operation.deadline_at,
    )

    ticket = wire._issue(
        reservation, operation.smoke_grant_id,
        retrieval_digest(REQUEST),
        monotonic() + 5.0, Event(),
    )

    wire._advance(ticket, REQUEST, "ready", "claimed")
    wire._before_exchange(ticket, URL)
    wire._before_send(ticket, URL)

    with pytest.raises(AcquisitionError):
        wire._before_send(ticket, URL)

    wire._record(ticket, REQUEST, page)

    assert wire._settle(ticket, reservation)[2] == page

    with pytest.raises(AcquisitionError):
        wire._settle(ticket, reservation)


def test_live_retrieval_disabled():
    with pytest.raises(AcquisitionError) as error:
        wire.retrieve_controlled(
            REQUEST, Budget(), ticket=object()
        )

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED


@pytest.mark.integration
def test_database_entrypoint_and_unknown_citations_fail_closed():
    from tests.test_s07_budget_postgres import database

    async def scenario():
        async with database() as (admin, app, handle, engine):
            durable = DurableExecution(
                app, isolated_test_scope=True
            )

            with pytest.raises(AcquisitionError) as error:
                await durable._retrieve_smoke(handle, REQUEST)

            assert error.value.code is ErrorCode.EXTERNAL_DISABLED

            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                before = await service.snapshot(handle)

                with pytest.raises(AcquisitionError):
                    await service._reserve_smoke_retrieval(
                        handle, REQUEST
                    )

                assert await service.snapshot(handle) == before

            async with app() as session, session.begin():
                with pytest.raises(BudgetRejected):
                    await resolve_real_citations(
                        session, handle, (uuid4(),)
                    )

    asyncio.run(scenario())
