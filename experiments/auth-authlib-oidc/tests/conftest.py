import pytest
import socket


def pytest_configure(config):
    config.option.showlocals = False
    config.option.showcapture = "no"

from authlib_oidc_poc.config import OIDCConfig
from authlib_oidc_poc.fake_provider import FakeOIDCProvider


@pytest.fixture
def config():
    return OIDCConfig()


@pytest.fixture
def provider(config):
    return FakeOIDCProvider(config.issuer)


@pytest.fixture(autouse=True)
def forbid_external_connections(monkeypatch):
    """Python guardrail; not an OS sandbox. ASGI/MockTransport remain local."""
    def denied(*args, **kwargs):
        raise RuntimeError("External networking forbidden in OIDC PoC")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
