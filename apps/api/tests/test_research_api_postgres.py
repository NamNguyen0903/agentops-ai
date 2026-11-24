"""Research HTTP tests on the guarded disposable PostgreSQL target."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from agentops_api.api.routes.research import make_research_router
from agentops_api.core.config import Settings
from agentops_api.models.identity import AuthSession
from agentops_api.models.research import ResearchTask
from agentops_api.services.auth import AuthService, digest

from test_research_postgres import database


pytestmark = pytest.mark.integration

URL = "/api/v1/research/tasks"
ORIGIN = "http://localhost"
COOKIE = "agentops_dev_session"
QUESTION = "Compare synthetic competitors"


async def create_client(sessions, owners, capacity=50):
    tokens = {}
    now = datetime.now(timezone.utc)

    async with sessions() as session, session.begin():
        for owner in owners:
            token = str(uuid4())
            csrf = str(uuid4())
            tokens[owner] = (token, csrf)

            session.add(AuthSession(
                user_id=owner,
                token_digest=digest(token),
                csrf_token_digest=digest(csrf),
                created_at=now,
                last_seen_at=now,
                idle_expires_at=now + timedelta(minutes=30),
                absolute_expires_at=now + timedelta(hours=12),
            ))

    settings = Settings(
        auth_review_enabled=True,
        research_queue_capacity=capacity,
    )

    auth_settings = SimpleNamespace(
        origin=ORIGIN,
        session_cookie=COOKIE,
    )

    app = FastAPI()
    app.state.auth_service = AuthService(sessions, None)
    app.state.orm_database = SimpleNamespace(
        session_factory=sessions,
    )

    app.include_router(
        make_research_router(settings, auth_settings),
        prefix="/api/v1",
    )

    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=ORIGIN,
    )

    return client, app, tokens


def headers(tokens, owner, key="test-key"):
    token, csrf = tokens[owner]
    return {
        "Cookie": f"{COOKIE}={token}",
        "Origin": ORIGIN,
        "X-CSRF-Token": csrf,
        "Idempotency-Key": key,
    }


async def count_tasks(sessions, owners):
    async with sessions() as session, session.begin():
        return await session.scalar(
            select(func.count())
            .select_from(ResearchTask)
            .where(ResearchTask.owner_id.in_(owners))
        )


def test_submission_replay_conflict_and_committed_visibility():
    async def scenario():
        async with database() as (sessions, owners):
            owner, other = owners
            client, app, tokens = await create_client(sessions, owners)

            async with client:
                response = await client.post(
                    URL,
                    headers=headers(tokens, owner),
                    json={"question": QUESTION},
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["task_id"]

                # Independent transaction sees the committed task.
                assert await count_tasks(sessions, owners) == 1

                replay = await client.post(
                    URL,
                    headers=headers(tokens, owner),
                    json={"question": QUESTION},
                )
                assert replay.status_code == 202
                assert replay.json()["task_id"] == task_id

                conflict = await client.post(
                    URL,
                    headers=headers(tokens, owner),
                    json={"question": "Different question"},
                )
                assert conflict.status_code == 409
                assert await count_tasks(sessions, owners) == 1

                owned = await client.get(
                    f"{URL}/{task_id}",
                    headers=headers(tokens, owner),
                )
                foreign = await client.get(
                    f"{URL}/{task_id}",
                    headers=headers(tokens, other),
                )
                missing = await client.get(
                    f"{URL}/{uuid4()}",
                    headers=headers(tokens, other),
                )

                assert owned.status_code == 200
                assert foreign.status_code == missing.status_code == 404
                assert foreign.json()["code"] == missing.json()["code"]

                foreign_history = await client.get(
                    URL, headers=headers(tokens, other),
                )
                assert foreign_history.json()["items"] == []

    asyncio.run(scenario())


def test_concurrent_submissions_enforce_capacity_and_replay():
    async def scenario():
        async with database() as (sessions, owners):
            owner, other = owners
            client, app, tokens = await create_client(
                sessions, owners, capacity=1,
            )

            async with client:
                async def submit(user):
                    return await client.post(
                        URL,
                        headers=headers(tokens, user),
                        json={"question": QUESTION},
                    )

                first, second = await asyncio.gather(
                    submit(owner), submit(other),
                )

                assert sorted([
                    first.status_code, second.status_code,
                ]) == [202, 429]

                winner = owner if first.status_code == 202 else other
                accepted = first if first.status_code == 202 else second

                replay = await submit(winner)

                assert replay.status_code == 202
                assert replay.json()["task_id"] == accepted.json()["task_id"]
                assert await count_tasks(sessions, owners) == 1

    asyncio.run(scenario())


def test_concurrent_identical_http_requests_create_one_row():
    async def scenario():
        async with database() as (sessions, owners):
            client, app, tokens = await create_client(sessions, owners)

            async with client:
                async def submit():
                    return await client.post(
                        URL,
                        headers=headers(tokens, owners[0]),
                        json={"question": QUESTION},
                    )

                responses = await asyncio.gather(
                    submit(), submit(), submit(),
                )

                assert all(r.status_code == 202 for r in responses)
                assert len({
                    r.json()["task_id"] for r in responses
                }) == 1

                assert await count_tasks(sessions, owners) == 1

    asyncio.run(scenario())


def test_session_origin_csrf_and_input_fail_closed():
    async def scenario():
        async with database() as (sessions, owners):
            owner = owners[0]
            client, app, tokens = await create_client(sessions, owners)

            async with client:
                valid = headers(tokens, owner)

                scenarios = [
                    (
                        {k: v for k, v in valid.items() if k != "Cookie"},
                        401,
                    ),
                    ({**valid, "Origin": "https://invalid.example"}, 403),
                    ({**valid, "X-CSRF-Token": "wrong"}, 403),
                    (
                        {k: v for k, v in valid.items()
                         if k != "X-CSRF-Token"},
                        403,
                    ),
                ]

                for request_headers, expected in scenarios:
                    result = await client.post(
                        URL,
                        headers=request_headers,
                        json={"question": QUESTION},
                    )
                    assert result.status_code == expected

                invalid = await client.post(
                    URL,
                    headers=valid,
                    json={"question": "   "},
                )
                assert invalid.status_code == 422

                forged_owner = await client.post(
                    URL,
                    headers=valid,
                    json={
                        "question": QUESTION,
                        "owner_id": str(owners[1]),
                    },
                )
                assert forged_owner.status_code == 422

                assert await count_tasks(sessions, owners) == 0

    asyncio.run(scenario())


def test_commit_failure_is_not_acknowledged():
    async def scenario():
        async with database() as (sessions, owners):
            client, app, tokens = await create_client(sessions, owners)

            class FailingCommitSession(Session):
                pass

            @event.listens_for(FailingCommitSession, "before_commit")
            def reject_commit(session):
                raise SQLAlchemyError("synthetic private database error")

            failing_factory = async_sessionmaker(
                bind=sessions.kw["bind"],
                sync_session_class=FailingCommitSession,
                expire_on_commit=False,
                autoflush=False,
                autobegin=False,
            )

            app.state.orm_database.session_factory = failing_factory

            async with client:
                response = await client.post(
                    URL,
                    headers=headers(tokens, owners[0]),
                    json={"question": QUESTION},
                )

                assert response.status_code == 503
                assert "synthetic private" not in response.text
                assert await count_tasks(sessions, owners) == 0

    asyncio.run(scenario())


def test_http_history_pagination_and_deleted_task_isolation():
    from sqlalchemy import update

    async def scenario():
        async with database() as (sessions, owners):
            owner, other = owners
            client, app, tokens = await create_client(sessions, owners)

            async with client:
                created = []

                for key in ("a", "b", "c"):
                    response = await client.post(
                        URL,
                        headers=headers(tokens, owner, key),
                        json={"question": QUESTION},
                    )
                    assert response.status_code == 202
                    created.append(response.json()["task_id"])

                foreign = await client.post(
                    URL,
                    headers=headers(tokens, other, "foreign"),
                    json={"question": QUESTION},
                )
                assert foreign.status_code == 202

                first = await client.get(
                    URL,
                    headers=headers(tokens, owner),
                    params={"limit": 2},
                )
                assert first.status_code == 200
                first_page = first.json()
                assert len(first_page["items"]) == 2
                assert first_page["next_cursor"]

                second = await client.get(
                    URL,
                    headers=headers(tokens, owner),
                    params={
                        "limit": 2,
                        "cursor": first_page["next_cursor"],
                    },
                )
                assert second.status_code == 200
                second_page = second.json()

                assert len(second_page["items"]) == 1
                assert second_page["next_cursor"] is None

                ids = {
                    item["id"]
                    for item in first_page["items"] + second_page["items"]
                }
                assert ids == set(created)

                from uuid import UUID

                deleted_id = UUID(created[0])

                async with sessions() as session, session.begin():
                    await session.execute(
                        update(ResearchTask)
                        .where(ResearchTask.id == deleted_id)
                        .values(deleted_at=func.clock_timestamp())
                    )

                detail_response = await client.get(
                    f"{URL}/{deleted_id}",
                    headers=headers(tokens, owner),
                )
                assert detail_response.status_code == 404

                history_response = await client.get(
                    URL, headers=headers(tokens, owner),
                )
                assert history_response.status_code == 200
                assert len(history_response.json()["items"]) == 2

                replay = await client.post(
                    URL,
                    headers=headers(tokens, owner, "a"),
                    json={"question": QUESTION},
                )
                assert replay.status_code == 409

    asyncio.run(scenario())


@pytest.mark.parametrize("condition", [
    "expired", "revoked", "disabled",
])
def test_invalid_session_cannot_access_research(condition):
    from sqlalchemy import update

    async def scenario():
        async with database() as (sessions, owners):
            owner = owners[0]
            client, app, tokens = await create_client(sessions, owners)

            async with sessions() as session, session.begin():
                if condition == "expired":
                    await session.execute(
                        update(AuthSession)
                        .where(AuthSession.user_id == owner)
                        .values(
                            idle_expires_at=datetime.now(timezone.utc)
                            - timedelta(minutes=1)
                        )
                    )
                elif condition == "revoked":
                    await session.execute(
                        update(AuthSession)
                        .where(AuthSession.user_id == owner)
                        .values(revoked_at=func.clock_timestamp())
                    )

            if condition == "disabled":
                await app.state.auth_service.disable_user_and_revoke_sessions(
                    owner
                )

            async with client:
                result = await client.get(
                    URL, headers=headers(tokens, owner),
                )
                assert result.status_code == 401

                result = await client.post(
                    URL,
                    headers=headers(tokens, owner),
                    json={"question": QUESTION},
                )
                assert result.status_code == 401
                assert await count_tasks(sessions, owners) == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("payload,key", [
    ({"question": "x" * 4001}, "valid"),
    ({"question": "   "}, "valid"),
    ({"question": "Valid", "scope": {"unknown": "value"}}, "valid"),
    ({"question": "Valid", "scope": {"category": "x" * 2001}}, "valid"),
    ({"question": "Valid"}, "x" * 129),
])
def test_invalid_submission_creates_no_task(payload, key):
    async def scenario():
        async with database() as (sessions, owners):
            owner = owners[0]
            client, app, tokens = await create_client(sessions, owners)

            async with client:
                result = await client.post(
                    URL,
                    headers=headers(tokens, owner, key),
                    json=payload,
                )

                assert result.status_code == 422
                assert await count_tasks(sessions, owners) == 0

    asyncio.run(scenario())
