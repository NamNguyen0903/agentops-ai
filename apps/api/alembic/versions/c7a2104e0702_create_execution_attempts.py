"""Add durable execution attempt ownership for S07.

Revision ID: c7a2104e0702
Revises: b6e0326a7103

The existing Alembic environment continues to restrict execution
to the explicitly disposable migration-test database.
"""

from alembic import op
import sqlalchemy as sa

revision = "c7a2104e0702"
down_revision = "b6e0326a7103"
branch_labels = None
depends_on = None

SCHEMA = "app"
TABLE = "research_execution_attempts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "generation",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "worker_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "end_reason",
            sa.String(32),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_research_execution_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_attempt_owner_task",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "task_id",
            "generation",
            name="uq_research_attempt_task_generation",
        ),
        sa.CheckConstraint(
            "generation BETWEEN 1 AND 2",
            name=op.f(
                "ck_research_execution_attempts_generation_bounds"
            ),
        ),
        sa.CheckConstraint(
            "heartbeat_at >= claimed_at",
            name=op.f(
                "ck_research_execution_attempts_heartbeat_order"
            ),
        ),
        sa.CheckConstraint(
            "lease_expires_at > heartbeat_at",
            name=op.f(
                "ck_research_execution_attempts_lease_order"
            ),
        ),
        sa.CheckConstraint(
            "lease_expires_at <= "
            "heartbeat_at + interval '30 seconds'",
            name=op.f(
                "ck_research_execution_attempts_lease_duration"
            ),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= heartbeat_at",
            name=op.f(
                "ck_research_execution_attempts_end_order"
            ),
        ),
        sa.CheckConstraint(
            "(ended_at IS NULL AND end_reason IS NULL) OR "
            "(ended_at IS NOT NULL AND end_reason IS NOT NULL)",
            name=op.f(
                "ck_research_execution_attempts_end_consistency"
            ),
        ),
        sa.CheckConstraint(
            "end_reason IS NULL OR end_reason IN ("
            "'completed', 'insufficient_evidence', 'failed', "
            "'timed_out', 'lease_expired', 'deleted', "
            "'indeterminate', 'attempts_exhausted')",
            name=op.f(
                "ck_research_execution_attempts_end_reason_code"
            ),
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "uq_research_attempt_active_task",
        TABLE,
        ["task_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    op.create_index(
        "ix_research_attempt_active_lease",
        TABLE,
        ["lease_expires_at", "task_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    op.execute(
        "REVOKE ALL PRIVILEGES "
        "ON TABLE app.research_execution_attempts FROM PUBLIC"
    )

    op.execute(
        "REVOKE ALL PRIVILEGES "
        "ON TABLE app.research_execution_attempts FROM agentops_app"
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE "
        "ON TABLE app.research_execution_attempts TO agentops_app"
    )


def downgrade() -> None:
    # Destructive only within the authorized disposable test database.
    op.drop_table(
        TABLE,
        schema=SCHEMA,
    )
