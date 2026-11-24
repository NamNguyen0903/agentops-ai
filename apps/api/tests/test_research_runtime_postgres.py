"""Full application factory tests using the isolated runtime DB role."""

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from agentops_api.core.auth_config import AuthSettings
from agentops_api.core.config import Settings
from agentops_api.main import create_app
from agentops_api.services.auth import digest

from test_identity_db_integration import get_test_database_url


pytestmark = pytest.mark.integration

ORIGIN = "http://127.0.0.1:5173"
TASKS = "/api/v1/research/tasks"
CSRF = "/api/v1/auth/csrf"

RUNTIME_PASSWORD = "isolated-test-only-runtime"


class OfflineProvider:
    """Fail closed; this suite must never invoke a real OIDC provider."""

    async def authorize(self):
        raise AssertionError("Live authorization is not permitted")

    async def exchange(self, *args, **kwargs):
        raise AssertionError("Live token exchange is not permitted")


@pytest.fixture
def runtime_environment():
    migration_url = get_test_database_url()

    assert migration_url.host == "db"
    assert migration_url.database == "agentops_migration_test"

    runtime_url = migration_url.set(
        username="agentops_app",
        password=RUNTIME_PASSWORD,
    )

    migrator = create_engine(
        migration_url,
        hide_parameters=True,
    )

    runtime = create_engine(
        runtime_url,
        hide_parameters=True,
    )

    owners = [uuid4(), uuid4()]
    tokens = [str(uuid4()), str(uuid4())]
    now = datetime.now(timezone.utc)

    try:
        with migrator.begin() as connection:
            identity = connection.execute(text(
                "SELECT current_database(), current_user"
            )).one()

            assert identity == (
                "agentops_migration_test",
                "agentops_migrator",
            )

            for owner, token in zip(owners, tokens):
                connection.execute(
                    text("INSERT INTO app.users (id) VALUES (:id)"),
                    {"id": owner},
                )

                connection.execute(
                    text("""
                        INSERT INTO app.auth_sessions (
                            id,
                            user_id,
                            token_digest,
                            csrf_token_digest,
                            created_at,
                            last_seen_at,
                            idle_expires_at,
                            absolute_expires_at
                        ) VALUES (
                            :id,
                            :owner,
                            :token,
                            :csrf,
                            :now,
                            :now,
                            :idle,
                            :absolute
                        )
                    """),
                    {
                        "id": uuid4(),
                        "owner": owner,
                        "token": digest(token),
                        "csrf": digest(str(uuid4())),
                        "now": now,
                        "idle": now + timedelta(minutes=30),
                        "absolute": now + timedelta(hours=12),
                    },
                )

        with runtime.begin() as connection:
            identity = connection.execute(text(
                "SELECT current_database(), current_user"
            )).one()

            assert identity == (
                "agentops_migration_test",
                "agentops_app",
            )

            assert connection.scalar(text(
                "SELECT id FROM app.queue_control "
                "WHERE id = 1 FOR UPDATE"
            )) == 1

        settings = Settings(
            database_enabled=True,
            database_host=runtime_url.host,
            database_port=runtime_url.port or 5432,
            database_name=runtime_url.database,
            database_user="agentops_app",
            database_password=RUNTIME_PASSWORD,
            auth_review_enabled=True,
            research_queue_capacity=50,
        )

        auth = AuthSettings(
            client_id="synthetic-offline-client",
            client_secret="synthetic-offline-secret",
            context_key=base64.b64encode(b"x" * 32).decode(),
            origin=ORIGIN,
            development_http=True,
        )

        app = create_app(
            settings,
            auth_settings=auth,
            auth_provider=OfflineProvider(),
        )

        with TestClient(app, base_url=ORIGIN) as client:
            yield client, auth, migrator, runtime, owners, tokens

    finally:
        with migrator.begin() as connection:
            for owner in owners:
                connection.execute(
                    text(
                        "DELETE FROM app.research_tasks "
                        "WHERE owner_id = :owner"
                    ),
                    {"owner": owner},
                )

                connection.execute(
                    text(
                        "DELETE FROM app.auth_sessions "
                        "WHERE user_id = :owner"
                    ),
                    {"owner": owner},
                )

                connection.execute(
                    text("DELETE FROM app.users WHERE id = :owner"),
                    {"owner": owner},
                )

        runtime.dispose()
        migrator.dispose()


