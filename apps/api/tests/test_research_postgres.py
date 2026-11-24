"""Real PostgreSQL tests restricted to the existing disposable migration target.

Each case uses independent sessions and synthetic UUID owners. Cleanup affects
only those owners. Schema changes are performed by the isolated lifecycle runner.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from agentops_api.models.identity import User
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.research import (
    IdempotencyConflict, ResearchSubmission, get_task, list_tasks, submit_task,
)
from test_identity_db_integration import get_test_database_url

pytestmark = pytest.mark.integration
REQUEST = ResearchSubmission(question="Compare synthetic products")


@asynccontextmanager
async def database():
    engine = create_async_engine(
        get_test_database_url(), poolclass=NullPool, hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000 -c lock_timeout=3000"},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False, autobegin=False, autoflush=False)
    owners = (uuid4(), uuid4())
    try:
        async with sessions() as session, session.begin():
            identity = (await session.execute(text(
                "SELECT current_database(), current_user, "
                "(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='app')"
            ))).one()
            assert identity == ("agentops_migration_test", "agentops_migrator", "agentops_migrator")
            session.add_all([User(id=owner) for owner in owners])
        yield sessions, owners
    finally:
        try:
            async with sessions() as session, session.begin():
                await session.execute(update(ResearchTask).where(ResearchTask.owner_id.in_(owners)).values(retry_parent_id=None))
                await session.execute(delete(ResearchTask).where(ResearchTask.owner_id.in_(owners)))
                await session.execute(delete(User).where(User.id.in_(owners)))
        finally:
            await engine.dispose()


async def submit(session, owner, key="key", request=REQUEST):
    return await submit_task(session, owner_id=owner, idempotency_key=key, submission=request)


def test_committed_task_survives_independent_sessions_and_is_owner_scoped():
    async def scenario():
        async with database() as (sessions, (owner, other)):
            async with sessions() as session, session.begin():
                result = await submit(session, owner)
                task_id = result.task.id
                assert result.created and result.task.status == "queued"
                assert result.task.current_stage is None
            async with sessions() as session, session.begin():
                task = await get_task(session, owner_id=owner, task_id=task_id)
                assert task.question == REQUEST.question
                assert task.scope == REQUEST.scope.model_dump(mode="json")
                assert task.request_fingerprint == REQUEST.fingerprint()
                assert task.created_at.tzinfo is not None
                assert await get_task(session, owner_id=other, task_id=task_id) is None
                assert await list_tasks(session, owner_id=other) == []
                assert [row.id for row in await list_tasks(session, owner_id=owner)] == [task_id]
    asyncio.run(scenario())


def test_owner_foreign_key_rejects_nonexistent_user():
    async def scenario():
        async with database() as (sessions, _):
            with pytest.raises(IntegrityError) as error:
                async with sessions() as session, session.begin():
                    await submit(session, uuid4())
            assert error.value.orig.sqlstate == "23503"
    asyncio.run(scenario())


def test_owner_key_reuse_conflict_and_database_unique_constraint():
    async def scenario():
        async with database() as (sessions, (owner, other)):
            async with sessions() as session, session.begin():
                first = await submit(session, owner)
            async with sessions() as session, session.begin():
                duplicate = await submit(session, owner)
                assert not duplicate.created and duplicate.task.id == first.task.id
                distinct = await submit(session, other)
                assert distinct.created and distinct.task.id != first.task.id
            with pytest.raises(IdempotencyConflict):
                async with sessions() as session, session.begin():
                    await submit(session, owner, request=ResearchSubmission(question="Different"))
            with pytest.raises(IntegrityError) as error:
                async with sessions() as session, session.begin():
                    session.add(ResearchTask(owner_id=owner, question="Duplicate", scope={},
                                             idempotency_key="key", request_fingerprint=bytes(32)))
                    await session.flush()
            assert error.value.orig.sqlstate == "23505"
    asyncio.run(scenario())


@pytest.mark.parametrize("values", [
    {"status": "invented"}, {"scope": []}, {"request_fingerprint": b"short"},
    {"question": " "}, {"idempotency_key": ""},
    {"status": "completed"}, {"status": "running"},
    {"started_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    {"error_category": "raw exception: secret"},
])
def test_database_rejects_invalid_record(values):
    async def scenario():
        async with database() as (sessions, (owner, _)):
            with pytest.raises(IntegrityError) as error:
                async with sessions() as session, session.begin():
                    row = dict(owner_id=owner, question="Question", scope={}, status="queued",
                               idempotency_key="key", request_fingerprint=bytes(32))
                    row.update(values)
                    session.add(ResearchTask(**row))
                    await session.flush()
            assert error.value.orig.sqlstate == "23514"
    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["queued", "running", "completed", "insufficient_evidence", "failed", "timed_out"])
def test_all_prd_states_have_representable_timestamps(status):
    async def scenario():
        async with database() as (sessions, (owner, _)):
            async with sessions() as session, session.begin():
                result = await submit(session, owner)
                values = {"status": status, "updated_at": text("clock_timestamp()")}
                if status in {"running", "completed", "insufficient_evidence"}:
                    values["started_at"] = text("clock_timestamp()")
                if status not in {"queued", "running"}:
                    values["completed_at"] = text("clock_timestamp()")
                await session.execute(update(ResearchTask).where(ResearchTask.id == result.task.id).values(**values))
            async with sessions() as session, session.begin():
                task = await get_task(session, owner_id=owner, task_id=result.task.id)
                assert task.status == status
    asyncio.run(scenario())


def test_rollback_does_not_persist_or_reserve_key():
    async def scenario():
        async with database() as (sessions, (owner, _)):
            async with sessions() as session:
                await session.begin()
                first = await submit(session, owner)
                first_id = first.task.id
                await session.rollback()
            async with sessions() as session, session.begin():
                assert await get_task(session, owner_id=owner, task_id=first_id) is None
                second = await submit(session, owner)
                assert second.created and second.task.id != first_id
    asyncio.run(scenario())


@pytest.mark.parametrize("rollback_first", [False, True])
def test_concurrent_duplicate_waits_for_commit_or_rollback(rollback_first):
    async def scenario():
        async with database() as (sessions, (owner, _)):
            pid_ready = asyncio.Future()

            async def competitor():
                async with sessions() as second, second.begin():
                    pid_ready.set_result(await second.scalar(text("SELECT pg_backend_pid()")))
                    return await submit(second, owner)

            async with sessions() as first:
                await first.begin()
                initial = await submit(first, owner)
                initial_id = initial.task.id
                pending = asyncio.create_task(competitor())
                try:
                    pid = await asyncio.wait_for(pid_ready, timeout=2)
                    async with sessions() as observer, observer.begin():
                        async with asyncio.timeout(2):
                            while not await observer.scalar(text(
                                "SELECT cardinality(pg_blocking_pids(:pid)) > 0"
                            ), {"pid": pid}):
                                await asyncio.sleep(0.02)
                    assert not pending.done(), "Second insertion must wait on the real unique key"
                    if rollback_first:
                        await first.rollback()
                    else:
                        await first.commit()
                    result = await asyncio.wait_for(pending, timeout=3)
                    assert result.created is rollback_first
                    assert (result.task.id == initial_id) is (not rollback_first)
                finally:
                    if first.in_transaction():
                        await first.rollback()
                    if not pending.done():
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
            async with sessions() as session, session.begin():
                assert len(await list_tasks(session, owner_id=owner)) == 1
    asyncio.run(scenario())


def test_deleted_tasks_hidden_and_key_not_resurrected():
    async def scenario():
        async with database() as (sessions, (owner, _)):
            async with sessions() as session, session.begin():
                result = await submit(session, owner)
                await session.execute(update(ResearchTask).where(ResearchTask.id == result.task.id)
                                      .values(deleted_at=text("clock_timestamp()")))
            async with sessions() as session, session.begin():
                assert await get_task(session, owner_id=owner, task_id=result.task.id) is None
                assert await list_tasks(session, owner_id=owner) == []
            with pytest.raises(IdempotencyConflict):
                async with sessions() as session, session.begin():
                    await submit(session, owner)
    asyncio.run(scenario())


def test_retry_parent_must_belong_to_same_owner():
    async def scenario():
        async with database() as (sessions, (owner, other)):
            async with sessions() as session, session.begin():
                parent = await submit(session, owner)
                child = await submit(session, other)
            with pytest.raises(IntegrityError) as error:
                async with sessions() as session, session.begin():
                    await session.execute(update(ResearchTask).where(ResearchTask.id == child.task.id)
                                          .values(retry_parent_id=parent.task.id))
            assert error.value.orig.sqlstate == "23503"
    asyncio.run(scenario())


def test_keyset_history_with_tied_timestamps_has_no_duplicates():
    async def scenario():
        async with database() as (sessions, (owner, _)):
            async with sessions() as session, session.begin():
                for key in ("a", "b", "c"):
                    await submit(session, owner, key)
            async with sessions() as session, session.begin():
                first = await list_tasks(session, owner_id=owner, limit=2)
                second = await list_tasks(session, owner_id=owner, limit=2,
                                          before=(first[-1].created_at, first[-1].id))
                assert len(first) == 2 and len(second) == 1
                assert len({row.id for row in first + second}) == 3
                assert first[0].created_at == second[0].created_at
    asyncio.run(scenario())
