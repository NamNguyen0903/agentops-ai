"""S07 durable execution lifecycle.

Development MVP persistence operations only. No worker process,
network dispatcher, provider integration or report publication.

All public operations own a short transaction. A returned ownership
handle is usable only after the claim transaction commits.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_api.models.execution import ResearchExecutionAttempt
from agentops_api.models.queue import QueueControl
from agentops_api.models.research import ResearchTask
from agentops_api.services.execution_budget import (
    initialize_context,
    lifecycle_reconcile,
)


GLOBAL_RUNNING_LIMIT = 5
PER_USER_RUNNING_LIMIT = 1
PENDING_LIMIT = 50

QUEUE_TIMEOUT = timedelta(seconds=60)
RUNNING_TIMEOUT = timedelta(seconds=180)
LEASE_DURATION = timedelta(seconds=30)

HEARTBEAT_INTERVAL_SECONDS = 10
IDLE_POLL_SECONDS = 1
RECOVERY_INSPECTION_SECONDS = 5
MAX_ATTEMPTS = 2

TERMINAL_STATES = frozenset({
    "completed",
    "insufficient_evidence",
    "failed",
    "timed_out",
})

# Successful report completion requires the later integrated
# publication boundary. WP02 must not fabricate completion.
WORKER_FINISH_STATES = frozenset({
    "failed",
    "insufficient_evidence",
})


class ExecutionRejected(RuntimeError):
    """Fixed, non-sensitive lifecycle rejection."""


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    owner_id: UUID
    task_id: UUID
    attempt_id: UUID
    worker_id: UUID
    generation: int


def running_deadline(started_at: datetime) -> datetime:
    return started_at + RUNNING_TIMEOUT


def bounded_lease(
    now: datetime,
    started_at: datetime,
) -> datetime:
    expiry = min(
        now + LEASE_DURATION,
        running_deadline(started_at),
    )

    if expiry <= now:
        raise ExecutionRejected("execution_deadline_expired")

    return expiry


def _validate_worker(worker_id: UUID) -> None:
    if not isinstance(worker_id, UUID):
        raise ExecutionRejected("invalid_worker_identity")

    if worker_id.int == 0:
        raise ExecutionRejected("invalid_worker_identity")


def _validate_handle(handle: ExecutionHandle) -> None:
    if not isinstance(handle, ExecutionHandle):
        raise ExecutionRejected("invalid_execution_handle")

    for identity in (
        handle.owner_id,
        handle.task_id,
        handle.attempt_id,
        handle.worker_id,
    ):
        _validate_worker(identity)

    if type(handle.generation) is not int:
        raise ExecutionRejected("invalid_generation")

    if not 1 <= handle.generation <= MAX_ATTEMPTS:
        raise ExecutionRejected("invalid_generation")


async def _lock_queue(session: AsyncSession) -> None:
    locked = await session.scalar(
        select(QueueControl.id)
        .where(QueueControl.id == 1)
        .with_for_update()
    )

    if locked != 1:
        raise ExecutionRejected("queue_control_unavailable")


async def _clock(session: AsyncSession) -> datetime:
    now = await session.scalar(
        select(func.clock_timestamp())
    )

    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ExecutionRejected("database_clock_unavailable")

    return now


async def _task(
    session: AsyncSession,
    owner_id: UUID,
    task_id: UUID,
) -> ResearchTask | None:
    return await session.scalar(
        select(ResearchTask)
        .where(
            ResearchTask.id == task_id,
            ResearchTask.owner_id == owner_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def _active_attempt(
    session: AsyncSession,
    task: ResearchTask,
) -> ResearchExecutionAttempt | None:
    result = await session.scalars(
        select(ResearchExecutionAttempt)
        .where(
            ResearchExecutionAttempt.task_id == task.id,
            ResearchExecutionAttempt.owner_id == task.owner_id,
            ResearchExecutionAttempt.ended_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    return result.one_or_none()


async def _generation(
    session: AsyncSession,
    task: ResearchTask,
) -> int:
    return int(
        await session.scalar(
            select(
                func.coalesce(
                    func.max(ResearchExecutionAttempt.generation),
                    0,
                )
            )
            .where(
                ResearchExecutionAttempt.task_id == task.id,
                ResearchExecutionAttempt.owner_id == task.owner_id,
            )
        )
    )


def _end_attempt(
    attempt: ResearchExecutionAttempt,
    now: datetime,
    reason: str,
) -> None:
    if attempt.ended_at is not None:
        raise ExecutionRejected("attempt_already_ended")

    if now < attempt.heartbeat_at:
        raise ExecutionRejected("database_clock_regression")

    attempt.ended_at = now
    attempt.end_reason = reason


def _terminal(
    task: ResearchTask,
    status: str,
    now: datetime,
    category: str | None,
) -> None:
    if task.status in TERMINAL_STATES:
        raise ExecutionRejected("terminal_task_immutable")

    if status not in TERMINAL_STATES:
        raise ExecutionRejected("invalid_terminal_state")

    if now < (task.started_at or task.created_at):
        raise ExecutionRejected("database_clock_regression")

    task.status = status
    task.current_stage = None
    task.completed_at = now
    task.updated_at = now
    task.error_category = category


async def _new_attempt(
    session: AsyncSession,
    task: ResearchTask,
    worker_id: UUID,
    generation: int,
    now: datetime,
) -> ExecutionHandle:
    if task.deleted_at is not None:
        raise ExecutionRejected("deleted_task")

    if task.status != "running" or task.started_at is None:
        raise ExecutionRejected("task_not_running")

    if not 1 <= generation <= MAX_ATTEMPTS:
        raise ExecutionRejected("attempts_exhausted")

    attempt = ResearchExecutionAttempt(
        id=uuid4(),
        owner_id=task.owner_id,
        task_id=task.id,
        worker_id=worker_id,
        generation=generation,
        claimed_at=now,
        heartbeat_at=now,
        lease_expires_at=bounded_lease(now, task.started_at),
    )

    session.add(attempt)
    await session.flush()

    return ExecutionHandle(
        owner_id=task.owner_id,
        task_id=task.id,
        attempt_id=attempt.id,
        worker_id=worker_id,
        generation=generation,
    )


class ExecutionService:
    """Internal, explicitly isolated lifecycle operations.

    These methods are not HTTP routes and are not a worker entrypoint.
    The opt-in argument is an application boundary, not a substitute
    for operator-controlled infrastructure isolation.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        isolated_test_scope: bool = False,
    ) -> None:
        if isolated_test_scope is not True:
            raise ExecutionRejected("worker_activation_disabled")

        self._session = session

    async def _guard(self) -> None:
        # Validate the live database identity before any lifecycle DML.
        from sqlalchemy import text

        identity = (
            await self._session.execute(
                text(
                    "SELECT current_database(), current_user"
                )
            )
        ).one()

        if tuple(identity) != (
            "agentops_migration_test",
            "agentops_app",
        ):
            raise ExecutionRejected("unauthorized_execution_database")

        isolation = await self._session.scalar(
            text("SHOW transaction_isolation")
        )

        if isolation != "read committed":
            raise ExecutionRejected("unsupported_transaction_isolation")

        await _lock_queue(self._session)

    async def claim(
        self,
        worker_id: UUID,
    ) -> ExecutionHandle | None:
        """Claim one eligible task under serialized capacity control."""
        _validate_worker(worker_id)

        session = self._session

        async with session.begin():
            await self._guard()

            now = await _clock(session)

            running = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchTask)
                    .where(
                        ResearchTask.status == "running",
                    )
                )
            )

            if running >= GLOBAL_RUNNING_LIMIT:
                return None

            running_owners = (
                select(ResearchTask.owner_id)
                .where(ResearchTask.status == "running")
                .distinct()
            )

            task = await session.scalar(
                select(ResearchTask)
                .where(
                    ResearchTask.status == "queued",
                    ResearchTask.deleted_at.is_(None),
                    ResearchTask.created_at > now - QUEUE_TIMEOUT,
                    ResearchTask.created_at <= now,
                    ResearchTask.owner_id.not_in(running_owners),
                )
                .order_by(
                    ResearchTask.created_at,
                    ResearchTask.id,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )

            if task is None:
                return None

            now = await _clock(session)

            if task.created_at + QUEUE_TIMEOUT <= now:
                _terminal(
                    task,
                    "timed_out",
                    now,
                    "queue_timeout",
                )
                await session.flush()
                return None

            if task.started_at is not None:
                raise ExecutionRejected("invalid_queued_task")

            if await _generation(session, task) != 0:
                raise ExecutionRejected("queued_task_attempt_history")

            task.status = "running"
            task.started_at = now
            task.updated_at = now
            task.current_stage = None
            task.error_category = None

            await session.flush()

            handle = await _new_attempt(
                session,
                task,
                worker_id,
                1,
                now,
            )
            await initialize_context(session, task, now)

        return handle

    async def _owned(
        self,
        handle: ExecutionHandle,
    ) -> tuple[ResearchTask, ResearchExecutionAttempt, datetime]:
        session = self._session

        task = await _task(
            session,
            handle.owner_id,
            handle.task_id,
        )

        if (
            task is None
            or task.deleted_at is not None
            or task.status != "running"
            or task.started_at is None
        ):
            raise ExecutionRejected("task_not_owned")

        attempt = await _active_attempt(session, task)

        if attempt is None:
            raise ExecutionRejected("attempt_not_active")

        if (
            attempt.id != handle.attempt_id
            or attempt.worker_id != handle.worker_id
            or attempt.generation != handle.generation
        ):
            raise ExecutionRejected("stale_execution_handle")

        now = await _clock(session)

        if now < attempt.heartbeat_at:
            raise ExecutionRejected("database_clock_regression")

        if attempt.lease_expires_at <= now:
            raise ExecutionRejected("execution_lease_expired")

        if running_deadline(task.started_at) <= now:
            raise ExecutionRejected("execution_deadline_expired")

        return task, attempt, now

    async def heartbeat(
        self,
        handle: ExecutionHandle,
    ) -> datetime:
        _validate_handle(handle)

        session = self._session

        async with session.begin():
            await self._guard()

            task, attempt, now = await self._owned(handle)

            assert task.started_at is not None

            expiry = bounded_lease(now, task.started_at)

            attempt.heartbeat_at = now
            attempt.lease_expires_at = expiry

            await session.flush()

        return expiry

    async def finish(
        self,
        handle: ExecutionHandle,
        status: str,
    ) -> None:
        """Fenced terminal transition; report publication excluded."""
        _validate_handle(handle)

        if status not in WORKER_FINISH_STATES:
            raise ExecutionRejected("terminal_transition_not_authorized")

        session = self._session

        async with session.begin():
            await self._guard()

            task, attempt, now = await self._owned(handle)

            unsafe = await lifecycle_reconcile(
                session,
                task,
                now,
                close_unknown=(status == "failed"),
            )

            if unsafe and status != "failed":
                raise ExecutionRejected("unsafe_terminal_transition")
            _end_attempt(attempt, now, status)

            category = (
                "execution_failed"
                if status == "failed"
                else "insufficient_evidence"
            )

            if unsafe:
                category = "indeterminate_execution"
            _terminal(task, status, now, category)

            await session.flush()

    async def recover(
        self,
        owner_id: UUID,
        task_id: UUID,
        worker_id: UUID,
    ) -> ExecutionHandle | None:
        """Replace an expired ownership generation in isolated scope.

        External dispatch is unavailable in this package. Recovery must
        not be connected to real provider execution before durable
        operation accounting and cancellation reconciliation exist.
        """
        for identity in (owner_id, task_id, worker_id):
            _validate_worker(identity)

        session = self._session

        async with session.begin():
            await self._guard()

            task = await _task(session, owner_id, task_id)

            if (
                task is None
                or task.deleted_at is not None
                or task.status != "running"
                or task.started_at is None
            ):
                return None

            attempt = await _active_attempt(session, task)
            now = await _clock(session)

            if now < task.started_at:
                raise ExecutionRejected("database_clock_regression")

            if attempt is None:
                await lifecycle_reconcile(
                    session, task, now,
                    close_unknown=True,
                    recovery=True,
                )
                _terminal(
                    task,
                    "failed",
                    now,
                    "indeterminate_execution",
                )
                await session.flush()
                return None

            if now < attempt.heartbeat_at:
                raise ExecutionRejected("database_clock_regression")

            if running_deadline(task.started_at) <= now:
                await lifecycle_reconcile(
                    session, task, now,
                    close_unknown=True,
                    recovery=True,
                )
                _end_attempt(attempt, now, "timed_out")
                _terminal(
                    task,
                    "timed_out",
                    now,
                    "execution_timeout",
                )
                await session.flush()
                return None

            if attempt.lease_expires_at > now:
                return None
            unsafe = await lifecycle_reconcile(
                session, task, now,
                close_unknown=True,
                recovery=True,
            )

            if unsafe:
                _end_attempt(attempt, now, "indeterminate")

                _terminal(
                    task,
                    "failed",
                    now,
                    "indeterminate_execution",
                )

                await session.flush()
                return None

            generation = await _generation(session, task)

            if generation != attempt.generation:
                raise ExecutionRejected("attempt_history_mismatch")

            if generation >= MAX_ATTEMPTS:
                _end_attempt(
                    attempt,
                    now,
                    "attempts_exhausted",
                )
                _terminal(
                    task,
                    "failed",
                    now,
                    "attempts_exhausted",
                )
                await session.flush()
                return None

            _end_attempt(attempt, now, "lease_expired")

            # Flush the old ownership retirement before insertion:
            # the partial unique index permits one unfinished attempt.
            await session.flush()

            task.updated_at = now

            handle = await _new_attempt(
                session,
                task,
                worker_id,
                generation + 1,
                now,
            )

        return handle

    async def expire_one(self) -> bool:
        """Perform one bounded maintenance transition.

        Deleted active attempts are retired without reopening tasks.
        Queue and running deadlines remain distinct.
        """
        session = self._session

        async with session.begin():
            await self._guard()

            now = await _clock(session)

            from sqlalchemy import and_, or_

            active_exists = (
                select(ResearchExecutionAttempt.id)
                .where(
                    ResearchExecutionAttempt.task_id == ResearchTask.id,
                    ResearchExecutionAttempt.owner_id == ResearchTask.owner_id,
                    ResearchExecutionAttempt.ended_at.is_(None),
                )
                .exists()
            )

            task = await session.scalar(
                select(ResearchTask)
                .where(
                    or_(
                        and_(
                            ResearchTask.deleted_at.is_not(None),
                            or_(
                                active_exists,
                                ResearchTask.status == "running",
                            ),
                        ),
                        and_(
                            ResearchTask.deleted_at.is_(None),
                            ResearchTask.status == "queued",
                            ResearchTask.created_at <= now - QUEUE_TIMEOUT,
                        ),
                        and_(
                            ResearchTask.deleted_at.is_(None),
                            ResearchTask.status == "running",
                            ResearchTask.started_at <= now - RUNNING_TIMEOUT,
                        ),
                    )
                )
                .order_by(
                    ResearchTask.created_at,
                    ResearchTask.id,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )

            if task is None:
                return False

            attempt = await _active_attempt(session, task)
            now = await _clock(session)

            if task.deleted_at is not None:
                if task.started_at is not None:
                    await lifecycle_reconcile(
                        session, task, now,
                        close_unknown=True,
                        recovery=True,
                    )
                if attempt is not None:
                    _end_attempt(attempt, now, "deleted")

                if task.status == "running":
                    _terminal(
                        task,
                        "failed",
                        now,
                        "task_deleted",
                    )

            elif task.status == "queued":
                if task.created_at + QUEUE_TIMEOUT > now:
                    return False

                _terminal(
                    task,
                    "timed_out",
                    now,
                    "queue_timeout",
                )

            elif task.status == "running":
                if task.started_at is None:
                    raise ExecutionRejected("invalid_running_task")

                if running_deadline(task.started_at) > now:
                    return False
                await lifecycle_reconcile(
                    session, task, now,
                    close_unknown=True,
                    recovery=True,
                )

                if attempt is not None:
                    _end_attempt(attempt, now, "timed_out")

                _terminal(
                    task,
                    "timed_out",
                    now,
                    "execution_timeout",
                )

            else:
                return False

            await session.flush()

        return True