def test_full_application_runtime_submission(runtime_environment):
    client, auth, migrator, _, owners, tokens = runtime_environment

    assert client.get(TASKS).status_code == 401

    client.cookies.set(auth.session_cookie, tokens[0])

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(owners[0])

    csrf_response = client.get(CSRF)
    assert csrf_response.status_code == 200
    assert csrf_response.headers["cache-control"] == "no-store"

    csrf = csrf_response.json()["csrf_token"]

    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": csrf,
        "Idempotency-Key": str(uuid4()),
    }

    payload = {
        "question": "Compare synthetic competitors",
        "scope": {
            "geography": "Europe",
            "category": None,
            "time_scope": None,
            "competitors": ["Company A", "Company B"],
        },
    }

    result = client.post(TASKS, json=payload, headers=headers)
    assert result.status_code == 202, result.text

    accepted = result.json()
    task_id = accepted["task_id"]

    assert accepted["status"] == "queued"
    assert accepted["status_url"] == f"{TASKS}/{task_id}"
    assert result.headers["cache-control"] == "no-store"

    with migrator.connect() as connection:
        persisted = connection.execute(
            text("""
                SELECT owner_id, question, status, current_stage
                FROM app.research_tasks
                WHERE id = :id
            """),
            {"id": task_id},
        ).one()

        assert persisted.owner_id == owners[0]
        assert persisted.question == payload["question"]
        assert persisted.status == "queued"
        assert persisted.current_stage is None

    replay = client.post(TASKS, json=payload, headers=headers)

    assert replay.status_code == 202
    assert replay.json()["task_id"] == task_id

    conflict = client.post(
        TASKS,
        headers=headers,
        json={"question": "Changed question"},
    )

    assert conflict.status_code == 409

    history = client.get(TASKS)
    assert history.status_code == 200

    assert [item["id"] for item in history.json()["items"]] == [task_id]

    detail = client.get(f"{TASKS}/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["scope"] == payload["scope"]

    client.cookies.clear()
    client.cookies.set(auth.session_cookie, tokens[1])

    assert client.get(TASKS).json()["items"] == []
    assert client.get(f"{TASKS}/{task_id}").status_code == 404

    with migrator.connect() as connection:
        count = connection.scalar(
            text("""
                SELECT count(*) FROM app.research_tasks
                WHERE owner_id = :owner
            """),
            {"owner": owners[0]},
        )

        assert count == 1


def test_runtime_security_boundaries(runtime_environment):
    client, auth, migrator, runtime, owners, tokens = runtime_environment

    client.cookies.set(auth.session_cookie, tokens[0])

    assert client.get(
        CSRF,
        headers={"Origin": "https://invalid.example"},
    ).status_code == 403

    csrf_response = client.get(CSRF)
    assert csrf_response.status_code == 200

    csrf = csrf_response.json()["csrf_token"]

    payload = {"question": "Synthetic security check"}

    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": csrf,
        "Idempotency-Key": str(uuid4()),
    }

    wrong_origin = client.post(
        TASKS,
        json=payload,
        headers={**headers, "Origin": "https://invalid.example"},
    )

    assert wrong_origin.status_code == 403

    wrong_csrf = client.post(
        TASKS,
        json=payload,
        headers={**headers, "X-CSRF-Token": "invalid-proof"},
    )

    assert wrong_csrf.status_code == 403

    missing_csrf = client.post(
        TASKS,
        json=payload,
        headers={
            "Origin": ORIGIN,
            "Idempotency-Key": str(uuid4()),
        },
    )

    assert missing_csrf.status_code == 403

    forged_owner = client.post(
        TASKS,
        headers=headers,
        json={**payload, "owner_id": str(owners[1])},
    )

    assert forged_owner.status_code == 422

    with migrator.connect() as connection:
        count = connection.scalar(
            text("""
                SELECT count(*) FROM app.research_tasks
                WHERE owner_id = :owner
            """),
            {"owner": owners[0]},
        )

        assert count == 0

    with runtime.connect() as connection:
        assert connection.scalar(text(
            "SELECT current_user"
        )) == "agentops_app"

        assert not connection.scalar(text(
            "SELECT has_schema_privilege(current_user, 'app', 'CREATE')"
        ))

        for privilege in ("INSERT", "DELETE"):
            assert not connection.scalar(
                text("""
                    SELECT has_table_privilege(
                        current_user, 'app.queue_control', :privilege
                    )
                """),
                {"privilege": privilege},
            )

        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert not connection.scalar(
                text("""
                    SELECT has_table_privilege(
                        current_user, 'app.alembic_version', :privilege
                    )
                """),
                {"privilege": privilege},
            )


def test_runtime_session_revocation(runtime_environment):
    client, auth, _, _, _, tokens = runtime_environment

    client.cookies.set(auth.session_cookie, tokens[0])

    csrf_response = client.get(CSRF)
    assert csrf_response.status_code == 200

    logout = client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf_response.json()["csrf_token"],
        },
    )

    assert logout.status_code == 204

    # Replay the original cookie after server-side revocation.
    client.cookies.clear()
    client.cookies.set(auth.session_cookie, tokens[0])

    assert client.get(TASKS).status_code == 401
    assert client.get(CSRF).status_code == 401
