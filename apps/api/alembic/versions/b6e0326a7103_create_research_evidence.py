"""Create immutable synthetic research evidence.

Revision ID: b6e0326a7103
Revises: 94e4c1a20902
"""

from alembic import op
import sqlalchemy as sa

revision = "b6e0326a7103"
down_revision = "94e4c1a20902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("retrieved_url", sa.String(2048), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("acquisition_method", sa.String(32), nullable=False),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "content_hash",
            sa.LargeBinary(32),
            nullable=False,
        ),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_research_evidence"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_evidence_owner_task",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "owner_id", "task_id", "execution_id", "id",
            name="uq_research_evidence_scope_id",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 512",
            name=op.f("ck_research_evidence_title_nonempty"),
        ),
        sa.CheckConstraint(
            "length(excerpt) BETWEEN 1 AND 4096 "
            "AND length(btrim(excerpt)) > 0",
            name=op.f("ck_research_evidence_excerpt_bounds"),
        ),
        sa.CheckConstraint(
            "source_url ~ '^https?://' "
            "AND retrieved_url ~ '^https?://'",
            name=op.f("ck_research_evidence_url_schemes"),
        ),
        sa.CheckConstraint(
            "octet_length(content_hash) = 32",
            name=op.f("ck_research_evidence_hash_length"),
        ),
        sa.CheckConstraint(
            "acquisition_method = 'fixture_retrieval'",
            name=op.f("ck_research_evidence_acquisition_method"),
        ),
        sa.CheckConstraint(
            "synthetic IS TRUE",
            name=op.f("ck_research_evidence_synthetic_only"),
        ),
        sa.CheckConstraint(
            "published_at IS NULL",
            name=op.f("ck_research_evidence_publication_unknown"),
        ),
        schema="app",
    )

    op.create_index(
        "ix_research_evidence_scope",
        "research_evidence",
        ["owner_id", "task_id", "execution_id"],
        schema="app",
    )

    op.execute(
        "REVOKE ALL PRIVILEGES "
        "ON TABLE app.research_evidence FROM PUBLIC"
    )

    op.execute(
        "REVOKE ALL PRIVILEGES "
        "ON TABLE app.research_evidence FROM agentops_app"
    )

    op.execute(
        "GRANT SELECT, INSERT "
        "ON TABLE app.research_evidence TO agentops_app"
    )


def downgrade() -> None:
    # Existing Alembic environment restrictions remain active.
    op.drop_table("research_evidence", schema="app")
