"""Owner-scoped research submission under caller-owned explicit transactions.

Use PostgreSQL READ COMMITTED. INSERT's unique-key conflict waits for a concurrent
winner; the following SELECT sees that committed row. This is not a worker queue.
Never acknowledge a submission until the caller's transaction has committed.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_api.models.research import ResearchTask


class ResearchScope(BaseModel):
    """Initial structured scope; text describes intent, not executable filters."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    geography: str | None = None
    competitors: tuple[str, ...] = ()
    category: str | None = None
    time_scope: str | None = None

    @field_validator("competitors", mode="before")
    @classmethod
    def accept_json_array(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


class ResearchSubmission(BaseModel):
    """Validated persistence input, independent of the future HTTP contract.

    Initial PRD hypotheses: question 4,000 and serialized scope 2,000 characters.
    model_validate(context={question_limit: ..., scope_limit: ...}) can override
    these limits. Inputs are preserved, not silently trimmed or case-folded.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    question: str = Field(min_length=1)
    scope: ResearchScope = Field(default_factory=ResearchScope)

    @model_validator(mode="after")
    def validate_limits(self, info: ValidationInfo) -> "ResearchSubmission":
        limits = info.context or {}
        scope_json = json.dumps(self.scope.model_dump(mode="json"), ensure_ascii=False)
        scope_values = (self.scope.geography, self.scope.category, self.scope.time_scope, *self.scope.competitors)
        if not self.question.strip() or "\x00" in self.question or any(
            value is not None and "\x00" in value for value in scope_values
        ):
            raise ValueError("Research input must be nonempty and contain no NUL characters")
        if len(self.question) > limits.get("question_limit", 4000):
            raise ValueError("Research question exceeds the configured limit")
        if len(scope_json) > limits.get("scope_limit", 2000):
            raise ValueError("Research scope exceeds the configured limit")
        return self

    def fingerprint(self) -> bytes:
        canonical = json.dumps(
            {"version": 1, **self.model_dump(mode="json")},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).digest()


class IdempotencyConflict(ValueError):
    """Key was already used for a different request, or a deleted task."""


@dataclass(frozen=True)
class SubmissionResult:
    task: ResearchTask
    created: bool


async def submit_task(
    session: AsyncSession, *, owner_id: UUID, idempotency_key: str,
    submission: ResearchSubmission,
    validation_limits: dict[str, int] | None = None,
) -> SubmissionResult:
    """Insert or reuse a live task; no commit, implicit transaction, or retry.

    owner_id must originate from the authenticated server principal. This layer
    scopes data access but does not itself authenticate or enforce admission quotas.
    Retry endpoints are deferred; callers cannot supply a retry parent here.
    """
    if not session.in_transaction():
        raise RuntimeError("Research submission requires an explicit transaction")
    if not idempotency_key.strip() or len(idempotency_key) > 128 or "\x00" in idempotency_key:
        raise ValueError("Invalid idempotency key")
    # Revalidate even model_construct inputs at this persistence boundary.
    submission = ResearchSubmission.model_validate(submission.model_dump(), context=validation_limits)
    fingerprint = submission.fingerprint()
    inserted_id = await session.scalar(
        insert(ResearchTask).values(
            id=uuid4(), owner_id=owner_id, question=submission.question,
            scope=submission.scope.model_dump(mode="json"), status="queued",
            idempotency_key=idempotency_key, request_fingerprint=fingerprint,
        ).on_conflict_do_nothing(constraint="uq_research_tasks_owner_key")
        .returning(ResearchTask.id)
    )
    task = (await session.scalars(
        select(ResearchTask).where(
            ResearchTask.owner_id == owner_id,
            ResearchTask.idempotency_key == idempotency_key,
        ).execution_options(populate_existing=True)
    )).one()
    if task.deleted_at is not None or task.request_fingerprint != fingerprint:
        raise IdempotencyConflict("Idempotency key is unavailable for this request")
    return SubmissionResult(task=task, created=inserted_id is not None)


async def get_task(session: AsyncSession, *, owner_id: UUID, task_id: UUID) -> ResearchTask | None:
    return await session.scalar(select(ResearchTask).where(
        ResearchTask.id == task_id, ResearchTask.owner_id == owner_id,
        ResearchTask.deleted_at.is_(None),
    ).execution_options(populate_existing=True))


async def list_tasks(
    session: AsyncSession, *, owner_id: UUID, limit: int = 20,
    before: tuple[datetime, UUID] | None = None,
) -> list[ResearchTask]:
    """Stable descending keyset order; HTTP cursor encoding belongs to WP02."""
    if not 1 <= limit <= 100:
        raise ValueError("History limit must be between 1 and 100")
    query = select(ResearchTask).where(
        ResearchTask.owner_id == owner_id, ResearchTask.deleted_at.is_(None),
    )
    if before is not None:
        query = query.where(tuple_(ResearchTask.created_at, ResearchTask.id) < before)
    query = query.order_by(ResearchTask.created_at.desc(), ResearchTask.id.desc()).limit(limit)
    return list((await session.scalars(query.execution_options(populate_existing=True))).all())
