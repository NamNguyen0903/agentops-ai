"""Isolated application integration of actual S05/S06 execution boundaries.

Short database transactions execute on the owning event loop. Synchronous
adapter/connector work executes on a bounded daemon thread, with no database
transaction held across dispatch. A thread is NOT forcibly cancellable.
Timeout or cancellation revokes dispatch, discards late results and blocks
the durable context. The thread retains resource cleanup ownership until it
exits. A reserved/dispatching row remains fail-closed if reconciliation fails.

No public worker, caller-supplied callable or live entrypoint is exposed.
"""
import asyncio
import concurrent.futures
from hashlib import sha256
import json
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid5

from agentops_api.agent.durable_hooks import _OBSERVER
from agentops_api.agent.s06.budgets import Budget
from agentops_api.services.execution_budget import (
    BudgetRejected, ExecutionBudgetService, ReservationRequest,
)
from agentops_api.services.execution_receipts import _issue
from agentops_api.services.execution_runner import _observe_cleanup

_ACTIVE = {}
_ACTIVE_LOCK = Lock()


def operation_identity(task_id, kind, request, hop=0):
    if kind not in {"search", "retrieval"} or type(hop) is not int or not 0 <= hop <= 3:
        raise BudgetRejected("invalid_logical_operation")
    from agentops_api.agent.s06.contracts import (
        SearchRequest, RetrievalRequest, validate_contract,
    )
    schema = SearchRequest if kind == "search" else RetrievalRequest
    checked = validate_contract(schema, request)
    data = json.dumps(checked.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    root = uuid5(task_id, "s07:" + kind + ":" + sha256(data.encode()).hexdigest())
    return root if hop == 0 else uuid5(root, f"hop:{hop}")


class _Observer:
    def __init__(self, owner, handle, loop, deadline, kind, request):
        self.owner, self.handle, self.loop = owner, handle, loop
        self.deadline, self.kind, self.request = deadline, kind, request
        self.stopped = Event()
        self.retries = {}
        self.operation_deadline = None
        self.synthetic_provider = False

    def check(self):
        if self.stopped.is_set() or monotonic() >= self.deadline:
            raise BudgetRejected("execution_observation_expired")

    def call(self, method, *args, **kwargs):
        self.check()
        future = asyncio.run_coroutine_threadsafe(
            self.owner._tracked_call(method, self.handle, *args, **kwargs), self.loop,
        )
        # Never cancel an unknown commit. Retain its session/task and let
        # fenced reconciliation/recovery determine the durable outcome.
        try:
            value = future.result(timeout=max(0.001, self.deadline - monotonic()))
        except concurrent.futures.TimeoutError:
            self.stopped.set()
            raise BudgetRejected("accounting_observation_expired") from None
        self.check()
        return value

    def begin(self, reservation):
        started = monotonic()
        self.call("begin_dispatch", reservation)
        remaining = self.call("_actual_remaining", reservation)
        self.deadline = min(self.deadline, started + remaining)
        self.check()

    def finish(
        self, reservation, outcome, *, retryable=False, credits=None
    ):
        receipt = _issue(
            reservation, outcome,
            retryable=retryable, provider_credits=credits,
        )
        accepted = self.call("_complete_actual", reservation, receipt)
        if accepted == "indeterminate":
            raise BudgetRejected("indeterminate_operation")

    def acquire(self, kind, operation, args, kwargs, *, hop):
        self.check()
        if kind != self.kind:
            raise BudgetRejected("operation_kind_mismatch")
        index = kwargs.get("redirects", 0) if hop else 0
        operation_id = operation_identity(self.handle.task_id, kind, self.request, index)
        root = operation_identity(self.handle.task_id, kind, self.request)
        ordinal = self.retries.get(index, 0)
        reservation = self.call(
            "reserve", ReservationRequest(operation_id, kind, retry_ordinal=ordinal),
            _root_operation_id=root,
            _synthetic_provider_request=(
                self.request if self.synthetic_provider else None
            ),
        )
        self.begin(reservation)
        try:
            result = operation(*args, **kwargs)
        except Exception as exc:
            from agentops_api.agent.s06.transport import TransientTransportError
            from agentops_api.services.s06_acquisition.transport_failures import RetryableTransportFailure
            eligible = (kind == "retrieval" and type(exc) in {
                TransientTransportError, RetryableTransportFailure,
            })
            self.finish(reservation, "failed" if eligible else "indeterminate", retryable=eligible)
            if eligible:
                self.retries[index] = ordinal + 1
            raise
        credits = None
        if self.synthetic_provider:
            from agentops_api.services.provider_accounting import (
                observed_synthetic_credits,
            )
            try:
                credits = observed_synthetic_credits(result)
            except Exception:
                self.finish(reservation, "indeterminate")
                raise

        self.finish(reservation, "succeeded", credits=credits)
        return result

    def search_smoke(self, request, budget):
        from agentops_api.services.s06_acquisition.tavily import search_live

        self.check()

        reservation = self.call("_reserve_smoke_search", request)

        ticket, deadline = self.call(
            "_begin_smoke_search_wire",
            reservation, request, self.stopped,
        )

        self.deadline = min(self.deadline, deadline)
        budget._deadline = min(budget._deadline, self.deadline)

        # This controlled operation already owns durable accounting.
        # Do not enter the generic synthetic acquisition observer.
        budget._durable_observer = None

        self.check()
        # The controlled path already committed its durable reservation.
        # The Tavily decorator observes a ContextVar, not only Budget.
        token = _OBSERVER.set(None)
        try:
            result = search_live(request, budget, _wire_ticket=ticket)
        finally:
            _OBSERVER.reset(token)
        self.check()

        accepted = self.call(
            "_complete_smoke_search", reservation, ticket
        )

        if accepted != "succeeded":
            raise BudgetRejected("indeterminate_operation")

        return result

    def retrieval_smoke(self, request, budget):
        from agentops_api.services.s06_acquisition.controlled_retrieval import (
            retrieve_controlled,
        )

        self.check()

        reservation = self.call("_reserve_smoke_retrieval", request)

        ticket, deadline = self.call(
            "_begin_smoke_retrieval_wire",
            reservation, request, self.stopped,
        )

        self.deadline = min(self.deadline, deadline)
        budget._deadline = min(budget._deadline, self.deadline)
        budget._durable_observer = None

        self.check()
        retrieve_controlled(request, budget, ticket=ticket)
        self.check()

        return self.call(
            "_complete_smoke_retrieval", reservation, ticket
        )

    def adapter(self, name, repair, operation, args, kwargs):
        self.check()
        if self.kind != "s05" or type(repair) is not bool:
            raise BudgetRejected("adapter_authority_invalid")
        reservation = self.call("_reserve_stage", name, repair)
        self.begin(reservation)
        try:
            raw = operation(*args, **kwargs)
            outcome = self._adapter_outcome(name, args, raw)
        except Exception:
            self.finish(reservation, "indeterminate")
            raise
        self.finish(reservation, outcome)
        return raw

    @staticmethod
    def _adapter_outcome(name, args, raw):
        from agentops_api.agent.s05.adapters import (
            _validate_research_plan, validate_fixture_research_output,
        )
        from agentops_api.agent.s05.planner import _planner_repair_eligible
        from agentops_api.agent.s05.report import validate_draft_report, _writer_repair_eligible
        if name == "planner":
            try:
                _validate_research_plan(raw)
            except Exception:
                if _planner_repair_eligible(raw):
                    return "failed"
                raise
        elif name == "research":
            validate_fixture_research_output(*args, raw)
        elif name == "writer":
            try:
                validate_draft_report(*args, raw)
            except Exception:
                if _writer_repair_eligible(*args, raw):
                    return "failed"
                raise
        else:
            raise BudgetRejected("adapter_identity_invalid")
        return "succeeded"


class DurableExecution:
    """Internal test-scope service, detached from API and worker startup."""
    def __init__(self, session_factory, *, isolated_test_scope=False):
        if isolated_test_scope is not True:
            raise BudgetRejected("isolated_execution_required")
        self._factory = session_factory
        self._db_lock = asyncio.Lock()
        self._pending = set()

    async def _call(self, method, handle, *args, **kwargs):
        # Every callback owns its session, including delayed cleanup.
        async with self._db_lock, self._factory() as session:
            service = ExecutionBudgetService(session, isolated_test_scope=True)
            return await getattr(service, method)(handle, *args, **kwargs)

    async def _tracked_call(self, method, handle, *args, **kwargs):
        task = asyncio.current_task()
        self._pending.add(task)
        try:
            return await self._call(method, handle, *args, **kwargs)
        finally:
            self._pending.discard(task)

    async def run_s05(self, handle):
        return await self._run(handle, "s05", None, None)

    async def _search_smoke(self, handle, request):
        from agentops_api.services.smoke_runtime import (
            require as require_live_authorization,
        )

        require_live_authorization()

        return await self._run(
            handle, "search", request, ("controlled-smoke",)
        )

    async def search_offline(self, handle, request):
        return await self._run(handle, "search", request, ("offline",))

    async def search_isolated(self, handle, request, *, transport):
        import httpx
        if type(transport) is not httpx.MockTransport:
            raise BudgetRejected("isolated_transport_required")
        return await self._run(handle, "search", request, ("isolated", transport))

    async def _retrieve_smoke(self, handle, request):
        from agentops_api.services.smoke_runtime import (
            require as require_live_authorization,
        )

        require_live_authorization()

        return await self._run(
            handle, "retrieval", request, ("controlled-smoke",)
        )

    async def retrieve_offline(self, handle, request, *, resolver, transport):
        from agentops_api.agent.s06.transport import FixtureResolver, FixtureTransport
        if type(resolver) is not FixtureResolver or type(transport) is not FixtureTransport:
            raise BudgetRejected("isolated_transport_required")
        return await self._run(handle, "retrieval", request, ("offline", resolver, transport))

    async def retrieve_isolated(self, handle, request, *, resolver):
        from agentops_api.agent.s06.transport import FixtureResolver
        if type(resolver) is not FixtureResolver:
            raise BudgetRejected("isolated_resolver_required")
        return await self._run(handle, "retrieval", request, ("isolated", resolver))

    async def _run(self, handle, kind, request, fixture):
        from agentops_api.services.s06_workflow import require_tracing_disabled
        require_tracing_disabled()
        started = monotonic()
        graph_input, remaining, snapshot = await self._call("_actual_input", handle)
        if kind != "s05":
            from agentops_api.agent.s06.contracts import SearchRequest, RetrievalRequest, validate_contract
            request = validate_contract(SearchRequest if kind == "search" else RetrievalRequest, request)
            operation_identity(handle.task_id, kind, request)
        loop = asyncio.get_running_loop()
        deadline = started + remaining
        if kind != "s05":
            deadline = min(deadline, started + 15.0)
        observer = _Observer(self, handle, loop, deadline, kind, request)
        observer.synthetic_provider = (
            kind == "search" and fixture[0] == "isolated"
        )
        completion = loop.create_future()

        def publish(value, error):
            if not completion.done():
                completion.set_result((value, error))

        def execute():
            token = _OBSERVER.set(observer)
            value, error = None, False
            try:
                observer.check()
                if kind == "s05":
                    from langsmith import tracing_context
                    from agentops_api.agent.s05.workflow import run_specialized_workflow
                    with tracing_context(enabled=False):
                        value = run_specialized_workflow(graph_input, deadline_monotonic=deadline)
                else:
                    budget = Budget()
                    budget._durable_observer = observer
                    budget._deadline = deadline
                    budget._searches = snapshot.search_calls
                    budget._retrievals = snapshot.retrieval_calls
                    if kind == "search" and fixture[0] == "controlled-smoke":
                        value = observer.search_smoke(request, budget)
                    elif kind == "search" and fixture[0] == "offline":
                        from agentops_api.agent.s06.providers import search_offline
                        value = search_offline(request, budget)
                    elif kind == "search":
                        from agentops_api.services.s06_acquisition.tavily import search_isolated
                        value = search_isolated(request, budget, transport=fixture[1])
                    elif fixture[0] == "controlled-smoke":
                        value = observer.retrieval_smoke(request, budget)
                    elif fixture[0] == "offline":
                        from agentops_api.agent.s06.retrieval import retrieve_offline
                        value = retrieve_offline(request, budget, resolver=fixture[1], transport=fixture[2])
                    else:
                        from agentops_api.services.s06_acquisition.integrated_retrieval import retrieve_isolated
                        value = retrieve_isolated(request, budget, resolver=fixture[1])
                observer.check()
            except BaseException:
                # Raw provider/input/exception details never cross this boundary.
                error, value = True, None
            finally:
                _OBSERVER.reset(token)
                with _ACTIVE_LOCK:
                    if _ACTIVE.get(handle.task_id) is thread:
                        _ACTIVE.pop(handle.task_id, None)
                try:
                    loop.call_soon_threadsafe(publish, value, error)
                except RuntimeError:
                    pass

        if kind != "s05" and fixture[0] == "controlled-smoke":
            from contextvars import copy_context
            from agentops_api.services.smoke_runtime import check_operation

            check_operation(handle, kind, request)
            runtime_context = copy_context()
            thread = Thread(
                target=runtime_context.run,
                args=(execute,),
                name="s08-controlled-operation",
                daemon=True,
            )
        else:
            thread = Thread(
                target=execute,
                name="s07-isolated-operation",
                daemon=True,
            )
        with _ACTIVE_LOCK:
            if handle.task_id in _ACTIVE or len(_ACTIVE) >= 5:
                raise BudgetRejected("local_execution_capacity")
            _ACTIVE[handle.task_id] = thread
        try:
            thread.start()
            # Reservation and lease checks may shorten the observer's
            # deadline after the synchronous thread starts. Never wait
            # until the original outer deadline after authority narrows.
            # Poll only the local observation boundary; this is not a
            # claim that a synchronous thread can be forcibly stopped.
            while not completion.done():
                remaining = min(deadline, observer.deadline) - monotonic()
                if remaining <= 0:
                    raise BudgetRejected("execution_observation_expired")
                await asyncio.wait(
                    {completion},
                    timeout=min(remaining, 0.05),
                )
            value, error = completion.result()
            if error or monotonic() >= observer.deadline:
                raise BudgetRejected("execution_failed_closed")
            final = await self._call("_actual_finished", handle)
            observer.check()
            if kind == "s05" and (
                final.adapter_invocations != value.counters.adapter_invocations
                or final.repair_attempts != value.counters.repair_attempts
            ):
                raise BudgetRejected("accounting_integrity")
            return value
        except BaseException:
            observer.stopped.set()
            if not thread.is_alive():
                with _ACTIVE_LOCK:
                    if _ACTIVE.get(handle.task_id) is thread:
                        _ACTIVE.pop(handle.task_id, None)
            cleanup = asyncio.create_task(self._call("_abandon_actual", handle))
            self._pending.add(cleanup)
            cleanup.add_done_callback(self._pending.discard)
            # The session remains owned by cleanup. A bounded observation is
            # not proof of its completion or of synchronous/remote cancellation.
            await _observe_cleanup(cleanup)
            raise
