"""S07 actual application boundaries against disposable PostgreSQL.

The database and runtime role are real. Search provider responses and offline
retrieval data are deterministic; these cases do not certify live providers
or replace the separate actual DNS/TCP/TLS connector acceptance suite.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from threading import Event
from uuid import uuid4
import pytest
import httpx
from sqlalchemy import delete, select, text, func

from agentops_api.models.execution import ResearchExecutionAttempt
from agentops_api.models.execution_context import ResearchExecutionContext, ResearchOperationReservation
from agentops_api.models.identity import User
from agentops_api.models.research import ResearchTask
from agentops_api.agent.s06.contracts import SearchRequest, RetrievalRequest
from agentops_api.agent.s06.transport import FixtureResolver, FixtureTransport, TransientTransportError
from agentops_api.services.durable_execution import DurableExecution
from agentops_api.services.execution import ExecutionRejected
from agentops_api.services.execution_budget import BudgetRejected, ReservationRequest
from agentops_api.services.execution_receipts import _issue
from test_identity_db_integration import get_test_database_url
from test_s07_execution_postgres import make_engine, factory, seed, lifecycle, age_attempt, FIXTURE_RUNTIME_PASSWORD
from test_s07_durable_integration import response

pytestmark = pytest.mark.integration


@asynccontextmanager
async def database():
    url = get_test_database_url()
    assert (url.host, url.port, url.database, url.username) == (
        "db", 5432, "agentops_migration_test", "agentops_migrator",
    )
    migrator = make_engine(url)
    runtime = make_engine(url.set(username="agentops_app", password=FIXTURE_RUNTIME_PASSWORD), isolation_level="READ COMMITTED")
    admin, app = factory(migrator), factory(runtime)
    owner = uuid4()
    initialized = False
    try:
        async with admin() as session, session.begin():
            assert tuple((await session.execute(text("SELECT current_database(), current_user"))).one()) == ("agentops_migration_test", "agentops_migrator")
            assert await session.scalar(text("SELECT version_num FROM app.alembic_version")) == "d8b3105f0804"
            assert await session.scalar(select(func.count()).select_from(ResearchTask)) == 0
            session.add(User(id=owner))
        initialized = True
        await seed(admin, owner)
        handle = await lifecycle(app, "claim", uuid4())
        assert handle is not None
        yield admin, app, handle, DurableExecution(app, isolated_test_scope=True)
    finally:
        try:
            if initialized:
                async with admin() as session, session.begin():
                    for model in (ResearchOperationReservation, ResearchExecutionContext, ResearchExecutionAttempt, ResearchTask, User):
                        key = model.id if model is User else model.owner_id
                        await session.execute(delete(model).where(key == owner))
        finally:
            await runtime.dispose()
            await migrator.dispose()


async def ledger(admin, handle):
    async with admin() as session, session.begin():
        return list((await session.scalars(select(ResearchOperationReservation).where(
            ResearchOperationReservation.task_id == handle.task_id,
        ).order_by(ResearchOperationReservation.reserved_at))).all())


def test_actual_s05_adapter_results_are_durably_accounted():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            result = await engine.run_s05(handle)
            assert result.outcome == "candidate_ready"
            rows = await ledger(admin, handle)
            assert len(rows) == 3
            assert all(r.kind == "adapter" and r.status == "succeeded" for r in rows)
            assert all(r.dispatched_at >= r.reserved_at and r.resolved_at <= r.deadline_at for r in rows)
            snapshot = await engine._call("snapshot", handle)
            assert snapshot.adapter_invocations == 3 and snapshot.model_calls == 0
            # Duplicate workflow cannot reset or replay a completed stage.
            with pytest.raises(BudgetRejected):
                await engine.run_s05(handle)
            assert len(await ledger(admin, handle)) == 3
    asyncio.run(scenario())


def test_reservation_and_dispatch_are_committed_before_actual_provider_boundary():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            loop = asyncio.get_running_loop()
            observed = []
            async def inspect():
                rows = await ledger(admin, handle)
                assert len(rows) == 1 and rows[0].status == "dispatching"
                # Acquiring this lock on a separate connection proves the
                # dispatch does not retain the queue coordination transaction.
                async with admin() as session, session.begin():
                    await session.execute(text("SELECT id FROM app.queue_control WHERE id=1 FOR UPDATE NOWAIT"))
                observed.append(True)
            def respond(request):
                asyncio.run_coroutine_threadsafe(inspect(), loop).result(timeout=3)
                return httpx.Response(200, json={"results": [], "usage": {"credits": 1}})
            result = await engine.search_isolated(handle, SearchRequest(query="synthetic"), transport=httpx.MockTransport(respond))
            assert result.synthetic is True and observed == [True]
            rows = await ledger(admin, handle)
            assert rows[0].status == "succeeded"
            assert rows[0].actual_cost_microusd is None
    asyncio.run(scenario())


def test_retry_redirect_cumulative_accounting_and_original_deadline():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            result = await engine.retrieve_offline(
                handle, RetrievalRequest(url="https://example.com/start"),
                resolver=FixtureResolver({"example.com": ("93.184.216.34",)}),
                transport=FixtureTransport((TransientTransportError(), response(302, "/next"), response())),
            )
            assert result.body == b"ok"
            rows = await ledger(admin, handle)
            assert len(rows) == 3
            assert [r.status for r in rows] == ["failed", "succeeded", "succeeded"]
            assert [r.retry_ordinal for r in rows] == [0, 1, 0]
            assert rows[0].operation_id == rows[1].operation_id != rows[2].operation_id
            assert all(r.deadline_at <= rows[0].deadline_at for r in rows)
            assert (await engine._call("snapshot", handle)).retrieval_calls == 3
    asyncio.run(scenario())


def test_parallel_duplicate_search_cannot_dispatch_twice():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            request = SearchRequest(query="same logical operation")
            results = await asyncio.gather(
                engine.search_offline(handle, request),
                DurableExecution(app, isolated_test_scope=True).search_offline(handle, request),
                return_exceptions=True,
            )
            rows = await ledger(admin, handle)
            assert len(rows) == 1
            assert sum(not isinstance(r, Exception) for r in results) <= 1
            assert (await engine._call("snapshot", handle)).search_calls == 1
    asyncio.run(scenario())


def test_recovery_keeps_original_counters_deadline_and_rejects_stale_outcome():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            await engine.search_offline(handle, SearchRequest(query="prior operation"))
            before = await engine._call("snapshot", handle)
            row = (await ledger(admin, handle))[0]
            await age_attempt(admin, handle)
            next_handle = await lifecycle(app, "recover", handle.owner_id, handle.task_id, uuid4())
            assert next_handle is not None and next_handle.generation == 2
            after = await engine._call("snapshot", next_handle)
            assert after == before
            with pytest.raises((BudgetRejected, ExecutionRejected)):
                await engine.search_offline(handle, SearchRequest(query="stale"))
            assert len(await ledger(admin, next_handle)) == 1
    asyncio.run(scenario())


def test_reservation_then_crash_is_never_refunded_or_retried():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            reservation = await engine._call("reserve", handle, ReservationRequest(uuid4(), "search"))
            before = await engine._call("snapshot", handle)
            await age_attempt(admin, handle)
            assert await lifecycle(app, "recover", handle.owner_id, handle.task_id, uuid4()) is None
            async with admin() as session, session.begin():
                context = await session.get(ResearchExecutionContext, handle.task_id)
                task = await session.get(ResearchTask, handle.task_id)
                assert context.search_calls == before.search_calls == 1
                assert context.deadline_at == before.deadline_at
                assert context.blocked_at is not None and task.status == "failed"
            rows = await ledger(admin, handle)
            assert rows[0].status == "indeterminate" and not rows[0].retry_eligible
    asyncio.run(scenario())


def test_cancel_discards_late_provider_result_and_keeps_charge():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            entered, release = Event(), Event()
            def respond(request):
                entered.set()
                assert release.wait(3)
                return httpx.Response(200, json={"results": [], "usage": {"credits": 1}})
            job = asyncio.create_task(engine.search_isolated(handle, SearchRequest(query="cancelled"), transport=httpx.MockTransport(respond)))
            try:
                async with asyncio.timeout(3):
                    while not entered.is_set():
                        await asyncio.sleep(0.005)
                job.cancel()
                await asyncio.sleep(0)
                job.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(job, 1.5)
            finally:
                release.set()
                from agentops_api.services.durable_execution import _ACTIVE
                async with asyncio.timeout(3):
                    while handle.task_id in _ACTIVE or engine._pending:
                        await asyncio.sleep(0.005)
            rows = await ledger(admin, handle)
            assert len(rows) == 1 and rows[0].status == "indeterminate"
            snapshot = await engine._call("snapshot", handle)
            assert snapshot.blocked and snapshot.search_calls == 1
    asyncio.run(scenario())


def test_forged_receipt_and_stale_generation_cannot_reconcile():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            from agentops_api.services.execution_receipts import _Receipt
            reservation = await engine._call("reserve", handle, ReservationRequest(uuid4(), "search"))
            await engine._call("begin_dispatch", handle, reservation)
            with pytest.raises(BudgetRejected):
                await engine._call("_complete_actual", handle, reservation, _Receipt())
            with pytest.raises((BudgetRejected, ExecutionRejected)):
                await engine._call("_complete_actual", replace(handle, generation=2), reservation, _issue(reservation, "succeeded"))
            assert (await ledger(admin, handle))[0].status == "dispatching"
    asyncio.run(scenario())


@pytest.mark.parametrize(("kind", "limit"), [("search", 6), ("retrieval", 12)])
def test_cumulative_limits_prevent_an_extra_actual_dispatch(kind, limit):
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async def perform(index):
                if kind == "search":
                    return await engine.search_offline(handle, SearchRequest(query=f"fixture {index}"))
                return await engine.retrieve_offline(
                    handle, RetrievalRequest(url=f"https://example.com/fixture-{index}"),
                    resolver=FixtureResolver({"example.com": ("93.184.216.34",)}),
                    transport=FixtureTransport((response(),)),
                )
            for index in range(limit):
                await perform(index)
            with pytest.raises(BudgetRejected):
                await perform(limit)
            rows = await ledger(admin, handle)
            assert len(rows) == limit and all(r.status == "succeeded" for r in rows)
            snapshot = await engine._call("snapshot", handle)
            assert getattr(snapshot, "search_calls" if kind == "search" else "retrieval_calls") == limit
    asyncio.run(scenario())


def test_expired_reservation_never_enters_dispatch():
    async def scenario():
        from datetime import timedelta
        async with database() as (admin, app, handle, engine):
            reservation = await engine._call("reserve", handle, ReservationRequest(uuid4(), "search"))
            await asyncio.sleep(0.03)
            async with admin() as session, session.begin():
                row = await session.get(ResearchOperationReservation, reservation.reservation_id)
                row.deadline_at = row.reserved_at + timedelta(milliseconds=1)
                expired = replace(reservation, deadline_at=row.deadline_at)
            with pytest.raises(BudgetRejected):
                await engine._call("begin_dispatch", handle, expired)
            rows = await ledger(admin, handle)
            assert rows[0].status == "reserved" and rows[0].dispatched_at is None
            assert (await engine._call("snapshot", handle)).search_calls == 1
    asyncio.run(scenario())


from test_s06_isolated_network import certificates


def test_actual_s06_tls_http_redirect_accounting(monkeypatch, certificates):
    from test_s06_final_security import LocalTLSConnector, reply, text_reply
    from agentops_api.services.s06_acquisition import pinned_transport as pinned
    connector = LocalTLSConnector(certificates, [
        reply(b"302 Found", (b"Location: https://example.org/next",)),
        text_reply(b"accounted isolated response"),
    ])
    loop = None
    inspected = []
    async def scenario():
        nonlocal loop
        loop = asyncio.get_running_loop()
        async with database() as (admin, app, handle, engine):
            async def inspect():
                rows = await ledger(admin, handle)
                assert rows[-1].status == "dispatching"
                async with admin() as session, session.begin():
                    await session.execute(text("SELECT id FROM app.queue_control WHERE id=1 FOR UPDATE NOWAIT"))
                inspected.append(len(rows))
            def connect(target, budget, deadline):
                asyncio.run_coroutine_threadsafe(inspect(), loop).result(timeout=3)
                return connector.connect(target, budget, deadline)
            monkeypatch.setattr(pinned, "_connect_bound", connect)
            result = await engine.retrieve_isolated(
                handle, RetrievalRequest(url="https://example.com/start"),
                resolver=FixtureResolver({"example.com": ("1.1.1.1",), "example.org": ("8.8.8.8",)}),
            )
            assert result.body == b"accounted isolated response"
            assert inspected == [1, 2]
            rows = await ledger(admin, handle)
            assert len(rows) == 2 and all(r.status == "succeeded" for r in rows)
            assert rows[1].deadline_at <= rows[0].deadline_at
            assert (await engine._call("snapshot", handle)).retrieval_calls == 2
    try:
        asyncio.run(scenario())
    finally:
        connector.finish()


def test_actual_s06_invalid_http_fails_closed_with_charge(monkeypatch, certificates):
    from test_s06_final_security import LocalTLSConnector
    from agentops_api.services.s06_acquisition import pinned_transport as pinned
    connector = LocalTLSConnector(certificates, [b"not HTTP\r\n\r\n"])
    monkeypatch.setattr(pinned, "_connect_bound", connector.connect)
    async def scenario():
        async with database() as (admin, app, handle, engine):
            with pytest.raises(BudgetRejected):
                await engine.retrieve_isolated(
                    handle, RetrievalRequest(url="https://example.com/start"),
                    resolver=FixtureResolver({"example.com": ("1.1.1.1",)}),
                )
            snapshot = await engine._call("snapshot", handle)
            assert snapshot.retrieval_calls == 1 and snapshot.blocked
            rows = await ledger(admin, handle)
            assert rows[0].status == "indeterminate" and not rows[0].retry_eligible
    try:
        asyncio.run(scenario())
    finally:
        connector.finish()



def test_actual_s05_repair_uses_the_same_durable_allowance(monkeypatch):
    from agentops_api.agent.s05 import planner
    original = planner.plan_fixture
    calls = []
    def once(context):
        result = original(context)
        calls.append(True)
        return result.model_copy(update={"assumptions": ("",)}) if len(calls) == 1 else result
    monkeypatch.setattr(planner, "plan_fixture", once)
    async def scenario():
        async with database() as (admin, app, handle, engine):
            result = await engine.run_s05(handle)
            assert result.outcome == "candidate_ready"
            assert result.counters.adapter_invocations == 4 and result.counters.repair_attempts == 1
            rows = await ledger(admin, handle)
            assert len(rows) == 4 and sum(row.is_repair for row in rows) == 1
            assert [row.status for row in rows] == ["failed", "succeeded", "succeeded", "succeeded"]
    asyncio.run(scenario())


def test_disposable_runtime_grants_for_accounting():
    from sqlalchemy.exc import DBAPIError
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with app() as session, session.begin():
                for table in ("research_execution_contexts", "research_operation_ledger"):
                    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        actual = await session.scalar(text("SELECT has_table_privilege(current_user, :table, :privilege)"), {"table": "app." + table, "privilege": privilege})
                        assert actual is (privilege != "DELETE")
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(text("DELETE FROM app.research_operation_ledger WHERE false"))
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(text("CREATE TABLE app.s07_unauthorized_probe(id integer)"))
    asyncio.run(scenario())


def test_durable_model_tokens_and_estimated_cost_do_not_refund():
    async def scenario():
        async with database() as (admin, app, handle, engine):
            for _ in range(4):
                assert await engine._call("execute_synthetic", handle,
                    ReservationRequest(uuid4(), "model", reserved_tokens=10000, reserved_cost_microusd=250000)) == "succeeded"
            with pytest.raises(BudgetRejected):
                await engine._call("execute_synthetic", handle,
                    ReservationRequest(uuid4(), "model", reserved_tokens=1))
            snapshot = await engine._call("snapshot", handle)
            assert snapshot.model_calls == 4
            assert snapshot.reserved_tokens == 40000 and snapshot.reserved_cost_microusd == 1000000
            assert len(await ledger(admin, handle)) == 4
    asyncio.run(scenario())


def test_original_task_deadline_rejects_actual_dispatch():
    from datetime import timedelta
    from sqlalchemy import update
    async def scenario():
        async with database() as (admin, app, handle, engine):
            async with admin() as session, session.begin():
                now = await session.scalar(select(func.clock_timestamp()))
                started = now - timedelta(seconds=181)
                await session.execute(update(ResearchTask).where(ResearchTask.id == handle.task_id).values(created_at=started-timedelta(seconds=1), started_at=started))
                await session.execute(update(ResearchExecutionContext).where(ResearchExecutionContext.task_id == handle.task_id).values(started_at=started, deadline_at=started+timedelta(seconds=180)))
            with pytest.raises((BudgetRejected, ExecutionRejected)):
                await engine.search_offline(handle, SearchRequest(query="expired task"))
            assert await ledger(admin, handle) == []
    asyncio.run(scenario())


def test_expired_authority_discards_late_success_and_recovery_is_fail_closed():
    from datetime import timedelta
    from time import monotonic
    from sqlalchemy import update
    from agentops_api.services.durable_execution import _ACTIVE
    async def scenario():
        async with database() as (admin, app, handle, engine):
            entered, release = Event(), Event()
            def delayed(request):
                entered.set()
                assert release.wait(3)
                return httpx.Response(200, json={"results": [], "usage": {"credits": 1}})
            async with admin() as session, session.begin():
                now = await session.scalar(select(func.clock_timestamp()))
                await session.execute(update(ResearchExecutionAttempt).where(ResearchExecutionAttempt.id == handle.attempt_id).values(lease_expires_at=now+timedelta(seconds=1)))
            before = monotonic()
            try:
                with pytest.raises((BudgetRejected, ExecutionRejected)):
                    await engine.search_isolated(handle, SearchRequest(query="late result"), transport=httpx.MockTransport(delayed))
                assert entered.is_set() and monotonic() - before < 3.0
            finally:
                release.set()
                async with asyncio.timeout(3):
                    while handle.task_id in _ACTIVE or engine._pending:
                        await asyncio.sleep(0.005)
            assert await lifecycle(app, "recover", handle.owner_id, handle.task_id, uuid4()) is None
            rows = await ledger(admin, handle)
            assert len(rows) == 1 and rows[0].status == "indeterminate"
            async with admin() as session, session.begin():
                context = await session.get(ResearchExecutionContext, handle.task_id)
                assert context.search_calls == 1 and context.blocked_at is not None
    asyncio.run(scenario())


# S07 WP04 R04: actual synchronous boundaries, not synthetic
# subprocess termination. The deadline variant uses a conservative
# timing seam AFTER reading the real durable remaining authority.
# It never extends a reservation, task deadline, or lease.
async def _r04_cancel_actual(
    engine, handle, admin, make_job, entered, release,
    mode, monkeypatch, expected_kind,
):
    from agentops_api.services.durable_execution import _ACTIVE

    original_call = engine._call

    if mode == "deadline":
        async def narrowed(method, *args, **kwargs):
            value = await original_call(
                method, *args, **kwargs
            )
            if method == "_actual_remaining":
                return min(value, 1.0)
            return value

        monkeypatch.setattr(engine, "_call", narrowed)

    job = asyncio.create_task(make_job())

    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                if job.done():
                    await job
                    raise AssertionError(
                        "Actual boundary was not entered"
                    )
                await asyncio.sleep(0.005)

        # The reservation must already be durable before
        # cancellation or timeout is observed by the caller.
        rows = await ledger(admin, handle)
        assert len(rows) == 1
        assert rows[0].kind == expected_kind
        assert rows[0].status == "dispatching"
        assert rows[0].dispatched_at is not None

        if mode == "cancel":
            job.cancel()
            await asyncio.sleep(0)
            job.cancel()

            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(
                    asyncio.shield(job), 2.5
                )
        else:
            with pytest.raises(
                BudgetRejected,
                match="execution_observation_expired",
            ):
                await asyncio.wait_for(
                    asyncio.shield(job), 2.5
                )

        # Caller returned while the synchronous operation
        # was still deliberately blocked. Do NOT certify
        # thread termination or remote cancellation.
        assert not release.is_set()
        assert handle.task_id in _ACTIVE
        assert _ACTIVE[handle.task_id].is_alive()

        async with asyncio.timeout(3):
            while engine._pending:
                await asyncio.sleep(0.005)

        rows = await ledger(admin, handle)

        assert len(rows) == 1
        assert rows[0].status == "indeterminate"
        assert not rows[0].retry_eligible

        snapshot = await engine._call("snapshot", handle)
        assert snapshot.blocked

        if expected_kind == "adapter":
            assert snapshot.adapter_invocations == 1
            assert snapshot.repair_attempts == 0
        else:
            assert snapshot.retrieval_calls == 1

        # No second local execution while the first thread
        # and its cleanup ownership remain active.
        with pytest.raises(BudgetRejected):
            await make_job()

        assert len(await ledger(admin, handle)) == 1

    finally:
        release.set()

        if not job.done():
            job.cancel()

        await asyncio.wait_for(
            asyncio.gather(job, return_exceptions=True),
            5,
        )

        async with asyncio.timeout(5):
            while handle.task_id in _ACTIVE or engine._pending:
                await asyncio.sleep(0.005)

    # Late success must not become an authoritative outcome.
    rows = await ledger(admin, handle)
    assert len(rows) == 1
    assert rows[0].status == "indeterminate"
    assert not rows[0].retry_eligible

    with pytest.raises(BudgetRejected):
        await make_job()

    assert len(await ledger(admin, handle)) == 1


@pytest.mark.parametrize("mode", ["cancel", "deadline"])
def test_r04_actual_s05_cancellation(
    monkeypatch, mode
):
    from agentops_api.agent.s05 import planner
    from agentops_api.agent.s05.workflow import (
        run_specialized_workflow,
    )

    assert callable(run_specialized_workflow)

    original = planner.plan_fixture
    entered = Event()
    release = Event()
    calls = []

    def delayed_planner(context):
        calls.append(True)
        value = original(context)
        entered.set()

        assert release.wait(8)
        return value

    monkeypatch.setattr(
        planner, "plan_fixture", delayed_planner
    )

    async def scenario():
        async with database() as (
            admin, app, handle, engine
        ):
            await _r04_cancel_actual(
                engine,
                handle,
                admin,
                lambda: engine.run_s05(handle),
                entered,
                release,
                mode,
                monkeypatch,
                "adapter",
            )

            assert len(calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["cancel", "deadline"])
def test_r04_actual_s06_retrieval_cancellation(
    monkeypatch, certificates, mode
):
    from test_s06_final_security import (
        LocalTLSConnector,
        reply,
    )
    from agentops_api.services.s06_acquisition import (
        pinned_transport as pinned,
        integrated_retrieval as integrated,
    )

    # Execute the real isolated TLS/HTTP connector first.
    # Pause its returned redirect at the acquisition boundary.
    # A late response must never dispatch a second hop.
    connector = LocalTLSConnector(
        certificates,
        [
            reply(
                b"302 Found",
                (b"Location: https://example.org/next",),
            )
        ],
    )

    monkeypatch.setattr(
        pinned, "_connect_bound", connector.connect
    )

    original = integrated.exchange

    entered = Event()
    release = Event()
    calls = []

    def delayed_exchange(*args, **kwargs):
        calls.append(True)

        value = original(*args, **kwargs)

        entered.set()
        assert release.wait(8)

        return value

    monkeypatch.setattr(
        integrated, "exchange", delayed_exchange
    )

    async def scenario():
        async with database() as (
            admin, app, handle, engine
        ):
            def make_job():
                return engine.retrieve_isolated(
                    handle,
                    RetrievalRequest(
                        url="https://example.com/start"
                    ),
                    resolver=FixtureResolver({
                        "example.com": ("1.1.1.1",),
                        "example.org": ("8.8.8.8",),
                    }),
                )

            await _r04_cancel_actual(
                engine,
                handle,
                admin,
                make_job,
                entered,
                release,
                mode,
                monkeypatch,
                "retrieval",
            )

            assert len(calls) == 1

    try:
        asyncio.run(scenario())
    finally:
        connector.finish()
