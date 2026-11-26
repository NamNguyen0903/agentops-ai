"""Task-owned durable accounting for S07 Development MVP.

Persistence declarations only. No database connection, dispatch,
provider activation or worker startup occurs on import.

Cross-row accounting and attempt authorization are enforced by
the application service under the approved transaction lock order.
"""

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.schema import conv

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
        UniqueConstraint(
            'owner_id', 'task_id', 'attempt_id', 'id', 'acquisition_origin', 'kind', 'status',
            name="uq_s08_operation_scope",
        ),
        ForeignKeyConstraint(
            ['owner_id', 'task_id', 'smoke_grant_id'],
            ['app.research_smoke_grants.owner_id', 'app.research_smoke_grants.task_id', 'app.research_smoke_grants.id'],
            name="fk_s08_operation_grant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(\n    (\n        acquisition_origin IS NULL\n        AND provider_name IS NULL\n        AND reserved_provider_credits IS NULL\n        AND observed_provider_credits IS NULL\n        AND smoke_grant_id IS NULL\n        AND request_sha256 IS NULL\n    )\n    OR\n    (\n        acquisition_origin IN ('synthetic', 'live')\n        AND kind IN ('search', 'retrieval')\n        AND request_sha256 IS NOT NULL\n        AND octet_length(request_sha256) = 32\n        AND (\n            (acquisition_origin = 'synthetic'\n             AND smoke_grant_id IS NULL)\n            OR\n            (acquisition_origin = 'live'\n             AND smoke_grant_id IS NOT NULL\n             AND retry_ordinal = 0\n             AND NOT retry_eligible)\n        )\n        AND (\n            (\n                kind = 'search'\n                AND provider_name = 'tavily'\n                AND reserved_provider_credits = 1\n                AND (\n                    observed_provider_credits IS NULL\n                    OR (\n                        observed_provider_credits = 1\n                        AND dispatched_at IS NOT NULL\n                        AND resolved_at IS NOT NULL\n                    )\n                )\n                AND (\n                    status <> 'succeeded'\n                    OR observed_provider_credits = 1\n                )\n            )\n            OR\n            (\n                kind = 'retrieval'\n                AND provider_name IS NULL\n                AND reserved_provider_credits IS NULL\n                AND observed_provider_credits IS NULL\n            )\n        )\n    )\n) IS TRUE",
            name=conv("ck_s08_operation_provider"),
        ),
        Index(
            "ix_s08_operation_grant",
            "smoke_grant_id",
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

    acquisition_origin: Mapped[str | None] = mapped_column(sa.String(16))

    provider_name: Mapped[str | None] = mapped_column(sa.String(32))

    reserved_provider_credits: Mapped[int | None] = mapped_column(sa.Integer())

    observed_provider_credits: Mapped[int | None] = mapped_column(sa.Integer())

    smoke_grant_id: Mapped[UUID | None] = mapped_column(sa.UUID())

    request_sha256: Mapped[bytes | None] = mapped_column(sa.LargeBinary(32))

class ResearchSmokeGrant(Base):
    """Durable scope; no grant issuance or live authorization on import."""

    __table__ = sa.Table(
        "research_smoke_grants",
        Base.metadata,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("provider_name", sa.String(32), nullable=False),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column(
            "grant_kind", sa.String(24), nullable=False,
            server_default=sa.text("'search_bound'"),
        ),
        sa.Column("query_sha256", sa.LargeBinary(32)),
        sa.Column("retrieval_url_sha256", sa.LargeBinary(32)),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_search_requests", sa.Integer(), nullable=False),
        sa.Column("max_provider_credits", sa.Integer(), nullable=False),
        sa.Column("max_retrieval_requests", sa.Integer(), nullable=False),
        sa.Column(
            "lock_marker",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id"],
            [
                "app.research_execution_contexts.owner_id",
                "app.research_execution_contexts.task_id",
            ],
            name="fk_s08_grant_context",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "owner_id", "task_id",
            name="uq_s08_grant_task",
        ),
        sa.UniqueConstraint(
            "owner_id", "task_id", "id",
            name="uq_s08_grant_scope_id",
        ),
        sa.CheckConstraint(
            "((grant_kind = 'search_bound' AND (provider_name = 'tavily' AND endpoint = 'https://api.tavily.com/search')) OR (grant_kind = 'retrieval_only' AND provider_name = 'rfc_editor' AND endpoint = 'https://www.rfc-editor.org/rfc/rfc9110.txt')) IS TRUE",
            name=conv("ck_s08_grant_provider"),
        ),
        sa.CheckConstraint(
            "((grant_kind = 'search_bound' AND query_sha256 IS NOT NULL AND (octet_length(query_sha256) = 32)) OR (grant_kind = 'retrieval_only' AND query_sha256 IS NULL)) IS TRUE",
            name=conv("ck_s08_grant_query"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at "
            "AND expires_at <= issued_at + interval '15 minutes'",
            name=conv("ck_s08_grant_expiry"),
        ),
        sa.CheckConstraint(
            "((grant_kind = 'search_bound' AND (max_search_requests BETWEEN 1 AND 6 AND max_provider_credits = max_search_requests)) OR (grant_kind = 'retrieval_only' AND max_search_requests = 0 AND max_provider_credits = 0 AND max_retrieval_requests = 1)) IS TRUE",
            name=conv("ck_s08_grant_credits"),
        ),
        sa.CheckConstraint(
            "((((max_retrieval_requests = 0 AND retrieval_url_sha256 IS NULL) OR (max_retrieval_requests = 1 AND retrieval_url_sha256 IS NOT NULL AND octet_length(retrieval_url_sha256) = 32))) AND (grant_kind <> 'retrieval_only' OR retrieval_url_sha256 = decode('b0a7ba3817a5518b609f59cf294e1f585487af51d71ceb697ee2a722cd448b00', 'hex'))) IS TRUE",
            name=conv("ck_s08_grant_retrieval"),
        ),
        sa.CheckConstraint(
            "lock_marker = 0",
            name=conv("ck_s08_grant_lock_marker"),
        ),
        schema="app",
    )


class ResearchRealEvidence(Base):
    """Separate immutable real-evidence persistence foundation."""

    __table__ = sa.Table(
        "research_real_evidence",
        Base.metadata,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("operation_ledger_id", sa.UUID(), nullable=False),
        sa.Column("acquisition_origin", sa.String(16), nullable=False),
        sa.Column("operation_kind", sa.String(16), nullable=False),
        sa.Column("operation_status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("retrieved_url", sa.String(2048), nullable=False),
        sa.Column("source_identity_sha256", sa.LargeBinary(32), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("acquisition_method", sa.String(32), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            [
                "owner_id", "task_id", "attempt_id",
                "operation_ledger_id", "acquisition_origin",
                "operation_kind", "operation_status",
            ],
            [
                "app.research_operation_ledger.owner_id",
                "app.research_operation_ledger.task_id",
                "app.research_operation_ledger.attempt_id",
                "app.research_operation_ledger.id",
                "app.research_operation_ledger.acquisition_origin",
                "app.research_operation_ledger.kind",
                "app.research_operation_ledger.status",
            ],
            name="fk_s08_real_operation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "owner_id", "task_id", "attempt_id",
            "source_identity_sha256", "content_hash",
            name="uq_s08_real_dedup",
        ),
        sa.CheckConstraint(
            "acquisition_origin = 'live' "
            "AND operation_kind = 'retrieval' "
            "AND operation_status = 'succeeded' "
            "AND acquisition_method = 'http_retrieval'",
            name=conv("ck_s08_real_origin"),
        ),
        sa.CheckConstraint(
            "octet_length(source_identity_sha256) = 32 "
            "AND octet_length(content_hash) = 32",
            name=conv("ck_s08_real_hashes"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 512 "
            "AND length(excerpt) BETWEEN 1 AND 4096 "
            "AND length(btrim(excerpt)) > 0",
            name=conv("ck_s08_real_text"),
        ),
        sa.CheckConstraint(
            "source_url ~ '^https?://' "
            "AND retrieved_url ~ '^https?://'",
            name=conv("ck_s08_real_urls"),
        ),
        sa.CheckConstraint(
            "published_at IS NULL OR published_at <= retrieved_at",
            name=conv("ck_s08_real_publication"),
        ),
        schema="app",
    )
