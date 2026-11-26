"""Durable attempt ownership for S07 Development MVP.

Persistence declarations only: importing this module must not start workers,
open database connections, or authorize external execution.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from agentops_api.core.orm import Base
from agentops_api.models import research as _research  # noqa: F401


class ResearchExecutionAttempt(Base):
    """One durable ownership generation for a research task."""

    __tablename__ = "research_execution_attempts"

    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_attempt_owner_task",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "task_id",
            "generation",
            name="uq_research_attempt_task_generation",
        ),
        CheckConstraint(
            "generation BETWEEN 1 AND 2",
            name="generation_bounds",
        ),
        CheckConstraint(
            "heartbeat_at >= claimed_at",
            name="heartbeat_order",
        ),
        CheckConstraint(
            "lease_expires_at > heartbeat_at",
            name="lease_order",
        ),
        CheckConstraint(
            "lease_expires_at <= "
            "heartbeat_at + interval '30 seconds'",
            name="lease_duration",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= heartbeat_at",
            name="end_order",
        ),
        CheckConstraint(
            "(ended_at IS NULL AND end_reason IS NULL) OR "
            "(ended_at IS NOT NULL AND end_reason IS NOT NULL)",
            name="end_consistency",
        ),
        CheckConstraint(
            "end_reason IS NULL OR end_reason IN ("
            "'completed', 'insufficient_evidence', 'failed', "
            "'timed_out', 'lease_expired', 'deleted', "
            "'indeterminate', 'attempts_exhausted')",
            name="end_reason_code",
        ),
        Index(
            "uq_research_attempt_active_task",
            "task_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_research_attempt_active_lease",
            "lease_expires_at",
            "task_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    owner_id: Mapped[UUID] = mapped_column(
        nullable=False,
    )

    task_id: Mapped[UUID] = mapped_column(
        nullable=False,
    )

    generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    worker_id: Mapped[UUID] = mapped_column(
        nullable=False,
    )

    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    lease_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    end_reason: Mapped[str | None] = mapped_column(
        String(32),
    )
