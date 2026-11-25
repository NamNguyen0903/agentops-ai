"""Isolated bounded acquisition hardening verification."""

import socket
import threading

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
from agentops_api.agent.s06.network_policy import (
    BoundDestination,
    validate_url,
)
from agentops_api.agent.s06.transport import FixtureResolver

from agentops_api.services.s06_acquisition import (
    bounded_http as wire,
    credentials,
    integrated_retrieval as integrated,
    pinned_transport as pinned,
    tavily,
)


CRLF = bytes((13, 10))


def expect(code, operation, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        operation(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


class PeerSocket:
    """Real local socket I/O with simulated public peer metadata."""

    def __init__(self, sock, ip):
        self.sock = sock
        self.ip = ip
        self.closed = False
        self.timeouts = []

    def settimeout(self, timeout):
        assert not self.closed
        self.timeouts.append(timeout)
        self.sock.settimeout(timeout)

    def getpeername(self):
        return self.ip, 443

    def sendall(self, data):
        self.sock.sendall(data)

    def recv(self, size):
        return self.sock.recv(size)

    def close(self):
        self.closed = True
        self.sock.close()


def response(
    status=b"200 OK",
    headers=None,
    body=b"synthetic",
):
    if headers is None:
        headers = (
            b"Content-Type: text/plain",
            b"Content-Length: 9",
        )

    return (
        CRLF.join([
            b"HTTP/1.1 " + status,
            *headers,
            b"Connection: close",
        ])
        + CRLF * 2
        + body
    )


class IsolatedConnector:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.targets = []
        self.requests = []
        self.sockets = []
        self.threads = []
        self.errors = []

    def connect(self, target, budget, deadline):
        self.targets.append(target)

        assert self.payloads

        payload = self.payloads.pop(0)

        if isinstance(payload, Exception):
            raise payload

        left, right = socket.socketpair()

        left.settimeout(3)
        right.settimeout(3)

        wrapper = PeerSocket(
            left,
            target.ip,
        )

        self.sockets.append(wrapper)

        def serve():
            try:
                request = bytearray()

                while CRLF * 2 not in request:
                    chunk = right.recv(4096)

                    if not chunk:
                        return

                    request.extend(chunk)

                    assert len(request) <= 16384

                self.requests.append(
                    bytes(request)
                )

                right.sendall(payload)

            except (
                BrokenPipeError,
                ConnectionResetError,
            ):
                pass

            except Exception as exc:
                self.errors.append(exc)

            finally:
                right.close()

        thread = threading.Thread(
            target=serve,
            daemon=True,
        )

        self.threads.append(thread)
        thread.start()

        return wrapper

    def finish(self):
        for wrapper in self.sockets:
            assert wrapper.closed
            assert wrapper.sock.fileno() == -1

        for thread in self.threads:
            thread.join(timeout=5)

            assert not thread.is_alive()

        assert not self.errors


def target():
    return BoundDestination(
        validate_url(
            "https://example.com/source"
        ),
        "93.184.216.34",
    )


def exchange(monkeypatch, payload):
    connector = IsolatedConnector([payload])

    monkeypatch.setattr(
        pinned,
        "_connect_bound",
        connector.connect,
    )

    budget = Budget()

    try:
        result = wire.exchange(
            target(),
            budget,
            budget.operation_deadline(),
        )

        return result, connector

    finally:
        connector.finish()


def test_real_socket_body_and_ownership(monkeypatch):
    result, connector = exchange(
        monkeypatch,
        response(),
    )

    assert b"".join(result.chunks) == b"synthetic"

    assert (
        b"GET /source HTTP/1.1"
        in connector.requests[0]
    )

    assert (
        b"Host: example.com"
        in connector.requests[0]
    )

    assert connector.sockets[0].sock.fileno() == -1


def test_zero_length_body(monkeypatch):
    result, _ = exchange(
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
                b"Content-Length: 0",
            ),
            body=b"",
        ),
    )

    assert result.chunks == ()


def test_truncated_body(monkeypatch):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
                b"Content-Length: 20",
            ),
            body=b"short",
        ),
    )


def test_close_delimited_body(monkeypatch):
    result, _ = exchange(
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
            ),
        ),
    )

    assert b"".join(result.chunks) == b"synthetic"


@pytest.mark.parametrize("headers", [
    (
        b"Content-Type: text/plain",
        b"Content-Length: 9",
        b"content-length: 10",
    ),
    (
        b"Content-Type: text/plain",
        b" folded-header",
    ),
    (
        b"Content-Type: text/plain",
        b"Invalid Header: value",
    ),
    (
        b"Content-Type: text/plain",
        b"Broken-Header",
    ),
    (
        b"Content-Type: text/plain",
        b"Content-Length: -1",
    ),
    (
        b"Content-Type: text/plain",
        b"Transfer-Encoding: chunked",
    ),
    (
        b"Content-Type: text/plain",
        b"X-Invalid: abc" + bytes((0,)),
    ),
])
def test_malformed_wire_headers(
    monkeypatch,
    headers,
):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        response(headers=headers),
    )


def test_header_size_bounded(monkeypatch):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"X-Large: " + b"x" * 16384,
            ),
        ),
    )


def test_header_count_bounded(monkeypatch):
    headers = tuple(
        f"X-Test-{number}: value".encode()
        for number in range(65)
    )

    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        response(headers=headers),
    )


@pytest.mark.parametrize("encoding", [
    b"gzip",
    b"br",
    b"deflate",
])
def test_compression_rejected(
    monkeypatch,
    encoding,
):
    expect(
        ErrorCode.UNSUPPORTED_CONTENT,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
                b"Content-Encoding: " + encoding,
            ),
        ),
    )


def test_declared_body_limit(monkeypatch):
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
                b"Content-Length: 1048577",
            ),
            body=b"",
        ),
    )


def test_undeclared_body_limit(monkeypatch):
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
            ),
            body=b"x" * 1048577,
        ),
    )


def test_exact_body_limit(monkeypatch):
    payload = b"x" * 1048576

    result, _ = exchange(
        monkeypatch,
        response(
            headers=(
                b"Content-Type: text/plain",
                b"Content-Length: 1048576",
            ),
            body=payload,
        ),
    )

    assert b"".join(result.chunks) == payload


@pytest.mark.parametrize("status", [
    b"100 Continue",
    b"101 Switching Protocols",
    b"999 Invalid",
    b"Invalid",
])
def test_unsupported_status(
    monkeypatch,
    status,
):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        response(status=status),
    )


@pytest.mark.parametrize("content_type", [
    b"application/pdf",
    b"image/png",
    b"application/zip",
])
def test_unsupported_content_type(
    monkeypatch,
    content_type,
):
    expect(
        ErrorCode.UNSUPPORTED_CONTENT,
        exchange,
        monkeypatch,
        response(
            headers=(
                b"Content-Type: " + content_type,
            ),
        ),
    )


class AdvancingSocket:
    def __init__(self, clock, chunks):
        self.clock = clock
        self.chunks = list(chunks)
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, size):
        self.clock[0] += 4.0

        if not self.chunks:
            return b""

        chunk = self.chunks.pop(0)

        assert len(chunk) <= size

        return chunk


def test_slow_headers_absolute_deadline():
    now = [0.0]

    budget = Budget(
        clock=lambda: now[0]
    )

    deadline = budget.operation_deadline()

    sock = AdvancingSocket(
        now,
        [b"x"] * 10,
    )

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        wire.read_head,
        sock,
        budget,
        deadline,
    )

    assert len(sock.timeouts) < 10

    assert (
        sock.timeouts[-1]
        < sock.timeouts[0]
    )


