"""Add research task persistence without worker or provider execution.

Revision ID: 83d3b0f10901
Revises: 0291ce4556fe
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "83d3b0f10901"
down_revision = "0291ce4556fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.String(64)),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("retry_parent_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("error_category", sa.String(64)),
        sa.PrimaryKeyConstraint("id", name="pk_research_tasks"),
        sa.ForeignKeyConstraint(["owner_id"], ["app.users.id"],
                                name="fk_research_tasks_owner_id_users", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_research_tasks_owner_key"),
        sa.UniqueConstraint("owner_id", "id", name="uq_research_tasks_owner_id"),
        sa.ForeignKeyConstraint(
            ["owner_id", "retry_parent_id"], ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_tasks_owner_retry_parent", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','insufficient_evidence','failed','timed_out')",
            name=op.f("ck_research_tasks_valid_status"),
        ),
        sa.CheckConstraint("length(btrim(question)) > 0", name=op.f("ck_research_tasks_question_nonempty")),
        sa.CheckConstraint("jsonb_typeof(scope) = 'object'", name=op.f("ck_research_tasks_scope_object")),
        sa.CheckConstraint("length(btrim(idempotency_key)) > 0", name=op.f("ck_research_tasks_key_nonempty")),
        sa.CheckConstraint("octet_length(request_fingerprint) = 32", name=op.f("ck_research_tasks_fingerprint_length")),
        sa.CheckConstraint("retry_parent_id IS NULL OR retry_parent_id <> id", name=op.f("ck_research_tasks_not_own_retry")),
        sa.CheckConstraint("started_at IS NULL OR started_at >= created_at", name=op.f("ck_research_tasks_start_order")),
        sa.CheckConstraint("completed_at IS NULL OR completed_at >= COALESCE(started_at, created_at)",
                           name=op.f("ck_research_tasks_completion_order")),
        sa.CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name=op.f("ck_research_tasks_deletion_order")),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_research_tasks_update_order")),
        sa.CheckConstraint(
            "(status IN ('queued','running') AND completed_at IS NULL) OR "
            "(status IN ('completed','insufficient_evidence','failed','timed_out') AND completed_at IS NOT NULL)",
            name=op.f("ck_research_tasks_terminal_timestamp"),
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL) OR "
            "(status IN ('running','completed','insufficient_evidence') AND started_at IS NOT NULL) OR "
            "status IN ('failed','timed_out')", name=op.f("ck_research_tasks_start_timestamp"),
        ),
        sa.CheckConstraint("error_category IS NULL OR error_category ~ '^[a-z][a-z0-9_]{0,63}$'",
                           name=op.f("ck_research_tasks_error_category_code")),
        schema="app",
    )
    op.create_index("ix_research_tasks_owner_history", "research_tasks", ["owner_id", "created_at", "id"],
                    schema="app", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_research_tasks_queue", "research_tasks", ["created_at", "id"],
                    schema="app", postgresql_where=sa.text("status = 'queued' AND deleted_at IS NULL"))
    op.execute("REVOKE ALL PRIVILEGES ON TABLE app.research_tasks FROM agentops_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app.research_tasks TO agentops_app")


def downgrade() -> None:
    # Destructive only to the research table; existing guard restricts execution
    # to the explicitly disposable migration-test database.
    op.drop_table("research_tasks", schema="app")
