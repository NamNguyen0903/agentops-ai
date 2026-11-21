
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agentops_api.api.routes.readiness import get_database_probe
from agentops_api.core.config import Settings
from agentops_api.core.database import DatabaseProbe
from agentops_api.main import create_app


@pytest.fixture(autouse=True)
def clear_database_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in list(os.environ):
        if name.startswith("AGENTOPS_DATABASE_"):
            monkeypatch.delenv(name)


def enabled_settings() -> Settings:
    return Settings(
        database_enabled=True,
        database_password="test-only-secret-not-real",
    )


def mock_connection(
    *,
    row: tuple[int] = (1,),
    query_error: Exception | None = None,
):
    conn = AsyncMock()
    conn.__aenter__.return_value = conn

    cursor = AsyncMock()
    cursor.__aenter__.return_value = cursor
    cursor.fetchone.return_value = row
    cursor.execute.side_effect = query_error

    conn.cursor = MagicMock(return_value=cursor)
    return conn, cursor


def test_database_disabled_by_default() -> None:
    assert Settings().database_enabled is False


def test_enabled_database_requires_password() -> None:
    with pytest.raises(ValidationError):
        Settings(database_enabled=True)


def test_invalid_database_port() -> None:
    with pytest.raises(ValidationError):
        Settings(database_port=70000)


def test_environment_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AGENTOPS_DATABASE_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "AGENTOPS_DATABASE_PASSWORD",
        "test-only",
    )

    settings = Settings()

    assert settings.database_enabled is True
    assert settings.database_password is not None


def test_password_not_in_settings_repr() -> None:
    assert (
        "test-only-secret-not-real"
        not in repr(enabled_settings())
    )


def test_liveness_never_connects_to_database() -> None:
    with patch(
        "agentops_api.core.database."
        "psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as connect:
        with TestClient(
            create_app(enabled_settings())
        ) as client:
            response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentops-api",
    }
    connect.assert_not_awaited()


@pytest.mark.parametrize("ready", [True, False])
def test_readiness_http_contract(ready: bool) -> None:
    application = create_app(Settings())

    probe = MagicMock(spec=DatabaseProbe)
    probe.is_ready = AsyncMock(return_value=ready)

    application.dependency_overrides[
        get_database_probe
    ] = lambda: probe

    with TestClient(application) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == (200 if ready else 503)
    assert response.headers["cache-control"] == "no-store"

    if ready:
        assert response.json() == {
            "status": "ready",
            "checks": {"database": "ok"},
        }
    else:
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["error"]["code"] == "database_not_ready"
        assert (
            data["error"]["request_id"]
            == response.headers["x-request-id"]
        )


def test_disabled_probe_skips_connection() -> None:
    with patch(
        "agentops_api.core.database."
        "psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as connect:
        result = asyncio.run(
            DatabaseProbe(Settings()).is_ready()
        )

    assert result is False
    connect.assert_not_awaited()


def test_success_closes_resources() -> None:
    conn, cursor = mock_connection()

    with patch(
        "agentops_api.core.database."
        "psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
        return_value=conn,
    ) as connect:
        result = asyncio.run(
            DatabaseProbe(enabled_settings()).is_ready()
        )

    assert result is True
    assert connect.call_args.kwargs["connect_timeout"] == 2
    assert connect.call_args.kwargs["autocommit"] is True
    cursor.execute.assert_awaited_once_with("SELECT 1")
    cursor.__aexit__.assert_awaited_once()
    conn.__aexit__.assert_awaited_once()


def test_failed_query_closes_resources() -> None:
    conn, cursor = mock_connection(
        query_error=psycopg.OperationalError(
            "sensitive driver detail"
        ),
    )

    with patch(
        "agentops_api.core.database."
        "psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
        return_value=conn,
    ):
        result = asyncio.run(
            DatabaseProbe(enabled_settings()).is_ready()
        )

    assert result is False
    cursor.__aexit__.assert_awaited_once()
    conn.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        psycopg.OperationalError("private database detail"),
        TimeoutError(),
        OSError("connection failed"),
    ],
)
def test_connection_failures_return_false(error: Exception) -> None:
    with patch(
        "agentops_api.core.database."
        "psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
        side_effect=error,
    ):
        assert (
            asyncio.run(
                DatabaseProbe(enabled_settings()).is_ready()
            )
            is False
        )


def test_connection_timeout_releases_lock() -> None:
    async def scenario() -> None:
        async def never_connect(**kwargs):
            await asyncio.Event().wait()

        probe = DatabaseProbe(enabled_settings())

        with patch(
            "agentops_api.core.database."
            "psycopg.AsyncConnection.connect",
            new_callable=AsyncMock,
            side_effect=never_connect,
        ):
            assert await probe.is_ready() is False

        conn, _ = mock_connection()

        with patch(
            "agentops_api.core.database."
            "psycopg.AsyncConnection.connect",
            new_callable=AsyncMock,
            return_value=conn,
        ):
            assert await probe.is_ready() is True

    asyncio.run(scenario())



def test_query_timeout_releases_lock() -> None:
    async def scenario() -> None:
        async def blocked_query(*args, **kwargs):
            await asyncio.Event().wait()

        conn, cursor = mock_connection()
        cursor.execute.side_effect = blocked_query

        probe = DatabaseProbe(enabled_settings())

        with patch(
            "agentops_api.core.database."
            "psycopg.AsyncConnection.connect",
            new_callable=AsyncMock,
            return_value=conn,
        ):
            assert await probe.is_ready() is False

        cursor.__aexit__.assert_awaited_once()
        conn.__aexit__.assert_awaited_once()

        next_conn, _ = mock_connection()

        with patch(
            "agentops_api.core.database."
            "psycopg.AsyncConnection.connect",
            new_callable=AsyncMock,
            return_value=next_conn,
        ):
            assert await probe.is_ready() is True

    asyncio.run(scenario())


def test_concurrent_probe_rejected() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked_connect(**kwargs):
            started.set()
            await release.wait()
            raise psycopg.OperationalError("test")

        probe = DatabaseProbe(enabled_settings())

        with patch(
            "agentops_api.core.database."
            "psycopg.AsyncConnection.connect",
            new_callable=AsyncMock,
            side_effect=blocked_connect,
        ) as connect:
            first = asyncio.create_task(probe.is_ready())

            try:
                await asyncio.wait_for(started.wait(), 1)
                assert await probe.is_ready() is False
                assert connect.await_count == 1
            finally:
                release.set()
                await first

    asyncio.run(scenario())
