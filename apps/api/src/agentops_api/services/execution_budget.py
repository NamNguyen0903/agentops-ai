"""Durable S07 accounting primitives for isolated Development MVP.

Every public method owns a short transaction. No provider invocation,
worker startup, arbitrary callable execution or publication is exposed.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select

from agentops_api.models.execution_context import (
    ResearchExecutionContext,
    ResearchOperationReservation,
)


LIMITS = {
    "search_calls": 6,
    "retrieval_calls": 12,
    "model_calls": 8,
    "reserved_tokens": 40000,
    "reserved_cost_microusd": 1000000,
    "adapter_invocations": 4,
    "repair_attempts": 1,
}

CALL_COUNTER = {
    "search": "search_calls",
    "retrieval": "retrieval_calls",
    "model": "model_calls",
    "adapter": "adapter_invocations",
}

OPERATION_SECONDS = {
    "search": 15,
    "retrieval": 15,
    "model": 45,
    "adapter": 30,
}

UNRESOLVED = frozenset({"reserved", "dispatching"})

ADAPTER_NAMES = ("planner", "research", "writer")


class BudgetRejected(RuntimeError):
    """Sanitized accounting rejection."""


@dataclass(frozen=True, slots=True)
class ReservationRequest:
    operation_id: UUID
    kind: str
    retry_ordinal: int = 0
    reserved_tokens: int = 0
    reserved_cost_microusd: int = 0


@dataclass(frozen=True, slots=True)
class ReservationHandle:
    reservation_id: UUID
    operation_id: UUID
    task_id: UUID
    owner_id: UUID
    attempt_id: UUID
    generation: int
    deadline_at: datetime


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    task_id: UUID
    started_at: datetime
    deadline_at: datetime
    search_calls: int
    retrieval_calls: int
    model_calls: int
    reserved_tokens: int
    reserved_cost_microusd: int
    adapter_invocations: int
    repair_attempts: int
    blocked: bool


def require_uuid(value):
    if type(value) is not UUID or value.int == 0:
        raise BudgetRejected("invalid_operation_identity")


def bounded_integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise BudgetRejected("invalid_accounting_value")


def validate_request(request):
    if type(request) is not ReservationRequest:
        raise BudgetRejected("invalid_reservation_request")

    require_uuid(request.operation_id)

    if (
        type(request.kind) is not str
        or request.kind not in {"search", "retrieval", "model"}
    ):
        raise BudgetRejected("invalid_operation_kind")

    bounded_integer(request.retry_ordinal, 1)
    bounded_integer(request.reserved_tokens, 40000)
    bounded_integer(request.reserved_cost_microusd, 1000000)

    if request.kind != "model" and request.reserved_tokens:
        raise BudgetRejected("invalid_token_reservation")

    if request.kind == "model" and request.retry_ordinal:
        raise BudgetRejected("model_retry_not_authorized")


def reservation_deadline(context, attempt, now, kind):
    if kind not in OPERATION_SECONDS:
        raise BudgetRejected("invalid_operation_kind")

    if now < context.updated_at:
        raise BudgetRejected("database_clock_regression")

    deadline = min(
        context.deadline_at,
        context.started_at + timedelta(seconds=30),
        attempt.lease_expires_at,
        now + timedelta(seconds=OPERATION_SECONDS[kind]),
    )

    if deadline <= now:
        raise BudgetRejected("operation_deadline_expired")

    return deadline


def calculate_charge(context, request):
    validate_request(request)

    values = {
        name: getattr(context, name)
        for name in LIMITS
    }

    for name, maximum in LIMITS.items():
        bounded_integer(values[name], maximum)

    values[CALL_COUNTER[request.kind]] += 1

    values["reserved_tokens"] += request.reserved_tokens

    values["reserved_cost_microusd"] += (
        request.reserved_cost_microusd
    )

    for name, maximum in LIMITS.items():
        if values[name] > maximum:
            raise BudgetRejected("budget_exhausted")

    return values


def snapshot_context(context):
    return BudgetSnapshot(
        task_id=context.task_id,
        started_at=context.started_at,
        deadline_at=context.deadline_at,
        blocked=context.blocked_at is not None,
        **{
            name: getattr(context, name)
            for name in LIMITS
        },
    )


def validate_context_identity(context, task, now):
    if context is None:
        raise BudgetRejected("execution_context_missing")

    if (
        task.started_at is None
        or context.task_id != task.id
        or context.owner_id != task.owner_id
        or context.started_at != task.started_at
        or context.deadline_at
        != task.started_at + timedelta(seconds=180)
    ):
        raise BudgetRejected("execution_context_identity_mismatch")

    if now < context.updated_at:
        raise BudgetRejected("database_clock_regression")

    for name, maximum in LIMITS.items():
        bounded_integer(
            getattr(context, name), maximum
        )

    if context.repair_attempts > context.adapter_invocations:
        raise BudgetRejected("accounting_integrity")

    if (context.blocked_at is None) != (
        context.block_reason is None
    ):
        raise BudgetRejected("accounting_integrity")


async def lock_context(session, task):
    return await session.scalar(
        select(ResearchExecutionContext)
        .where(
            ResearchExecutionContext.task_id == task.id,
            ResearchExecutionContext.owner_id == task.owner_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_ledger(session, task):
    result = await session.scalars(
        select(ResearchOperationReservation)
        .where(
            ResearchOperationReservation.task_id == task.id,
            ResearchOperationReservation.owner_id == task.owner_id,
        )
        .order_by(ResearchOperationReservation.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    return tuple(result.all())


def validate_retry(request, rows):
    matches = [
        row for row in rows
        if row.operation_id == request.operation_id
    ]

    if request.retry_ordinal == 0:
        if matches:
            raise BudgetRejected("duplicate_operation")

        return

    if len(matches) != 1:
        raise BudgetRejected("retry_not_authorized")

    prior = matches[0]

    if (
        prior.retry_ordinal != 0
        or prior.kind != request.kind
        or prior.status != "failed"
        or prior.retry_eligible is not True
        or prior.dispatched_at is None
        or prior.resolved_at is None
    ):
        raise BudgetRejected("retry_not_authorized")


def validate_ledger(context, rows):
    expected = {
        name: 0 for name in LIMITS
    }

    operations = {}

    for row in rows:
        if (
            row.owner_id != context.owner_id
            or row.task_id != context.task_id
            or row.kind not in CALL_COUNTER
        ):
            raise BudgetRejected("accounting_integrity")

        key = (
            row.operation_id, row.retry_ordinal
        )

        if key in operations:
            raise BudgetRejected("accounting_integrity")

        operations[key] = row

        bounded_integer(row.retry_ordinal, 1)
        bounded_integer(row.reserved_tokens, 40000)
        bounded_integer(
            row.reserved_cost_microusd, 1000000
        )

        if row.kind != "model" and row.reserved_tokens:
            raise BudgetRejected("accounting_integrity")

        expected[CALL_COUNTER[row.kind]] += 1

        expected["reserved_tokens"] += row.reserved_tokens

        expected["reserved_cost_microusd"] += (
            row.reserved_cost_microusd
        )

        if row.is_repair:
            expected["repair_attempts"] += 1

        if (
            row.reserved_at < context.started_at
            or row.deadline_at > context.deadline_at
            or row.deadline_at
            > context.started_at + timedelta(seconds=30)
            or row.deadline_at <= row.reserved_at
        ):
            raise BudgetRejected("accounting_integrity")

    for (_, ordinal), row in operations.items():
        if ordinal == 1:
            prior = operations.get(
                (row.operation_id, 0)
            )

            if (
                prior is None
                or prior.kind != row.kind
                or prior.status != "failed"
                or prior.retry_eligible is not True
                or prior.resolved_at is None
                or prior.resolved_at > row.reserved_at
            ):
                raise BudgetRejected("accounting_integrity")

            if row.deadline_at > prior.deadline_at:
                raise BudgetRejected("accounting_integrity")

    for name, value in expected.items():
        if getattr(context, name) != value:
            raise BudgetRejected("accounting_integrity")

    if sum(
        row.status in UNRESOLVED
        for row in rows
    ) > 1:
        raise BudgetRejected("accounting_integrity")

    if any(
        row.status == "indeterminate"
        for row in rows
    ) and context.blocked_at is None:
        raise BudgetRejected("accounting_integrity")


def block_context(context, now, reason):
    if context.blocked_at is None:
        context.blocked_at = now
        context.block_reason = reason

    context.updated_at = now


def close_unresolved(context, rows, now):
    unresolved = [
        row for row in rows
        if row.status in UNRESOLVED
    ]

    for row in unresolved:
        if (
            now < row.reserved_at
            or (
                row.dispatched_at is not None
                and now < row.dispatched_at
            )
        ):
            raise BudgetRejected("database_clock_regression")

        row.status = "indeterminate"
        row.resolved_at = now
        row.retry_eligible = False

    if unresolved:
        block_context(
            context, now, "indeterminate_operation"
        )

    return bool(unresolved)


async def initialize_context(session, task, now):
    if await lock_context(session, task) is not None:
        raise BudgetRejected("duplicate_execution_context")

    if task.started_at != now or task.status != "running":
        raise BudgetRejected("invalid_context_initialization")

    context = ResearchExecutionContext(
        task_id=task.id,
        owner_id=task.owner_id,
        started_at=task.started_at,
        deadline_at=task.started_at + timedelta(seconds=180),
        updated_at=now,
        **{name: 0 for name in LIMITS},
    )

    session.add(context)

    await session.flush()

    return context


async def lifecycle_reconcile(
    session,
    task,
    now,
    *,
    close_unknown,
    recovery=False,
):
    """Inspect accounting under queue, task and attempt locks."""

    context = await lock_context(session, task)

    if context is None:
        return task.started_at is not None

    try:
        validate_context_identity(
            context, task, now
        )

        rows = await lock_ledger(session, task)

        validate_ledger(context, rows)

    except BudgetRejected:
        if now >= context.updated_at:
            block_context(
                context, now, "accounting_integrity"
            )

        return True

    unresolved = any(
        row.status in UNRESOLVED
        for row in rows
    )

    if unresolved and close_unknown:
        close_unresolved(context, rows, now)

    # Adapter charge records do not prove adapter completion.
    # Until trusted stage completion exists, never recover
    # a workflow whose adapter execution may have started.
    if recovery and context.adapter_invocations:
        block_context(
            context, now, "indeterminate_operation"
        )

    return (
        unresolved
        or context.blocked_at is not None
    )


class ExecutionBudgetService:
    """Isolated reservation authority, not an execution engine."""

    def __init__(
        self,
        session,
        *,
        isolated_test_scope=False,
    ):
        from agentops_api.services.execution import (
            ExecutionService,
        )

        self._session = session

        self._lifecycle = ExecutionService(
            session,
            isolated_test_scope=isolated_test_scope,
        )

    async def _owned_context(
        self, handle, *, allow_blocked=False
    ):
        from agentops_api.services.execution import (
            _validate_handle,
            _clock,
        )

        _validate_handle(handle)

        await self._lifecycle._guard()

        task, attempt, _ = await self._lifecycle._owned(
            handle
        )

        context = await lock_context(
            self._session, task
        )

        if context is None:
            raise BudgetRejected("execution_context_missing")

        rows = await lock_ledger(
            self._session, task
        )

        now = await _clock(self._session)

        if (
            now < attempt.heartbeat_at
            or now >= attempt.lease_expires_at
            or now >= context.deadline_at
        ):
            raise BudgetRejected("execution_authority_expired")

        validate_context_identity(
            context, task, now
        )

        validate_ledger(context, rows)

        if (
            not allow_blocked
            and context.blocked_at is not None
        ):
            raise BudgetRejected("execution_context_blocked")

        return task, attempt, context, rows, now

    async def snapshot(self, handle):
        async with self._session.begin():
            _, _, context, _, _ = await self._owned_context(
                handle, allow_blocked=True
            )

            result = snapshot_context(context)

        return result

    async def reserve(self, handle, request, *, _root_operation_id=None):
        validate_request(request)

        async with self._session.begin():
            task, attempt, context, rows, now = (
                await self._owned_context(handle)
            )

            if any(
                row.status in UNRESOLVED
                for row in rows
            ):
                raise BudgetRejected("unresolved_operation")

            validate_retry(request, rows)

            deadline = reservation_deadline(
                context, attempt, now, request.kind
            )

            deadline = retry_deadline(
                request, rows, deadline, now
            )

            if _root_operation_id is not None:
                require_uuid(_root_operation_id)
                roots = [r for r in rows if (
                    r.operation_id == _root_operation_id and r.retry_ordinal == 0
                )]
                if roots:
                    root = roots[0]
                    if root.kind != request.kind:
                        raise BudgetRejected("operation_root_mismatch")
                    deadline = min(deadline, root.deadline_at)
                elif request.operation_id != _root_operation_id:
                    raise BudgetRejected("operation_root_missing")
                if deadline <= now:
                    raise BudgetRejected("operation_deadline_expired")

            values = calculate_charge(
                context, request
            )

            for name, value in values.items():
                setattr(context, name, value)

            context.updated_at = now

            row = ResearchOperationReservation(
                id=uuid4(),
                task_id=task.id,
                owner_id=task.owner_id,
                attempt_id=attempt.id,
                operation_id=request.operation_id,
                kind=request.kind,
                retry_ordinal=request.retry_ordinal,
                is_repair=False,
                reserved_at=now,
                deadline_at=deadline,
                reserved_tokens=request.reserved_tokens,
                reserved_cost_microusd=(
                    request.reserved_cost_microusd
                ),
                status="reserved",
                retry_eligible=False,
            )

            self._session.add(row)

            await self._session.flush()

            result = ReservationHandle(
                reservation_id=row.id,
                operation_id=row.operation_id,
                task_id=task.id,
                owner_id=task.owner_id,
                attempt_id=attempt.id,
                generation=attempt.generation,
                deadline_at=deadline,
            )

        return result

    def _select_reservation(
        self, handle, reservation, attempt, rows
    ):
        if type(reservation) is not ReservationHandle:
            raise BudgetRejected("invalid_reservation_handle")

        for value in (
            reservation.reservation_id,
            reservation.operation_id,
            reservation.owner_id,
            reservation.task_id,
            reservation.attempt_id,
        ):
            require_uuid(value)

        if (
            reservation.owner_id != handle.owner_id
            or reservation.task_id != handle.task_id
            or reservation.attempt_id != attempt.id
            or type(reservation.generation) is not int
            or reservation.generation != attempt.generation
        ):
            raise BudgetRejected("stale_reservation_handle")

        matches = [
            row for row in rows
            if row.id == reservation.reservation_id
        ]

        if len(matches) != 1:
            raise BudgetRejected("reservation_not_owned")

        row = matches[0]

        if (
            row.operation_id != reservation.operation_id
            or row.attempt_id != reservation.attempt_id
            or row.deadline_at != reservation.deadline_at

        ):
            raise BudgetRejected("reservation_not_owned")

        return row

    async def begin_dispatch(self, handle, reservation):
        async with self._session.begin():
            _, attempt, context, rows, now = (
                await self._owned_context(handle)
            )

            row = self._select_reservation(
                handle, reservation, attempt, rows
            )

            if row.status != "reserved":
                raise BudgetRejected("dispatch_already_consumed")

            deadline = min(
                row.deadline_at,
                context.deadline_at,
                attempt.lease_expires_at,
            )

            if now >= deadline:
                raise BudgetRejected("operation_deadline_expired")

            row.status = "dispatching"
            row.dispatched_at = now
            context.updated_at = now

            await self._session.flush()

        return deadline

    async def reconcile(
        self,
        handle,
        reservation,
        *,
        outcome,
        actual_tokens=None,
        actual_cost_microusd=None,
    ):
        raise BudgetRejected("caller_outcome_not_authorized")

    async def charge_adapter(
        self,
        handle,
        *,
        operation_id,
        adapter_name,
        repair=False,
    ):
        raise BudgetRejected("charge_only_adapter_not_authorized")

    async def _reserve_stage(
        self, handle, stage, repair
    ):
        async with self._session.begin():
            task, attempt, context, rows, now = (
                await self._owned_context(handle)
            )

            # A replacement generation may start a fresh deterministic
            # graph only when no earlier generation reserved any operation.
            # Current-generation stage history, cumulative limits, the
            # original deadline and the ownership fence still apply.
            if attempt.generation != 1 and any(
                row.attempt_id != attempt.id for row in rows
            ):
                raise BudgetRejected("adapter_resume_not_authorized")

            if any(
                row.status in UNRESOLVED
                for row in rows
            ):
                raise BudgetRejected("unresolved_operation")

            expected = validate_stage_history(
                context, rows
            )

            if expected != (stage, repair):
                raise BudgetRejected("adapter_order_invalid")

            if context.adapter_invocations >= 4:
                raise BudgetRejected("adapter_budget_exhausted")

            if repair and context.repair_attempts >= 1:
                raise BudgetRejected("repair_budget_exhausted")

            operation_id = stage_operation_id(
                task.id, stage, repair
            )

            if any(
                row.operation_id == operation_id
                for row in rows
            ):
                raise BudgetRejected("duplicate_operation")

            deadline = reservation_deadline(
                context, attempt, now, "adapter"
            )

            context.adapter_invocations += 1

            if repair:
                context.repair_attempts += 1

            context.updated_at = now

            row = ResearchOperationReservation(
                id=uuid4(),
                owner_id=task.owner_id,
                task_id=task.id,
                attempt_id=attempt.id,
                operation_id=operation_id,
                kind="adapter",
                retry_ordinal=0,
                is_repair=repair,
                reserved_at=now,
                deadline_at=deadline,
                reserved_tokens=0,
                reserved_cost_microusd=0,
                status="reserved",
                retry_eligible=False,
            )

            self._session.add(row)
            await self._session.flush()

            result = ReservationHandle(
                reservation_id=row.id,
                operation_id=operation_id,
                task_id=task.id,
                owner_id=task.owner_id,
                attempt_id=attempt.id,
                generation=attempt.generation,
                deadline_at=deadline,
            )

        return result


    async def _reconcile_trusted(
        self, handle, reservation, result
    ):
        async with self._session.begin():
            _, attempt, context, rows, now = (
                await self._owned_context(handle)
            )

            row = self._select_reservation(
                handle, reservation, attempt, rows
            )

            if row.status != "dispatching":
                raise BudgetRejected("operation_not_dispatching")

            outcome = validate_synthetic_result(
                result, row.kind
            )

            tokens = result.tokens
            cost = result.cost_microusd

            try:
                if outcome == "succeeded":
                    bounded_integer(
                        tokens, row.reserved_tokens
                    )

                    bounded_integer(
                        cost, row.reserved_cost_microusd
                    )

            except BudgetRejected:
                outcome = "indeterminate"

            if now >= row.deadline_at:
                outcome = "indeterminate"

            row.status = outcome
            row.resolved_at = now
            row.retry_eligible = False

            if outcome == "indeterminate":
                block_context(
                    context, now, "indeterminate_operation"
                )

            elif outcome == "succeeded":
                row.actual_tokens = (
                    tokens if row.kind == "model" else None
                )

                row.actual_cost_microusd = cost

            elif outcome == "failed":
                row.retry_eligible = (
                    row.kind in {"search", "retrieval"}
                    and row.retry_ordinal == 0
                    and result.outcome == "retryable_failure"
                    and result.process_exit_verified is True
                )

                if (
                    row.kind == "adapter"
                    and row.is_repair
                ):
                    block_context(
                        context, now, "indeterminate_operation"
                    )

            context.updated_at = now
            await self._session.flush()

        return outcome


    async def _execute_reserved_synthetic(
        self, handle, reservation, request
    ):
        import asyncio

        from time import monotonic

        from agentops_api.services.execution_runner import (
            SyntheticResult,
            run_synthetic,
        )

        started = monotonic()

        deadline = await self.begin_dispatch(
            handle, reservation
        )

        async with self._session.begin():
            _, attempt, context, rows, now = (
                await self._owned_context(handle)
            )

            row = self._select_reservation(
                handle, reservation, attempt, rows
            )

            if (
                row.status != "dispatching"
                or row.kind != request.kind
            ):
                raise BudgetRejected("dispatch_authority_invalid")

            remaining = (
                min(
                    deadline,
                    row.deadline_at,
                    context.deadline_at,
                    attempt.lease_expires_at,
                ) - now
            ).total_seconds()

        remaining = min(
            remaining - (monotonic() - started),
            OPERATION_SECONDS[request.kind],
        )

        unknown = SyntheticResult(
            "indeterminate", None, None, False, False
        )

        if remaining <= 0:
            return await self._reconcile_trusted(
                handle, reservation, unknown
            )

        try:
            result = await run_synthetic(
                request,
                timeout_seconds=remaining,
                isolated_test_scope=True,
            )

        except asyncio.CancelledError:
            async def reconcile_unknown():
                return await self._reconcile_trusted(
                    handle, reservation, unknown
                )

            from agentops_api.services.execution_runner import (
                _observe_cleanup,
            )

            try:
                await _observe_cleanup(
                    asyncio.create_task(reconcile_unknown())
                )
            except Exception:
                pass

            raise

        return await self._reconcile_trusted(
            handle, reservation, result
        )


    async def execute_synthetic(
        self, handle, request, *, mode="success"
    ):
        from agentops_api.services.execution_runner import (
            SyntheticRequest,
            validate_synthetic_request,
        )

        validate_request(request)

        fixture = SyntheticRequest(
            request.kind, mode
        )

        validate_synthetic_request(fixture)

        reservation = await self.reserve(
            handle, request
        )

        return await self._execute_reserved_synthetic(
            handle, reservation, fixture
        )


    async def execute_synthetic_stage(
        self, handle, stage, *, repair=False, mode="success"
    ):
        from agentops_api.services.execution_runner import (
            SyntheticRequest,
            validate_synthetic_request,
        )

        if type(repair) is not bool:
            raise BudgetRejected("invalid_repair_flag")

        fixture = SyntheticRequest(
            "adapter", mode
        )

        validate_synthetic_request(fixture)

        reservation = await self._reserve_stage(
            handle, stage, repair
        )

        return await self._execute_reserved_synthetic(
            handle, reservation, fixture
        )



    async def _actual_input(self, handle):
        """Read authoritative input and original deadlines in a short tx."""
        from agentops_api.agent.s05.contract import S05GraphInput
        async with self._session.begin():
            task, attempt, context, rows, now = await self._owned_context(handle)
            if any(row.status in UNRESOLVED for row in rows):
                raise BudgetRejected("unresolved_operation")
            request = S05GraphInput(
                task_id=task.id, attempt_id=attempt.id,
                question=task.question, scope=task.scope,
            )
            remaining = (min(
                context.deadline_at, context.started_at + timedelta(seconds=30),
                attempt.lease_expires_at,
            ) - now).total_seconds()
            if remaining <= 0:
                raise BudgetRejected("operation_deadline_expired")
            snapshot = snapshot_context(context)
        return request, remaining, snapshot

    async def _actual_remaining(self, handle, reservation):
        async with self._session.begin():
            _, attempt, context, rows, now = await self._owned_context(handle)
            row = self._select_reservation(handle, reservation, attempt, rows)
            if row.status != "dispatching":
                raise BudgetRejected("dispatch_authority_invalid")
            remaining = (min(
                row.deadline_at, context.deadline_at, attempt.lease_expires_at,
            ) - now).total_seconds()
            if remaining <= 0:
                raise BudgetRejected("operation_deadline_expired")
        return remaining

    async def _complete_actual(self, handle, reservation, receipt):
        from agentops_api.services.execution_receipts import _consume
        outcome, retryable = _consume(receipt, reservation)
        async with self._session.begin():
            _, attempt, context, rows, now = await self._owned_context(handle)
            row = self._select_reservation(handle, reservation, attempt, rows)
            if row.status != "dispatching":
                raise BudgetRejected("operation_not_dispatching")
            if now >= row.deadline_at:
                outcome, retryable = "indeterminate", False
            row.status = outcome
            row.resolved_at = now
            row.retry_eligible = bool(
                retryable and outcome == "failed" and row.retry_ordinal == 0
                and row.kind in {"search", "retrieval"}
            )
            if outcome == "indeterminate":
                block_context(context, now, "indeterminate_operation")
            context.updated_at = now
            await self._session.flush()
        return outcome

    async def _abandon_actual(self, handle):
        async with self._session.begin():
            _, _, context, rows, now = await self._owned_context(
                handle, allow_blocked=True,
            )
            close_unresolved(context, rows, now)
            block_context(context, now, "cancellation_unverified")
            await self._session.flush()

    async def _actual_finished(self, handle):
        async with self._session.begin():
            _, _, context, rows, _ = await self._owned_context(handle)
            if any(row.status in UNRESOLVED for row in rows):
                raise BudgetRejected("unresolved_operation")
            result = snapshot_context(context)
        return result


_STAGE_NAMESPACE = UUID(
    "f9a68dd2-e916-49bc-973d-90dc5f7778de"
)


def stage_operation_id(task_id, stage, repair=False):
    require_uuid(task_id)

    if (
        type(stage) is not str
        or stage not in ADAPTER_NAMES
        or type(repair) is not bool
        or (repair and stage == "research")
    ):
        raise BudgetRejected("invalid_adapter_identity")

    return uuid5(
        _STAGE_NAMESPACE,
        f"{task_id}:{stage}:{int(repair)}",
    )


def validate_stage_history(context, rows):
    """Return next permitted normal stage or required repair."""

    records = [
        row for row in rows
        if row.kind == "adapter"
    ]

    records.sort(
        key=lambda row: (row.reserved_at, str(row.id))
    )

    if len(records) != context.adapter_invocations:
        raise BudgetRejected("accounting_integrity")

    normal = 0
    repairs = 0
    required_repair = None

    for row in records:
        if row.status in UNRESOLVED:
            raise BudgetRejected("unresolved_operation")

        if row.status not in {"succeeded", "failed"}:
            raise BudgetRejected("unsafe_stage_outcome")

        if row.is_repair:
            if required_repair is None or repairs:
                raise BudgetRejected("repair_not_authorized")

            stage = required_repair

            if row.operation_id != stage_operation_id(
                context.task_id, stage, True
            ):
                raise BudgetRejected("stage_identity_mismatch")

            repairs += 1

            if row.status != "succeeded":
                raise BudgetRejected("repair_failed")

            required_repair = None
            normal += 1
            continue

        if required_repair is not None:
            raise BudgetRejected("repair_required")

        if normal >= len(ADAPTER_NAMES):
            raise BudgetRejected("adapter_budget_exhausted")

        stage = ADAPTER_NAMES[normal]

        if row.operation_id != stage_operation_id(
            context.task_id, stage, False
        ):
            raise BudgetRejected("stage_identity_mismatch")

        if row.status == "failed":
            if (
                stage not in {"planner", "writer"}
                or repairs
            ):
                raise BudgetRejected("repair_not_authorized")

            required_repair = stage

        else:
            normal += 1

    if repairs != context.repair_attempts:
        raise BudgetRejected("accounting_integrity")

    if required_repair is not None:
        return required_repair, True

    if normal == len(ADAPTER_NAMES):
        return None, False

    return ADAPTER_NAMES[normal], False


def validate_synthetic_result(result, kind):
    from agentops_api.services.execution_runner import (
        SyntheticResult,
    )

    if type(result) is not SyntheticResult:
        raise BudgetRejected("invalid_trusted_result")

    if result.process_exit_verified is not True:
        return "indeterminate"

    outcome = result.outcome

    if outcome == "succeeded":
        return "succeeded"

    if (
        outcome == "retryable_failure"
        and kind in {"search", "retrieval"}
    ):
        return "failed"

    if (
        outcome == "invalid_stage_output"
        and kind == "adapter"
    ):
        return "failed"

    return "indeterminate"


def retry_deadline(request, rows, proposed_deadline, now):
    """A retry cannot extend its initial logical operation deadline."""

    if request.retry_ordinal == 0:
        return proposed_deadline

    matches = [
        row for row in rows
        if row.operation_id == request.operation_id
        and row.retry_ordinal == 0
    ]

    if len(matches) != 1:
        raise BudgetRejected("retry_not_authorized")

    prior = matches[0]

    if (
        prior.kind != request.kind
        or prior.status != "failed"
        or prior.retry_eligible is not True
    ):
        raise BudgetRejected("retry_not_authorized")

    deadline = min(
        proposed_deadline,
        prior.deadline_at,
    )

    if deadline <= now:
        raise BudgetRejected("operation_deadline_expired")

    return deadline
