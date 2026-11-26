"""WP02-FINAL application execution boundary tests.

All provider requests use MockTransport.
All resolver responses are simulated.
No live API, real secret, or public network connection.
"""

import socket
import threading
import time

import httpx
import pytest

from agentops_api.agent.s06.budgets import Budget

from agentops_api.agent.s06.contracts import (
    SearchRequest,
    RetrievalRequest,
)

from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)

from agentops_api.services.s06_acquisition import (
    authorization,
    credentials,
    integrated_retrieval,
    pinned_transport,
    resolver,
    tavily,
)


def expect(code, operation, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        operation(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


def allow():
    # Test-only replacement of authorization seam.
    return None


def test_actual_policy_remains_disabled():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        authorization.require_live_authorization,
    )


def test_credential_denied_before_environment(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("secret lookup forbidden")

    monkeypatch.setattr(
        credentials.os.environ,
        "get",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        credentials.read_tavily_credential,
    )

    assert calls == []


def test_credential_redaction(monkeypatch):
    monkeypatch.setattr(
        credentials,
        "require_live_authorization",
        allow,
    )

    secret = "synthetic-test-credential"

    monkeypatch.setenv(
        "TAVILY_API_KEY",
        secret,
    )

    credential = credentials.read_tavily_credential()

    assert secret not in repr(credential)
    assert secret not in str(credential)

    assert (
        credentials.authorization_header(credential)
        == "Bearer " + secret
    )


@pytest.mark.parametrize("value", [
    "",
    " ",
    "x" * 513,
    "bad" + chr(10) + "header",
    "bad" + chr(13) + "header",
    "bad" + chr(0),
    "bad token",
    "nonascii-" + chr(233),
])
def test_invalid_credential_rejected(
    monkeypatch,
    value,
):
    monkeypatch.setattr(
        credentials,
        "require_live_authorization",
        allow,
    )

    if chr(0) in value:
        monkeypatch.setattr(
            credentials.os.environ,
            "get",
            lambda name: value,
        )
    else:
        monkeypatch.setenv(
            "TAVILY_API_KEY",
            value,
        )

    expect(
        ErrorCode.PROVIDER_FAILURE,
        credentials.read_tavily_credential,
    )


def test_missing_credential_rejected(monkeypatch):
    monkeypatch.setattr(
        credentials,
        "require_live_authorization",
        allow,
    )

    monkeypatch.delenv(
        "TAVILY_API_KEY",
        raising=False,
    )

    expect(
        ErrorCode.PROVIDER_FAILURE,
        credentials.read_tavily_credential,
    )


def test_forged_credential_header_rejected():
    forged = credentials.TavilyCredential(
        "unsafe" + chr(10) + "header"
    )

    expect(
        ErrorCode.PROVIDER_FAILURE,
        credentials.authorization_header,
        forged,
    )


def test_live_vendor_path_with_mock_transport(monkeypatch):
    monkeypatch.setattr(
        tavily,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setattr(
        credentials,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "synthetic-test-token",
    )

    requests = []

    def handler(request):
        requests.append(request)

        assert str(request.url) == tavily.ENDPOINT

        assert request.method == "POST"

        assert (
            request.headers["Authorization"]
            == "Bearer synthetic-test-token"
        )

        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Fixture",
                        "url": "https://example.com/",
                        "content": "Synthetic response",
                        "score": 0.9,
                    }
                ],
                "usage": {
                    "credits": 1,
                },
            },
        )

    original_client = httpx.Client

    def mock_client(**kwargs):
        assert type(kwargs["transport"]) is (
            tavily.TavilyPinnedTransport
        )
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False

        fixture_transport = kwargs["transport"]

        kwargs["transport"] = httpx.MockTransport(
            lambda request: _s08_mock_exchange(
                fixture_transport, handler, request
            )
        )

        return original_client(**kwargs)

    monkeypatch.setattr(
        tavily.httpx,
        "Client",
        mock_client,
    )

    budget = Budget()

    outcome = _s08_partial(_s08_fixture_search, monkeypatch)(
        SearchRequest(query="fixture"),
        budget,
    )

    assert len(requests) == 1
    assert outcome.synthetic is False
    assert outcome.credits == 1
    assert len(outcome.hits) == 1
    assert budget.snapshot().searches == 1


def test_live_vendor_entry_denies_without_approval(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("forbidden")

    monkeypatch.setattr(
        tavily,
        "read_tavily_credential",
        forbidden,
    )

    monkeypatch.setattr(
        tavily.httpx,
        "Client",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_live,
        SearchRequest(query="fixture"),
        Budget(),
    )

    assert calls == []


def test_internal_vendor_helper_denies_live():
    budget = Budget()

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily._execute,
        SearchRequest(query="fixture"),
        budget,
        deadline=budget.operation_deadline(),
        header="Bearer synthetic",
        transport=None,
        synthetic=False,
    )


