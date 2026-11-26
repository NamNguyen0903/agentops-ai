"""S08 positive persistence using expired offline DB fixtures.

All content is fabricated for verification.
No authorization override, credential access or external I/O.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import fields, replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update

from agentops_api.agent.s06.contracts import (
    RetrievalRequest, RetrievedPage, SearchRequest,
)
from agentops_api.agent.s06.evidence import (
    EvidenceScope, EvidenceLimitExceeded, from_retrieved_page,
)
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.execution_context import (
    ResearchExecutionContext,
    ResearchOperationReservation,
    ResearchRealEvidence,
    ResearchSmokeGrant,
)
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.evidence import store_evidence
from agentops_api.services.execution import ExecutionRejected
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.provider_accounting import query_digest
from agentops_api.services.real_evidence import (
    RealPageObservation, build_values,
    retrieval_digest, resolve_real_citations,
)
from agentops_api.services.controlled_research import (
    _read_verified_excerpt,
)
from agentops_api.services.s06_acquisition.authorization import (
    require_live_authorization,
)
from tests.test_s07_budget_postgres import database

pytestmark = pytest.mark.integration

URL = "https://example.com/research"
REQUEST = RetrievalRequest(url=URL)


@asynccontextmanager
async def seeded():
    with pytest.raises(AcquisitionError) as error:
        require_live_authorization()

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED

    async with database() as (admin, app, handle, engine):
        grant_id = uuid4()

        try:
            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )
                context = await session.get(
                    ResearchExecutionContext, handle.task_id
                )

                assert context is not None

                # This fixture is expired before insertion.
                # It cannot authorize any provider operation.
                session.add(ResearchSmokeGrant(
                    id=grant_id,
                    owner_id=handle.owner_id,
                    task_id=handle.task_id,
                    provider_name="tavily",
                    endpoint="https://api.tavily.com/search",
                    query_sha256=query_digest(
                        SearchRequest(query="Expired offline fixture")
                    ),
                    retrieval_url_sha256=retrieval_digest(REQUEST),
                    issued_at=now - timedelta(minutes=2),
                    expires_at=now - timedelta(minutes=1),
                    max_search_requests=1,
                    max_provider_credits=1,
                    max_retrieval_requests=1,
                    lock_marker=0,
                ))
                await session.flush()

                deadline = min(
                    now + timedelta(seconds=10),
                    context.started_at + timedelta(seconds=30),
                    context.deadline_at,
                )
                assert deadline > now

                row = ResearchOperationReservation(
                    id=uuid4(),
                    owner_id=handle.owner_id,
                    task_id=handle.task_id,
                    attempt_id=handle.attempt_id,
                    operation_id=uuid4(),
                    kind="retrieval",
                    retry_ordinal=0,
                    is_repair=False,
                    reserved_at=now,
                    deadline_at=deadline,
                    reserved_tokens=0,
                    reserved_cost_microusd=0,
                    status="succeeded",
                    dispatched_at=now,
                    resolved_at=now,
                    retry_eligible=False,
                    acquisition_origin="live",
                    smoke_grant_id=grant_id,
                    request_sha256=retrieval_digest(REQUEST),
                )

                context.retrieval_calls = 1
                context.updated_at = now

                session.add(row)
                await session.flush()

                values = build_values(
                    handle, row, REQUEST,
                    RealPageObservation(
                        URL, URL, "text/plain",
                        b"Offline database provenance fixture.",
                    ),
                    now,
                )

            # Verify runtime INSERT and actual relational constraints.
            # This intentionally does not certify live settlement.
            async with app() as session, session.begin():
                session.add(ResearchRealEvidence(**values))
                await session.flush()

            yield admin, app, handle, values

        finally:
            async with admin() as session, session.begin():
                for model in (
                    ResearchRealEvidence,
                    ResearchEvidence,
                    ResearchOperationReservation,
                    ResearchSmokeGrant,
                ):
                    await session.execute(
                        delete(model).where(
                            model.owner_id == handle.owner_id,
                            model.task_id == handle.task_id,
                        )
                    )


def test_positive_database_citation_roundtrip():
    async def scenario():
        async with seeded() as (admin, app, handle, values):
            result = await _read_verified_excerpt(
                app, handle, values["id"]
            )

            assert result.evidence_id == values["id"]
            assert result.source_url == URL
            assert result.excerpt == values["excerpt"]
            assert result.retrieved_at == values["retrieved_at"]
            assert result.published_at is None

    asyncio.run(scenario())


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "attempt_id",
])
def test_foreign_or_invalid_attempt_handle_rejected(field):
    async def scenario():
        async with seeded() as (admin, app, handle, values):
            forged = replace(handle, **{field: uuid4()})

            async with app() as session, session.begin():
                with pytest.raises(
                    (BudgetRejected, ExecutionRejected)
                ):
                    await resolve_real_citations(
                        session, forged, (values["id"],)
                    )

            result = await _read_verified_excerpt(
                app, handle, values["id"]
            )
            assert result.evidence_id == values["id"]

    asyncio.run(scenario())


def test_deleted_task_cannot_resolve_existing_evidence():
    async def scenario():
        async with seeded() as (admin, app, handle, values):
            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )
                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == handle.task_id)
                    .values(deleted_at=now)
                )

            async with app() as session, session.begin():
                with pytest.raises(
                    (BudgetRejected, ExecutionRejected)
                ):
                    await resolve_real_citations(
                        session, handle, (values["id"],)
                    )

    asyncio.run(scenario())


def test_tampered_database_excerpt_is_rejected():
    async def scenario():
        async with seeded() as (admin, app, handle, values):
            async with admin() as session, session.begin():
                await session.execute(
                    update(ResearchRealEvidence)
                    .where(ResearchRealEvidence.id == values["id"])
                    .values(excerpt="Modified offline fixture.")
                )

            async with app() as session, session.begin():
                with pytest.raises(BudgetRejected):
                    await resolve_real_citations(
                        session, handle, (values["id"],)
                    )

    asyncio.run(scenario())


def test_shared_capacity_rejects_twenty_first_record():
    async def scenario():
        async with seeded() as (admin, app, handle, values):
            scope = EvidenceScope(
                owner_id=handle.owner_id,
                task_id=handle.task_id,
                execution_id=handle.attempt_id,
            )

            def record(index):
                url = "https://example.com/fixture/" + str(index)
                return from_retrieved_page(
                    scope,
                    title="Offline synthetic fixture",
                    page=RetrievedPage(
                        source_url=url,
                        retrieved_url=url,
                        content_type="text/plain",
                        body=("Fixture " + str(index)).encode(),
                        synthetic=True,
                    ),
                    retrieved_at=values["retrieved_at"],
                )

            async with admin() as session, session.begin():
                for index in range(19):
                    item = record(index)
                    session.add(ResearchEvidence(**{
                        field.name: getattr(item, field.name)
                        for field in fields(item)
                    }))
                await session.flush()

            async with app() as session, session.begin():
                with pytest.raises(EvidenceLimitExceeded):
                    await store_evidence(
                        session,
                        scope=scope,
                        record=record(20),
                        execution_handle=handle,
                    )

            async with app() as session, session.begin():
                duplicate = await store_evidence(
                    session,
                    scope=scope,
                    record=record(0),
                    execution_handle=handle,
                )
                assert duplicate.created is False

            async with admin() as session, session.begin():
                for model, expected in (
                    (ResearchEvidence, 19),
                    (ResearchRealEvidence, 1),
                ):
                    count = await session.scalar(
                        select(func.count())
                        .select_from(model)
                        .where(model.task_id == handle.task_id)
                    )
                    assert count == expected

    asyncio.run(scenario())
