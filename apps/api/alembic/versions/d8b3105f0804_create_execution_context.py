"""Add S07 durable execution context and operation ledger.

Revision ID: d8b3105f0804
Revises: c7a2104e0702

Execution remains restricted by the existing Alembic environment
to the explicitly disposable migration-test database.
"""

from alembic import op
import sqlalchemy as sa


revision = "d8b3105f0804"
down_revision = "c7a2104e0702"
branch_labels = None
depends_on = None

SCHEMA = "app"
CONTEXT = "research_execution_contexts"
LEDGER = "research_operation_ledger"


def _check(table, label, expression):
    return sa.CheckConstraint(
        expression,
        name=op.f(f"ck_{table}_{label}"),
    )


def _counter(name):
    return sa.Column(
        name,
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )


def _time(name, nullable=False):
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
    )


def _uuid(name):
    return sa.Column(
        name,
        sa.UUID(),
        nullable=False,
    )


def upgrade():
    op.create_unique_constraint(
        "uq_execution_attempt_owner_task_id",
        "research_execution_attempts",
        ["owner_id", "task_id", "id"],
        schema=SCHEMA,
    )

    op.create_table(
        CONTEXT,
        _uuid("task_id"),
        _uuid("owner_id"),
        _time("started_at"),
        _time("deadline_at"),
        _counter("search_calls"),
        _counter("retrieval_calls"),
        _counter("model_calls"),
        _counter("reserved_tokens"),
        _counter("reserved_cost_microusd"),
        _counter("adapter_invocations"),
        _counter("repair_attempts"),
        _time("updated_at"),
        _time("blocked_at", nullable=True),
        sa.Column("block_reason", sa.String(32)),
        sa.PrimaryKeyConstraint(
            "task_id",
            name=op.f("pk_research_execution_contexts"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_exec_context_owner_task",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "task_id",
            name="uq_exec_context_owner_task",
        ),
        _check(
            CONTEXT,
            "original_deadline",
            "deadline_at = started_at + interval '180 seconds'",
        ),
        _check(CONTEXT, "search_bounds", "search_calls BETWEEN 0 AND 6"),
        _check(
            CONTEXT, "retrieval_bounds",
            "retrieval_calls BETWEEN 0 AND 12",
        ),
        _check(CONTEXT, "model_bounds", "model_calls BETWEEN 0 AND 8"),
        _check(
            CONTEXT, "token_bounds",
            "reserved_tokens BETWEEN 0 AND 40000",
        ),
        _check(
            CONTEXT, "cost_bounds",
            "reserved_cost_microusd BETWEEN 0 AND 1000000",
        ),
        _check(
            CONTEXT, "adapter_bounds",
            "adapter_invocations BETWEEN 0 AND 4",
        ),
        _check(
            CONTEXT, "repair_bounds",
            "repair_attempts BETWEEN 0 AND 1 "
            "AND repair_attempts <= adapter_invocations",
        ),
        _check(CONTEXT, "updated_order", "updated_at >= started_at"),
        _check(
            CONTEXT, "block_consistency",
            "(blocked_at IS NULL AND block_reason IS NULL) OR "
            "(blocked_at IS NOT NULL AND block_reason IS NOT NULL)",
        ),
        _check(
            CONTEXT, "block_order",
            "blocked_at IS NULL OR blocked_at >= started_at",
        ),
        _check(
            CONTEXT, "block_reason",
            "block_reason IS NULL OR block_reason IN ("
            "'indeterminate_operation', 'deadline_exceeded', "
            "'cancellation_unverified', 'accounting_integrity')",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        LEDGER,
        _uuid("id"),
        _uuid("owner_id"),
        _uuid("task_id"),
        _uuid("attempt_id"),
        _uuid("operation_id"),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("retry_ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "is_repair",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        _time("reserved_at"),
        _time("deadline_at"),
        _counter("reserved_tokens"),
        _counter("reserved_cost_microusd"),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'reserved'"),
        ),
        _time("dispatched_at", nullable=True),
        _time("resolved_at", nullable=True),
        sa.Column(
            "retry_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("actual_tokens", sa.Integer()),
        sa.Column("actual_cost_microusd", sa.Integer()),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_research_operation_ledger"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id"],
            [
                "app.research_execution_contexts.owner_id",
                "app.research_execution_contexts.task_id",
            ],
            name="fk_operation_owner_context",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id", "attempt_id"],
            [
                "app.research_execution_attempts.owner_id",
                "app.research_execution_attempts.task_id",
                "app.research_execution_attempts.id",
            ],
            name="fk_operation_owner_attempt",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "task_id", "operation_id", "retry_ordinal",
            name="uq_operation_logical_retry",
        ),
        _check(
            LEDGER, "kind_code",
            "kind IN ('search', 'retrieval', 'model', 'adapter')",
        ),
        _check(LEDGER, "retry_bounds", "retry_ordinal BETWEEN 0 AND 1"),
        _check(
            LEDGER, "retry_kind",
            "retry_ordinal = 0 OR kind IN ('search', 'retrieval')",
        ),
        _check(
            LEDGER, "repair_kind",
            "NOT is_repair OR kind = 'adapter'",
        ),
        _check(
            LEDGER, "deadline_order",
            "deadline_at > reserved_at",
        ),
        _check(
            LEDGER, "deadline_bound",
            "deadline_at <= reserved_at + "
            "CASE WHEN kind = 'model' THEN interval '45 seconds' "
            "WHEN kind = 'adapter' THEN interval '30 seconds' "
            "ELSE interval '15 seconds' END",
        ),
        _check(
            LEDGER, "token_bounds",
            "reserved_tokens BETWEEN 0 AND 40000",
        ),
        _check(
            LEDGER, "cost_bounds",
            "reserved_cost_microusd BETWEEN 0 AND 1000000",
        ),
        _check(
            LEDGER, "token_kind",
            "kind = 'model' OR reserved_tokens = 0",
        ),
        _check(
            LEDGER, "status_code",
            "status IN ('reserved', 'dispatching', "
            "'succeeded', 'failed', 'cancelled', "
            "'timed_out', 'indeterminate')",
        ),
        _check(
            LEDGER, "dispatch_order",
            "dispatched_at IS NULL OR ("
            "dispatched_at >= reserved_at "
            "AND dispatched_at < deadline_at)",
        ),
        _check(
            LEDGER, "resolution_order",
            "resolved_at IS NULL OR ("
            "resolved_at >= reserved_at AND "
            "(dispatched_at IS NULL OR "
            "resolved_at >= dispatched_at))",
        ),
        _check(
            LEDGER, "status_consistency",
            "(status = 'reserved' AND dispatched_at IS NULL "
            "AND resolved_at IS NULL) OR "
            "(status = 'dispatching' AND dispatched_at IS NOT NULL "
            "AND resolved_at IS NULL) OR "
            "(status IN ('succeeded', 'failed', 'cancelled', "
            "'timed_out', 'indeterminate') "
            "AND resolved_at IS NOT NULL)",
        ),
        _check(
            LEDGER, "success_consistency",
            "status <> 'succeeded' OR "
            "(dispatched_at IS NOT NULL "
            "AND resolved_at <= deadline_at)",
        ),
        _check(
            LEDGER, "retry_eligibility",
            "NOT retry_eligible OR "
            "(status = 'failed' AND retry_ordinal = 0 "
            "AND kind IN ('search', 'retrieval') "
            "AND dispatched_at IS NOT NULL)",
        ),
        _check(
            LEDGER, "actual_token_bounds",
            "actual_tokens IS NULL OR ("
            "kind = 'model' AND actual_tokens >= 0 "
            "AND actual_tokens <= reserved_tokens)",
        ),
        _check(
            LEDGER, "actual_cost_bounds",
            "actual_cost_microusd IS NULL OR ("
            "actual_cost_microusd >= 0 "
            "AND actual_cost_microusd <= reserved_cost_microusd)",
        ),
        _check(
            LEDGER, "actual_usage_resolution",
            "resolved_at IS NOT NULL OR "
            "(actual_tokens IS NULL "
            "AND actual_cost_microusd IS NULL)",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "uq_operation_unresolved_task",
        LEDGER,
        ["task_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('reserved', 'dispatching')"
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_operation_attempt",
        LEDGER,
        ["attempt_id"],
        schema=SCHEMA,
    )

    for table in (CONTEXT, LEDGER):
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE app.{table} FROM PUBLIC"
        )

        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE app.{table} FROM agentops_app"
        )

        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON TABLE app.{table} "
            "TO agentops_app"
        )


def downgrade():
    # Existing Alembic target guard remains mandatory.
    op.drop_table(LEDGER, schema=SCHEMA)
    op.drop_table(CONTEXT, schema=SCHEMA)

    op.drop_constraint(
        "uq_execution_attempt_owner_task_id",
        "research_execution_attempts",
        type_="unique",
        schema=SCHEMA,
    )
