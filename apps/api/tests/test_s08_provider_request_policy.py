"""Offline S08 Basic Search wire policy verification."""

import json
import socket

import httpx
import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import SearchRequest
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.services.s06_acquisition import (
    authorization,
    credentials,
    provider_transport,
    tavily,
)
from agentops_api.services.s06_acquisition.request_policy import (
    prepare_basic_request,
    validate_basic_wire_request,
)


def payload():
    return prepare_basic_request(
        SearchRequest(
            query="public market research",
            max_results=3,
        )
    )


def encode(value):
    return json.dumps(value).encode("utf-8")


def expect(code, function, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        function(*args, **kwargs)

    assert exc.value.code is code


def test_valid_wire_payload():
    request = validate_basic_wire_request(encode(payload()))

    assert request.query == "public market research"
    assert request.max_results == 3
    assert tavily.prepare_basic_request(request) == payload()


@pytest.mark.parametrize("key,value", [
    ("search_depth", "advanced"),
    ("search_depth", "fast"),
    ("topic", "news"),
    ("auto_parameters", True),
    ("auto_parameters", 0),
    ("include_answer", True),
    ("include_raw_content", True),
    ("include_images", True),
    ("include_image_descriptions", True),
    ("include_favicon", True),
    ("include_usage", False),
    ("include_usage", 1),
    ("max_results", True),
    ("max_results", "3"),
    ("max_results", 1000),
    ("query", ""),
    ("query", ["invalid"]),
    ("api_key", "synthetic-forbidden"),
    ("include_domains", ["example.com"]),
    ("extra_option", True),
])
def test_unapproved_options(key, value):
    body = payload()
    body[key] = value

    expect(
        ErrorCode.INVALID_INPUT,
        validate_basic_wire_request,
        encode(body),
    )


@pytest.mark.parametrize("key", [
    "query", "search_depth", "max_results", "include_usage",
])
def test_missing_fields(key):
    body = payload()
    del body[key]

    expect(
        ErrorCode.INVALID_INPUT,
        validate_basic_wire_request,
        encode(body),
    )


@pytest.mark.parametrize("body", [
    b"",
    b"null",
    b"[]",
    b"{",
    b"\xff",
    b'{"query":"one","query":"two"}',
    b'{"max_results":NaN}',
    b"x" * 16385,
    bytearray(b"{}"),
    "{}",
])
def test_invalid_encoding(body):
    expect(
        ErrorCode.INVALID_INPUT,
        validate_basic_wire_request,
        body,
    )


def test_valid_request_does_not_authorize_execution():
    validate_basic_wire_request(encode(payload()))

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        authorization.require_live_authorization,
    )


def test_default_deny_before_secrets_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected live access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)

    monkeypatch.setenv(
        "AGENTOPS_ENABLE_LIVE_SEARCH", "true"
    )
    monkeypatch.setenv(
        "TAVILY_API_KEY", "synthetic-never-dispatched"
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        credentials.read_tavily_credential,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_live,
        SearchRequest(query="public research"),
        Budget(),
    )

    budget = Budget()

    transport = provider_transport.TavilyPinnedTransport(
        budget,
        budget.operation_deadline(),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        transport.handle_request,
        httpx.Request(
            "POST",
            provider_transport.ENDPOINT,
            json=payload(),
        ),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        transport._exchange,
        object(),
        encode(payload()),
        "Bearer isolated-test-token",
    )


def test_wire_rejection_before_destination_processing(monkeypatch):
    # Test-only seam. No production authorization is changed.
    # Both network boundaries are replaced by failure sentinels.

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected destination or network processing")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    monkeypatch.setattr(
        provider_transport,
        "require_live_authorization",
        lambda: None,
    )
    monkeypatch.setattr(
        provider_transport,
        "bind_destination",
        forbidden,
    )
    monkeypatch.setattr(
        provider_transport.pinned,
        "validated_target",
        forbidden,
    )
    monkeypatch.setattr(
        provider_transport.pinned,
        "_connect_bound",
        forbidden,
    )

    body = payload()
    body["search_depth"] = "advanced"

    budget = Budget()
    transport = provider_transport.TavilyPinnedTransport(
        budget,
        budget.operation_deadline(),
    )

    expect(
        ErrorCode.INVALID_INPUT,
        transport.handle_request,
        httpx.Request(
            "POST",
            provider_transport.ENDPOINT,
            headers={
                "Authorization": "Bearer isolated-test-token"
            },
            content=encode(body),
        ),
    )

    expect(
        ErrorCode.INVALID_INPUT,
        transport._exchange,
        object(),
        encode(body),
        "Bearer isolated-test-token",
    )


def test_isolated_adapter_positive_control():
    calls = []

    def handler(request):
        validate_basic_wire_request(request.content)
        calls.append(request.method)

        assert str(request.url) == tavily.ENDPOINT
        assert request.headers["authorization"] == (
            "Bearer isolated-test-token"
        )

        return httpx.Response(
            200,
            json={
                "results": [],
                "usage": {"credits": 1},
                "request_id": "synthetic-s08-fixture",
            },
        )

    budget = Budget()

    result = tavily.search_isolated(
        SearchRequest(query="public research"),
        budget,
        transport=httpx.MockTransport(handler),
    )

    assert result.synthetic is True
    assert result.credits == 1
    assert calls == ["POST"]
    assert budget.snapshot().searches == 1
