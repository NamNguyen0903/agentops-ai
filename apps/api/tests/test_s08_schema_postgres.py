"""S08 disposable PostgreSQL schema foundation verification."""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from agentops_api.models.execution_context import (
    ResearchExecutionContext,
    ResearchOperationReservation,
    ResearchSmokeGrant,
    ResearchRealEvidence,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AGENTOPS_RUN_DB_INTEGRATION") != "1",
        reason="Disposable PostgreSQL integration requires explicit opt-in",
    ),
]


@pytest.fixture(scope="module")
def connection():
    assert os.environ.get("AGENTOPS_RUN_DB_INTEGRATION") == "1"
    assert Path("/.dockerenv").is_file()

    url = make_url(os.environ["AGENTOPS_MIGRATION_DATABASE_URL"])

    assert url.host == "db"
    assert url.database == "agentops_migration_test"
    assert url.username == "agentops_migrator"

    engine = sa.create_engine(url)

    try:
        with engine.connect() as conn:
            assert conn.execute(
                sa.text("SELECT current_database()")
            ).scalar_one() == "agentops_migration_test"

            assert conn.execute(
                sa.text("SELECT current_user")
            ).scalar_one() == "agentops_migrator"

            yield conn
    finally:
        engine.dispose()


def scalar(conn, statement, **params):
    return conn.execute(
        sa.text(statement), params
    ).scalar_one()


def test_exact_migration_head(connection):
    assert scalar(
        connection,
        "SELECT version_num FROM app.alembic_version",
    ) == "f9d3106b0802"


def test_all_foundation_tables_exist(connection):
    inspector = sa.inspect(connection)
    names = set(inspector.get_table_names(schema="app"))

    assert {
        "research_execution_contexts",
        "research_operation_ledger",
        "research_smoke_grants",
        "research_real_evidence",
        "research_evidence",
    } <= names


def test_existing_ledger_columns_preserved(connection):
    cols = {
        item["name"]: item
        for item in sa.inspect(connection).get_columns(
            "research_operation_ledger", schema="app"
        )
    }

    for name in (
        "reserved_tokens",
        "reserved_cost_microusd",
        "actual_tokens",
        "actual_cost_microusd",
        "deadline_at",
        "retry_ordinal",
        "owner_id",
        "task_id",
        "attempt_id",
    ):
        assert name in cols

    for name in (
        "acquisition_origin",
        "provider_name",
        "reserved_provider_credits",
        "observed_provider_credits",
        "smoke_grant_id",
        "request_sha256",
    ):
        assert cols[name]["nullable"] is True


def test_orm_mappings_registered():
    assert ResearchExecutionContext.__table__.schema == "app"
    assert ResearchOperationReservation.__table__.schema == "app"

    assert ResearchSmokeGrant.__table__.fullname == (
        "app.research_smoke_grants"
    )
    assert ResearchRealEvidence.__table__.fullname == (
        "app.research_real_evidence"
    )


@pytest.mark.parametrize("table,expected", [
    (
        "research_operation_ledger",
        {"ck_s08_operation_provider"},
    ),
    (
        "research_smoke_grants",
        {
            "ck_s08_grant_provider",
            "ck_s08_grant_query",
            "ck_s08_grant_expiry",
            "ck_s08_grant_credits",
            "ck_s08_grant_retrieval",
            "ck_s08_grant_lock_marker",
        },
    ),
    (
        "research_real_evidence",
        {
            "ck_s08_real_origin",
            "ck_s08_real_hashes",
            "ck_s08_real_text",
            "ck_s08_real_urls",
            "ck_s08_real_publication",
        },
    ),
])
def test_validated_check_constraints(connection, table, expected):
    rows = connection.execute(
        sa.text("""
            SELECT con.conname, con.convalidated
            FROM pg_constraint AS con
            JOIN pg_class AS cls ON cls.oid = con.conrelid
            JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
            WHERE ns.nspname = 'app'
              AND cls.relname = :table
              AND con.contype = 'c'
        """),
        {"table": table},
    ).all()

    actual = {
        row[0] for row in rows if row[1] is True
    }

    assert expected <= actual


def test_real_evidence_composite_lineage(connection):
    fks = sa.inspect(connection).get_foreign_keys(
        "research_real_evidence", schema="app"
    )

    fk = next(
        item for item in fks
        if item["name"] == "fk_s08_real_operation"
    )

    assert fk["referred_schema"] == "app"
    assert fk["referred_table"] == "research_operation_ledger"

    assert fk["constrained_columns"] == [
        "owner_id", "task_id", "attempt_id",
        "operation_ledger_id", "acquisition_origin",
        "operation_kind", "operation_status",
    ]

    assert fk["referred_columns"] == [
        "owner_id", "task_id", "attempt_id", "id",
        "acquisition_origin", "kind", "status",
    ]


def test_grant_task_and_operation_scope(connection):
    inspector = sa.inspect(connection)

    unique = inspector.get_unique_constraints(
        "research_smoke_grants", schema="app"
    )

    assert any(
        item["name"] == "uq_s08_grant_task"
        and item["column_names"] == ["owner_id", "task_id"]
        for item in unique
    )

    fks = inspector.get_foreign_keys(
        "research_operation_ledger", schema="app"
    )

    fk = next(
        item for item in fks
        if item["name"] == "fk_s08_operation_grant"
    )

    assert fk["referred_table"] == "research_smoke_grants"
    assert fk["constrained_columns"] == [
        "owner_id", "task_id", "smoke_grant_id",
    ]


