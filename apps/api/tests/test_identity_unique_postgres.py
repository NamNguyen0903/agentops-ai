"""Unique-key contention and rollback on the explicitly isolated PostgreSQL target."""
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from test_identity_db_integration import get_test_database_url


@pytest.mark.integration
def test_unique_insert_waits_and_rollback_releases_key():
    engine = create_engine(
        get_test_database_url(), poolclass=NullPool, hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
    )
    user_id = uuid.uuid4()
    insert = text("INSERT INTO app.users (id) VALUES (:id)")
    count = text("SELECT count(*) FROM app.users WHERE id = :id")
    try:
        with engine.connect() as first, engine.connect() as second:
            identity = first.execute(text(
                "SELECT current_database(), current_user, "
                "(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='app')"
            )).one()
            assert identity == (
                "agentops_migration_test", "agentops_migrator", "agentops_migrator"
            )
            first.rollback()
            first.execute(insert, {"id": user_id})
            try:
                second.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                with pytest.raises(OperationalError) as failure:
                    second.execute(insert, {"id": user_id})
                assert failure.value.orig.sqlstate == "55P03"
            finally:
                second.rollback()
                first.rollback()
            assert second.scalar(count, {"id": user_id}) == 0
            second.execute(insert, {"id": user_id})
            second.rollback()
            assert first.scalar(count, {"id": user_id}) == 0
    finally:
        engine.dispose()
