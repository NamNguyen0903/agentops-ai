"""Final isolated acquisition security verification.

No real credentials or public network access.
TLS uses a local socket pair and an ephemeral trusted CA.
Public peer address and DNS answer metadata are simulated.
"""

import errno
import socket
import ssl
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
    bind_destination,
)
from agentops_api.agent.s06.transport import FixtureResolver

from agentops_api.services.s06_acquisition import (
    bounded_http as wire,
    credentials,
    integrated_retrieval as integrated,
    pinned_transport as pinned,
    provider_transport as provider,
    resolver,
    tavily,
)

from agentops_api.services.s06_acquisition.transport_failures import (
    RetryableTransportFailure,
    transport_failure,
)

from test_s06_isolated_network import certificates


def allow():
    return None


def expect(code, operation, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        operation(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


@pytest.mark.parametrize("number", [
    errno.ECONNRESET,
    errno.ECONNREFUSED,
    errno.ECONNABORTED,
    errno.EPIPE,
])
def test_transient_classification(number):
    error = transport_failure(
        OSError(number, "private details")
    )

    assert type(error) is RetryableTransportFailure
    assert error.code is ErrorCode.TRANSPORT_FAILURE
    assert "private details" not in str(error)


@pytest.mark.parametrize("number", [
    errno.EACCES,
    errno.EINVAL,
    errno.EBADF,
    errno.ENOMEM,
])
def test_permanent_transport_error(number):
    error = transport_failure(
        OSError(number, "private details")
    )

    assert type(error) is AcquisitionError
    assert error.code is ErrorCode.TRANSPORT_FAILURE


def test_timeout_classification():
    error = transport_failure(
        TimeoutError("private timeout")
    )

    assert error.code is ErrorCode.DEADLINE_EXCEEDED


def test_resolver_deadline_preserved():
    def expired(host):
        raise AcquisitionError(
            ErrorCode.DEADLINE_EXCEEDED
        )

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        bind_destination,
        "https://example.com/",
        expired,
    )


def test_generic_transport_failure_not_retried(monkeypatch):
    calls = []

    def broken(*args):
        calls.append(True)

        raise AcquisitionError(
            ErrorCode.TRANSPORT_FAILURE
        )

    monkeypatch.setattr(
        integrated,
        "exchange",
        broken,
    )

    budget = Budget()

    expect(
        ErrorCode.TRANSPORT_FAILURE,
        integrated.retrieve_isolated,
        RetrievalRequest(
            url="https://example.com/"
        ),
        budget,
        resolver=FixtureResolver({
            "example.com": ("1.1.1.1",),
        }),
    )

    assert len(calls) == 1
    assert budget.snapshot().retrievals == 1


def test_provider_transport_default_denied():
    budget = Budget()

    transport = provider.TavilyPinnedTransport(
        budget,
        budget.operation_deadline(),
    )

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        transport.handle_request,
        httpx.Request(
            "POST",
            provider.ENDPOINT,
            content=b"{}",
        ),
    )


@pytest.mark.parametrize("url", [
    "https://example.com/search",
    "http://api.tavily.com/search",
    "https://api.tavily.com/other",
    "https://api.tavily.com/search?extra=1",
])
def test_provider_origin_is_fixed(monkeypatch, url):
    monkeypatch.setattr(
        provider,
        "require_live_authorization",
        allow,
    )

    budget = Budget()

    transport = provider.TavilyPinnedTransport(
        budget,
        budget.operation_deadline(),
    )

    expect(
        ErrorCode.UNSAFE_DESTINATION,
        transport.handle_request,
        httpx.Request(
            "POST",
            url,
            content=b"{}",
        ),
    )


class PublicPeerTLS:
    """Real TLS socket with simulated public peer metadata."""

    def __init__(self, secured, ip):
        self.secured = secured
        self.ip = ip

    def getpeername(self):
        return self.ip, 443

    def settimeout(self, value):
        self.secured.settimeout(value)

    def recv(self, size):
        return self.secured.recv(size)

    def sendall(self, data):
        self.secured.sendall(data)

    def close(self):
        self.secured.close()


