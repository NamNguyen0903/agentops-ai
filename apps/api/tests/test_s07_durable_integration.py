"""Actual S05/S06 boundary compatibility, without database acceptance claims."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from agentops_api.agent.durable_hooks import _OBSERVER
from agentops_api.agent.s05.contract import S05GraphInput
from agentops_api.agent.s05.workflow import run_specialized_workflow
from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import SearchRequest, RetrievalRequest
from agentops_api.agent.s06.providers import search_offline
from agentops_api.agent.s06.retrieval import retrieve_offline
from agentops_api.agent.s06.transport import FixtureResolver, FixtureTransport, TransportResponse, TransientTransportError
from agentops_api.services.durable_execution import DurableExecution, operation_identity
from agentops_api.services.execution_budget import BudgetRejected, ReservationHandle
from agentops_api.services.execution_receipts import _Receipt, _issue, _consume
from agentops_api.services.execution_runner import _observe_cleanup


@pytest.mark.parametrize("scope", [False, None, 1])
def test_application_execution_is_disabled_by_default(scope):
    with pytest.raises(BudgetRejected):
        DurableExecution(None, isolated_test_scope=scope)


def reservation():
    return ReservationHandle(
        uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), 1,
        datetime.now(timezone.utc),
    )


def test_receipt_cannot_be_forged_reused_or_rebound():
    a, b = reservation(), reservation()
    with pytest.raises(BudgetRejected):
        _consume(_Receipt(), a)
    receipt = _issue(a, "succeeded")
    with pytest.raises(BudgetRejected):
        _consume(receipt, b)
    with pytest.raises(BudgetRejected):
        _consume(receipt, a)
    receipt = _issue(a, "succeeded")
    assert _consume(receipt, a) == ("succeeded", False)
    with pytest.raises(BudgetRejected):
        _consume(receipt, a)


def test_logical_identity_binds_task_and_request_not_attempt():
    task = uuid4()
    request = RetrievalRequest(url="https://example.com/fixture")
    root = operation_identity(task, "retrieval", request)
    assert root == operation_identity(task, "retrieval", request)
    assert root != operation_identity(uuid4(), "retrieval", request)
    assert root != operation_identity(task, "retrieval", RetrievalRequest(url="https://example.com/other"))
    assert len({operation_identity(task, "retrieval", request, n) for n in range(4)}) == 4


class RecordingObserver:
    def __init__(self):
        self.events = []
    def adapter(self, name, repair, operation, args, kwargs):
        self.events.append((name, repair))
        return operation(*args, **kwargs)
    def acquire(self, kind, operation, args, kwargs, *, hop):
        self.events.append((kind, kwargs.get("redirects", 0), hop))
        return operation(*args, **kwargs)


def test_actual_s05_graph_uses_all_three_accounted_boundaries():
    from langsmith import tracing_context
    observer = RecordingObserver()
    token = _OBSERVER.set(observer)
    try:
        with tracing_context(enabled=False):
            result = run_specialized_workflow(S05GraphInput(
                task_id=uuid4(), attempt_id=uuid4(), question="Compare synthetic fixtures",
            ))
    finally:
        _OBSERVER.reset(token)
    assert result.outcome == "candidate_ready"
    assert result.counters.adapter_invocations == 3
    assert observer.events == [("planner", False), ("research", False), ("writer", False)]


def response(status=200, location=None):
    headers = (("content-type", "text/plain"), ("content-length", "2"))
    if location:
        headers = (("location", location),)
    return TransportResponse(status, headers, (b"ok",), "93.184.216.34", True, "example.com")


def test_actual_s06_retry_and_redirect_reenter_accounted_boundary():
    observer = RecordingObserver()
    token = _OBSERVER.set(observer)
    budget = Budget()
    budget._durable_observer = observer
    try:
        search_offline(SearchRequest(query="synthetic"), budget)
        result = retrieve_offline(
            RetrievalRequest(url="https://example.com/fixture"), budget,
            resolver=FixtureResolver({"example.com": ("93.184.216.34",)}),
            transport=FixtureTransport((TransientTransportError(), response(302, "/next"), response())),
        )
    finally:
        _OBSERVER.reset(token)
    assert result.body == b"ok"
    assert budget.snapshot().searches == 1
    assert budget.snapshot().retrievals == 3
    assert observer.events == [("search", 0, False), ("retrieval", 0, True), ("retrieval", 0, True), ("retrieval", 1, True)]


def test_repeated_cancellation_is_bounded_and_cleanup_remains_owned():
    async def scenario():
        released = asyncio.Event()
        cleanup = asyncio.create_task(released.wait())
        observer = asyncio.create_task(_observe_cleanup(cleanup, timeout_seconds=0.05))
        await asyncio.sleep(0)
        for _ in range(3):
            observer.cancel()
            await asyncio.sleep(0.005)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(observer, 0.5)
        assert not cleanup.done()
        released.set()
        await cleanup
    asyncio.run(scenario())


def test_public_live_authorization_is_still_unconditionally_denied():
    from agentops_api.services.s06_acquisition.authorization import require_live_authorization
    from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
    with pytest.raises(AcquisitionError) as exc:
        require_live_authorization()
    assert exc.value.code == ErrorCode.EXTERNAL_DISABLED
