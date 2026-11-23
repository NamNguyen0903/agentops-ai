
"""AG-003.3B — PostgreSQL concurrency verification.

Uses two independent psql connections through Docker.
Only the disposable migration-test database is permitted.
All test writes are rolled back.
"""

import os
import secrets
import subprocess
import time
import uuid

import pytest


DATABASE = "agentops_migration_test"
ROLE = "agentops_migrator"

PSQL = [
    "docker", "compose",
    "--env-file", "../../.env.postgres",
    "exec", "-T", "db",
    "psql", "-X",
    "-v", "ON_ERROR_STOP=1",
    "-U", ROLE,
    "-d", DATABASE,
]


def run_sql(sql, timeout=15):
    return subprocess.run(
        [*PSQL, "-At", "-c", sql],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def validate_target():
    result = run_sql("""
        SELECT current_database() || '|' || current_user
        || '|' ||
        COALESCE((
            SELECT pg_get_userbyid(nspowner)
            FROM pg_namespace
            WHERE nspname = 'app'
        ), '');
    """)

    assert result.stdout.strip() == (
        "agentops_migration_test"
        "|agentops_migrator"
        "|agentops_migrator"
    )


@pytest.mark.skipif(
    os.getenv("AGENTOPS_RUN_LEGACY_COMPOSE_TESTS") != "1",
    reason="Legacy shared Compose test requires separate explicit opt-in",
)
@pytest.mark.integration
def test_concurrent_unique_insert_and_rollback():
    validate_target()

    test_id = str(uuid.uuid4())
    lock_key = secrets.randbelow(1_000_000_000) + 1

    # Connection A inserts a record and holds its transaction.
    sql_a = f"""
        BEGIN;
        INSERT INTO app.users (id)
        VALUES ('{test_id}'::uuid);

        SELECT pg_advisory_xact_lock({lock_key});
        SELECT pg_sleep(8);
        ROLLBACK;
    """

    # Connection B attempts the same primary key.
    # PostgreSQL should block, then raise a lock timeout.
    sql_b = f"""
        BEGIN;
        SET LOCAL lock_timeout = '1500ms';

        DO $$
        BEGIN
            BEGIN
                INSERT INTO app.users (id)
                VALUES ('{test_id}'::uuid);
            EXCEPTION
                WHEN lock_not_available THEN
                    RAISE NOTICE
                        'PASS: concurrent insert blocked';
                    RETURN;
            END;

            RAISE EXCEPTION
                'FAIL: conflicting insert unexpectedly succeeded';
        END
        $$;

        ROLLBACK;
    """

    process_a = subprocess.Popen(
        [*PSQL, "-At", "-c", sql_a],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Wait until connection A holds the advisory lock.
        # The lock is acquired after its INSERT.
        deadline = time.monotonic() + 6

        while True:
            if process_a.poll() is not None:
                raise AssertionError(
                    "Connection A exited before the lock check"
                )

            lock_result = run_sql(f"""
                SELECT count(*)
                FROM pg_locks
                WHERE locktype = 'advisory'
                  AND classid = 0
                  AND objid = {lock_key}
                  AND objsubid = 1
                  AND granted;
            """)

            if int(lock_result.stdout.strip()) >= 1:
                break

            if time.monotonic() >= deadline:
                raise AssertionError(
                    "Connection A did not acquire its lock"
                )

            time.sleep(0.1)

        # Independent connection B must encounter contention.
        result_b = run_sql(sql_b, timeout=6)

        assert (
            "PASS: concurrent insert blocked"
            in result_b.stderr
        ), "Concurrent insert did not encounter expected lock"

        stdout_a, stderr_a = process_a.communicate(timeout=12)

        assert process_a.returncode == 0, (
            "Connection A failed"
        )

        assert "ROLLBACK" in stdout_a

        # The initial transaction was rolled back.
        result = run_sql(f"""
            SELECT count(*)
            FROM app.users
            WHERE id = '{test_id}'::uuid;
        """)

        assert result.stdout.strip() == "0"

        # A new transaction can now insert that same UUID.
        result = run_sql(f"""
            BEGIN;
            INSERT INTO app.users (id)
            VALUES ('{test_id}'::uuid);
            ROLLBACK;
        """)

        assert "ROLLBACK" in result.stdout

        # The verification insert must also leave no data.
        result = run_sql(f"""
            SELECT count(*)
            FROM app.users
            WHERE id = '{test_id}'::uuid;
        """)

        assert result.stdout.strip() == "0"

    finally:
        if process_a.poll() is None:
            process_a.terminate()
            try:
                process_a.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process_a.kill()
                process_a.communicate()
