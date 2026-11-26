"""S08 provider accounting and real evidence foundation.

Revision ID: e8c2106a0801
Revises: d8b3105f0804

Disposable Development MVP migration verification only.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import conv

revision = "e8c2106a0801"
down_revision = "d8b3105f0804"
branch_labels = None
depends_on = None

SCHEMA = "app"
LEDGER = "research_operation_ledger"
GRANTS = "research_smoke_grants"
REAL = "research_real_evidence"


def upgrade():
    op.create_table(
        GRANTS,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("provider_name", sa.String(32), nullable=False),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column("query_sha256", sa.LargeBinary(32), nullable=False),
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
            "provider_name = 'tavily' "
            "AND endpoint = 'https://api.tavily.com/search'",
            name=conv("ck_s08_grant_provider"),
        ),
        sa.CheckConstraint(
            "octet_length(query_sha256) = 32",
            name=conv("ck_s08_grant_query"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at "
            "AND expires_at <= issued_at + interval '15 minutes'",
            name=conv("ck_s08_grant_expiry"),
        ),
        sa.CheckConstraint(
            "max_search_requests BETWEEN 1 AND 6 "
            "AND max_provider_credits = max_search_requests",
            name=conv("ck_s08_grant_credits"),
        ),
        sa.CheckConstraint(
            "((max_retrieval_requests = 0 "
            "AND retrieval_url_sha256 IS NULL) OR "
            "(max_retrieval_requests = 1 "
            "AND retrieval_url_sha256 IS NOT NULL "
            "AND octet_length(retrieval_url_sha256) = 32))",
            name=conv("ck_s08_grant_retrieval"),
        ),
        sa.CheckConstraint(
            "lock_marker = 0",
            name=conv("ck_s08_grant_lock_marker"),
        ),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('acquisition_origin', sa.String(16)),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('provider_name', sa.String(32)),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('reserved_provider_credits', sa.Integer()),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('observed_provider_credits', sa.Integer()),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('smoke_grant_id', sa.UUID()),
        schema=SCHEMA,
    )

    op.add_column(
        LEDGER,
        sa.Column('request_sha256', sa.LargeBinary(32)),
        schema=SCHEMA,
    )

    op.create_unique_constraint(
        "uq_s08_operation_scope",
        LEDGER,
        ['owner_id', 'task_id', 'attempt_id', 'id', 'acquisition_origin', 'kind', 'status'],
        schema=SCHEMA,
    )

    op.create_foreign_key(
        "fk_s08_operation_grant",
        LEDGER,
        GRANTS,
        ['owner_id', 'task_id', 'smoke_grant_id'],
        ["owner_id", "task_id", "id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )

    op.create_check_constraint(
        op.f("ck_s08_operation_provider"),
        LEDGER,
        "(\n    (\n        acquisition_origin IS NULL\n        AND provider_name IS NULL\n        AND reserved_provider_credits IS NULL\n        AND observed_provider_credits IS NULL\n        AND smoke_grant_id IS NULL\n        AND request_sha256 IS NULL\n    )\n    OR\n    (\n        acquisition_origin IN ('synthetic', 'live')\n        AND kind IN ('search', 'retrieval')\n        AND request_sha256 IS NOT NULL\n        AND octet_length(request_sha256) = 32\n        AND (\n            (acquisition_origin = 'synthetic'\n             AND smoke_grant_id IS NULL)\n            OR\n            (acquisition_origin = 'live'\n             AND smoke_grant_id IS NOT NULL\n             AND retry_ordinal = 0\n             AND NOT retry_eligible)\n        )\n        AND (\n            (\n                kind = 'search'\n                AND provider_name = 'tavily'\n                AND reserved_provider_credits = 1\n                AND (\n                    observed_provider_credits IS NULL\n                    OR (\n                        observed_provider_credits = 1\n                        AND dispatched_at IS NOT NULL\n                        AND resolved_at IS NOT NULL\n                    )\n                )\n                AND (\n                    status <> 'succeeded'\n                    OR observed_provider_credits = 1\n                )\n            )\n            OR\n            (\n                kind = 'retrieval'\n                AND provider_name IS NULL\n                AND reserved_provider_credits IS NULL\n                AND observed_provider_credits IS NULL\n            )\n        )\n    )\n) IS TRUE",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_s08_operation_grant",
        LEDGER,
        ["smoke_grant_id"],
        schema=SCHEMA,
    )

    op.create_table(
        REAL,
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
        schema=SCHEMA,
    )

    for table in (GRANTS, REAL):
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE app.{table} FROM PUBLIC"
        )
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE app.{table} FROM agentops_app"
        )

    op.execute(
        "GRANT SELECT ON app.research_smoke_grants TO agentops_app"
    )
    op.execute(
        "GRANT UPDATE (lock_marker) "
        "ON app.research_smoke_grants TO agentops_app"
    )
    op.execute(
        "GRANT SELECT, INSERT "
        "ON app.research_real_evidence TO agentops_app"
    )


def downgrade():
    # Never remove populated S08 accounting/evidence through this
    # downgrade. The existing disposable target guard also applies.
    bind = op.get_bind()

    for table in (REAL, GRANTS):
        if bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM app.{table})")
        ).scalar_one():
            raise RuntimeError("S08 downgrade requires empty new tables")

    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 "
            "FROM app.research_operation_ledger "
            "WHERE acquisition_origin IS NOT NULL)"
        )
    ).scalar_one():
        raise RuntimeError("S08 downgrade requires empty provider usage")

    op.drop_table(REAL, schema=SCHEMA)

    op.drop_index(
        "ix_s08_operation_grant",
        table_name=LEDGER,
        schema=SCHEMA,
    )

    op.drop_constraint(
        "fk_s08_operation_grant",
        LEDGER,
        type_="foreignkey",
        schema=SCHEMA,
    )

    op.drop_constraint(
        "uq_s08_operation_scope",
        LEDGER,
        type_="unique",
        schema=SCHEMA,
    )

    op.drop_constraint(
        op.f("ck_s08_operation_provider"),
        LEDGER,
        type_="check",
        schema=SCHEMA,
    )

    op.drop_column(LEDGER, 'request_sha256', schema=SCHEMA)
    op.drop_column(LEDGER, 'smoke_grant_id', schema=SCHEMA)
    op.drop_column(LEDGER, 'observed_provider_credits', schema=SCHEMA)
    op.drop_column(LEDGER, 'reserved_provider_credits', schema=SCHEMA)
    op.drop_column(LEDGER, 'provider_name', schema=SCHEMA)
    op.drop_column(LEDGER, 'acquisition_origin', schema=SCHEMA)

    op.drop_table(GRANTS, schema=SCHEMA)
