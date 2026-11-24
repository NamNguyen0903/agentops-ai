
"""Regression tests for reusable authentication dependency."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agentops_api.api.dependencies.auth import require_principal


def make_test_app(service=None, cookie_name="test_session"):
    app = FastAPI()

    if service is not None:
        app.state.auth_service = service

    if cookie_name is not None:
        app.state.auth_session_cookie_name = cookie_name

    @app.get("/protected")
    async def protected(user_id: str = Depends(require_principal)):
        return {"user_id": user_id}

    return app


def test_valid_session_returns_authenticated_user():
    service = SimpleNamespace(
        principal=AsyncMock(return_value={"id": "user-123"})
    )
    app = make_test_app(service)

    with TestClient(app) as client:
        client.cookies.set("test_session", "valid-token")
        response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123"}
    service.principal.assert_awaited_once_with("valid-token")


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_missing_or_invalid_session_returns_401(token):
    service = SimpleNamespace(
        principal=AsyncMock(return_value=None)
    )
    app = make_test_app(service)

    with TestClient(app) as client:
        if token is not None:
            client.cookies.set("test_session", token)

        response = client.get("/protected")

    assert response.status_code == 401


def test_authentication_disabled_fails_closed():
    app = make_test_app()

    with TestClient(app) as client:
        response = client.get("/protected")

    assert response.status_code == 503


def test_database_failure_returns_503():
    service = SimpleNamespace(
        principal=AsyncMock(side_effect=RuntimeError("database unavailable"))
    )
    app = make_test_app(service)

    with TestClient(app) as client:
        client.cookies.set("test_session", "synthetic-token")
        response = client.get("/protected")

    assert response.status_code == 503
    assert "database unavailable" not in response.text


def test_missing_cookie_configuration_fails_closed():
    service = SimpleNamespace(
        principal=AsyncMock(return_value={"id": "user-123"})
    )
    app = make_test_app(service, cookie_name=None)

    with TestClient(app) as client:
        response = client.get("/protected")

    assert response.status_code == 503
    service.principal.assert_not_awaited()


def test_client_cannot_supply_authenticated_user_id():
    service = SimpleNamespace(principal=AsyncMock(return_value={'id':'server-owned-user'}))
    with TestClient(make_test_app(service)) as client:
        client.cookies.set('test_session','synthetic-token')
        response = client.get('/protected?user_id=attacker', headers={'X-User-ID':'attacker'})
    assert response.json() == {'user_id':'server-owned-user'}
