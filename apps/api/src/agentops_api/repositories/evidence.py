"""Task-scoped evidence operations under caller-owned transactions.

The application must supply an authenticated owner and
a trusted execution context. Execution IDs are not durable
worker leases, and this repository does not authenticate.

The task row is locked before evidence admission to
serialize the task-wide limit under PostgreSQL READ COMMITTED.
No task lifecycle mutation or transaction commit is performed.
"""

from dataclasses import dataclass, fields
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_api.agent.s06.evidence import (
    EvidenceLimitExceeded,
    EvidenceRecord,
    EvidenceRejected,
    EvidenceUnavailable,
    MAX_EVIDENCE_PER_TASK,
    valid_uuid,
    validate_record,
    validate_scope,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.research import ResearchTask


@dataclass(frozen=True, slots=True)
class EvidenceInsertResult:
    record: EvidenceRecord
    created: bool


def require_transaction(session):
    if not session.in_transaction():
        raise RuntimeError(
            "Evidence requires an explicit transaction"
        )


async def require_task(
    session, scope, *, execution_handle=None
):
    # Worker-owned evidence is authorized by durable lifecycle
    # and accounting authority, not merely an execution UUID.
    if execution_handle is not None:
        from agentops_api.services.execution import (
            ExecutionHandle,
        )
        from agentops_api.services.execution_budget import (
            ExecutionBudgetService, UNRESOLVED,
        )

        if (
            type(execution_handle) is not ExecutionHandle
            or execution_handle.owner_id != scope.owner_id
            or execution_handle.task_id != scope.task_id
            or execution_handle.attempt_id != scope.execution_id
        ):
            raise EvidenceUnavailable()

        service = ExecutionBudgetService(
            session, isolated_test_scope=True,
        )

        _, _, _, rows, _ = await service._owned_context(
            execution_handle
        )

        if any(row.status in UNRESOLVED for row in rows):
            raise EvidenceUnavailable()

        return

    # Serialize writes and reject deleted/unowned tasks.
    task_id = await session.scalar(
        select(ResearchTask.id)
        .where(
            ResearchTask.id == scope.task_id,
            ResearchTask.owner_id == scope.owner_id,
            ResearchTask.deleted_at.is_(None),
        )
        .with_for_update()
    )

    if task_id != scope.task_id:
        raise EvidenceUnavailable()

    # Preserve the legacy offline S06 path for tasks that
    # have never had durable worker ownership. Check attempt
    # history AFTER obtaining the task lock.
    from agentops_api.models.execution import (
        ResearchExecutionAttempt,
    )

    has_attempt = await session.scalar(
        select(
            select(ResearchExecutionAttempt.id)
            .where(
                ResearchExecutionAttempt.owner_id == scope.owner_id,
                ResearchExecutionAttempt.task_id == scope.task_id,
            )
            .exists()
        )
    )

    if has_attempt is not False:
        raise EvidenceUnavailable()


def scope_filters(scope):
    return (
        ResearchEvidence.owner_id == scope.owner_id,
        ResearchEvidence.task_id == scope.task_id,
        ResearchEvidence.execution_id == scope.execution_id,
    )


def decode_row(row, scope):
    try:
        values = {
            field.name: getattr(row, field.name)
            for field in fields(EvidenceRecord)
        }

        # PostgreSQL may return an aware timestamp using
        # the session timezone rather than timezone.utc.
        value = values["retrieved_at"]

        if value.tzinfo is None or value.utcoffset() is None:
            raise EvidenceRejected()

        values["retrieved_at"] = value.astimezone(timezone.utc)

        return validate_record(
            EvidenceRecord(**values),
            scope,
        )

    except Exception:
        raise EvidenceRejected() from None


async def find_row(session, scope, evidence_id):
    return await session.scalar(
        select(ResearchEvidence)
        .where(
            *scope_filters(scope),
            ResearchEvidence.id == evidence_id,
        )
        .execution_options(populate_existing=True)
    )


async def store_evidence(
    session: AsyncSession,
    *,
    scope,
    record,
    execution_handle=None,
) -> EvidenceInsertResult:
    require_transaction(session)

    scope = validate_scope(scope)
    record = validate_record(record, scope)

    await require_task(
        session, scope,
        execution_handle=execution_handle,
    )

    existing = await find_row(
        session, scope, record.id
    )

    if existing is not None:
        return EvidenceInsertResult(
            record=decode_row(existing, scope),
            created=False,
        )

    # Count across both evidence stores and every attempt.
    # The existing task lock serializes repository writers.
    # Duplicates above do not consume another record slot.
    from agentops_api.models.execution_context import ResearchRealEvidence

    real_count = (
        select(func.count())
        .select_from(ResearchRealEvidence)
        .where(
            ResearchRealEvidence.owner_id == scope.owner_id,
            ResearchRealEvidence.task_id == scope.task_id,
        )
        .scalar_subquery()
    )

    count = await session.scalar(
        select(func.count() + real_count)
        .select_from(ResearchEvidence)
        .where(
            ResearchEvidence.owner_id == scope.owner_id,
            ResearchEvidence.task_id == scope.task_id,
        )
    )

    if type(count) is not int or count < 0:
        raise EvidenceRejected()

    if count >= MAX_EVIDENCE_PER_TASK:
        raise EvidenceLimitExceeded()

    values = {
        field.name: getattr(record, field.name)
        for field in fields(EvidenceRecord)
    }

    inserted_id = await session.scalar(
        insert(ResearchEvidence)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[ResearchEvidence.id]
        )
        .returning(ResearchEvidence.id)
    )

    stored = await find_row(
        session, scope, record.id
    )

    if stored is None:
        # Includes a collision outside the authorized scope.
        raise EvidenceUnavailable()

    if inserted_id is not None and inserted_id != record.id:
        raise EvidenceRejected()

    return EvidenceInsertResult(
        record=decode_row(stored, scope),
        created=inserted_id is not None,
    )


async def get_evidence(
    session: AsyncSession,
    *,
    scope,
    evidence_id,
    execution_handle=None,
) -> EvidenceRecord | None:
    require_transaction(session)

    scope = validate_scope(scope)
    evidence_id = valid_uuid(evidence_id)

    await require_task(
        session, scope,
        execution_handle=execution_handle,
    )

    row = await find_row(
        session, scope, evidence_id
    )

    if row is None:
        return None

    return decode_row(row, scope)


async def list_evidence(
    session: AsyncSession,
    *,
    scope,
    execution_handle=None,
) -> tuple[EvidenceRecord, ...]:
    require_transaction(session)

    scope = validate_scope(scope)

    await require_task(
        session, scope,
        execution_handle=execution_handle,
    )

    rows = (
        await session.scalars(
            select(ResearchEvidence)
            .where(*scope_filters(scope))
            .order_by(
                ResearchEvidence.retrieved_at,
                ResearchEvidence.id,
            )
            .limit(MAX_EVIDENCE_PER_TASK + 1)
            .execution_options(populate_existing=True)
        )
    ).all()

    if len(rows) > MAX_EVIDENCE_PER_TASK:
        raise EvidenceRejected()

    records = tuple(
        decode_row(row, scope)
        for row in rows
    )

    if len({record.id for record in records}) != len(records):
        raise EvidenceRejected()

    return records
