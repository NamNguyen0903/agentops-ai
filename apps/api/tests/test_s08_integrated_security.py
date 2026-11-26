"""S08 integrated evidence security.

All database cases require the disposable integration runner.
No real grant, external request or authorization override.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.contracts import (
    RetrievalRequest,
    SearchRequest,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.execution_context import (
    ResearchRealEvidence,
    ResearchSmokeGrant,
    ResearchOperationReservation,
)
from agentops_api.services.execution_budget import (
    BudgetRejected,
    ExecutionBudgetService,
    ReservationRequest,
)
from agentops_api.services.real_evidence import (
    resolve_real_citations,
)
from agentops_api.services.controlled_research import (
    run_controlled_research,
)
from agentops_api.services.s06_acquisition.authorization import (
    require_live_authorization,
)
from tests.test_s07_budget_postgres import database

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("ids", [
    (),
    ("fake-id",),
    (uuid4(),) * 2,
    tuple(uuid4() for _ in range(21)),
])
def test_invalid_citation_collection_rejected(ids):
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session, session.begin():
                with pytest.raises(BudgetRejected):
                    await resolve_real_citations(
                        session, handle, ids
                    )

    asyncio.run(scenario())


def test_citation_requires_explicit_transaction():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session:
                assert not session.in_transaction()

                with pytest.raises(BudgetRejected):
                    await resolve_real_citations(
                        session, handle, (uuid4(),)
                    )

                assert not session.in_transaction()

    asyncio.run(scenario())


def test_unresolved_operation_blocks_citation_resolution():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session:
                service = ExecutionBudgetService(
                    session, isolated_test_scope=True
                )

                await service.reserve(
                    handle,
                    ReservationRequest(uuid4(), "search"),
                )

            async with app() as session, session.begin():
                with pytest.raises(BudgetRejected):
                    await resolve_real_citations(
                        session, handle, (uuid4(),)
                    )

    asyncio.run(scenario())


def test_denied_workflow_has_no_database_side_effects():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            with pytest.raises(AcquisitionError) as error:
                await run_controlled_research(
                    app, handle,
                    SearchRequest(query="Public research"),
                    RetrievalRequest(
                        url="https://example.com/research"
                    ),
                )

            assert error.value.code is ErrorCode.EXTERNAL_DISABLED

            async with admin() as session, session.begin():
                for model in (
                    ResearchRealEvidence,
                    ResearchSmokeGrant,
                    ResearchOperationReservation,
                ):
                    count = await session.scalar(
                        select(func.count())
                        .select_from(model)
                        .where(model.task_id == handle.task_id)
                    )

                    assert count == 0

    asyncio.run(scenario())


def test_app_can_read_both_evidence_counts():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session, session.begin():
                real_count = (
                    select(func.count())
                    .select_from(ResearchRealEvidence)
                    .where(
                        ResearchRealEvidence.owner_id == handle.owner_id,
                        ResearchRealEvidence.task_id == handle.task_id,
                    )
                    .scalar_subquery()
                )

                count = await session.scalar(
                    select(func.count() + real_count)
                    .select_from(ResearchEvidence)
                    .where(
                        ResearchEvidence.owner_id == handle.owner_id,
                        ResearchEvidence.task_id == handle.task_id,
                    )
                )

                assert type(count) is int
                assert count == 0

    asyncio.run(scenario())


def test_live_gate_not_relaxed_by_evaluation():
    with pytest.raises(AcquisitionError) as error:
        require_live_authorization()

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED
