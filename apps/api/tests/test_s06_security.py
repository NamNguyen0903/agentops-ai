"""Adversarial offline acquisition tests."""

import ast
from pathlib import Path

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import RetrievalRequest
from agentops_api.agent.s06.errors import ErrorCode
from agentops_api.agent.s06.network_policy import (
    validate_url,
    bind_destination,
)
from agentops_api.agent.s06.retrieval import retrieve_offline
from agentops_api.agent.s06.transport import (
    FixtureResolver,
    FixtureTransport,
)

from test_s06_acquisition import (
    expect,
    fetch,
    response,
    resolver,
)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/",
    "gopher://example.com/",
    "http://localhost/",
    "http://foo.local/",
    "http://foo.internal/",
    "http://127.0.0.1/",
    "http://0.0.0.0/",
    "http://10.0.0.1/",
    "http://172.16.0.1/",
    "http://192.168.1.1/",
    "http://169.254.169.254/",
    "http://100.64.0.1/",
    "http://224.0.0.1/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[64:ff9b::7f00:1]/",
    "http://2130706433/",
    "http://0177.0.0.1/",
    "http://0x7f000001/",
    "http://127.1/",
    "https://user:secret@example.com/",
    "https://example.com@127.0.0.1/",
    "https://example.com:8443/",
    "https://example.com./",
    "https://%65xample.com/",
    "https://example.com:",
    "https://example.com/" + chr(10),
    " https://example.com/",
    "https://example.com" + chr(92) + "@127.0.0.1/",
])
def test_unsafe_urls(url):
    expect(
        ErrorCode.UNSAFE_DESTINATION,
        validate_url,
        url,
    )


@pytest.mark.parametrize("url,host", [
    ("https://EXAMPLE.com/path#fragment", "example.com"),
    ("http://1.1.1.1/", "1.1.1.1"),
    (
        "https://[2606:4700:4700::1111]/",
        "2606:4700:4700::1111",
    ),
])
def test_public_urls(url, host):
    assert validate_url(url).host == host


@pytest.mark.parametrize("answers", [
    ("127.0.0.1",),
    ("93.184.216.34", "10.0.0.1"),
    ("1.1.1.1", "::1"),
    ("169.254.169.254",),
    ("224.0.0.1",),
])
def test_all_dns_answers_checked(answers):
    expect(
        ErrorCode.UNSAFE_DESTINATION,
        bind_destination,
        "https://example.com/",
        FixtureResolver({"example.com": answers}),
    )


def test_empty_dns():
    expect(
        ErrorCode.DNS_FAILURE,
        bind_destination,
        "https://example.com/",
        FixtureResolver({"example.com": ()}),
    )


def test_peer_mismatch():
    expect(
        ErrorCode.TRANSPORT_INTEGRITY,
        fetch,
        [response(peer_ip="1.1.1.1")],
    )


def test_private_peer():
    expect(
        ErrorCode.UNSAFE_DESTINATION,
        fetch,
        [response(peer_ip="127.0.0.1")],
    )


@pytest.mark.parametrize("changes", [
    {"tls_verified": False},
    {"tls_verified": 1},
    {"tls_hostname": "example.org"},
    {"tls_hostname": None},
])
def test_tls_metadata(changes):
    expect(
        ErrorCode.TLS_FAILURE,
        fetch,
        [response(**changes)],
    )


@pytest.mark.parametrize("location", [
    "http://example.com/",
    "https://127.0.0.1/",
    "https://169.254.169.254/",
    "file:///etc/passwd",
    "https://user:password@example.org/",
])
def test_unsafe_redirect(location):
    expect(
        ErrorCode.UNSAFE_DESTINATION,
        fetch,
        [response(
            status=302,
            headers=(("Location", location),),
        )],
    )


def test_redirect_dns_rechecked():
    transport = FixtureTransport((
        response(
            status=302,
            headers=(
                ("Location", "https://example.org/"),
            ),
        ),
    ))

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        retrieve_offline,
        RetrievalRequest(url="https://example.com/"),
        Budget(),
        resolver=FixtureResolver({
            "example.com": ("93.184.216.34",),
            "example.org": ("127.0.0.1",),
        }),
        transport=transport,
    )

    assert len(transport.requests) == 1


def test_redirect_loop():
    expect(
        ErrorCode.REDIRECT_LIMIT,
        fetch,
        [response(
            status=302,
            headers=(("Location", "/"),),
        )],
    )


def test_redirect_limit():
    expect(
        ErrorCode.REDIRECT_LIMIT,
        fetch,
        [
            response(
                status=302,
                headers=(("Location", f"/page-{n}"),),
            )
            for n in range(1, 5)
        ],
    )


@pytest.mark.parametrize("encoding", [
    "gzip", "br", "deflate", "zstd", "gzip, identity",
])
def test_compressed_response(encoding):
    expect(
        ErrorCode.UNSUPPORTED_CONTENT,
        fetch,
        [response(headers=(
            ("Content-Type", "text/plain"),
            ("Content-Encoding", encoding),
        ))],
    )


@pytest.mark.parametrize("content_type", [
    "application/octet-stream",
    "application/zip",
    "image/png",
    "application/pdf",
])
def test_content_type(content_type):
    expect(
        ErrorCode.UNSUPPORTED_CONTENT,
        fetch,
        [response(headers=(
            ("Content-Type", content_type),
        ))],
    )


def test_declared_oversized_body():
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        fetch,
        [response(headers=(
            ("Content-Type", "text/plain"),
            ("Content-Length", "1048577"),
        ))],
    )


