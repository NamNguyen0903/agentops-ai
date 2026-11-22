
"""Tests for AG-003.3A SQLAlchemy infrastructure."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_api.core.config import Settings
from agentops_api.core.orm import (
    APP_SCHEMA,
    Base,
    NAMING_CONVENTION,
    OrmDatabase,
    database_url,
    get_session,
)
from agentops_api.main import create_app


def db_settings() -> Settings:
    return Settings(
        database_enabled=True,
        database_host="unused-test-host",
        database_password="test-only-password",
    )


def test_metadata_is_empty() -> None:
    assert Base.metadata.schema == APP_SCHEMA
    assert len(Base.metadata.tables) == 0


def test_primary_key_naming() -> None:
    metadata = MetaData(
        naming_convention=NAMING_CONVENTION
    )
    table = Table(
        "example",
        metadata,
        Column("id", Integer, primary_key=True),
    )

    assert table.primary_key.name == "pk_example"


def test_database_url_hides_password() -> None:
    settings = db_settings()
    settings.database_password = SecretStr(
        "test-only:@/%"
    )

    url = database_url(settings)

    assert url.password == "test-only:@/%"
    assert "test-only" not in str(url)


def test_disabled_database_creates_no_engine() -> None:
    with patch(
        "agentops_api.core.orm.create_async_engine"
    ) as create_engine:
        database = OrmDatabase(
            Settings(database_enabled=False)
        )

    assert database.engine is None
    assert database.session_factory is None
    create_engine.assert_not_called()


def test_engine_pool_configuration() -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()

    with (
        patch(
            "agentops_api.core.orm.create_async_engine",
            return_value=engine,
        ) as create_engine,
        patch(
            "agentops_api.core.orm.async_sessionmaker"
        ) as sessionmaker,
    ):
        database = OrmDatabase(db_settings())

    options = create_engine.call_args.kwargs

    assert options["pool_size"] == 2
    assert options["max_overflow"] == 0
    assert options["pool_timeout"] == 2
    assert options["hide_parameters"] is True
    assert sessionmaker.call_args.kwargs["autobegin"] is False

    asyncio.run(database.dispose())
    engine.dispose.assert_awaited_once()


def test_lifespan_disposes_engine() -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()

    with (
        patch(
            "agentops_api.core.orm.create_async_engine",
            return_value=engine,
        ),
        patch(
            "agentops_api.core.orm.async_sessionmaker"
        ),
    ):
        app = create_app(db_settings())

        with TestClient(app) as client:
            assert (
                client.get("/api/v1/health").status_code
                == 200
            )
            engine.dispose.assert_not_awaited()

        engine.dispose.assert_awaited_once()


def test_disabled_session_returns_503() -> None:
    app = create_app(
        Settings(database_enabled=False)
    )

    @app.get("/test-session")
    async def route(
        session: AsyncSession = Depends(get_session),
    ):
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/test-session")

    assert response.status_code == 503
    assert (
        response.json()["detail"]["code"]
        == "database_unavailable"
    )


def test_session_cleanup_without_commit() -> None:
    session = AsyncMock(spec=AsyncSession)

    manager = AsyncMock()
    manager.__aenter__.return_value = session
    manager.__aexit__.return_value = False

    database = MagicMock()
    database.session_factory = MagicMock(
        return_value=manager
    )
    database.dispose = AsyncMock()

    with patch(
        "agentops_api.main.OrmDatabase",
        return_value=database,
    ):
        app = create_app(
            Settings(database_enabled=False)
        )

        @app.get("/test-session")
        async def route(
            supplied: AsyncSession = Depends(get_session),
        ):
            assert supplied is session
            return {"ok": True}

        with TestClient(app) as client:
            response = client.get("/test-session")

    assert response.status_code == 200
    manager.__aexit__.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_dependency_override() -> None:
    app = create_app(
        Settings(database_enabled=False)
    )
    sentinel = object()

    async def override():
        yield sentinel

    app.dependency_overrides[get_session] = override

    @app.get("/test-override")
    async def route(session=Depends(get_session)):
        return {"overridden": session is sentinel}

    with TestClient(app) as client:
        response = client.get("/test-override")

    assert response.json() == {
        "overridden": True
    }
