
"""Opt-in real PostgreSQL sessions, no provider calls or development DB writes."""

import asyncio
import base64
import os
import secrets
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentops_api.core.auth_config import AuthSettings
from agentops_api.core.config import Settings
from agentops_api.main import create_app
from agentops_api.models.identity import (
    AuthIdentity,
    AuthSession,
    OIDCLoginTransaction,
    User,
)
from agentops_api.services.auth import AuthService, ContextCipher, digest


def test_postgres_session_contract():
    if os.getenv("AGENTOPS_RUN_DB_INTEGRATION") != "1":
        pytest.skip("Explicit disposable PostgreSQL opt-in required")

    url = make_url(os.environ["AGENTOPS_MIGRATION_DATABASE_URL"])

    assert url.database == "agentops_migration_test"
    assert url.username == "agentops_migrator"

    async def scenario():
        engine = create_async_engine(url, hide_parameters=True)
        factory = async_sessionmaker(
            engine,
            autobegin=False,
            expire_on_commit=False,
        )

        service = AuthService(
            factory,
            ContextCipher(
                base64.b64encode(secrets.token_bytes(32)).decode()
            ),
        )

        subject = secrets.token_hex(16)

        user_id = None
        other_user_id = None
        state = None

        try:
            # --------------------------------------------------
            # Create the primary test user
            # --------------------------------------------------
            async with factory() as session, session.begin():
                user = User()
                session.add(user)
                await session.flush()

                user_id = user.id

                session.add(
                    AuthIdentity(
                        user_id=user_id,
                        issuer="https://accounts.google.com",
                        subject=subject,
                    )
                )

            # --------------------------------------------------
            # Real API -> AuthService -> PostgreSQL
            # Offline identity provider, no external requests
            # --------------------------------------------------
            config = AuthSettings(
                client_id="offline",
                client_secret="synthetic",
                context_key=base64.b64encode(
                    secrets.token_bytes(32)
                ).decode(),
                origin="https://app.example.test",
            )

            state = secrets.token_urlsafe(32)

            provider = SimpleNamespace(
                authorize=AsyncMock(
                    return_value={
                        "state": state,
                        "nonce": "offline",
                        "code_verifier": "offline",
                        "url": (
                            "https://accounts.google.com"
                            "/o/oauth2/v2/auth"
                        ),
                    }
                ),
                exchange=AsyncMock(
                    return_value=(
                        "https://accounts.google.com",
                        subject,
                    )
                ),
            )

            app = create_app(
                Settings(
                    auth_review_enabled=True,
                    database_enabled=True,
                    database_password="unused",
                ),
                auth_settings=config,
                auth_provider=provider,
            )

            app.state.auth_service = service

            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url=config.origin,
            ) as browser:

                assert (
                    await browser.get("/api/v1/auth/me")
                ).status_code == 401

                assert (
                    await browser.get("/api/v1/auth/login/google")
                ).status_code == 302

                callback = (
                    "/api/v1/auth/callback/google"
                    f"?state={state}&code=offline"
                )

                async def exchange_after_commit(*args):
                    async with factory() as observer, observer.begin():
                        consumed = await observer.scalar(
                            select(OIDCLoginTransaction)
                            .where(
                                OIDCLoginTransaction.state_digest
                                == digest(state)
                            )
                            .with_for_update(nowait=True)
                        )

                        assert consumed is not None
                        assert consumed.consumed_at is not None
                        assert consumed.encrypted_context == b""

                    return "https://accounts.google.com", subject

                provider.exchange.side_effect = exchange_after_commit

                outcomes = await asyncio.gather(
                    browser.get(callback),
                    browser.get(callback),
                )

                assert sorted(
                    response.status_code for response in outcomes
                ) == [303, 400]

                assert provider.exchange.await_count == 1

                assert (
                    await browser.get(callback)
                ).status_code == 400

                assert provider.exchange.await_count == 1

                assert (
                    await browser.get("/api/v1/auth/me")
                ).json()["id"] == str(user_id)

                proof = (
                    await browser.get("/api/v1/auth/csrf")
                ).json()["csrf_token"]

                assert (
                    await browser.post(
                        "/api/v1/auth/logout",
                        headers={
                            "origin": config.origin,
                            "x-csrf-token": proof,
                        },
                    )
                ).status_code == 204

                assert (
                    await browser.get("/api/v1/auth/me")
                ).status_code == 401

            # ==================================================
            # SEC-10: Cross-user session isolation
            # ==================================================

            other_subject = secrets.token_hex(16)

            async with factory() as session, session.begin():
                other_user = User()
                session.add(other_user)

                await session.flush()
                other_user_id = other_user.id

                session.add(
                    AuthIdentity(
                        user_id=other_user_id,
                        issuer="https://accounts.google.com",
                        subject=other_subject,
                    )
                )

            # User A creates an active session.
            session_a = await service.login(
                "https://accounts.google.com",
                subject,
                None,
            )

            assert session_a is not None

            # User B logs in with A's existing session token.
            session_b = await service.login(
                "https://accounts.google.com",
                other_subject,
                session_a,
            )

            assert session_b is not None
            assert session_b != session_a

            # Switching accounts must not revoke A's session.
            assert (
                await service.principal(session_a)
            )["id"] == str(user_id)

            assert (
                await service.principal(session_b)
            )["id"] == str(other_user_id)

            # Same-account rotation must revoke B's old session.
            rotated_b = await service.login(
                "https://accounts.google.com",
                other_subject,
                session_b,
            )

            assert rotated_b is not None
            assert rotated_b != session_b

            assert await service.principal(session_b) is None

            assert (
                await service.principal(rotated_b)
            )["id"] == str(other_user_id)

            # A's session must still be valid.
            assert (
                await service.principal(session_a)
            )["id"] == str(user_id)

            # ==================================================
            # Existing authentication/session contract tests
            # ==================================================

            assert (
                await service.login(
                    "https://accounts.google.com",
                    "unprovisioned",
                    None,
                )
            ) is None

            token = await service.login(
                "https://accounts.google.com",
                subject,
                None,
            )

            assert (
                await service.principal(token)
            )["id"] == str(user_id)

            async with factory() as session, session.begin():
                record = await session.scalar(
                    select(AuthSession).where(
                        AuthSession.token_digest == digest(token)
                    )
                )

                assert record is not None
                assert record.token_digest != token.encode()

                assert (
                    record.absolute_expires_at - record.created_at
                ) == timedelta(hours=12)

                assert (
                    record.idle_expires_at
                    <= record.absolute_expires_at
                )

            # ==================================================
            # SEC-05: CSRF rotation
            # ==================================================

            csrf_old = (
                await service.principal(token, new_csrf=True)
            )["csrf_token"]

            csrf_new = (
                await service.principal(token, new_csrf=True)
            )["csrf_token"]

            assert csrf_old != csrf_new

            with pytest.raises(
                ValueError,
                match="Invalid CSRF proof",
            ):
                await service.principal(
                    token,
                    logout=True,
                    csrf=csrf_old,
                )

            # Invalid CSRF must not revoke the session.
            assert (
                await service.principal(token)
            )["id"] == str(user_id)

            with pytest.raises(ValueError):
                await service.principal(
                    token,
                    logout=True,
                    csrf="wrong",
                )

            # ==================================================
            # Same-user session rotation
            # ==================================================

            rotated = await service.login(
                "https://accounts.google.com",
                subject,
                token,
            )

            assert rotated is not None
            assert rotated != token

            assert await service.principal(token) is None

            csrf = (
                await service.principal(
                    rotated,
                    new_csrf=True,
                )
            )["csrf_token"]

            # Concurrent refresh cannot resurrect a session
            # after logout commits.
            await asyncio.gather(
                service.principal(rotated),
                service.principal(
                    rotated,
                    logout=True,
                    csrf=csrf,
                ),
            )

            assert await service.principal(rotated) is None

            # ==================================================
            # SEC-03: Account-wide session revocation
            # ==================================================

            old_session_1 = await service.login(
                "https://accounts.google.com",
                subject,
                None,
            )

            old_session_2 = await service.login(
                "https://accounts.google.com",
                subject,
                None,
            )

            assert old_session_1 is not None
            assert old_session_2 is not None
            assert old_session_1 != old_session_2

            assert (
                await service.disable_user_and_revoke_sessions(
                    user_id
                )
            ) is True

            async with factory() as session, session.begin():
                user = await session.get(User, user_id)

                assert user is not None
                assert user.is_active is False

                for token_value in (
                    old_session_1,
                    old_session_2,
                ):
                    record = await session.scalar(
                        select(AuthSession).where(
                            AuthSession.token_digest
                            == digest(token_value)
                        )
                    )

                    assert record is not None
                    assert record.revoked_at is not None

            assert await service.principal(old_session_1) is None
            assert await service.principal(old_session_2) is None

            # Reactivation must not resurrect revoked sessions.
            async with factory() as session, session.begin():
                user = await session.get(User, user_id)
                user.is_active = True

            assert await service.principal(old_session_1) is None
            assert await service.principal(old_session_2) is None

            new_session = await service.login(
                "https://accounts.google.com",
                subject,
                None,
            )

            assert new_session is not None

            assert (
                await service.principal(new_session)
            )["id"] == str(user_id)

            # ==================================================
            # Session expiration and inactive accounts
            # ==================================================

            for condition in ("idle", "absolute", "inactive"):
                token = await service.login(
                    "https://accounts.google.com",
                    subject,
                    None,
                )

                async with factory() as session, session.begin():
                    if condition == "inactive":
                        user = await session.get(User, user_id)
                        user.is_active = False
                    else:
                        row = await session.scalar(
                            select(AuthSession).where(
                                AuthSession.token_digest
                                == digest(token)
                            )
                        )

                        now = await session.scalar(
                            select(func.clock_timestamp())
                        )

                        row.created_at = now - timedelta(days=2)
                        row.idle_expires_at = (
                            now - timedelta(seconds=1)
                        )

                        if condition == "absolute":
                            row.absolute_expires_at = (
                                now - timedelta(seconds=1)
                            )

                assert await service.principal(token) is None

            assert (
                await service.login(
                    "https://accounts.google.com",
                    subject,
                    None,
                )
            ) is None

        finally:
            # --------------------------------------------------
            # Clean up disposable test data
            # --------------------------------------------------
            try:
                async with factory() as session, session.begin():
                    if other_user_id is not None:
                        await session.execute(
                            delete(User).where(
                                User.id == other_user_id
                            )
                        )

                    if user_id is not None:
                        await session.execute(
                            delete(User).where(
                                User.id == user_id
                            )
                        )

                    if state is not None:
                        await session.execute(
                            delete(OIDCLoginTransaction).where(
                                OIDCLoginTransaction.state_digest
                                == digest(state)
                            )
                        )
            finally:
                await engine.dispose()

    asyncio.run(scenario())
