"""Research admission and owner-scoped reads for S03."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_api.models.queue import QueueControl
from agentops_api.models.research import ResearchTask
from agentops_api.repositories.research import (
    IdempotencyConflict,
    ResearchSubmission,
    SubmissionResult,
    get_task,
    list_tasks,
    submit_task,
)


class QueueFull(Exception):
    """Configured pending queue capacity reached."""


class QueueUnavailable(Exception):
    """Required coordination record unavailable."""


async def admit_task(
    session: AsyncSession,
    *,
    owner_id: UUID,
    idempotency_key: str,
    submission: ResearchSubmission,
    capacity: int,
    validation_limits: dict[str, int],
) -> SubmissionResult:
    """Serialize replay, capacity checks and insert in one transaction."""
    if not session.in_transaction():
        raise RuntimeError("Explicit transaction required")

    if (
        not idempotency_key.strip()
        or len(idempotency_key) > 128
        or "\\x00" in idempotency_key
    ):
        raise ValueError("Invalid idempotency key")

    submission = ResearchSubmission.model_validate(
        submission.model_dump(),
        context=validation_limits,
    )

    control = await session.scalar(
        select(QueueControl)
        .where(QueueControl.id == 1)
        .with_for_update()
    )
    if control is None:
        raise QueueUnavailable()

    existing = await session.scalar(
        select(ResearchTask).where(
            ResearchTask.owner_id == owner_id,
            ResearchTask.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.deleted_at is not None
            or existing.request_fingerprint != submission.fingerprint()
        ):
            raise IdempotencyConflict("Idempotency conflict")
        return SubmissionResult(task=existing, created=False)

    pending = await session.scalar(
        select(func.count())
        .select_from(ResearchTask)
        .where(
            ResearchTask.status == "queued",
            ResearchTask.deleted_at.is_(None),
        )
    )

    if pending is None:
        raise QueueUnavailable()

    if pending >= capacity:
        raise QueueFull()

    return await submit_task(
        session,
        owner_id=owner_id,
        idempotency_key=idempotency_key,
        submission=submission,
        validation_limits=validation_limits,
    )


async def history(
    session: AsyncSession,
    *,
    owner_id: UUID,
    limit: int,
    before: tuple[datetime, UUID] | None = None,
) -> list[ResearchTask]:
    return await list_tasks(
        session, owner_id=owner_id, limit=limit, before=before,
    )


async def detail(
    session: AsyncSession,
    *,
    owner_id: UUID,
    task_id: UUID,
) -> ResearchTask | None:
    return await get_task(
        session, owner_id=owner_id, task_id=task_id,
    )
