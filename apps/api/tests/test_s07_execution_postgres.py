"""S07 lifecycle verification against the disposable PostgreSQL database.

No worker process, provider access, report publication or shared migrations.
Runtime lifecycle operations use the actual agentops_app role.
The migrator is used only for fixture setup, deterministic time aging,
inspection, constraint probes and scoped cleanup.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from agentops_api.models.execution import ResearchExecutionAttempt
from agentops_api.models.execution_context import (
    ResearchExecutionContext,
    ResearchOperationReservation,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.identity import User
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.research import ResearchSubmission
from agentops_api.services.execution import (
    ExecutionRejected,
    ExecutionService,
    running_deadline,
)
from agentops_api.services.research import QueueFull, admit_task
from test_identity_db_integration import get_test_database_url


pytestmark = pytest.mark.integration

REQUEST = ResearchSubmission(
    question="Compare synthetic S07 fixtures"
)

LIMITS = {
    "question_limit": 4000,
    "scope_limit": 2000,
}

# Public synthetic credential from the committed disposable bootstrap.
# This credential is never suitable for a shared database.
FIXTURE_RUNTIME_PASSWORD = "isolated-test-only-runtime"


def make_engine(url, **kwargs):
    return create_async_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": (
                "-c statement_timeout=10000 "
                "-c lock_timeout=5000 "
                "-c idle_in_transaction_session_timeout=10000"
            ),
        },
        **kwargs,
    )


def factory(engine):
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
        autobegin=False,
    )


@asynccontextmanager
async def database(owner_count=8):
    url = get_test_database_url()

    # Restrict to the existing internal Compose service.
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "agentops_migration_test"
    assert url.username == "agentops_migrator"

    migrator = make_engine(url)

    runtime = make_engine(
        url.set(
            username="agentops_app",
            password=FIXTURE_RUNTIME_PASSWORD,
        ),
        isolation_level="READ COMMITTED",
    )

    admin = factory(migrator)
    app = factory(runtime)

    owners = tuple(
        uuid4() for _ in range(owner_count)
    )

    initialized = False

    try:
        async with admin() as session, session.begin():
            identity = (
                await session.execute(text("""
                    SELECT current_database(), current_user,
                        (
                            SELECT pg_get_userbyid(nspowner)
                            FROM pg_namespace
                            WHERE nspname = 'app'
                        )
                """))
            ).one()

            assert tuple(identity) == (
                "agentops_migration_test",
                "agentops_migrator",
                "agentops_migrator",
            )

            revision = await session.scalar(text(
                "SELECT version_num FROM app.alembic_version"
            ))

            assert revision == "d8b3105f0804"

            # These tests exercise global capacity. They must not
            # silently depend on unrelated pre-existing tasks.
            assert await session.scalar(
                select(func.count()).select_from(ResearchTask)
            ) == 0

            session.add_all(
                User(id=owner) for owner in owners
            )

        initialized = True

        async with app() as session, session.begin():
            identity = (
                await session.execute(text(
                    "SELECT current_database(), current_user"
                ))
            ).one()

            assert tuple(identity) == (
                "agentops_migration_test",
                "agentops_app",
            )

            assert await session.scalar(
                text("SHOW transaction_isolation")
            ) == "read committed"

        yield admin, app, owners

    finally:
        try:
            if initialized:
                async with admin() as session, session.begin():
                    for model in (
                        ResearchEvidence,
                        ResearchOperationReservation,
                        ResearchExecutionContext,
                    ):
                        await session.execute(
                            delete(model).where(
                                model.owner_id.in_(owners)
                            )
                        )

                    await session.execute(
                        delete(ResearchExecutionAttempt).where(
                            ResearchExecutionAttempt.owner_id.in_(
                                owners
                            )
                        )
                    )

                    await session.execute(
                        delete(ResearchTask).where(
                            ResearchTask.owner_id.in_(owners)
                        )
                    )

                    await session.execute(
                        delete(User).where(
                            User.id.in_(owners)
                        )
                    )
        finally:
            await runtime.dispose()
            await migrator.dispose()


async def seed(admin, owner, count=1):
    ids = []

    async with admin() as session, session.begin():
        for _ in range(count):
            task = ResearchTask(
                id=uuid4(),
                owner_id=owner,
                question=REQUEST.question,
                scope=REQUEST.scope.model_dump(mode="json"),
                status="queued",
                idempotency_key=str(uuid4()),
                request_fingerprint=REQUEST.fingerprint(),
            )

            session.add(task)
            ids.append(task.id)

        await session.flush()

    return ids


async def lifecycle(app, method, *args):
    async with app() as session:
        service = ExecutionService(
            session,
            isolated_test_scope=True,
        )

        return await getattr(service, method)(*args)


async def parallel(count, operation):
    gate = asyncio.Event()

    async def run(index):
        await gate.wait()
        return await operation(index)

    jobs = [
        asyncio.create_task(run(index))
        for index in range(count)
    ]

    gate.set()

    return await asyncio.gather(*jobs)


async def get_task(admin, task_id):
    async with admin() as session, session.begin():
        return await session.scalar(
            select(ResearchTask).where(
                ResearchTask.id == task_id
            )
        )


async def attempts(admin, task_id):
    async with admin() as session, session.begin():
        return list(
            (
                await session.scalars(
                    select(ResearchExecutionAttempt)
                    .where(
                        ResearchExecutionAttempt.task_id
                        == task_id
                    )
                    .order_by(
                        ResearchExecutionAttempt.generation
                    )
                )
            ).all()
        )


async def active_counts(admin):
    async with admin() as session, session.begin():
        running = await session.scalar(
            select(func.count())
            .select_from(ResearchTask)
            .where(ResearchTask.status == "running")
        )

        active = await session.scalar(
            select(func.count())
            .select_from(ResearchExecutionAttempt)
            .where(
                ResearchExecutionAttempt.ended_at.is_(None)
            )
        )

        owners = (
            await session.execute(
                select(
                    ResearchTask.owner_id,
                    func.count(),
                )
                .where(ResearchTask.status == "running")
                .group_by(ResearchTask.owner_id)
            )
        ).all()

        return running, active, dict(owners)


async def age_attempt(admin, handle, seconds=31):
    """Age test attempt timestamps without changing task deadline."""
    async with admin() as session, session.begin():
        now = await session.scalar(
            select(func.clock_timestamp())
        )

        heartbeat = now - timedelta(seconds=seconds)

        result = await session.execute(
            update(ResearchExecutionAttempt)
            .where(
                ResearchExecutionAttempt.id
                == handle.attempt_id,
                ResearchExecutionAttempt.ended_at.is_(None),
            )
            .values(
                claimed_at=heartbeat,
                heartbeat_at=heartbeat,
                lease_expires_at=heartbeat
                + timedelta(seconds=30),
            )
        )

        assert result.rowcount == 1


async def submit(app, owner, key, capacity=50):
    async with app() as session, session.begin():
        return await admit_task(
            session,
            owner_id=owner,
            idempotency_key=key,
            submission=REQUEST,
            capacity=capacity,
            validation_limits=LIMITS,
        )


def test_ac04_attempt_constraints_and_owner_fk():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]

            handle = await lifecycle(
                app, "claim", uuid4()
            )

            assert handle.task_id == task_id

            row = (await attempts(admin, task_id))[0]

            async def probe(expected_state, **changes):
                values = {
                    "id": uuid4(),
                    "owner_id": row.owner_id,
                    "task_id": row.task_id,
                    "generation": 2,
                    "worker_id": uuid4(),
                    "claimed_at": row.claimed_at,
                    "heartbeat_at": row.heartbeat_at,
                    "lease_expires_at": row.lease_expires_at,
                    "ended_at": row.heartbeat_at,
                    "end_reason": "failed",
                }

                values.update(changes)

                with pytest.raises(IntegrityError) as error:
                    async with admin() as session, session.begin():
                        session.add(
                            ResearchExecutionAttempt(**values)
                        )
                        await session.flush()

                assert error.value.orig.sqlstate == expected_state

            await probe(
                "23505",
                ended_at=None,
                end_reason=None,
            )

            await probe(
                "23505",
                generation=1,
            )

            await probe(
                "23503",
                owner_id=owners[1],
            )

            await probe(
                "23514",
                generation=3,
            )

            await probe(
                "23514",
                lease_expires_at=row.heartbeat_at
                + timedelta(seconds=31),
            )

            await probe(
                "23514",
                ended_at=None,
            )

            assert len(
                await attempts(admin, task_id)
            ) == 1

    asyncio.run(scenario())


def test_ac05_runtime_cannot_delete_attempts_or_modify_schema():
    async def scenario():
        async with database() as (admin, app, owners):
            await seed(admin, owners[0])

            handle = await lifecycle(
                app, "claim", uuid4()
            )

            async with app() as session, session.begin():
                for privilege in ("SELECT", "INSERT", "UPDATE"):
                    assert await session.scalar(
                        text("""
                            SELECT has_table_privilege(
                                current_user,
                                'app.research_execution_attempts',
                                :privilege
                            )
                        """),
                        {"privilege": privilege},
                    )

                for privilege in (
                    "DELETE", "TRUNCATE",
                    "REFERENCES", "TRIGGER",
                ):
                    assert not await session.scalar(
                        text("""
                            SELECT has_table_privilege(
                                current_user,
                                'app.research_execution_attempts',
                                :privilege
                            )
                        """),
                        {"privilege": privilege},
                    )

                assert not await session.scalar(text("""
                    SELECT has_schema_privilege(
                        current_user, 'app', 'CREATE'
                    )
                """))

            with pytest.raises(DBAPIError) as error:
                async with app() as session, session.begin():
                    await session.execute(
                        delete(ResearchExecutionAttempt)
                        .where(
                            ResearchExecutionAttempt.id
                            == handle.attempt_id
                        )
                    )

            assert error.value.orig.sqlstate == "42501"

    asyncio.run(scenario())


def test_ac06_concurrent_single_task_claim_has_one_winner():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]

            results = await parallel(
                8,
                lambda _: lifecycle(
                    app, "claim", uuid4()
                ),
            )

            winners = [
                handle for handle in results
                if handle is not None
            ]

            assert len(winners) == 1
            assert winners[0].task_id == task_id
            assert winners[0].generation == 1

            rows = await attempts(admin, task_id)

            assert len(rows) == 1
            assert rows[0].ended_at is None

    asyncio.run(scenario())


def test_ac07_global_and_per_user_capacity_under_concurrency():
    async def scenario():
        async with database() as (admin, app, owners):
            for owner in owners:
                await seed(admin, owner, count=2)

            results = await parallel(
                12,
                lambda _: lifecycle(
                    app, "claim", uuid4()
                ),
            )

            winners = [
                handle for handle in results
                if handle is not None
            ]

            assert len(winners) == 5

            running, active, per_user = await active_counts(
                admin
            )

            assert running == active == 5
            assert len(per_user) == 5
            assert set(per_user.values()) == {1}

            first = winners[0]

            await lifecycle(
                app, "finish", first, "failed"
            )

            replacement = await lifecycle(
                app, "claim", uuid4()
            )

            assert replacement is not None

            running, active, per_user = await active_counts(
                admin
            )

            assert running == active == 5
            assert set(per_user.values()) == {1}

    asyncio.run(scenario())


def test_ac07_pending_hard_cap_and_idempotency_under_concurrency():
    async def scenario():
        async with database() as (admin, app, owners):
            owner = owners[0]

            await seed(admin, owner, count=49)

            async def contender(index):
                key = f"contender-{index}"

                try:
                    result = await submit(
                        app,
                        owner,
                        key,
                        capacity=1000,
                    )

                    return key, result
                except QueueFull:
                    return key, None

            results = await parallel(8, contender)

            winners = [
                (key, result)
                for key, result in results
                if result is not None
            ]

            assert len(winners) == 1

            key, first = winners[0]

            assert first.created

            replay = await submit(
                app,
                owner,
                key,
                capacity=1000,
            )

            assert not replay.created
            assert replay.task.id == first.task.id

            async with admin() as session, session.begin():
                assert await session.scalar(
                    select(func.count())
                    .select_from(ResearchTask)
                    .where(
                        ResearchTask.status == "queued",
                        ResearchTask.deleted_at.is_(None),
                    )
                ) == 50

            claimed = await lifecycle(
                app, "claim", uuid4()
            )

            assert claimed is not None

            admitted = await submit(
                app,
                owner,
                "released-pending-slot",
                capacity=1000,
            )

            assert admitted.created

            with pytest.raises(QueueFull):
                await submit(
                    app,
                    owner,
                    "overflow",
                    capacity=1000,
                )

    asyncio.run(scenario())


def test_ac07_admission_and_claim_share_capacity_coordination():
    async def scenario():
        async with database() as (admin, app, owners):
            owner = owners[0]

            await seed(admin, owner, count=50)

            async def admission():
                try:
                    return await submit(
                        app,
                        owner,
                        "concurrent-admission",
                        capacity=1000,
                    )
                except QueueFull:
                    return None

            result, claimed = await asyncio.gather(
                admission(),
                lifecycle(app, "claim", uuid4()),
            )

            assert claimed is not None

            async with admin() as session, session.begin():
                pending = await session.scalar(
                    select(func.count())
                    .select_from(ResearchTask)
                    .where(ResearchTask.status == "queued")
                )

                assert pending == (
                    50 if result is not None else 49
                )

            # The exact interleaving is not prescribed.
            # Both valid serial orders preserve the hard cap.
            assert pending <= 50

    asyncio.run(scenario())


def test_ac08_ac09_ac10_recovery_generation_and_heartbeat():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]

            first = await lifecycle(
                app, "claim", uuid4()
            )

            original = await get_task(admin, task_id)
            initial_start = original.started_at

            assert first.generation == 1

            renewed = await lifecycle(
                app, "heartbeat", first
            )

            row = (await attempts(admin, task_id))[0]

            assert renewed == row.lease_expires_at
            assert renewed <= running_deadline(initial_start)

            # A live lease must not be stolen.
            assert await lifecycle(
                app,
                "recover",
                first.owner_id,
                task_id,
                uuid4(),
            ) is None

            await age_attempt(admin, first)

            with pytest.raises(
                ExecutionRejected,
                match="execution_lease_expired",
            ):
                await lifecycle(app, "heartbeat", first)

            recovered = await parallel(
                6,
                lambda _: lifecycle(
                    app,
                    "recover",
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

            second = winners[0]

            assert second.generation == 2
            assert second.attempt_id != first.attempt_id
            assert second.worker_id != first.worker_id

            current = await get_task(admin, task_id)

            assert current.status == "running"
            assert current.started_at == initial_start

            rows = await attempts(admin, task_id)

            assert [row.generation for row in rows] == [1, 2]
            assert rows[0].end_reason == "lease_expired"
            assert rows[0].ended_at is not None
            assert rows[1].ended_at is None

            assert rows[1].lease_expires_at <= (
                running_deadline(initial_start)
            )

            with pytest.raises(
                ExecutionRejected,
                match="stale_execution_handle",
            ):
                await lifecycle(app, "heartbeat", first)

            with pytest.raises(
                ExecutionRejected,
                match="stale_execution_handle",
            ):
                await lifecycle(
                    app, "finish", first, "failed"
                )

            await lifecycle(app, "heartbeat", second)

            await age_attempt(admin, second)

            assert await lifecycle(
                app,
                "recover",
                second.owner_id,
                task_id,
                uuid4(),
            ) is None

            terminal = await get_task(admin, task_id)

            assert terminal.status == "failed"
            assert terminal.error_category == "attempts_exhausted"
            assert terminal.started_at == initial_start

            rows = await attempts(admin, task_id)

            assert len(rows) == 2
            assert all(row.ended_at for row in rows)

    asyncio.run(scenario())


def test_ac10_missing_active_attempt_fails_closed():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]

            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == task_id)
                    .values(
                        status="running",
                        started_at=now,
                        updated_at=now,
                    )
                )

            assert await lifecycle(
                app,
                "recover",
                owners[0],
                task_id,
                uuid4(),
            ) is None

            task = await get_task(admin, task_id)

            assert task.status == "failed"
            assert task.error_category == "indeterminate_execution"
            assert await attempts(admin, task_id) == []

    asyncio.run(scenario())


def test_ac11_forged_handle_rejection_and_terminal_immutability():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (await seed(admin, owners[0]))[0]

            handle = await lifecycle(
                app, "claim", uuid4()
            )

            forged = [
                replace(handle, owner_id=owners[1]),
                replace(handle, task_id=uuid4()),
                replace(handle, attempt_id=uuid4()),
                replace(handle, worker_id=uuid4()),
                replace(handle, generation=2),
            ]

            for candidate in forged:
                with pytest.raises(ExecutionRejected):
                    await lifecycle(
                        app, "heartbeat", candidate
                    )

                with pytest.raises(ExecutionRejected):
                    await lifecycle(
                        app,
                        "finish",
                        candidate,
                        "failed",
                    )

            assert (
                await get_task(admin, task_id)
            ).status == "running"

            await lifecycle(
                app,
                "finish",
                handle,
                "insufficient_evidence",
            )

            finished = await get_task(admin, task_id)

            assert finished.status == "insufficient_evidence"
            assert finished.completed_at is not None

            with pytest.raises(ExecutionRejected):
                await lifecycle(
                    app, "finish", handle, "failed"
                )

            assert await lifecycle(
                app,
                "recover",
                handle.owner_id,
                handle.task_id,
                uuid4(),
            ) is None

            again = await get_task(admin, task_id)

            assert again.status == finished.status
            assert again.completed_at == finished.completed_at
            assert again.error_category == finished.error_category

    asyncio.run(scenario())


def test_ac12_queue_and_running_deadlines():
    async def scenario():
        async with database() as (admin, app, owners):
            expired_id = (
                await seed(admin, owners[0])
            )[0]

            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == expired_id)
                    .values(
                        created_at=now - timedelta(seconds=61)
                    )
                )

            assert await lifecycle(
                app, "claim", uuid4()
            ) is None

            assert await lifecycle(
                app, "expire_one"
            ) is True

            expired = await get_task(admin, expired_id)

            assert expired.status == "timed_out"
            assert expired.started_at is None
            assert expired.error_category == "queue_timeout"

            running_id = (
                await seed(admin, owners[1])
            )[0]

            handle = await lifecycle(
                app, "claim", uuid4()
            )

            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                start = now - timedelta(seconds=181)

                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == running_id)
                    .values(
                        created_at=start - timedelta(seconds=1),
                        started_at=start,
                    )
                )

            # Even a remaining lease cannot authorize a write
            # beyond the task's original execution deadline.
            with pytest.raises(
                ExecutionRejected,
                match="execution_deadline_expired",
            ):
                await lifecycle(app, "heartbeat", handle)

            assert await lifecycle(
                app, "expire_one"
            ) is True

            terminal = await get_task(admin, running_id)

            assert terminal.status == "timed_out"
            assert terminal.error_category == "execution_timeout"
            assert terminal.started_at == start

    asyncio.run(scenario())


def test_ac13_deleted_tasks_cannot_claim_renew_recover_or_finish():
    async def scenario():
        async with database() as (admin, app, owners):
            queued_id = (
                await seed(admin, owners[0])
            )[0]

            async with admin() as session, session.begin():
                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == queued_id)
                    .values(deleted_at=func.clock_timestamp())
                )

            assert await lifecycle(
                app, "claim", uuid4()
            ) is None

            running_id = (
                await seed(admin, owners[1])
            )[0]

            handle = await lifecycle(
                app, "claim", uuid4()
            )

            async with admin() as session, session.begin():
                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == running_id)
                    .values(deleted_at=func.clock_timestamp())
                )

            with pytest.raises(ExecutionRejected):
                await lifecycle(app, "heartbeat", handle)

            with pytest.raises(ExecutionRejected):
                await lifecycle(
                    app, "finish", handle, "failed"
                )

            assert await lifecycle(
                app,
                "recover",
                handle.owner_id,
                running_id,
                uuid4(),
            ) is None

            assert await lifecycle(
                app, "expire_one"
            ) is True

            task = await get_task(admin, running_id)

            assert task.deleted_at is not None
            assert task.status == "failed"

            row = (await attempts(admin, running_id))[0]

            assert row.end_reason == "deleted"
            assert row.ended_at is not None

            assert await active_counts(admin) == (
                0, 0, {}
            )

    asyncio.run(scenario())


def test_ac13_deleted_running_without_active_attempt_releases_slot():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (
                await seed(admin, owners[0])
            )[0]

            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == task_id)
                    .values(
                        status="running",
                        started_at=now,
                        updated_at=now,
                        deleted_at=now,
                    )
                )

            assert await lifecycle(
                app, "expire_one"
            ) is True

            task = await get_task(admin, task_id)

            assert task.status == "failed"
            assert task.error_category == "task_deleted"

            assert await active_counts(admin) == (
                0, 0, {}
            )

    asyncio.run(scenario())


def test_execution_database_guard_rejects_migrator_role():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (
                await seed(admin, owners[0])
            )[0]

            with pytest.raises(
                ExecutionRejected,
                match="unauthorized_execution_database",
            ):
                await lifecycle(
                    admin, "claim", uuid4()
                )

            task = await get_task(admin, task_id)

            assert task.status == "queued"
            assert await attempts(admin, task_id) == []

    asyncio.run(scenario())


def test_claim_transaction_rolls_back_on_attempt_insert_failure():
    async def scenario():
        async with database() as (admin, app, owners):
            task_id = (
                await seed(admin, owners[0])
            )[0]

            # Real DB constraint failure through an injected attempt
            # UUID collision. No database operation is mocked.
            from unittest.mock import patch

            other_id = (
                await seed(admin, owners[1])
            )[0]

            async with admin() as session, session.begin():
                await session.execute(
                    update(ResearchTask)
                    .where(ResearchTask.id == other_id)
                    .values(deleted_at=func.clock_timestamp())
                )

                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                collision_id = uuid4()

                session.add(
                    ResearchExecutionAttempt(
                        id=collision_id,
                        owner_id=owners[1],
                        task_id=other_id,
                        generation=1,
                        worker_id=uuid4(),
                        claimed_at=now,
                        heartbeat_at=now,
                        lease_expires_at=now
                        + timedelta(seconds=30),
                        ended_at=now,
                        end_reason="failed",
                    )
                )

                await session.flush()

            with patch(
                "agentops_api.services.execution.uuid4",
                return_value=collision_id,
            ):
                with pytest.raises(IntegrityError):
                    await lifecycle(
                        app, "claim", uuid4()
                    )

            task = await get_task(admin, task_id)

            assert task.status == "queued"
            assert task.started_at is None
            assert await attempts(admin, task_id) == []

            actual = await lifecycle(
                app, "claim", uuid4()
            )

            assert actual.task_id == task_id
            assert actual.generation == 1

    asyncio.run(scenario())