def test_real_evidence_dedup_constraint(connection):
    unique = sa.inspect(connection).get_unique_constraints(
        "research_real_evidence", schema="app"
    )

    assert any(
        item["name"] == "uq_s08_real_dedup"
        and item["column_names"] == [
            "owner_id", "task_id", "attempt_id",
            "source_identity_sha256", "content_hash",
        ]
        for item in unique
    )


@pytest.mark.parametrize("table,privilege,expected", [
    ("research_smoke_grants", "SELECT", True),
    ("research_smoke_grants", "INSERT", False),
    ("research_smoke_grants", "UPDATE", False),
    ("research_smoke_grants", "DELETE", False),
    ("research_smoke_grants", "TRUNCATE", False),
    ("research_real_evidence", "SELECT", True),
    ("research_real_evidence", "INSERT", True),
    ("research_real_evidence", "UPDATE", False),
    ("research_real_evidence", "DELETE", False),
    ("research_real_evidence", "TRUNCATE", False),
])
def test_runtime_table_privileges(
    connection, table, privilege, expected
):
    actual = scalar(
        connection,
        "SELECT has_table_privilege("
        "'agentops_app', :table, :privilege)",
        table="app." + table,
        privilege=privilege,
    )

    assert actual is expected


@pytest.mark.parametrize("column,expected", [
    ("lock_marker", True),
    ("owner_id", False),
    ("task_id", False),
    ("provider_name", False),
    ("endpoint", False),
    ("query_sha256", False),
    ("retrieval_url_sha256", False),
    ("issued_at", False),
    ("expires_at", False),
    ("max_search_requests", False),
    ("max_provider_credits", False),
    ("max_retrieval_requests", False),
])
def test_grant_column_privileges(connection, column, expected):
    actual = scalar(
        connection,
        "SELECT has_column_privilege("
        "'agentops_app', 'app.research_smoke_grants', "
        ":column, 'UPDATE')",
        column=column,
    )

    assert actual is expected


@pytest.mark.parametrize("table", [
    "research_smoke_grants",
    "research_real_evidence",
])
def test_no_public_grants(connection, table):
    assert scalar(
        connection,
        """
        SELECT count(*)
        FROM pg_class AS cls
        JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
        CROSS JOIN LATERAL aclexplode(cls.relacl) AS acl
        WHERE ns.nspname = 'app'
          AND cls.relname = :table
          AND acl.grantee = 0
        """,
        table=table,
    ) == 0


def test_original_synthetic_constraints_retained(connection):
    checks = sa.inspect(connection).get_check_constraints(
        "research_evidence", schema="app"
    )

    expressions = " ".join(
        item["sqltext"].lower() for item in checks
    )

    assert "synthetic is true" in expressions
    assert "fixture_retrieval" in expressions
    assert "published_at is null" in expressions


def test_no_live_grants_or_real_evidence_created(connection):
    for table in (
        "research_smoke_grants",
        "research_real_evidence",
    ):
        assert scalar(
            connection,
            f"SELECT count(*) FROM app.{table}",
        ) == 0


def test_existing_context_deadline_and_search_budget(connection):
    checks = sa.inspect(connection).get_check_constraints(
        "research_execution_contexts", schema="app"
    )

    names = {item["name"] for item in checks}

    assert "ck_research_execution_contexts_original_deadline" in names
    assert "ck_research_execution_contexts_search_bounds" in names


@pytest.mark.parametrize("origin,kind,reserved,observed,valid", [
    (None, "search", None, None, True),
    ("synthetic", "search", 1, 1, True),
    ("synthetic", "search", 2, 1, False),
    ("synthetic", "search", 1, None, False),
    ("synthetic", "search", 1, 2, False),
    ("live", "search", 1, 1, False),
    ("unknown", "search", 1, 1, False),
])
def test_provider_check_predicate(
    connection, origin, kind, reserved, observed, valid
):
    # Evaluate the actual installed PostgreSQL CHECK expression
    # with controlled synthetic values. No grant or operation is
    # inserted and no live usage is represented.
    expression = scalar(
        connection,
        """
        SELECT pg_get_expr(con.conbin, con.conrelid)
        FROM pg_constraint AS con
        JOIN pg_class AS cls ON cls.oid = con.conrelid
        JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
        WHERE ns.nspname = 'app'
          AND cls.relname = 'research_operation_ledger'
          AND con.conname = 'ck_s08_operation_provider'
        """,
    )

    result = scalar(
        connection,
        f"""
        SELECT ({expression})
        FROM (
            SELECT
                CAST(:origin AS varchar) AS acquisition_origin,
                CAST(:kind AS varchar) AS kind,
                CASE WHEN CAST(:origin AS varchar) IS NULL
                    THEN NULL ELSE 'tavily' END AS provider_name,
                CAST(:reserved AS integer)
                    AS reserved_provider_credits,
                CAST(:observed AS integer)
                    AS observed_provider_credits,
                NULL::uuid AS smoke_grant_id,
                CASE WHEN CAST(:origin AS varchar) IS NULL
                    THEN NULL::bytea
                    ELSE decode(repeat('00', 32), 'hex')
                END AS request_sha256,
                0 AS retry_ordinal,
                false AS retry_eligible,
                CURRENT_TIMESTAMP AS dispatched_at,
                CURRENT_TIMESTAMP AS resolved_at,
                'succeeded'::varchar AS status
        ) AS candidate
        """,
        origin=origin,
        kind=kind,
        reserved=reserved,
        observed=observed,
    )

    assert result is valid
