"""Offline research API contract tests."""

from fastapi.testclient import TestClient

from agentops_api.core.config import Settings
from agentops_api.main import create_app
from agentops_api.api.routes.research import decode_cursor, encode_cursor

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


URL = "/api/v1/research/tasks"


def test_authentication_remains_disabled_by_default():
    settings = Settings()
    assert settings.auth_review_enabled is False

    with TestClient(create_app(settings)) as client:
        response = client.get(URL)

    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert response.headers["cache-control"] == "no-store"


def test_validation_does_not_echo_request_input():
    secret = "synthetic-private-research-input"

    with TestClient(create_app(Settings())) as client:
        response = client.post(
            URL,
            headers={"Idempotency-Key": "test"},
            json={"question": 123, "unexpected": secret},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert secret not in response.text


def test_cursor_round_trip():
    task = SimpleNamespace(
        created_at=datetime.now(timezone.utc),
        id=uuid4(),
    )
    assert decode_cursor(encode_cursor(task)) == (
        task.created_at, task.id,
    )


@pytest.mark.parametrize("cursor", [
    "", "invalid!", "W10=", "e30=",
])
def test_invalid_cursor_rejected(cursor):
    with pytest.raises(HTTPException) as error:
        decode_cursor(cursor)

    assert error.value.status_code == 422
