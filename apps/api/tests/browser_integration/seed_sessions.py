"""Seed synthetic sessions in the isolated browser database only."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text

from agentops_api.services.auth import digest


URL = (
    "postgresql+psycopg://"
    "agentops_migrator:isolated-test-only-migrator"
    "@127.0.0.1:18765/agentops_migration_test"
)

engine = create_engine(URL, hide_parameters=True)

owners = [uuid4(), uuid4()]
tokens = [str(uuid4()), str(uuid4())]
now = datetime.now(timezone.utc)

try:
    with engine.begin() as connection:
        identity = connection.execute(text(
            "SELECT current_database(), current_user"
        )).one()

        assert identity == (
            "agentops_migration_test",
            "agentops_migrator",
        )

        revision = connection.scalar(text(
            "SELECT version_num FROM app.alembic_version"
        ))

        assert revision == "94e4c1a20902"

        assert connection.scalar(text(
            "SELECT count(*) FROM app.research_tasks"
        )) == 0

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

    data = {
        "owner_a": str(owners[0]),
        "owner_b": str(owners[1]),
        "token_a": tokens[0],
        "token_b": tokens[1],
    }

    path = Path("/tmp/agentops-s03-browser-sessions.json")

    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    with os.fdopen(fd, "w") as output:
        json.dump(data, output)

    print("SYNTHETIC_OWNER_A_CREATED")
    print("SYNTHETIC_OWNER_B_CREATED")
    print("SYNTHETIC_SESSIONS_COMMITTED")
    print("WP04_BROWSER_SESSIONS_READY")

finally:
    engine.dispose()
