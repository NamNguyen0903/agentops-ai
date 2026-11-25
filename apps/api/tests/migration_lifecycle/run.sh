
#!/bin/sh
set -eu

echo "=== S03-WP02: Admission Migration Lifecycle ==="

# Copy source into a writable temporary directory.
# Keep the repository mount read-only.
mkdir -p /tmp/agentops-build

cp /workspace/pyproject.toml /tmp/agentops-build/
cp -R /workspace/src /tmp/agentops-build/

target="$(python -c 'import platform,sys; print(f"py{sys.version_info.major}{sys.version_info.minor}-{platform.system().lower()}-{platform.machine().lower()}")')"

python -m pip install --no-cache-dir \
    --only-binary=:all: --require-hashes \
    -r "/workspace/requirements/${target}-dev.txt"

python -m pip install --no-cache-dir \
    --no-deps --no-build-isolation \
    "/tmp/agentops-build[dev]"

python -m pip check

export PYTHONPATH="/workspace/src${PYTHONPATH:+:$PYTHONPATH}"

check_state() {
    python - "$1" <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

phase = sys.argv[1]
url = os.environ["AGENTOPS_MIGRATION_DATABASE_URL"]

engine = create_engine(url)

expected_tables = {
    "users",
    "auth_identities",
    "auth_sessions",
    "oidc_login_transactions",
    "research_tasks",
    "queue_control",
    "research_evidence",
}

revision = "b6e0326a7103"
if phase == "queue":
    expected_tables.remove("research_evidence")
    revision = "94e4c1a20902"
elif phase == "research":
    expected_tables.remove("research_evidence")
    expected_tables.remove("queue_control")
    revision = "83d3b0f10901"
elif phase == "identity":
    expected_tables.remove("research_evidence")
    expected_tables.remove("queue_control")
    expected_tables.remove("research_tasks")
    revision = "0291ce4556fe"

try:
    with engine.connect() as connection:
        identity = connection.execute(text("""
            SELECT current_database(), current_user,
                   (
                       SELECT pg_get_userbyid(nspowner)
                       FROM pg_namespace
                       WHERE nspname = 'app'
                   )
        """)).one()

        assert identity == (
            "agentops_migration_test",
            "agentops_migrator",
            "agentops_migrator",
        ), "Unauthorized database target"

        tables = set(connection.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'app'
              AND tablename <> 'alembic_version'
        """)).scalars())

        version_rows = connection.execute(text("""
            SELECT to_regclass('app.alembic_version')
        """)).scalar_one()

        current_revision = None
        if version_rows is not None:
            current_revision = connection.execute(text("""
                SELECT version_num
                FROM app.alembic_version
            """)).scalar_one_or_none()

        if phase == "empty":
            assert tables == set(), tables
            assert current_revision is None

        elif phase in {"upgraded", "queue", "research", "identity"}:
            assert tables == expected_tables, tables
            assert current_revision == revision

            constraints = connection.execute(text("""
                SELECT count(*)
                FROM pg_constraint
                WHERE connamespace = 'app'::regnamespace
            """)).scalar_one()

            assert constraints >= 19, constraints

            # Runtime role must have DML, but no DDL or Alembic access.
            for table_name in expected_tables:
                for privilege in (
                    "SELECT", "INSERT", "UPDATE", "DELETE"
                ):
                    permitted = connection.execute(
                        text("""
                            SELECT has_table_privilege(
                                'agentops_app',
                                :table_name,
                                :privilege
                            )
                        """),
                        {
                            "table_name": f"app.{table_name}",
                            "privilege": privilege,
                        },
                    ).scalar_one()

                    expected = (
                        privilege in {"SELECT", "INSERT"}
                        if table_name == "research_evidence"
                        else (
                            table_name != "queue_control"
                            or privilege in {"SELECT", "UPDATE"}
                        )
                    )
                    assert permitted == expected, (
                        f"Unexpected {privilege} permission "
                        f"on app.{table_name}"
                    )

            if "research_evidence" in expected_tables:
                owner = connection.scalar(text(
                    "SELECT tableowner FROM pg_tables "
                    "WHERE schemaname = 'app' "
                    "AND tablename = 'research_evidence'"
                ))

                assert owner == "agentops_migrator"

                for privilege in (
                    "TRUNCATE", "REFERENCES", "TRIGGER"
                ):
                    allowed = connection.scalar(
                        text(
                            "SELECT has_table_privilege("
                            "'agentops_app', "
                            "'app.research_evidence', "
                            ":privilege)"
                        ),
                        {"privilege": privilege},
                    )

                    assert not allowed

                print("PASS: S06 evidence ownership and grants")

            if "queue_control" in expected_tables:
                rows = connection.execute(text(
                    "SELECT id FROM app.queue_control"
                )).scalars().all()
                assert rows == [1], rows

                assert connection.scalar(text(
                    "SELECT id FROM app.queue_control "
                    "WHERE id = 1 FOR UPDATE"
                )) == 1

                print("PASS: queue singleton, grants and migrator lock")


            # No runtime schema creation.
            can_create = connection.execute(
                text("""
                    SELECT has_schema_privilege(
                        'agentops_app', 'app', 'CREATE'
                    )
                """)
            ).scalar_one()

            assert not can_create, (
                "Runtime role unexpectedly has CREATE"
            )


            for privilege in (
                "SELECT", "INSERT", "UPDATE", "DELETE"
            ):
                permitted = connection.execute(
                    text("""
                        SELECT has_table_privilege(
                            'agentops_app',
                            'app.alembic_version',
                            :privilege
                        )
                    """),
                    {"privilege": privilege},
                ).scalar_one()

                assert not permitted, (
                    "Runtime role has Alembic "
                    f"{privilege} privilege"
                )

        else:
            raise AssertionError("Unknown lifecycle phase")

        print(f"PASS: {phase} database state")
finally:
    engine.dispose()
PY
}

echo "=== 1. Verify empty database ==="
check_state empty

echo "=== 2. Upgrade to head ==="
python -m alembic -c alembic.ini upgrade 0291ce4556fe
check_state identity
python - <<'PY'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["AGENTOPS_MIGRATION_DATABASE_URL"], hide_parameters=True)
try:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO app.users (id) VALUES ('00000000-0000-0000-0000-000000000303')"))
finally:
    engine.dispose()
PY
python -m alembic -c alembic.ini upgrade head
check_state upgraded
python -m alembic -c alembic.ini check

echo "=== S06 Evidence-only migration lifecycle ==="

python -m alembic -c alembic.ini downgrade 94e4c1a20902
check_state queue

python -m alembic -c alembic.ini upgrade head
check_state upgraded
python -m alembic -c alembic.ini check

echo "PASS: S06 evidence-only downgrade and upgrade"

echo "=== 2a. Queue-only downgrade preserves WP01 schema ==="
python -m alembic -c alembic.ini downgrade 94e4c1a20902
check_state queue
python -m alembic -c alembic.ini downgrade 83d3b0f10901
check_state research
python -m alembic -c alembic.ini upgrade head
check_state upgraded
python -m alembic -c alembic.ini check

echo "=== 2b. Research-only downgrade preserves S02 identity data ==="
python -m alembic -c alembic.ini downgrade 0291ce4556fe
check_state identity
python - <<'PY'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["AGENTOPS_MIGRATION_DATABASE_URL"], hide_parameters=True)
try:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM app.users WHERE id = '00000000-0000-0000-0000-000000000303'")) == 1
        print("PASS: S02 identity row survives additive upgrade/downgrade")
finally:
    engine.dispose()
PY
python -m alembic -c alembic.ini upgrade head
check_state upgraded

echo "=== 3. Downgrade to base ==="
python -m alembic -c alembic.ini downgrade base
check_state empty

echo "=== 4. Upgrade again ==="
python -m alembic -c alembic.ini upgrade head
check_state upgraded

echo "PASS: Alembic migration lifecycle"
echo "=== 5. PostgreSQL Integration Tests ==="

export AGENTOPS_RUN_DB_INTEGRATION=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

python -m pytest -p no:cacheprovider -q --tb=short \
    tests/test_auth_postgres.py \
    tests/test_identity_db_integration.py \
    tests/test_identity_unique_postgres.py \
    tests/test_oidc_state_postgres.py \
    tests/test_auth_disable_concurrency.py \
    tests/test_research_postgres.py \
    tests/test_research_api_postgres.py \
    tests/test_research_runtime_postgres.py

echo "PASS: PostgreSQL integration tests"

echo "=== S06 Evidence PostgreSQL Integration ==="

python -m pytest -p no:cacheprovider -q --tb=short tests/test_s06_evidence_postgres.py

echo "PASS: S06 evidence PostgreSQL integration tests"

echo "=== S06 Workflow PostgreSQL Integration ==="

export LANGSMITH_TRACING=false
export LANGSMITH_TRACING_V2=false
export LANGCHAIN_TRACING=false
export LANGCHAIN_TRACING_V2=false

python -m pytest -p no:cacheprovider -q --tb=short tests/test_s06_workflow_postgres.py

echo "PASS: S06 workflow PostgreSQL integration tests"
