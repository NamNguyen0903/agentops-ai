
import pytest
from fastapi.testclient import TestClient

from agentops_api.core.config import Settings
from agentops_api.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_status_code(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_payload(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.json() == {
        "status": "ok",
        "service": "agentops-api",
    }


def test_health_is_deterministic(client: TestClient) -> None:
    responses = [
        client.get("/api/v1/health").json()
        for _ in range(3)
    ]

    assert responses == [
        {"status": "ok", "service": "agentops-api"}
    ] * 3


def test_health_registered_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
    assert "get" in response.json()["paths"]["/api/v1/health"]


def test_custom_application_name() -> None:
    settings = Settings(app_name="AgentOps Test API")
    application = create_app(settings=settings)

    assert application.title == "AgentOps Test API"