def test_internal_vendor_helper_rejects_unapproved_transport():
    budget = Budget()

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily._execute,
        SearchRequest(query="fixture"),
        budget,
        deadline=budget.operation_deadline(),
        header="Bearer synthetic",
        transport=None,
        synthetic=True,
    )


def make_resolver():
    budget = Budget()

    return resolver.DeadlineResolver(
        budget,
        budget.operation_deadline(),
    )


def answer(ip):
    family = (
        socket.AF_INET6
        if ":" in ip
        else socket.AF_INET
    )

    endpoint = (
        (ip, 0, 0, 0)
        if family == socket.AF_INET6
        else (ip, 0)
    )

    return (
        family,
        socket.SOCK_STREAM,
        6,
        "",
        endpoint,
    )


def test_resolver_default_denial(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("DNS forbidden")

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        make_resolver().resolve,
        "example.com",
    )

    assert calls == []


def test_resolver_all_answers_validated(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            answer("1.1.1.1"),
            answer("2606:4700:4700::1111"),
            answer("1.1.1.1"),
        ],
    )

    assert make_resolver().resolve(
        "example.com"
    ) == (
        "1.1.1.1",
        "2606:4700:4700::1111",
    )


@pytest.mark.parametrize("ip", [
    "127.0.0.1",
    "10.0.0.1",
    "169.254.169.254",
    "::1",
    "fc00::1",
])
def test_resolver_mixed_private_answers(
    monkeypatch,
    ip,
):
    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            answer("1.1.1.1"),
            answer(ip),
        ],
    )

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        make_resolver().resolve,
        "example.com",
    )


def test_resolver_answer_limit(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            answer("1.1.1.1")
        ] * 17,
    )

    expect(
        ErrorCode.DNS_FAILURE,
        make_resolver().resolve,
        "example.com",
    )


def test_resolver_sanitizes_os_error(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    def broken(*args, **kwargs):
        raise OSError("private DNS response")

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        broken,
    )

    expect(
        ErrorCode.DNS_FAILURE,
        make_resolver().resolve,
        "example.com",
    )


def test_resolver_bounded_wait_and_single_slot(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    release = threading.Event()
    entered = threading.Event()

    def blocked(*args, **kwargs):
        entered.set()
        release.wait(3)

        return [
            answer("1.1.1.1"),
        ]

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        blocked,
    )

    budget = Budget()

    deadline = (
        budget.operation_deadline() - 14.9
    )

    instance = resolver.DeadlineResolver(
        budget,
        deadline,
    )

    try:
        start = time.monotonic()

        expect(
            ErrorCode.DEADLINE_EXCEEDED,
            instance.resolve,
            "example.com",
        )

        assert entered.is_set()
        assert time.monotonic() - start < 1.5

        expect(
            ErrorCode.DNS_FAILURE,
            make_resolver().resolve,
            "example.org",
        )

    finally:
        release.set()

        assert resolver.DNS_SLOT.acquire(
            timeout=4
        )

        resolver.DNS_SLOT.release()


def test_socket_creation_default_denial(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("socket forbidden")

    monkeypatch.setattr(
        pinned_transport.socket,
        "socket",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        pinned_transport._open_socket,
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    assert calls == []


def test_authorized_socket_factory_is_reachable(monkeypatch):
    monkeypatch.setattr(
        pinned_transport,
        "require_live_authorization",
        allow,
    )

    # Socket is created, not connected.
    sock = pinned_transport._open_socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:
        assert sock.fileno() >= 0
    finally:
        sock.close()

    assert sock.fileno() == -1


def test_live_retrieval_denied_before_resolver(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("resolver forbidden")

    monkeypatch.setattr(
        integrated_retrieval,
        "DeadlineResolver",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        integrated_retrieval.retrieve_live,
        RetrievalRequest(
            url="https://example.com/"
        ),
        Budget(),
    )

    assert calls == []


def test_live_retrieval_routes_into_shared_execution(monkeypatch):
    monkeypatch.setattr(
        integrated_retrieval,
        "require_live_authorization",
        allow,
    )

    calls = []

    def fake_execution(
        request,
        budget,
        *,
        resolver,
        deadline,
        synthetic=False,
    ):
        calls.append(
            (request, budget, resolver, deadline, synthetic)
        )

        raise AcquisitionError(
            ErrorCode.EXTERNAL_DISABLED
        )

    monkeypatch.setattr(
        integrated_retrieval,
        "_retrieve",
        fake_execution,
    )

    budget = Budget()

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        integrated_retrieval.retrieve_live,
        RetrievalRequest(
            url="https://example.com/"
        ),
        budget,
    )

    assert len(calls) == 1

    request, actual, instance, deadline, synthetic = (
        calls[0]
    )

    assert actual is budget
    assert instance.budget is budget
    assert instance.deadline == deadline
    assert synthetic is False


# S08 successor fixture compatibility; original assertions retained.
from functools import partial as _s08_partial
from tests.s08_legacy_provider_fixture import (
    fixture_search as _s08_fixture_search,
    mock_exchange as _s08_mock_exchange,
)
