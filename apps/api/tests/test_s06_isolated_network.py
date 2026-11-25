"""Isolated TLS and HTTP socket lifecycle verification."""

import datetime
import socket
import ssl
import threading

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.network_policy import (
    BoundDestination,
    validate_url,
)
from agentops_api.services.s06_acquisition import (
    pinned_transport as pinned,
)

CRLF = bytes((13, 10))


def expect(code, function, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        function(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


def target():
    return BoundDestination(
        validate_url("https://example.com/source"),
        "93.184.216.34",
    )


def test_internal_connector_denied_without_authorization(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("external socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)

    budget = Budget()

    expect(
        ErrorCode.EXTERNAL_DISABLED,
        pinned._connect_bound,
        target(),
        budget,
        budget.operation_deadline(),
    )


@pytest.fixture
def certificates(tmp_path):
    now = datetime.datetime.now(datetime.timezone.utc)

    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    ca_name = x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            "AgentOps Isolated Test CA",
        )
    ])

    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = tmp_path / "ca.pem"

    ca_path.write_bytes(
        ca_cert.public_bytes(serialization.Encoding.PEM)
    )

    def server_context(hostname):
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, hostname)
            ]))
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                critical=False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH
                ]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        cert_path = tmp_path / "server.pem"
        key_path = tmp_path / "server-key.pem"

        cert_path.write_bytes(
            cert.public_bytes(serialization.Encoding.PEM)
        )

        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        context.load_cert_chain(
            str(cert_path),
            str(key_path),
        )

        return context

    return ca_path, server_context


def real_tls_handshake(
    certificates,
    *,
    hostname="example.com",
    trusted=True,
):
    ca_path, server_context = certificates
    server = server_context(hostname)
    client = pinned.tls_context()

    if trusted:
        client.load_verify_locations(cafile=str(ca_path))

    left, right = socket.socketpair()

    left.settimeout(3)
    right.settimeout(3)

    errors = []
    received = []

    def serve():
        try:
            with server.wrap_socket(
                right, server_side=True
            ) as secured:
                received.append(secured.recv(1024))
                secured.sendall(b"isolated-response")

        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    try:
        with client.wrap_socket(
            left, server_hostname="example.com"
        ) as secured:
            secured.sendall(b"isolated-request")

            assert secured.recv(1024) == b"isolated-response"

            assert secured.version() in {
                "TLSv1.2", "TLSv1.3",
            }

    finally:
        left.close()
        right.close()
        thread.join(timeout=5)
        assert not thread.is_alive()

    if errors:
        raise errors[0]

    assert received == [b"isolated-request"]


def test_actual_tls_valid_certificate(certificates):
    real_tls_handshake(certificates)


def test_actual_tls_hostname_mismatch(certificates):
    with pytest.raises(ssl.SSLCertVerificationError):
        real_tls_handshake(
            certificates,
            hostname="wrong.example.org",
        )


def test_actual_tls_untrusted_certificate(certificates):
    with pytest.raises(ssl.SSLCertVerificationError):
        real_tls_handshake(certificates, trusted=False)


class ConnectedSocket:
    """Real local socket I/O with simulated public peer metadata.

    Preserve the underlying descriptor until the HTTP parser
    has completed reading, even when HTTPConnection releases
    its connection-level ownership.
    """

    def __init__(self, sock):
        self.sock = sock
        self.timeouts = []
        self.close_requests = 0

    def getpeername(self):
        return "93.184.216.34", 443

    def settimeout(self, value):
        assert self.sock.fileno() >= 0
        self.timeouts.append(value)
        self.sock.settimeout(value)

    def sendall(self, data):
        self.sock.sendall(data)

    def makefile(self, *args, **kwargs):
        return self.sock.makefile(*args, **kwargs)

    def close(self):
        self.close_requests += 1

        # HTTPConnection may close its reference while
        # HTTPResponse still owns the underlying file.
        # The isolated harness retains socket ownership.

    def dispose(self):
        self.sock.close()


def wire_response(status, headers, body):
    return (
        CRLF.join([
            b"HTTP/1.1 " + status,
            *headers,
            b"Connection: close",
        ])
        + CRLF * 2
        + body
    )


def exchange(monkeypatch, payload):
    left, right = socket.socketpair()

    left.settimeout(3)
    right.settimeout(3)

    wrapped = ConnectedSocket(left)
    requests = []
    errors = []

    def serve():
        try:
            request = bytearray()

            while CRLF * 2 not in request:
                chunk = right.recv(4096)

                if not chunk:
                    break

                request.extend(chunk)

                if len(request) > 16384:
                    raise RuntimeError("Unexpected request size")

            requests.append(bytes(request))
            right.sendall(payload)

        except (BrokenPipeError, ConnectionResetError):
            pass

        except Exception as exc:
            errors.append(exc)

        finally:
            right.close()

    thread = threading.Thread(target=serve, daemon=True)

    monkeypatch.setattr(
        pinned, "_connect_bound",
        lambda *args: wrapped,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("External network forbidden")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    thread.start()
    budget = Budget()

    try:
        result = pinned._request_bound(
            target(),
            budget,
            budget.operation_deadline(),
        )

    finally:
        wrapped.dispose()
        thread.join(timeout=5)

        assert not thread.is_alive()
        assert not errors

    assert wrapped.close_requests >= 1

    return result, wrapped, requests


def test_actual_http_body_processing(monkeypatch):
    result, wrapped, requests = exchange(
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 9",
            ),
            b"synthetic",
        ),
    )

    assert b"".join(result.chunks) == b"synthetic"
    assert b"GET /source HTTP/1.1" in requests[0]
    assert b"Host: example.com" in requests[0]
    assert b"Accept-Encoding: identity" in requests[0]
    assert len(wrapped.timeouts) >= 3


def test_actual_http_truncated_body(monkeypatch):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 20",
            ),
            b"short",
        ),
    )


def test_actual_http_oversized_declared_body(monkeypatch):
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        exchange,
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 1048577",
            ),
            b"",
        ),
    )


def test_actual_http_oversized_undeclared_body(monkeypatch):
    expect(
        ErrorCode.RESPONSE_TOO_LARGE,
        exchange,
        monkeypatch,
        wire_response(
            b"200 OK",
            (b"Content-Type: text/plain",),
            b"x" * 1048577,
        ),
    )


def test_actual_http_compression_rejected(monkeypatch):
    expect(
        ErrorCode.UNSUPPORTED_CONTENT,
        exchange,
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Encoding: gzip",
            ),
            b"compressed-placeholder",
        ),
    )


def test_actual_http_duplicate_header(monkeypatch):
    expect(
        ErrorCode.INVALID_RESPONSE,
        exchange,
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 3",
                b"Content-Length: 4",
            ),
            b"abc",
        ),
    )


def test_actual_http_redirect_not_followed(monkeypatch):
    result, _, requests = exchange(
        monkeypatch,
        wire_response(
            b"302 Found",
            (b"Location: https://example.org/next",),
            b"",
        ),
    )

    assert result.status == 302
    assert result.chunks == ()
    assert len(requests) == 1


def test_actual_http_empty_framed_body(monkeypatch):
    result, _, _ = exchange(
        monkeypatch,
        wire_response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 0",
            ),
            b"",
        ),
    )

    assert result.chunks == ()
