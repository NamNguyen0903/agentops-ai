"""Disposable PostgreSQL verification for S06 evidence.

No development database, worker, provider, or live
research execution is authorized by this module.
"""

import asyncio
import os
from dataclasses import fields, replace
from datetime import timezone
from uuid import uuid4

import pytest

from sqlalchemy import (
    delete,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from agentops_api.agent.s06.evidence import (
    EvidenceLimitExceeded,
    EvidenceRecord,
    EvidenceRejected,
    EvidenceScope,
    EvidenceUnavailable,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.identity import User
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.evidence import (
    get_evidence,
    list_evidence,
    store_evidence,
)

from test_s06_evidence_domain import page, record


pytestmark = pytest.mark.integration


def disposable_urls():
    if os.getenv("AGENTOPS_RUN_DB_INTEGRATION") != "1":
        pytest.skip("Explicit disposable PostgreSQL opt-in required")

    url = make_url(
        os.environ["AGENTOPS_MIGRATION_DATABASE_URL"]
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "agentops_migration_test"
    assert url.username == "agentops_migrator"
    assert url.password == "isolated-test-only-migrator"
    assert not url.query

    runtime = url.set(
        username="agentops_app",
        password="isolated-test-only-runtime",
    )

    return url, runtime


async def verify_identity(engine, expected_role):
    async with engine.connect() as connection:
        identity = (
            await connection.execute(
                text(
                    "SELECT current_database(), current_user"
                )
            )
        ).one()

        assert tuple(identity) == (
            "agentops_migration_test",
            expected_role,
        )


async def fixture_scenario(callback):
    migrator_url, app_url = disposable_urls()

    engine_options = {
        "hide_parameters": True,
        "isolation_level": "READ COMMITTED",
        "connect_args": {
            "connect_timeout": 3,
            "options": (
                "-c statement_timeout=10000 "
                "-c lock_timeout=5000 "
                "-c timezone=UTC"
            ),
        },
    }

    migrator_engine = create_async_engine(
        migrator_url,
        **engine_options,
    )

    runtime_engine = create_async_engine(
        app_url,
        **engine_options,
    )

    migrator = async_sessionmaker(
        migrator_engine,
        autobegin=False,
        expire_on_commit=False,
    )

    runtime = async_sessionmaker(
        runtime_engine,
        autobegin=False,
        expire_on_commit=False,
    )

    first_owner = uuid4()
    second_owner = uuid4()

    first = EvidenceScope(
        owner_id=first_owner,
        task_id=uuid4(),
        execution_id=uuid4(),
    )

    sibling = EvidenceScope(
        owner_id=first_owner,
        task_id=uuid4(),
        execution_id=uuid4(),
    )

    other = EvidenceScope(
        owner_id=second_owner,
        task_id=uuid4(),
        execution_id=uuid4(),
    )

    owners = (first_owner, second_owner)

    task_ids = (
        first.task_id,
        sibling.task_id,
        other.task_id,
    )

    seeded = False

    try:
        await verify_identity(
            migrator_engine,
            "agentops_migrator",
        )

        await verify_identity(
            runtime_engine,
            "agentops_app",
        )

        async with migrator() as session, session.begin():
            session.add_all([
                User(id=first_owner),
                User(id=second_owner),
            ])

            await session.flush()

            for context in (first, sibling, other):
                session.add(
                    ResearchTask(
                        id=context.task_id,
                        owner_id=context.owner_id,
                        question="Synthetic evidence integration",
                        scope={},
                        status="queued",
                        idempotency_key=str(uuid4()),
                        request_fingerprint=b"x" * 32,
                    )
                )

            await session.flush()

        seeded = True

        await callback(
            runtime,
            migrator,
            first,
            sibling,
            other,
        )

    finally:
        try:
            if seeded:
                async with migrator() as session, session.begin():
                    await session.execute(
                        delete(ResearchEvidence).where(
                            ResearchEvidence.task_id.in_(
                                task_ids
                            )
                        )
                    )

                    await session.execute(
                        delete(ResearchTask).where(
                            ResearchTask.id.in_(task_ids)
                        )
                    )

                    await session.execute(
                        delete(User).where(
                            User.id.in_(owners)
                        )
                    )

        finally:
            await runtime_engine.dispose()
            await migrator_engine.dispose()


def execute(callback):
    asyncio.run(
        asyncio.wait_for(
            fixture_scenario(callback),
            timeout=60,
        )
    )


def values_of(value):
    return {
        item.name: getattr(value, item.name)
        for item in fields(EvidenceRecord)
    }


async def save(runtime, context, value):
    async with runtime() as session, session.begin():
        return await store_evidence(
            session,
            scope=context,
            record=value,
        )


async def fetch(runtime, context, evidence_id):
    async with runtime() as session, session.begin():
        return await get_evidence(
            session,
            scope=context,
            evidence_id=evidence_id,
        )


def test_postgres_round_trip_and_deduplication():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        first = await save(runtime, context, value)
        second = await save(runtime, context, value)

        assert first.created is True
        assert second.created is False
        assert first.record == second.record == value

        loaded = await fetch(
            runtime, context, value.id
        )

        assert loaded == value
        assert loaded.retrieved_at.tzinfo is timezone.utc

        async with runtime() as session, session.begin():
            assert await list_evidence(
                session, scope=context
            ) == (value,)

    execute(scenario)


def test_postgres_scope_isolation():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        await save(runtime, context, value)

        assert await fetch(
            runtime, sibling, value.id
        ) is None

        assert await fetch(
            runtime, other, value.id
        ) is None

        another_execution = replace(
            context, execution_id=uuid4()
        )

        assert await fetch(
            runtime, another_execution, value.id
        ) is None

        wrong_owner = replace(
            context, owner_id=other.owner_id
        )

        with pytest.raises(EvidenceUnavailable):
            await fetch(
                runtime, wrong_owner, value.id
            )

        with pytest.raises(EvidenceRejected):
            await save(runtime, sibling, value)

        with pytest.raises(EvidenceRejected):
            await save(runtime, another_execution, value)

        async with runtime() as session, session.begin():
            assert await list_evidence(
                session, scope=another_execution
            ) == ()

    execute(scenario)


def test_postgres_deleted_task_rejected():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        await save(runtime, context, value)

        # Synthetic test mutation only. The repository itself
        # has no task lifecycle mutation operation.
        async with migrator() as session, session.begin():
            await session.execute(
                update(ResearchTask)
                .where(ResearchTask.id == context.task_id)
                .values(deleted_at=func.now())
            )

        with pytest.raises(EvidenceUnavailable):
            await fetch(runtime, context, value.id)

        with pytest.raises(EvidenceUnavailable):
            await save(runtime, context, value)

        async with runtime() as session, session.begin():
            with pytest.raises(EvidenceUnavailable):
                await list_evidence(
                    session, scope=context
                )

    execute(scenario)


def test_postgres_caller_owned_rollback():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        async with runtime() as session:
            transaction = await session.begin()

            result = await store_evidence(
                session,
                scope=context,
                record=value,
            )

            assert result.created

            await transaction.rollback()

        assert await fetch(
            runtime, context, value.id
        ) is None

    execute(scenario)


def test_postgres_composite_foreign_key_rejection():
    async def scenario(runtime, migrator, context, sibling, other):
        candidate = values_of(record(context))

        candidate["owner_id"] = other.owner_id

        with pytest.raises(IntegrityError) as exc:
            async with runtime() as session, session.begin():
                await session.execute(
                    insert(ResearchEvidence).values(
                        **candidate
                    )
                )

        assert exc.value.orig.sqlstate == "23503"

    execute(scenario)


@pytest.mark.parametrize("field,value", [
    ("title", ""),
    ("excerpt", ""),
    ("excerpt", "x" * 4097),
    ("source_url", "file:///invalid"),
    ("content_hash", b"x"),
    ("acquisition_method", "live_search"),
    ("synthetic", False),
])
def test_postgres_check_constraints(field, value):
    async def scenario(runtime, migrator, context, sibling, other):
        candidate = values_of(record(context))
        candidate[field] = value

        with pytest.raises(IntegrityError) as exc:
            async with runtime() as session, session.begin():
                await session.execute(
                    insert(ResearchEvidence).values(
                        **candidate
                    )
                )

        assert exc.value.orig.sqlstate == "23514"

    execute(scenario)


def test_postgres_publication_timestamp_rejected():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)
        candidate = values_of(value)

        candidate["published_at"] = value.retrieved_at

        with pytest.raises(IntegrityError) as exc:
            async with runtime() as session, session.begin():
                await session.execute(
                    insert(ResearchEvidence).values(
                        **candidate
                    )
                )

        assert exc.value.orig.sqlstate == "23514"

    execute(scenario)


def test_postgres_runtime_immutable_permissions():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        await save(runtime, context, value)

        statements = (
            update(ResearchEvidence)
            .where(ResearchEvidence.id == value.id)
            .values(excerpt="unauthorized"),

            delete(ResearchEvidence)
            .where(ResearchEvidence.id == value.id),

            text(
                "TRUNCATE TABLE app.research_evidence"
            ),

            text(
                "ALTER TABLE app.research_evidence "
                "ADD COLUMN forbidden integer"
            ),

            text(
                "CREATE TABLE app.s06_forbidden_ddl (id integer)"
            ),
        )

        for statement in statements:
            with pytest.raises(DBAPIError) as exc:
                async with runtime() as session, session.begin():
                    await session.execute(statement)

            assert exc.value.orig.sqlstate == "42501"

        assert await fetch(
            runtime, context, value.id
        ) == value

    execute(scenario)


def test_postgres_tampered_stored_hash_rejected():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        await save(runtime, context, value)

        # Deliberate corruption using the disposable migrator.
        async with migrator() as session, session.begin():
            await session.execute(
                update(ResearchEvidence)
                .where(ResearchEvidence.id == value.id)
                .values(content_hash=b"x" * 32)
            )

        with pytest.raises(EvidenceRejected):
            await fetch(runtime, context, value.id)

    execute(scenario)


def test_postgres_concurrent_duplicate_insertions():
    async def scenario(runtime, migrator, context, sibling, other):
        value = record(context)

        ready = asyncio.Event()
        release = asyncio.Event()

        async def first_transaction():
            async with runtime() as session, session.begin():
                result = await store_evidence(
                    session,
                    scope=context,
                    record=value,
                )

                ready.set()
                await release.wait()

                return result

        first_task = asyncio.create_task(
            first_transaction()
        )

        second_task = None

        try:
            await asyncio.wait_for(
                ready.wait(),
                timeout=5,
            )

            second_task = asyncio.create_task(
                save(runtime, context, value)
            )

            await asyncio.sleep(0.1)

            # The first transaction still owns the task lock.
            assert not second_task.done()

        finally:
            release.set()

            pending = [first_task]

            if second_task is not None:
                pending.append(second_task)

            results = await asyncio.wait_for(
                asyncio.gather(
                    *pending,
                    return_exceptions=True,
                ),
                timeout=10,
            )

        assert len(results) == 2

        for result in results:
            assert not isinstance(result, BaseException)

        assert sum(item.created for item in results) == 1

        assert all(
            item.record == value
            for item in results
        )

        async with runtime() as session, session.begin():
            assert await list_evidence(
                session, scope=context
            ) == (value,)

    execute(scenario)


def test_postgres_concurrent_task_wide_limit():
    async def scenario(runtime, migrator, context, sibling, other):
        async with runtime() as session, session.begin():
            for number in range(19):
                candidate = record(
                    context,
                    page=page(
                        body=f"Evidence {number}".encode()
                    ),
                )

                assert (
                    await store_evidence(
                        session,
                        scope=context,
                        record=candidate,
                    )
                ).created

        second_context = replace(
            context,
            execution_id=uuid4(),
        )

        first_candidate = record(
            context,
            page=page(body=b"Final candidate one"),
        )

        second_candidate = record(
            second_context,
            page=page(body=b"Final candidate two"),
        )

        async def attempt(scope, candidate):
            try:
                result = await save(
                    runtime, scope, candidate
                )

                assert result.created
                return "created"

            except EvidenceLimitExceeded:
                return "limit"

        outcomes = await asyncio.wait_for(
            asyncio.gather(
                attempt(context, first_candidate),
                attempt(second_context, second_candidate),
            ),
            timeout=15,
        )

        assert sorted(outcomes) == [
            "created", "limit"
        ]

        async with runtime() as session, session.begin():
            count = await session.scalar(
                select(func.count())
                .select_from(ResearchEvidence)
                .where(
                    ResearchEvidence.owner_id == context.owner_id,
                    ResearchEvidence.task_id == context.task_id,
                )
            )

            assert count == 20

        # Existing duplicates remain readable and reusable
        # even when the task-wide budget is exhausted.
        duplicate = record(
            context,
            page=page(body=b"Evidence 0"),
        )

        assert not (
            await save(runtime, context, duplicate)
        ).created

    execute(scenario)
