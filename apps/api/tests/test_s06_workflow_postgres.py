"""S06 application pipeline on disposable PostgreSQL."""

from dataclasses import replace
from uuid import uuid4

import pytest

from sqlalchemy import delete, func, update

from agentops_api.agent.s06.workflow import run_offline
from agentops_api.agent.s06.workflow_contracts import (
    WorkflowInput,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.evidence import (
    list_evidence,
    store_evidence,
)
from agentops_api.services.s06_workflow import (
    OfflineWorkflowRejected,
    revalidate_outcome,
    run_fixture_workflow,
)

from test_s06_evidence_postgres import execute
from test_s06_workflow import QUESTION, snapshot


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def disable_tracing(monkeypatch):
    for flag in (
        "LANGSMITH_TRACING",
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING",
        "LANGCHAIN_TRACING_V2",
    ):
        monkeypatch.setenv(flag, "false")


def test_postgres_complete_fixture_pipeline():
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session, session.begin():
            outcome = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

            assert outcome.status == "synthetic_candidate"
            assert outcome.publishable is False
            assert outcome.real_evidence_count == 0
            assert outcome.synthetic_evidence_count == 2

            records = await list_evidence(
                session,
                scope=context,
            )

            assert len(records) == 2

            approved = {
                item.id: item.content_hash
                for item in records
            }

            for claim in outcome.candidate.claims:
                assert len(claim.citations) == 1

                citation = claim.citations[0]

                assert (
                    approved[citation.evidence_id]
                    == citation.content_hash
                )

        # Repeated acquisition reuses stable evidence IDs.
        async with runtime() as session, session.begin():
            second = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

            assert second == outcome

            assert len(
                await list_evidence(
                    session,
                    scope=context,
                )
            ) == 2

    execute(scenario)


def test_postgres_application_rollback():
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session:
            transaction = await session.begin()

            outcome = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

            assert outcome.candidate is not None

            await transaction.rollback()

        async with runtime() as session, session.begin():
            assert await list_evidence(
                session,
                scope=context,
            ) == ()

            with pytest.raises(OfflineWorkflowRejected):
                await revalidate_outcome(
                    session,
                    scope=context,
                    question=QUESTION,
                    outcome=outcome,
                )

    execute(scenario)


def test_postgres_missing_cited_evidence():
    async def scenario(runtime, migrator, context, sibling, other):
        records = snapshot(context, 3)

        async with runtime() as session, session.begin():
            for item in records:
                await store_evidence(
                    session,
                    scope=context,
                    record=item,
                )

        outcome = run_offline(
            WorkflowInput(
                scope=context,
                question=QUESTION,
                evidence=records,
            )
        )

        # Disposable test-only administrative deletion.
        async with migrator() as session, session.begin():
            await session.execute(
                delete(ResearchEvidence).where(
                    ResearchEvidence.id == records[0].id
                )
            )

        async with runtime() as session, session.begin():
            with pytest.raises(OfflineWorkflowRejected):
                await revalidate_outcome(
                    session,
                    scope=context,
                    question=QUESTION,
                    outcome=outcome,
                )

    execute(scenario)


def test_postgres_deleted_task_revalidation():
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session, session.begin():
            outcome = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

        # Test fixture only; application does not
        # perform this lifecycle mutation.
        async with migrator() as session, session.begin():
            await session.execute(
                update(ResearchTask)
                .where(ResearchTask.id == context.task_id)
                .values(deleted_at=func.now())
            )

        async with runtime() as session, session.begin():
            with pytest.raises(OfflineWorkflowRejected):
                await revalidate_outcome(
                    session,
                    scope=context,
                    question=QUESTION,
                    outcome=outcome,
                )

        async with runtime() as session, session.begin():
            with pytest.raises(OfflineWorkflowRejected):
                await run_fixture_workflow(
                    session,
                    scope=context,
                    question=QUESTION,
                )

    execute(scenario)


@pytest.mark.parametrize("dimension", [
    "owner",
    "task",
    "execution",
])
def test_postgres_cross_scope_candidate(dimension):
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session, session.begin():
            outcome = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

        if dimension == "owner":
            invalid_scope = other

        elif dimension == "task":
            invalid_scope = sibling

        else:
            invalid_scope = replace(
                context,
                execution_id=uuid4(),
            )

        async with runtime() as session, session.begin():
            with pytest.raises(OfflineWorkflowRejected):
                await revalidate_outcome(
                    session,
                    scope=invalid_scope,
                    question=QUESTION,
                    outcome=outcome,
                )

    execute(scenario)


def test_postgres_tampered_evidence_revalidation():
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session, session.begin():
            outcome = await run_fixture_workflow(
                session,
                scope=context,
                question=QUESTION,
            )

        evidence_id = (
            outcome.candidate.claims[0]
            .citations[0].evidence_id
        )

        async with migrator() as session, session.begin():
            await session.execute(
                update(ResearchEvidence)
                .where(
                    ResearchEvidence.id == evidence_id
                )
                .values(content_hash=b"x" * 32)
            )

        async with runtime() as session, session.begin():
            with pytest.raises(OfflineWorkflowRejected):
                await revalidate_outcome(
                    session,
                    scope=context,
                    question=QUESTION,
                    outcome=outcome,
                )

    execute(scenario)


def test_postgres_insufficient_repository_snapshot():
    async def scenario(runtime, migrator, context, sibling, other):
        records = snapshot(context, 1)

        async with runtime() as session, session.begin():
            await store_evidence(
                session,
                scope=context,
                record=records[0],
            )

            outcome = run_offline(
                WorkflowInput(
                    scope=context,
                    question=QUESTION,
                    evidence=records,
                )
            )

            result = await revalidate_outcome(
                session,
                scope=context,
                question=QUESTION,
                outcome=outcome,
            )

            assert result.status == "insufficient_evidence"
            assert result.candidate is None
            assert result.publishable is False

    execute(scenario)
