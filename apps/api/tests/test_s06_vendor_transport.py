"""Isolated vendor and pinned-connector verification."""

import json
import socket
import ssl
from dataclasses import replace

import httpx
import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import SearchRequest
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.network_policy import (
    BoundDestination,
    validate_url,
)
from agentops_api.services.s06_acquisition import (
    tavily,
    pinned_transport as pinned,
)


def expect(code, function, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        function(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


def sample():
    return {
        "query": "public market research",
        "answer": None,
        "images": [],
        "results": [
            {
                "title": "Synthetic source",
                "url": "https://example.com/source",
                "content": "Synthetic snippet",
                "score": 0.8,
                "raw_content": None,
            }
        ],
        "usage": {"credits": 1},
        "request_id": "isolated-fixture",
    }


def call(payload, budget=None):
    return tavily.search_isolated(
        SearchRequest(query="public market research"),
        budget if budget is not None else Budget(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=payload,
            )
        ),
    )


def test_request_contract():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == tavily.ENDPOINT

        assert request.headers["authorization"] == (
            "Bearer isolated-test-token"
        )

        assert request.headers["accept-encoding"] == "identity"

        body = json.loads(request.content)

        assert body["search_depth"] == "basic"
        assert body["auto_parameters"] is False
        assert body["include_answer"] is False
        assert body["include_raw_content"] is False
        assert body["include_images"] is False
        assert body["include_usage"] is True
        assert body["max_results"] == 10

        return httpx.Response(200, json=sample())

    budget = Budget()

    result = tavily.search_isolated(
        SearchRequest(query="public market research"),
        budget,
        transport=httpx.MockTransport(handler),
    )

    assert result.synthetic is True
    assert result.credits == 1
    assert len(result.hits) == 1
    assert budget.snapshot().searches == 1


@pytest.mark.parametrize("usage", [
    None,
    {},
    {"credits": True},
    {"credits": "1"},
    {"credits": 0},
    {"credits": 2},
    {"credits": 1.0},
])
def test_unexpected_usage(usage):
    payload = sample()
    payload["usage"] = usage

    expect(
        ErrorCode.INVALID_RESPONSE,
        call,
        payload,
    )


@pytest.mark.parametrize("field,value", [
    ("title", 12),
    ("title", ""),
    ("content", ["invalid"]),
    ("content", "x" * 4097),
    ("score", True),
    ("score", -1),
    ("score", 2),
    ("raw_content", "not authorized"),
    ("images", ["not authorized"]),
])
def test_invalid_hit(field, value):
    payload = sample()
    payload["results"][0][field] = value

    expect(
        ErrorCode.INVALID_RESPONSE,
        call,
        payload,
    )


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://169.254.169.254/",
    "file:///etc/passwd",
])
def test_unsafe_vendor_url(url):
    payload = sample()
    payload["results"][0]["url"] = url

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        call,
        payload,
    )


@pytest.mark.parametrize("status", [
    301, 302, 307, 400, 401, 429, 432, 433, 500,
])
def test_status_rejected_without_retry(status):
    requests = []

    def handler(request):
        requests.append(request)

        return httpx.Response(
            status,
            headers={"Location": "https://example.org/"},
            content=b"private provider details",
        )

    budget = Budget()

    expect(
        ErrorCode.PROVIDER_FAILURE,
        tavily.search_isolated,
        SearchRequest(query="public research"),
        budget,
        transport=httpx.MockTransport(handler),
    )

    assert len(requests) == 1
    assert budget.snapshot().searches == 1


def test_live_operations_disabled(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network invocation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_live,
        SearchRequest(query="public research"),
        Budget(),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        pinned.retrieve_live,
        object(),
        Budget(),
    )


def test_non_mock_transport_denied():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_isolated,
        SearchRequest(query="public research"),
        Budget(),
        transport=object(),
    )


def test_json_duplicate_keys():
    expect(
        ErrorCode.INVALID_RESPONSE,
        tavily.decode_json,
        b'{"results":[],"results":[]}',
    )


def test_oversized_json():
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        tavily.search_isolated,
        SearchRequest(query="public research"),
        Budget(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                content=b"x" * 1048577,
            )
        ),
    )


def test_vendor_credit_budget():
    budget = Budget()

    for _ in range(6):
        call(sample(), budget)

    expect(
        ErrorCode.BUDGET_EXHAUSTED,
        call,
        sample(),
        budget,
    )


def test_tls_context_secure_defaults():
    context = pinned.tls_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


class FakeSocket:
    def __init__(self, peer):
        self.peer = peer
        self.connected = None
        self.closed = False
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, endpoint):
        self.connected = endpoint

    def getpeername(self):
        return self.peer, 443

    def close(self):
        self.closed = True


def bound():
    return BoundDestination(
        validate_url("https://example.com/"),
        "93.184.216.34",
    )


def test_numeric_ip_binding_and_tls_hostname(monkeypatch):
    fake = FakeSocket("93.184.216.34")
    observed = {}

    class Context:
        def wrap_socket(self, sock, *, server_hostname):
            observed["hostname"] = server_hostname
            assert sock is fake
            return sock

    def socket_factory(family, kind):
        assert family == socket.AF_INET
        assert kind == socket.SOCK_STREAM
        return fake

    def forbidden_dns(*args, **kwargs):
        raise AssertionError("unexpected DNS resolution")

    monkeypatch.setattr(pinned, "_open_socket", socket_factory)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_dns)
    monkeypatch.setattr(pinned, "tls_context", Context)

    budget = Budget()

    result = pinned._connect_bound(
        bound(),
        budget,
        budget.operation_deadline(),
    )

    assert result is fake
    assert fake.connected == ("93.184.216.34", 443)
    assert observed["hostname"] == "example.com"


def test_connection_peer_mismatch(monkeypatch):
    fake = FakeSocket("1.1.1.1")

    monkeypatch.setattr(
        pinned, "_open_socket",
        lambda *args: fake,
    )

    budget = Budget()

    expect(
        ErrorCode.TRANSPORT_INTEGRITY,
        pinned._connect_bound,
        bound(),
        budget,
        budget.operation_deadline(),
    )

    assert fake.closed


def test_tls_failure_closes_connection(monkeypatch):
    fake = FakeSocket("93.184.216.34")

    class Context:
        def wrap_socket(self, *args, **kwargs):
            raise ssl.SSLCertVerificationError(
                "private certificate diagnostics"
            )

    monkeypatch.setattr(
        pinned, "_open_socket",
        lambda *args: fake,
    )

    monkeypatch.setattr(
        pinned, "tls_context", Context
    )

    budget = Budget()

    expect(
        ErrorCode.TLS_FAILURE,
        pinned._connect_bound,
        bound(),
        budget,
        budget.operation_deadline(),
    )

    assert fake.closed


def test_private_target_rejected_before_connect(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("socket creation forbidden")

    monkeypatch.setattr(pinned, "_open_socket", forbidden)

    target = replace(
        bound(),
        ip="127.0.0.1",
    )

    budget = Budget()

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        pinned._connect_bound,
        target,
        budget,
        budget.operation_deadline(),
    )


def test_literal_destination_cannot_change_ip():
    target = BoundDestination(
        validate_url("https://1.1.1.1/"),
        "93.184.216.34",
    )

    expect(
        ErrorCode.TRANSPORT_INTEGRITY,
        pinned.validated_target,
        target,
    )


def test_forged_destination_rejected():
    target = bound()

    target = replace(
        target,
        destination=replace(
            target.destination,
            host="localhost",
        ),
    )

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        pinned.validated_target,
        target,
    )