class LocalTLSConnector:
    def __init__(
        self,
        certificates,
        responses,
        *,
        trusted=True,
        certificate_hostname=None,
    ):
        self.certificates = certificates
        self.responses = list(responses)
        self.trusted = trusted
        self.certificate_hostname = certificate_hostname
        self.targets = []
        self.requests = []
        self.sockets = []
        self.threads = []
        self.errors = []

    def connect(self, target, budget, deadline):
        self.targets.append(target)

        ca_path, make_server = self.certificates

        server = make_server(
            self.certificate_hostname
            or target.destination.host
        )

        client = pinned.tls_context()

        if self.trusted:
            client.load_verify_locations(
                cafile=str(ca_path)
            )

        left, right = socket.socketpair()

        left.settimeout(
            budget.remaining(deadline)
        )

        right.settimeout(3)

        payload = self.responses.pop(0)

        def serve():
            try:
                with server.wrap_socket(
                    right,
                    server_side=True,
                ) as secured:
                    request = bytearray()

                    while wire.HEADER_END not in request:
                        chunk = secured.recv(4096)

                        if not chunk:
                            return

                        request.extend(chunk)

                        assert len(request) <= 32768

                    head, body = bytes(request).split(
                        wire.HEADER_END,
                        1,
                    )

                    expected = 0

                    for line in head.split(wire.CRLF):
                        if line.lower().startswith(
                            b"content-length:"
                        ):
                            expected = int(
                                line.split(b":", 1)[1]
                            )

                    while len(body) < expected:
                        chunk = secured.recv(4096)

                        if not chunk:
                            return

                        body += chunk

                    self.requests.append(
                        head + wire.HEADER_END + body
                    )

                    secured.sendall(payload)

            except (
                ssl.SSLError,
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

        try:
            secured = client.wrap_socket(
                left,
                server_hostname=target.destination.host,
            )

            self.sockets.append(secured)

            return PublicPeerTLS(
                secured,
                target.ip,
            )

        except ssl.SSLError:
            left.close()

            raise AcquisitionError(
                ErrorCode.TLS_FAILURE
            ) from None

        except BaseException:
            left.close()
            raise

    def finish(self):
        for secured in self.sockets:
            assert secured.fileno() == -1

        for thread in self.threads:
            thread.join(timeout=5)

            assert not thread.is_alive()

        assert not self.errors


def reply(status, headers, body=b""):
    return (
        wire.CRLF.join([
            b"HTTP/1.1 " + status,
            *headers,
            b"Connection: close",
        ])
        + wire.HEADER_END
        + body
    )


def text_reply(body=b"synthetic"):
    return reply(
        b"200 OK",
        (
            b"Content-Type: text/plain",
            (
                "Content-Length: " + str(len(body))
            ).encode("ascii"),
        ),
        body,
    )


def enable_test_dns(monkeypatch):
    calls = []

    def lookup(host, *args, **kwargs):
        calls.append(host)

        address = {
            "api.tavily.com": "1.1.1.1",
            "example.com": "1.1.1.1",
            "example.org": "8.8.8.8",
        }[host]

        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, 0),
            )
        ]

    monkeypatch.setattr(
        resolver,
        "require_live_authorization",
        allow,
    )

    monkeypatch.setattr(
        resolver.socket,
        "getaddrinfo",
        lookup,
    )

    return calls


def enable_vendor_test(monkeypatch, connector):
    for module in (
        tavily,
        provider,
        credentials,
    ):
        monkeypatch.setattr(
            module,
            "require_live_authorization",
            allow,
        )

    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "synthetic-wp05-credential",
    )

    monkeypatch.setattr(
        pinned,
        "_connect_bound",
        connector.connect,
    )

    return enable_test_dns(monkeypatch)


def test_provider_tls_dns_http_integration(
    monkeypatch,
    certificates,
):
    body = (
        b'{"results":[{"title":"Fixture",'
        b'"url":"https://example.com/",'
        b'"content":"Synthetic fixture","score":0.9}],'
        b'"usage":{"credits":1}}'
    )

    connector = LocalTLSConnector(
        certificates,
        [
            reply(
                b"200 OK",
                (
                    b"Content-Type: application/json",
                    (
                        "Content-Length: "
                        + str(len(body))
                    ).encode("ascii"),
                ),
                body,
            )
        ],
    )

    dns_calls = enable_vendor_test(
        monkeypatch,
        connector,
    )

    budget = Budget()

    try:
        result = tavily.search_live(
            SearchRequest(query="synthetic test"),
            budget,
        )

        assert result.credits == 1
        assert len(result.hits) == 1
        assert result.synthetic is False

        assert dns_calls == ["api.tavily.com"]
        assert budget.snapshot().searches == 1

        assert len(connector.requests) == 1

        request = connector.requests[0]

        assert b"POST /search HTTP/1.1" in request

        assert (
            b"Authorization: Bearer synthetic-wp05-credential"
            in request
        )

        assert connector.targets[0].ip == "1.1.1.1"

    finally:
        connector.finish()


