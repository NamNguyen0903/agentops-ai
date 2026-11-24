
"""PostgreSQL integration tests for AG-003.3B.

Run only against the disposable migration-test database.
No schema modifications, migrations, or data writes are performed.
"""

import os

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


DATABASE_ENV = "AGENTOPS_MIGRATION_DATABASE_URL"
OPT_IN_ENV = "AGENTOPS_RUN_DB_INTEGRATION"

EXPECTED_DATABASE = "agentops_migration_test"
EXPECTED_ROLE = "agentops_migrator"
EXPECTED_SCHEMA = "app"

EXPECTED_TABLES = {
    "users",
    "auth_identities",
    "auth_sessions",
    "oidc_login_transactions",
}


def get_test_database_url():
    """Validate target before opening a connection."""

    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(
            "PostgreSQL integration tests require explicit opt-in."
        )

    raw_url = os.getenv(DATABASE_ENV)

    if not raw_url:
        pytest.fail(
            "Migration test database URL is missing.",
            pytrace=False,
        )

    try:
        url = make_url(raw_url)
    except Exception:
        pytest.fail(
            "Invalid migration test database URL.",
            pytrace=False,
        )

    if (
        url.drivername != "postgresql+psycopg"
        or url.username != EXPECTED_ROLE
        or url.database != EXPECTED_DATABASE
        or not url.host
    ):
        pytest.fail(
            "Unauthorized migration test database target.",
            pytrace=False,
        )

    return url


@pytest.fixture
def db_connection():
    """Provide a validated, read-only test connection."""

    url = get_test_database_url()

    engine = None

    try:
        engine = create_engine(
            url,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 3,
                "options": (
                    "-c statement_timeout=10000 "
                    "-c lock_timeout=3000 "
                    "-c default_transaction_read_only=on"
                ),
            },
        )

        with engine.connect() as connection:
            role = connection.execute(
                text("SELECT current_user")
            ).scalar_one()

            database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            schema_owner = connection.execute(
                text(
                    "SELECT pg_get_userbyid(nspowner) "
                    "FROM pg_namespace "
                    "WHERE nspname = :schema"
                ),
                {"schema": EXPECTED_SCHEMA},
            ).scalar_one_or_none()

            if (
                role != EXPECTED_ROLE
                or database != EXPECTED_DATABASE
                or schema_owner != EXPECTED_ROLE
            ):
                pytest.fail(
                    "Database identity or schema ownership mismatch.",
                    pytrace=False,
                )

            connection.rollback()

            with connection.begin():
                yield connection

            # No INSERT/UPDATE/DELETE is performed by this smoke test.
            # Future write tests must use rollback-only fixtures.

    except pytest.fail.Exception:
        raise

    except Exception:
        pytest.fail(
            "PostgreSQL integration test setup failed. "
            "Check database connectivity and permissions.",
            pytrace=False,
        )

    finally:
        if engine is not None:
            engine.dispose()


def test_identity_tables_exist(db_connection):
    """Verify approved identity tables exist in the test DB."""

    rows = db_connection.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
            """
        ),
        {"schema": EXPECTED_SCHEMA},
    ).scalars().all()

    actual_tables = set(rows)

    missing_tables = EXPECTED_TABLES - actual_tables

    assert not missing_tables, (
        "Missing approved identity tables: "
        + ", ".join(sorted(missing_tables))
    )