def test_slow_body_absolute_deadline():
    now = [0.0]

    budget = Budget(
        clock=lambda: now[0]
    )

    deadline = budget.operation_deadline()

    sock = AdvancingSocket(
        now,
        [b"x"] * 10,
    )

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        wire.bounded_body,
        sock,
        b"",
        {"content-type": "text/plain"},
        budget,
        deadline,
    )


def test_socket_timeout_sanitized():
    class TimedOut:
        def settimeout(self, value):
            pass

        def recv(self, size):
            raise TimeoutError(
                "private response content"
            )

    budget = Budget()

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        wire.receive,
        TimedOut(),
        budget,
        budget.operation_deadline(),
        100,
    )


def test_real_socket_timeout():
    left, right = socket.socketpair()

    budget = Budget()

    deadline = min(
        budget.operation_deadline(),
        budget.operation_deadline() - 14.9,
    )

    try:
        expect(
            ErrorCode.DEADLINE_EXCEEDED,
            wire.receive,
            left,
            budget,
            deadline,
            100,
        )

    finally:
        left.close()
        right.close()


def retrieve(connector, monkeypatch, budget, resolver):
    monkeypatch.setattr(
        pinned,
        "_connect_bound",
        connector.connect,
    )

    return integrated.retrieve_isolated(
        RetrievalRequest(
            url="https://example.com/source"
        ),
        budget,
        resolver=resolver,
    )


def public_resolver():
    return FixtureResolver({
        "example.com": ("93.184.216.34",),
        "example.org": ("1.1.1.1",),
    })


def redirect(location):
    return response(
        status=b"302 Found",
        headers=(
            b"Location: " + location,
        ),
        body=b"",
    )


def test_integrated_redirect_binding(monkeypatch):
    connector = IsolatedConnector([
        redirect(
            b"https://example.org/next"
        ),
        response(),
    ])

    budget = Budget()

    try:
        page = retrieve(
            connector,
            monkeypatch,
            budget,
            public_resolver(),
        )

        assert page.body == b"synthetic"

        assert page.retrieved_url == (
            "https://example.org/next"
        )

        assert page.synthetic is True

        assert [
            item.ip
            for item in connector.targets
        ] == [
            "93.184.216.34",
            "1.1.1.1",
        ]

        assert budget.snapshot().retrievals == 2

    finally:
        connector.finish()


@pytest.mark.parametrize("answers", [
    ("127.0.0.1",),
    ("1.1.1.1", "127.0.0.1"),
    ("169.254.169.254",),
])
def test_redirect_private_dns_never_connected(
    monkeypatch,
    answers,
):
    connector = IsolatedConnector([
        redirect(
            b"https://example.org/next"
        ),
    ])

    resolver = FixtureResolver({
        "example.com": ("93.184.216.34",),
        "example.org": answers,
    })

    try:
        expect(
            ErrorCode.UNSAFE_DESTINATION,
            retrieve,
            connector,
            monkeypatch,
            Budget(),
            resolver,
        )

        assert len(connector.targets) == 1

    finally:
        connector.finish()


@pytest.mark.parametrize("location", [
    b"http://example.com/next",
    b"https://127.0.0.1/",
    b"file:///etc/passwd",
])
def test_unsafe_redirect_rejected(
    monkeypatch,
    location,
):
    connector = IsolatedConnector([
        redirect(location),
    ])

    try:
        expect(
            ErrorCode.UNSAFE_DESTINATION,
            retrieve,
            connector,
            monkeypatch,
            Budget(),
            public_resolver(),
        )

        assert len(connector.targets) == 1

    finally:
        connector.finish()


def test_integrated_redirect_loop(monkeypatch):
    connector = IsolatedConnector([
        redirect(b"/source"),
    ])

    try:
        expect(
            ErrorCode.REDIRECT_LIMIT,
            retrieve,
            connector,
            monkeypatch,
            Budget(),
            public_resolver(),
        )

        assert len(connector.targets) == 1

    finally:
        connector.finish()


