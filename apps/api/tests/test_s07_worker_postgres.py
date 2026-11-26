
"""S07 WP05 deterministic worker and fencing integration."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select, update, func

from agentops_api.agent.s06.evidence import (
    EvidenceScope,
    EvidenceUnavailable,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.evidence import (
    store_evidence,
    list_evidence,
)
from agentops_api.services.execution import (
    ExecutionRejected,
)
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.isolated_worker import IsolatedWorker
from agentops_api.services.s06_workflow import (
    OfflineWorkflowRejected,
    revalidate_outcome,
)
from agentops_api.agent.s06.workflow import run_offline
from agentops_api.agent.s06.workflow_contracts import WorkflowInput

from test_s07_execution_postgres import (
    database,
    seed,
    lifecycle,
    parallel,
    get_task,
    attempts,
    age_attempt,
    active_counts,
    REQUEST,
)
from test_s07_budget_postgres import ledger
from test_s06_evidence_domain import record

pytestmark = pytest.mark.integration


def scope_for(handle):
    return EvidenceScope(
        handle.owner_id,
        handle.task_id,
        handle.attempt_id,
    )


async def persisted(admin, task_id):
    async with admin() as session, session.begin():
        return list(
            (
                await session.scalars(
                    select(ResearchEvidence).where(
                        ResearchEvidence.task_id == task_id
                    )
                )
            ).all()
        )


def test_wp05_default_worker_activation_denied():
    for scope in (None, False, 1):
        with pytest.raises(ExecutionRejected):
            IsolatedWorker(
                None, isolated_test_scope=scope,
            )


def test_wp05_actual_claim_to_fenced_terminal():
    async def scenario():
        async with database(owner_count=1) as (
            admin, app, owners
        ):
            task_id = (await seed(admin, owners[0]))[0]

            worker = IsolatedWorker(
                app, isolated_test_scope=True,
            )

            outcome = await worker.run_one(uuid4())

            assert outcome.status == "synthetic_candidate"
            assert outcome.publishable is False
            assert outcome.real_evidence_count == 0
            assert outcome.synthetic_evidence_count == 2

            task = await get_task(admin, task_id)

            assert task.status == "insufficient_evidence"
            assert task.completed_at is not None

            history = await attempts(admin, task_id)

            assert len(history) == 1
            assert history[0].ended_at is not None

            evidence = await persisted(admin, task_id)

            assert len(evidence) == 2
            assert all(
                row.execution_id == history[0].id
                and row.owner_id == owners[0]
                and row.synthetic is True
                for row in evidence
            )

            hashes = {
                row.id: row.content_hash
                for row in evidence
            }

            for claim in outcome.candidate.claims:
                for citation in claim.citations:
                    assert (
                        hashes[citation.evidence_id]
                        == citation.content_hash
                    )

            assert await active_counts(admin) == (0, 0, {})
            assert await worker.run_one(uuid4()) is None

    asyncio.run(scenario())


def test_wp05_concurrent_workers_single_authority():
    async def scenario():
        async with database(owner_count=1) as (
            admin, app, owners
        ):
            task_id = (await seed(admin, owners[0]))[0]

            async def execute(_):
                worker = IsolatedWorker(
                    app, isolated_test_scope=True,
                )
                return await worker.run_one(uuid4())

            results = await parallel(5, execute)

            accepted = [
                value for value in results
                if value is not None
            ]

            assert len(accepted) == 1
            assert accepted[0].publishable is False
            assert len(await attempts(admin, task_id)) == 1
            assert len(await persisted(admin, task_id)) == 2

    asyncio.run(scenario())


def test_wp05_recovery_fences_old_evidence_and_outcome():
    async def scenario():
        async with database(owner_count=1) as (
            admin, app, owners
        ):
            task_id = (await seed(admin, owners[0]))[0]

            first = await lifecycle(
                app, "claim", uuid4(),
            )

            worker = IsolatedWorker(
                app, isolated_test_scope=True,
            )

            old_scope = scope_for(first)
            old_record = record(old_scope)

            before = await worker._execution._call(
                "snapshot", first,
            )

            await age_attempt(admin, first)

            recovered = await parallel(
                5,
                lambda _: lifecycle(
                    app, "recover",
                    first.owner_id,
                    task_id,
                    uuid4(),
                ),
            )

            winners = [
                handle for handle in recovered
                if handle is not None
            ]

            assert len(winners) == 1
            current = winners[0]

            assert current.generation == 2

            after = await worker._execution._call(
                "snapshot", current,
            )

            assert before == after

            with pytest.raises(
                (ExecutionRejected, BudgetRejected),
            ):
                async with app() as session, session.begin():
                    await store_evidence(
                        session,
                        scope=old_scope,
                        record=old_record,
                        execution_handle=first,
                    )

            with pytest.raises(EvidenceUnavailable):
                async with app() as session, session.begin():
                    await store_evidence(
                        session,
                        scope=old_scope,
                        record=old_record,
                    )

            stale_outcome = run_offline(
                WorkflowInput(
                    scope=old_scope,
                    question=REQUEST.question,
                    evidence=(old_record,),
                )
            )

            with pytest.raises(
                (ExecutionRejected, BudgetRejected),
            ):
                await worker._accept(
                    first,
                    (old_record,),
                    stale_outcome,
                )

            with pytest.raises(OfflineWorkflowRejected):
                async with app() as session, session.begin():
                    await revalidate_outcome(
                        session,
                        scope=old_scope,
                        question=REQUEST.question,
                        outcome=stale_outcome,
                        execution_handle=first,
                    )

            assert await persisted(admin, task_id) == []

            outcome = await worker.run_claimed(current)

            assert outcome.publishable is False

            assert all(
                row.execution_id == current.attempt_id
                for row in await persisted(admin, task_id)
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "barrier", ["deleted", "expired", "terminal"],
)
def test_wp05_outcome_and_evidence_barriers(barrier):
    async def scenario():
        async with database(owner_count=1) as (
            admin, app, owners
        ):
            task_id = (await seed(admin, owners[0]))[0]

            handle = await lifecycle(
                app, "claim", uuid4(),
            )

            worker = IsolatedWorker(
                app, isolated_test_scope=True,
            )

            records, outcome = await worker._prepare(handle)

            rows = await ledger(admin, handle)

            assert len(rows) == 9
            assert all(row.status == "succeeded" for row in rows)

            if barrier == "deleted":
                async with admin() as session, session.begin():
                    await session.execute(
                        update(ResearchTask)
                        .where(ResearchTask.id == task_id)
                        .values(
                            deleted_at=func.clock_timestamp()
                        )
                    )

            elif barrier == "expired":
                await age_attempt(admin, handle)

            else:
                await lifecycle(
                    app, "finish", handle, "failed",
                )

            before = await get_task(admin, task_id)

            with pytest.raises(
                (ExecutionRejected, BudgetRejected),
            ):
                await worker._accept(
                    handle, records, outcome,
                )

            with pytest.raises(
                (ExecutionRejected, BudgetRejected),
            ):
                async with app() as session, session.begin():
                    await store_evidence(
                        session,
                        scope=scope_for(handle),
                        record=records[0],
                        execution_handle=handle,
                    )

            assert await persisted(admin, task_id) == []

            after = await get_task(admin, task_id)

            assert after.status == before.status
            assert after.completed_at == before.completed_at
            assert after.deleted_at == before.deleted_at

            if barrier == "deleted":
                assert await lifecycle(
                    app, "expire_one",
                ) is True

            elif barrier == "expired":
                # Started adapter history cannot be replayed
                # as a fresh generation after a crash.
                assert await lifecycle(
                    app, "recover",
                    handle.owner_id,
                    task_id,
                    uuid4(),
                ) is None

                task = await get_task(admin, task_id)

                assert task.status == "failed"
                assert (
                    task.error_category
                    == "indeterminate_execution"
                )

    asyncio.run(scenario())


def test_wp05_forged_handle_and_invalid_outcome_rollback():
    async def scenario():
        async with database(owner_count=1) as (
            admin, app, owners
        ):
            task_id = (await seed(admin, owners[0]))[0]

            handle = await lifecycle(
                app, "claim", uuid4(),
            )

            worker = IsolatedWorker(
                app, isolated_test_scope=True,
            )

            records, outcome = await worker._prepare(handle)

            for forged in (
                replace(handle, worker_id=uuid4()),
                replace(handle, generation=2),
                replace(handle, owner_id=uuid4()),
            ):
                with pytest.raises(
                    (ExecutionRejected, BudgetRejected),
                ):
                    await worker._accept(
                        forged, records, outcome,
                    )

            # Evidence inserted in the transaction must be
            # rolled back if outcome validation rejects it.
            with pytest.raises(OfflineWorkflowRejected):
                await worker._accept(
                    handle,
                    records,
                    replace(outcome, publishable=True),
                )

            assert await persisted(admin, task_id) == []

            task = await get_task(admin, task_id)
            assert task.status == "running"

            accepted = await worker._accept(
                handle, records, outcome,
            )

            assert accepted.publishable is False
            assert len(await persisted(admin, task_id)) == 2

            with pytest.raises(
                (ExecutionRejected, BudgetRejected),
            ):
                await worker._accept(
                    handle, records, outcome,
                )

            assert len(await persisted(admin, task_id)) == 2

    asyncio.run(scenario())


def test_wp05_recovery_with_prior_operation_cannot_start_adapter():
    from agentops_api.agent.s06.contracts import SearchRequest

    async def scenario():
        async with database(owner_count=1) as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]
            first = await lifecycle(app, "claim", uuid4())
            worker = IsolatedWorker(app, isolated_test_scope=True)
            engine = worker._execution
            await engine.search_offline(
                first, SearchRequest(query="prior synthetic operation"),
            )
            before = await engine._call("snapshot", first)
            await age_attempt(admin, first)
            current = await lifecycle(
                app, "recover", first.owner_id, task_id, uuid4(),
            )
            assert current is not None and current.generation == 2
            assert await engine._call("snapshot", current) == before
            with pytest.raises(BudgetRejected, match="adapter_resume_not_authorized"):
                await engine._call("_reserve_stage", current, "planner", False)
            assert await engine._call("snapshot", current) == before
            rows = await ledger(admin, current)
            assert len(rows) == 1
            assert rows[0].attempt_id == first.attempt_id
            assert rows[0].kind == "search" and rows[0].status == "succeeded"
            assert await persisted(admin, task_id) == []

    asyncio.run(scenario())
