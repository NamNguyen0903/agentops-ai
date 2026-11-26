"""Task-owned durable accounting for S07 Development MVP.

Persistence declarations only. No database connection, dispatch,
provider activation or worker startup occurs on import.

Cross-row accounting and attempt authorization are enforced by
the application service under the approved transaction lock order.
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
from agentops_api.models.execution import ResearchExecutionAttempt


# Add relational integrity without changing WP02 lifecycle behavior.
# The matching migration explicitly creates this unique constraint.
ResearchExecutionAttempt.__table__.append_constraint(
    UniqueConstraint(
        "owner_id",
        "task_id",
        "id",
        name="uq_execution_attempt_owner_task_id",
    )
)


class ResearchExecutionContext(Base):
    """One durable accounting context for the whole research task."""

    __tablename__ = "research_execution_contexts"

    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_exec_context_owner_task",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "owner_id",
            "task_id",
            name="uq_exec_context_owner_task",
        ),
        CheckConstraint(
            "deadline_at = started_at + interval '180 seconds'",
            name="original_deadline",
        ),
        CheckConstraint(
            "search_calls BETWEEN 0 AND 6",
            name="search_bounds",
        ),
        CheckConstraint(
            "retrieval_calls BETWEEN 0 AND 12",
            name="retrieval_bounds",
        ),
        CheckConstraint(
            "model_calls BETWEEN 0 AND 8",
            name="model_bounds",
        ),
        CheckConstraint(
            "reserved_tokens BETWEEN 0 AND 40000",
            name="token_bounds",
        ),
        CheckConstraint(
            "reserved_cost_microusd BETWEEN 0 AND 1000000",
            name="cost_bounds",
        ),
        CheckConstraint(
            "adapter_invocations BETWEEN 0 AND 4",
            name="adapter_bounds",
        ),
        CheckConstraint(
            "repair_attempts BETWEEN 0 AND 1 "
            "AND repair_attempts <= adapter_invocations",
            name="repair_bounds",
        ),
        CheckConstraint(
            "updated_at >= started_at",
            name="updated_order",
        ),
        CheckConstraint(
            "(blocked_at IS NULL AND block_reason IS NULL) OR "
            "(blocked_at IS NOT NULL AND block_reason IS NOT NULL)",
            name="block_consistency",
        ),
        CheckConstraint(
            "blocked_at IS NULL OR blocked_at >= started_at",
            name="block_order",
        ),
        CheckConstraint(
            "block_reason IS NULL OR block_reason IN ("
            "'indeterminate_operation', 'deadline_exceeded', "
            "'cancellation_unverified', 'accounting_integrity')",
            name="block_reason",
        ),
    )

    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    search_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    retrieval_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    model_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    reserved_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    reserved_cost_microusd: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    adapter_invocations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    repair_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    block_reason: Mapped[str | None] = mapped_column(
        String(32)
    )


class ResearchOperationReservation(Base):
    """Durable identity and conservative charge for one dispatch."""

    __tablename__ = "research_operation_ledger"

    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "task_id"],
            [
                "app.research_execution_contexts.owner_id",
                "app.research_execution_contexts.task_id",
            ],
            name="fk_operation_owner_context",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_id", "task_id", "attempt_id"],
            [
                "app.research_execution_attempts.owner_id",
                "app.research_execution_attempts.task_id",
                "app.research_execution_attempts.id",
            ],
            name="fk_operation_owner_attempt",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "task_id",
            "operation_id",
            "retry_ordinal",
            name="uq_operation_logical_retry",
        ),
        CheckConstraint(
            "kind IN ('search', 'retrieval', 'model', 'adapter')",
            name="kind_code",
        ),
        CheckConstraint(
            "retry_ordinal BETWEEN 0 AND 1",
            name="retry_bounds",
        ),
        CheckConstraint(
            "retry_ordinal = 0 OR kind IN ('search', 'retrieval')",
            name="retry_kind",
        ),
        CheckConstraint(
            "NOT is_repair OR kind = 'adapter'",
            name="repair_kind",
        ),
        CheckConstraint(
            "deadline_at > reserved_at",
            name="deadline_order",
        ),
        CheckConstraint(
            "deadline_at <= reserved_at + "
            "CASE WHEN kind = 'model' THEN interval '45 seconds' "
            "WHEN kind = 'adapter' THEN interval '30 seconds' "
            "ELSE interval '15 seconds' END",
            name="deadline_bound",
        ),
        CheckConstraint(
            "reserved_tokens BETWEEN 0 AND 40000",
            name="token_bounds",
        ),
        CheckConstraint(
            "reserved_cost_microusd BETWEEN 0 AND 1000000",
            name="cost_bounds",
        ),
        CheckConstraint(
            "kind = 'model' OR reserved_tokens = 0",
            name="token_kind",
        ),
        CheckConstraint(
            "status IN ('reserved', 'dispatching', "
            "'succeeded', 'failed', 'cancelled', "
            "'timed_out', 'indeterminate')",
            name="status_code",
        ),
        CheckConstraint(
            "dispatched_at IS NULL OR ("
            "dispatched_at >= reserved_at "
            "AND dispatched_at < deadline_at)",
            name="dispatch_order",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR ("
            "resolved_at >= reserved_at AND "
            "(dispatched_at IS NULL OR "
            "resolved_at >= dispatched_at))",
            name="resolution_order",
        ),
        CheckConstraint(
            "(status = 'reserved' AND dispatched_at IS NULL "
            "AND resolved_at IS NULL) OR "
            "(status = 'dispatching' AND dispatched_at IS NOT NULL "
            "AND resolved_at IS NULL) OR "
            "(status IN ('succeeded', 'failed', 'cancelled', "
            "'timed_out', 'indeterminate') "
            "AND resolved_at IS NOT NULL)",
            name="status_consistency",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR "
            "(dispatched_at IS NOT NULL "
            "AND resolved_at <= deadline_at)",
            name="success_consistency",
        ),
        CheckConstraint(
            "NOT retry_eligible OR "
            "(status = 'failed' AND retry_ordinal = 0 "
            "AND kind IN ('search', 'retrieval') "
            "AND dispatched_at IS NOT NULL)",
            name="retry_eligibility",
        ),
        CheckConstraint(
            "actual_tokens IS NULL OR ("
            "kind = 'model' AND actual_tokens >= 0 "
            "AND actual_tokens <= reserved_tokens)",
            name="actual_token_bounds",
        ),
        CheckConstraint(
            "actual_cost_microusd IS NULL OR ("
            "actual_cost_microusd >= 0 "
            "AND actual_cost_microusd <= reserved_cost_microusd)",
            name="actual_cost_bounds",
        ),
        CheckConstraint(
            "resolved_at IS NOT NULL OR "
            "(actual_tokens IS NULL "
            "AND actual_cost_microusd IS NULL)",
            name="actual_usage_resolution",
        ),
        Index(
            "uq_operation_unresolved_task",
            "task_id",
            unique=True,
            postgresql_where=text(
                "status IN ('reserved', 'dispatching')"
            ),
        ),
        Index(
            "ix_operation_attempt",
            "attempt_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4
    )

    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    task_id: Mapped[UUID] = mapped_column(nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(nullable=False)
    operation_id: Mapped[UUID] = mapped_column(nullable=False)

    kind: Mapped[str] = mapped_column(
        String(16), nullable=False
    )

    retry_ordinal: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    is_repair: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        server_default=text("false")
    )

    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    reserved_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    reserved_cost_microusd: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        server_default=text("0")
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False,
        server_default=text("'reserved'")
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    retry_eligible: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        server_default=text("false")
    )

    actual_tokens: Mapped[int | None] = mapped_column(
        Integer
    )

    actual_cost_microusd: Mapped[int | None] = mapped_column(
        Integer
    )
