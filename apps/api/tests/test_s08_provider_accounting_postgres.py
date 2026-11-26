"""S08 scope and synthetic provider accounting integration."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from agentops_api.agent.s06.contracts import SearchRequest
from agentops_api.models.execution_context import (
    ResearchOperationReservation,
)
from agentops_api.services.durable_execution import DurableExecution
from agentops_api.services.execution_budget import (
    BudgetRejected,
    ExecutionBudgetService,
)
from agentops_api.services.provider_accounting import (
    assess_search_scope,
    query_digest,
    request_digest,
)
from tests.test_s07_budget_postgres import database


pytestmark = pytest.mark.integration


def policy_fixture():
    now = datetime.now(timezone.utc)
    task = SimpleNamespace(id=uuid4(), owner_id=uuid4())
    request = SearchRequest(query="Public market research")
    grant = SimpleNamespace(
        id=uuid4(),
        task_id=task.id,
        owner_id=task.owner_id,
        provider_name="tavily",
        endpoint="https://api.tavily.com/search",
        query_sha256=query_digest(request),
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(seconds=5),
        max_search_requests=1,
        max_provider_credits=1,
        lock_marker=0,
    )
    return grant, task, request, now


def test_scope_assessment_respects_grant_expiry():
    grant, task, request, now = policy_fixture()

    assert assess_search_scope(
        grant, task, [], request,
        now, now + timedelta(seconds=15),
    ) == grant.expires_at


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "provider_name", "endpoint",
    "query_sha256", "expires_at", "max_search_requests",
    "max_provider_credits", "lock_marker",
])
def test_scope_rejects_unapproved_values(field):
    grant, task, request, now = policy_fixture()

    bad = {
        "owner_id": uuid4(),
        "task_id": uuid4(),
        "provider_name": "other",
        "endpoint": "https://example.com/search",
        "query_sha256": bytes(32),
        "expires_at": now,
        "max_search_requests": 7,
        "max_provider_credits": 2,
        "lock_marker": 1,
    }

    setattr(grant, field, bad[field])

    with pytest.raises(BudgetRejected):
        assess_search_scope(
            grant, task, [], request,
            now, now + timedelta(seconds=15),
        )


@pytest.mark.parametrize("status", [
    "reserved", "dispatching", "failed",
    "indeterminate", "succeeded",
])
def test_scope_never_refunds_reservations(status):
    grant, task, request, now = policy_fixture()

    # Pure in-memory policy fixture. No live grant or ledger
    # record is created in PostgreSQL.
    row = SimpleNamespace(
        smoke_grant_id=grant.id,
        owner_id=task.owner_id,
        task_id=task.id,
        acquisition_origin="live",
        kind="search",
        provider_name="tavily",
        reserved_provider_credits=1,
        retry_ordinal=0,
        retry_eligible=False,
        status=status,
    )

    with pytest.raises(
        BudgetRejected, match="provider_allowance_exhausted"
    ):
        assess_search_scope(
            grant, task, [row], request,
            now, now + timedelta(seconds=15),
        )


def test_missing_database_grant_cannot_authorize():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )
                with pytest.raises(
                    BudgetRejected, match="smoke_grant_missing"
                ):
                    await service._assess_smoke_search(
                        handle,
                        SearchRequest(query="Public research"),
                    )

    asyncio.run(scenario())


@pytest.mark.parametrize("credits", [1, None, 2])
def test_provider_credit_is_durable_and_not_refunded(credits):
    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="Public market research")
            calls = []

            def handler(http_request):
                calls.append(http_request.method)
                payload = {
                    "results": [],
                    "request_id": "synthetic-s08-accounting",
                }
                if credits is not None:
                    payload["usage"] = {"credits": credits}
                return httpx.Response(200, json=payload)

            service = DurableExecution(
                app, isolated_test_scope=True
            )
            transport = httpx.MockTransport(handler)

            if credits == 1:
                result = await service.search_isolated(
                    handle, request, transport=transport
                )
                assert result.synthetic is True
                assert result.credits == 1
            else:
                with pytest.raises(BudgetRejected):
                    await service.search_isolated(
                        handle, request, transport=transport
                    )

            assert calls == ["POST"]

            async with admin() as session, session.begin():
                rows = (
                    await session.scalars(
                        select(ResearchOperationReservation).where(
                            ResearchOperationReservation.task_id
                            == handle.task_id,
                            ResearchOperationReservation.kind
                            == "search",
                        )
                    )
                ).all()

                assert len(rows) == 1
                row = rows[0]

                assert row.owner_id == handle.owner_id
                assert row.attempt_id == handle.attempt_id
                assert row.acquisition_origin == "synthetic"
                assert row.provider_name == "tavily"
                assert row.reserved_provider_credits == 1
                assert row.smoke_grant_id is None
                assert row.request_sha256 == request_digest(request)
                assert row.retry_ordinal == 0
                assert row.retry_eligible is False

                if credits == 1:
                    assert row.status == "succeeded"
                    assert row.observed_provider_credits == 1
                else:
                    assert row.status == "indeterminate"
                    assert row.observed_provider_credits is None

            # Same logical operation cannot dispatch twice.
            with pytest.raises(BudgetRejected):
                await service.search_isolated(
                    handle, request, transport=transport
                )
            assert calls == ["POST"]

    asyncio.run(scenario())

def test_atomic_smoke_plan_has_bound_fields_and_deadline():
    from agentops_api.services.provider_accounting import plan_smoke_search

    grant, task, request, now = policy_fixture()

    deadline, fields = plan_smoke_search(
        grant, task, [], request,
        now, now + timedelta(seconds=15),
    )

    assert deadline == grant.expires_at
    assert fields == {
        "acquisition_origin": "live",
        "provider_name": "tavily",
        "reserved_provider_credits": 1,
        "observed_provider_credits": None,
        "request_sha256": request_digest(request),
        "smoke_grant_id": grant.id,
    }


def test_scope_rejects_foreign_live_reservation():
    grant, task, request, now = policy_fixture()

    row = SimpleNamespace(
        smoke_grant_id=uuid4(),
        acquisition_origin="live",
    )

    with pytest.raises(
        BudgetRejected, match="provider_accounting_integrity"
    ):
        assess_search_scope(
            grant, task, [row], request,
            now, now + timedelta(seconds=15),
        )


@pytest.mark.parametrize("synthetic,origin,accepted", [
    (True, "synthetic", True),
    (True, "live", False),
    (False, "synthetic", False),
    (False, "live", True),
])
def test_observation_origin_is_not_interchangeable(
    synthetic, origin, accepted
):
    from agentops_api.services.provider_accounting import (
        observed_provider_credits,
    )
    from agentops_api.services.s06_acquisition.tavily import (
        VerifiedSearchResponse,
    )

    # In-memory observations only; no provider I/O or real ledger write.
    result = VerifiedSearchResponse(
        hits=(), credits=1, synthetic=synthetic
    )

    if accepted:
        assert observed_provider_credits(
            result, expected_origin=origin
        ) == 1
    else:
        with pytest.raises(BudgetRejected, match="provider_usage_invalid"):
            observed_provider_credits(
                result, expected_origin=origin
            )


def test_live_reservation_still_default_denied():
    from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
    from agentops_api.services.execution_budget import ReservationRequest

    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="Public research")

            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                before = await service.snapshot(handle)

                with pytest.raises(AcquisitionError) as error:
                    await service._reserve_smoke_search(handle, request)

                assert error.value.code is ErrorCode.EXTERNAL_DISABLED

                with pytest.raises(AcquisitionError) as error:
                    await service.reserve(
                        handle,
                        ReservationRequest(uuid4(), "search"),
                        _smoke_provider_request=request,
                    )

                assert error.value.code is ErrorCode.EXTERNAL_DISABLED
                assert await service.snapshot(handle) == before

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


def test_synthetic_reservation_identity_is_bound():
    from agentops_api.services.execution_budget import ReservationRequest

    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                before = await service.snapshot(handle)

                with pytest.raises(
                    BudgetRejected, match="invalid_provider_reservation"
                ):
                    await service.reserve(
                        handle,
                        ReservationRequest(uuid4(), "search"),
                        _synthetic_provider_request=SearchRequest(
                            query="Public research"
                        ),
                    )

                assert await service.snapshot(handle) == before

    asyncio.run(scenario())


def test_parallel_provider_reservation_and_dispatch_are_one_shot():
    from agentops_api.services.durable_execution import operation_identity
    from agentops_api.services.execution_budget import (
        ReservationHandle, ReservationRequest,
    )

    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="Public research")
            logical_id = operation_identity(
                handle.task_id, "search", request
            )

            async def reserve():
                async with app() as session:
                    service = ExecutionBudgetService(
                        session, isolated_test_scope=True
                    )
                    return await service.reserve(
                        handle,
                        ReservationRequest(logical_id, "search"),
                        _synthetic_provider_request=request,
                    )

            results = await asyncio.gather(
                reserve(), reserve(), return_exceptions=True
            )

            winners = [
                item for item in results
                if type(item) is ReservationHandle
            ]

            rejected = [
                item for item in results
                if isinstance(item, BudgetRejected)
            ]

            assert len(winners) == len(rejected) == 1

            reservation = winners[0]

            async with admin() as session, session.begin():
                row = await session.scalar(
                    select(ResearchOperationReservation).where(
                        ResearchOperationReservation.id
                        == reservation.reservation_id
                    )
                )

                assert row.status == "reserved"
                assert row.reserved_provider_credits == 1
                assert row.observed_provider_credits is None

            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                assert await service.snapshot(handle)

                await service.begin_dispatch(handle, reservation)

                with pytest.raises(
                    BudgetRejected, match="dispatch_already_consumed"
                ):
                    await service.begin_dispatch(handle, reservation)

                await service._abandon_actual(handle)

                snapshot = await service.snapshot(handle)
                assert snapshot.search_calls == 1
                assert snapshot.blocked is True

            async with admin() as session, session.begin():
                row = await session.scalar(
                    select(ResearchOperationReservation).where(
                        ResearchOperationReservation.id
                        == reservation.reservation_id
                    )
                )

                assert row.status == "indeterminate"
                assert row.reserved_provider_credits == 1
                assert row.observed_provider_credits is None
                assert row.retry_eligible is False

    asyncio.run(scenario())


def test_provider_receipt_is_single_use():
    from agentops_api.services.durable_execution import operation_identity
    from agentops_api.services.execution_budget import ReservationRequest
    from agentops_api.services.execution_receipts import _issue

    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="Public research")

            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                reservation = await service.reserve(
                    handle,
                    ReservationRequest(
                        operation_identity(
                            handle.task_id, "search", request
                        ),
                        "search",
                    ),
                    _synthetic_provider_request=request,
                )

                await service.begin_dispatch(handle, reservation)

                # Test-only synthetic trusted receipt.
                receipt = _issue(
                    reservation, "succeeded", provider_credits=1
                )

                assert await service._complete_actual(
                    handle, reservation, receipt
                ) == "succeeded"

                with pytest.raises(
                    BudgetRejected, match="untrusted_outcome_receipt"
                ):
                    await service._complete_actual(
                        handle, reservation, receipt
                    )

                assert (await service.snapshot(handle)).search_calls == 1

            async with admin() as session, session.begin():
                row = await session.scalar(
                    select(ResearchOperationReservation).where(
                        ResearchOperationReservation.id
                        == reservation.reservation_id
                    )
                )

                assert row.status == "succeeded"
                assert row.acquisition_origin == "synthetic"
                assert row.reserved_provider_credits == 1
                assert row.observed_provider_credits == 1

    asyncio.run(scenario())
