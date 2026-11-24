"""Research persistence only; lifecycle execution belongs to a future worker."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    LargeBinary, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agentops_api.core.orm import Base
from agentops_api.models import identity as _identity  # noqa: F401


class ResearchTask(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_research_tasks_owner_key"),
        UniqueConstraint("owner_id", "id", name="uq_research_tasks_owner_id"),
        ForeignKeyConstraint(
            ["owner_id", "retry_parent_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_tasks_owner_retry_parent", ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','insufficient_evidence','failed','timed_out')",
            name="valid_status",
        ),
        CheckConstraint("length(btrim(question)) > 0", name="question_nonempty"),
        CheckConstraint("jsonb_typeof(scope) = 'object'", name="scope_object"),
        CheckConstraint("length(btrim(idempotency_key)) > 0", name="key_nonempty"),
        CheckConstraint("octet_length(request_fingerprint) = 32", name="fingerprint_length"),
        CheckConstraint("retry_parent_id IS NULL OR retry_parent_id <> id", name="not_own_retry"),
        CheckConstraint("started_at IS NULL OR started_at >= created_at", name="start_order"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= COALESCE(started_at, created_at)",
            name="completion_order",
        ),
        CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name="deletion_order"),
        CheckConstraint("updated_at >= created_at", name="update_order"),
        CheckConstraint(
            "(status IN ('queued','running') AND completed_at IS NULL) OR "
            "(status IN ('completed','insufficient_evidence','failed','timed_out') AND completed_at IS NOT NULL)",
            name="terminal_timestamp",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL) OR "
            "(status IN ('running','completed','insufficient_evidence') AND started_at IS NOT NULL) OR "
            "status IN ('failed','timed_out')", name="start_timestamp",
        ),
        CheckConstraint(
            "error_category IS NULL OR error_category ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="error_category_code",
        ),
        Index("ix_research_tasks_owner_history", "owner_id", "created_at", "id",
              postgresql_where=text("deleted_at IS NULL")),
        Index("ix_research_tasks_queue", "created_at", "id",
              postgresql_where=text("status = 'queued' AND deleted_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="RESTRICT"), nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    current_stage: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    retry_parent_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_category: Mapped[str | None] = mapped_column(String(64))