@pytest.mark.parametrize("mode", [
    "untrusted",
    "wrong-hostname",
])
def test_provider_tls_rejection(
    monkeypatch,
    certificates,
    mode,
):
    connector = LocalTLSConnector(
        certificates,
        [text_reply()],
        trusted=mode != "untrusted",
        certificate_hostname=(
            "wrong.example.org"
            if mode == "wrong-hostname"
            else None
        ),
    )

    enable_vendor_test(
        monkeypatch,
        connector,
    )

    budget = Budget()

    try:
        expect(
            ErrorCode.TLS_FAILURE,
            tavily.search_live,
            SearchRequest(query="synthetic"),
            budget,
        )

        assert not connector.requests
        assert budget.snapshot().searches == 1

    finally:
        connector.finish()


def test_provider_redirect_not_followed(
    monkeypatch,
    certificates,
):
    connector = LocalTLSConnector(
        certificates,
        [
            reply(
                b"302 Found",
                (
                    b"Location: https://example.org/",
                ),
            )
        ],
    )

    calls = enable_vendor_test(
        monkeypatch,
        connector,
    )

    budget = Budget()

    try:
        expect(
            ErrorCode.PROVIDER_FAILURE,
            tavily.search_live,
            SearchRequest(query="synthetic"),
            budget,
        )

        assert calls == ["api.tavily.com"]
        assert len(connector.requests) == 1
        assert budget.snapshot().searches == 1

    finally:
        connector.finish()


def test_integrated_tls_redirect(
    monkeypatch,
    certificates,
):
    connector = LocalTLSConnector(
        certificates,
        [
            reply(
                b"302 Found",
                (
                    b"Location: https://example.org/next",
                ),
            ),
            text_reply(),
        ],
    )

    monkeypatch.setattr(
        pinned,
        "_connect_bound",
        connector.connect,
    )

    budget = Budget()

    try:
        page = integrated.retrieve_isolated(
            RetrievalRequest(
                url="https://example.com/source"
            ),
            budget,
            resolver=FixtureResolver({
                "example.com": ("1.1.1.1",),
                "example.org": ("8.8.8.8",),
            }),
        )

        assert page.synthetic is True
        assert page.body == b"synthetic"

        assert page.retrieved_url == (
            "https://example.org/next"
        )

        assert budget.snapshot().retrievals == 2

        assert [
            target.ip
            for target in connector.targets
        ] == [
            "1.1.1.1",
            "8.8.8.8",
        ]

        assert all(
            b"Authorization:" not in request
            for request in connector.requests
        )

    finally:
        connector.finish()


def test_provider_deadline_propagation(monkeypatch):
    for module in (
        tavily,
        provider,
        credentials,
    ):
        monkeypatch.setattr(
            module,
            "require_live_authorization",
            allow,
        )

    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "synthetic-test-token",
    )

    now = [0.0]

    budget = Budget(
        clock=lambda: now[0]
    )

    enable_test_dns(monkeypatch)

    class SlowHeaderSocket:
        def __init__(self):
            self.closed = False
            self.reads = 0

        def getpeername(self):
            return "1.1.1.1", 443

        def settimeout(self, timeout):
            assert timeout > 0

        def sendall(self, data):
            pass

        def recv(self, size):
            self.reads += 1
            now[0] += 4.0

            return b"x"

        def close(self):
            self.closed = True

    sock = SlowHeaderSocket()

    monkeypatch.setattr(
        pinned,
        "_connect_bound",
        lambda *args: sock,
    )

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        tavily.search_live,
        SearchRequest(query="synthetic"),
        budget,
    )

    assert sock.closed
    assert sock.reads <= 4
    assert budget.snapshot().searches == 1
