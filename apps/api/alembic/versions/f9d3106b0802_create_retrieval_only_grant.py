"""Explicit retrieval-only smoke grants.

Preserve historical search-bound grants and privileges.
Development MVP disposable verification only.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f9d3106b0802'
down_revision = 'e8c2106a0801'
branch_labels = None
depends_on = None

TABLE = "research_smoke_grants"
SCHEMA = "app"

OLD = {'ck_s08_grant_provider': "provider_name = 'tavily' AND endpoint = 'https://api.tavily.com/search'", 'ck_s08_grant_query': 'octet_length(query_sha256) = 32', 'ck_s08_grant_credits': 'max_search_requests BETWEEN 1 AND 6 AND max_provider_credits = max_search_requests', 'ck_s08_grant_retrieval': '((max_retrieval_requests = 0 AND retrieval_url_sha256 IS NULL) OR (max_retrieval_requests = 1 AND retrieval_url_sha256 IS NOT NULL AND octet_length(retrieval_url_sha256) = 32))'}
NEW = {'ck_s08_grant_provider': "((grant_kind = 'search_bound' AND (provider_name = 'tavily' AND endpoint = 'https://api.tavily.com/search')) OR (grant_kind = 'retrieval_only' AND provider_name = 'rfc_editor' AND endpoint = 'https://www.rfc-editor.org/rfc/rfc9110.txt')) IS TRUE", 'ck_s08_grant_query': "((grant_kind = 'search_bound' AND query_sha256 IS NOT NULL AND (octet_length(query_sha256) = 32)) OR (grant_kind = 'retrieval_only' AND query_sha256 IS NULL)) IS TRUE", 'ck_s08_grant_credits': "((grant_kind = 'search_bound' AND (max_search_requests BETWEEN 1 AND 6 AND max_provider_credits = max_search_requests)) OR (grant_kind = 'retrieval_only' AND max_search_requests = 0 AND max_provider_credits = 0 AND max_retrieval_requests = 1)) IS TRUE", 'ck_s08_grant_retrieval': "((((max_retrieval_requests = 0 AND retrieval_url_sha256 IS NULL) OR (max_retrieval_requests = 1 AND retrieval_url_sha256 IS NOT NULL AND octet_length(retrieval_url_sha256) = 32))) AND (grant_kind <> 'retrieval_only' OR retrieval_url_sha256 = decode('b0a7ba3817a5518b609f59cf294e1f585487af51d71ceb697ee2a722cd448b00', 'hex'))) IS TRUE"}


def _drop_checks(checks):
    for name in sorted(checks):
        op.drop_constraint(
            op.f(name), TABLE, type_="check", schema=SCHEMA,
        )


def _create_checks(checks):
    for name, condition in sorted(checks.items()):
        op.create_check_constraint(
            op.f(name), TABLE, condition, schema=SCHEMA,
        )


def upgrade():
    _drop_checks(OLD)
    op.add_column(
        TABLE,
        sa.Column(
            "grant_kind", sa.String(24), nullable=False,
            server_default=sa.text("'search_bound'"),
        ),
        schema=SCHEMA,
    )
    op.alter_column(
        TABLE, "query_sha256", nullable=True,
        existing_type=sa.LargeBinary(32), schema=SCHEMA,
    )
    _create_checks(NEW)


def downgrade():
    bind = op.get_bind()

    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 "
        "FROM app.research_smoke_grants "
        "WHERE grant_kind <> 'search_bound')"
    )).scalar_one():
        raise RuntimeError("Retrieval-only grants must be absent")

    _drop_checks(NEW)
    op.alter_column(
        TABLE, "query_sha256", nullable=False,
        existing_type=sa.LargeBinary(32), schema=SCHEMA,
    )
    op.drop_column(TABLE, "grant_kind", schema=SCHEMA)
    _create_checks(OLD)