def test_actual_oversized_body():
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        fetch,
        [response(chunks=(
            b"x" * 1048576,
            b"y",
        ))],
    )


def test_exact_body_boundary():
    page, _ = fetch([
        response(chunks=(b"x" * 1048576,)),
    ])

    assert len(page.body) == 1048576


@pytest.mark.parametrize("length", [
    "-1", "+10", "nan", "abc", "10.5", "1",
])
def test_invalid_content_length(length):
    expect(
        ErrorCode.INVALID_RESPONSE,
        fetch,
        [response(headers=(
            ("Content-Type", "text/plain"),
            ("Content-Length", length),
        ))],
    )


def test_duplicate_headers():
    expect(
        ErrorCode.INVALID_RESPONSE,
        fetch,
        [response(headers=(
            ("Content-Type", "text/plain"),
            ("content-type", "text/html"),
        ))],
    )


def test_unknown_transport_disabled():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        retrieve_offline,
        RetrievalRequest(url="https://example.com/"),
        Budget(),
        resolver=resolver(),
        transport=object(),
    )


def test_unknown_resolver_disabled():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        retrieve_offline,
        RetrievalRequest(url="https://example.com/"),
        Budget(),
        resolver=lambda host: ("1.1.1.1",),
        transport=FixtureTransport((response(),)),
    )


def test_no_network_invocation(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("network call forbidden")

    monkeypatch.setattr(
        socket, "getaddrinfo", forbidden
    )
    monkeypatch.setattr(
        socket, "create_connection", forbidden
    )
    monkeypatch.setattr(
        socket, "socket", forbidden
    )

    page, _ = fetch([response()])
    assert page.synthetic is True


def test_no_direct_io_imports():
    from agentops_api.agent.s06 import retrieval

    root = Path(retrieval.__file__).parent

    allowed = {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "ipaddress",
        "langgraph",
        "math",
        "pydantic",
        "re",
        "time",
        "typing",
        "urllib",
        "uuid",
    }

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed

                    if alias.name.startswith("urllib"):
                        assert alias.name == "urllib.parse"

                    if alias.name.startswith("langgraph"):
                        raise AssertionError(
                            "Use exact approved LangGraph imports"
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module.split(".")[0] in allowed

                    if node.module.startswith("urllib"):
                        assert node.module == "urllib.parse"

                    if node.module.startswith("langgraph"):
                        assert path.name == "workflow.py"
                        assert node.module == "langgraph.graph"
                        assert {
                            alias.name for alias in node.names
                        } == {"START", "END", "StateGraph"}


@pytest.mark.parametrize("url", [
    "http://[fec0::1]/",
    "https://[3fff::1]/",
    "https://[2001:db8::1]/",
    "https://[2002::1]/",
])
def test_additional_special_use_destinations(url):
    expect(
        ErrorCode.UNSAFE_DESTINATION,
        validate_url,
        url,
    )


@pytest.mark.parametrize("changes", [
    {"status": True},
    {"status": "200"},
    {"status": 600},
    {"headers": []},
    {"headers": (("Content-Type", "text/plain", "extra"),)},
    {"headers": (("Content-Type", 123),)},
    {"chunks": ["invalid"]},
    {"chunks": ("invalid",)},
])
def test_malformed_transport_metadata(changes):
    expect(
        ErrorCode.INVALID_RESPONSE,
        fetch,
        [response(**changes)],
    )


@pytest.mark.parametrize("value", [
    float("nan"),
    float("inf"),
    float("-inf"),
    True,
    "10",
])
def test_invalid_clock_initialization(value):
    expect(
        ErrorCode.INVALID_INPUT,
        Budget,
        clock=lambda: value,
    )


def test_clock_regression_rejected():
    now = [10.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 9.0

    expect(
        ErrorCode.INVALID_INPUT,
        budget.operation_deadline,
    )


def test_forged_request_fields():
    from agentops_api.agent.s06.contracts import (
        SearchRequest,
        validate_contract,
    )

    request = SearchRequest(query="test")

    object.__setattr__(
        request, "allow_external", True
    )

    expect(
        ErrorCode.INVALID_INPUT,
        validate_contract,
        SearchRequest,
        request,
    )


def test_forged_nested_hit_fields():
    from agentops_api.agent.s06.contracts import (
        SearchHit,
        SearchResult,
        validate_contract,
    )

    hit = SearchHit(
        title="fixture",
        url="https://example.com/",
        snippet="synthetic",
    )

    result = SearchResult(hits=(hit,))

    object.__setattr__(
        result.hits[0],
        "unexpected_permission",
        True,
    )

    expect(
        ErrorCode.INVALID_RESPONSE,
        validate_contract,
        SearchResult,
        result,
        output=True,
    )


def test_provider_error_category_normalized(monkeypatch):
    from agentops_api.agent.s06.contracts import SearchRequest
    from agentops_api.agent.s06.errors import AcquisitionError
    from agentops_api.agent.s06.providers import (
        FixtureSearchProvider,
        search_offline,
    )

    def broken(*args, **kwargs):
        raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED)

    monkeypatch.setattr(
        FixtureSearchProvider, "search", broken
    )

    expect(
        ErrorCode.PROVIDER_FAILURE,
        search_offline,
        SearchRequest(query="test"),
        Budget(),
    )


def test_transport_error_category_normalized(monkeypatch):
    from agentops_api.agent.s06.errors import AcquisitionError

    def broken(*args, **kwargs):
        raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED)

    monkeypatch.setattr(
        FixtureTransport, "send", broken
    )

    expect(
        ErrorCode.TRANSPORT_FAILURE,
        fetch,
        [response()],
    )