def test_integrated_retry_budget(monkeypatch):
    connector = IsolatedConnector([
        RetryableTransportFailure(),
        response(),
    ])

    budget = Budget()

    try:
        page = retrieve(
            connector,
            monkeypatch,
            budget,
            public_resolver(),
        )

        assert page.body == b"synthetic"
        assert budget.snapshot().retrievals == 2
        assert len(connector.targets) == 2

    finally:
        connector.finish()


def test_retry_limit(monkeypatch):
    connector = IsolatedConnector([
        RetryableTransportFailure(),
        RetryableTransportFailure(),
    ])

    budget = Budget()

    try:
        expect(
            ErrorCode.TRANSPORT_FAILURE,
            retrieve,
            connector,
            monkeypatch,
            budget,
            public_resolver(),
        )

        assert budget.snapshot().retrievals == 2

    finally:
        connector.finish()


@pytest.mark.parametrize("code", [
    ErrorCode.TLS_FAILURE,
    ErrorCode.TRANSPORT_INTEGRITY,
    ErrorCode.DEADLINE_EXCEEDED,
    ErrorCode.EXTERNAL_DISABLED,
])
def test_non_retryable_failure(
    monkeypatch,
    code,
):
    connector = IsolatedConnector([
        AcquisitionError(code),
    ])

    try:
        expect(
            code,
            retrieve,
            connector,
            monkeypatch,
            Budget(),
            public_resolver(),
        )

        assert len(connector.targets) == 1

    finally:
        connector.finish()


def test_unknown_resolver_rejected():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        integrated.retrieve_isolated,
        RetrievalRequest(
            url="https://example.com/"
        ),
        Budget(),
        resolver=object(),
    )


def test_live_boundaries_deny_before_network(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError(
            "network must remain disabled"
        )

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        forbidden,
    )

    monkeypatch.setattr(
        socket,
        "socket",
        forbidden,
    )

    monkeypatch.setattr(
        httpx,
        "Client",
        forbidden,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_live,
        SearchRequest(query="test"),
        Budget(),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        integrated.retrieve_live,
        RetrievalRequest(
            url="https://example.com/"
        ),
        Budget(),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        credentials.read_tavily_credential,
    )

    assert calls == []


def test_internal_connector_still_denied(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError(
            "socket creation forbidden"
        )

    monkeypatch.setattr(
        socket,
        "socket",
        forbidden,
    )

    budget = Budget()

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        wire.exchange,
        target(),
        budget,
        budget.operation_deadline(),
    )

    assert calls == []


def test_environment_cannot_enable_live(monkeypatch):
    monkeypatch.setenv(
        "AGENTOPS_ENABLE_LIVE_SEARCH",
        "true",
    )

    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "synthetic-never-send-credential",
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        credentials.read_tavily_credential,
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        tavily.search_live,
        SearchRequest(query="test"),
        Budget(),
    )


def test_prepared_request_has_no_credentials():
    payload = tavily.prepare_basic_request(
        SearchRequest(query="market research")
    )

    assert payload["search_depth"] == "basic"
    assert payload["auto_parameters"] is False
    assert payload["include_answer"] is False
    assert payload["include_raw_content"] is False
    assert payload["include_images"] is False

    assert "api_key" not in payload
    assert "authorization" not in payload


def test_prepared_request_preserves_result_limit():
    payload = tavily.prepare_basic_request(
        SearchRequest(
            query="fixture",
            max_results=3,
        )
    )

    assert payload["query"] == "fixture"
    assert payload["max_results"] == 3


def test_forged_vendor_request_rejected():
    request = SearchRequest.model_construct(
        query="fixture",
        max_results=1000,
    )

    expect(
        ErrorCode.INVALID_INPUT,
        tavily.prepare_basic_request,
        request,
    )

from agentops_api.services.s06_acquisition.transport_failures import RetryableTransportFailure
