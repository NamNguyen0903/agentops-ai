"""Controlled Alembic runner for AgentOps AI.

AG-003.3B: only disposable migration-test database is authorized.
Production/development database migrations require separate approval.
"""

import os

from alembic import context
from alembic.util import CommandError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from agentops_api.core.orm import APP_SCHEMA, Base

# Register all identity tables with SQLAlchemy metadata.
from agentops_api.models import identity  # noqa: F401


EXPECTED_ROLE = "agentops_migrator"
TEST_DATABASE = "agentops_migration_test"
ENV_DATABASE_URL = "AGENTOPS_MIGRATION_DATABASE_URL"


def run_migrations_offline() -> None:
    raise CommandError(
        "Offline migrations are disabled for AG-003.3B."
    )


def run_migrations_online() -> None:
    raw_url = os.environ.get(ENV_DATABASE_URL)

    if not raw_url:
        raise CommandError(
            f"{ENV_DATABASE_URL} is required."
        )

    url = make_url(raw_url)

    if url.drivername != "postgresql+psycopg":
        raise CommandError("Migration requires postgresql+psycopg.")

    if url.username != EXPECTED_ROLE:
        raise CommandError("Migration role is not authorized.")

    if url.database != TEST_DATABASE:
        raise CommandError(
            "Only the disposable migration-test database "
            "is authorized at this stage."
        )

    if len(Base.metadata.tables) != 4:
        raise CommandError(
            "Expected four approved identity models."
        )

    engine = create_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": (
                "-c statement_timeout=10000 "
                "-c lock_timeout=3000"
            ),
        },
    )

    try:
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
                {"schema": APP_SCHEMA},
            ).scalar_one_or_none()

            if (
                role != EXPECTED_ROLE
                or database != TEST_DATABASE
                or schema_owner != EXPECTED_ROLE
            ):
                raise CommandError(
                    "Database role, name, or schema ownership "
                    "does not match the approved test environment."
                )

            # Finish read-only inspection before starting the
            # explicit Alembic migration transaction.
            connection.rollback()

            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                include_schemas=True,
                version_table_schema=APP_SCHEMA,
                compare_type=True,
                transactional_ddl=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
