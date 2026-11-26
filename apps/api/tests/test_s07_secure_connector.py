"""S07 actual network integration verification.

All authorization seams are scoped to this test process.
No live provider execution, database or application worker.
"""

import ipaddress
import os
import socket
import ssl
from pathlib import Path

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import RetrievalRequest
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.services.s06_acquisition import (
    authorization,
    integrated_retrieval as integrated,
    pinned_transport as pinned,
    resolver as dns,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTOPS_S07_NETWORK_FIXTURE") != "1",
    reason="requires isolated S07 network infrastructure",
)

PRIMARY = "11.77.0.10"
SECONDARY = "11.77.0.11"

SOURCE = "source.s07.test"
REDIRECT = "redirect.s07.test"
MIXED = "mixed.s07.test"
REBIND = "rebind.s07.test"
WRONG = "wrong.s07.test"

ALLOWED_HOSTS = {
    SOURCE,
    REDIRECT,
    MIXED,
    REBIND,
    WRONG,
}

ALLOWED_IPS = {PRIMARY, SECONDARY}

CA = "/s07-ca.pem"

REAL_GETADDRINFO = socket.getaddrinfo
REAL_SOCKET = socket.socket
REAL_OPEN_SOCKET = pinned._open_socket
REAL_VERIFY_PEER = pinned.verify_peer
REAL_WRAP_SOCKET = ssl.SSLContext.wrap_socket


def require_isolated_scope():
    assert os.environ.get(
        "AGENTOPS_S07_NETWORK_FIXTURE"
    ) == "1"

    assert Path("/.dockerenv").is_file()

    for line in Path(
        "/proc/net/route"
    ).read_text().splitlines()[1:]:
        fields = line.split()
        assert fields[1] != "00000000"

    ipv6 = Path("/proc/net/ipv6_route")

    if ipv6.exists():
        for line in ipv6.read_text().splitlines():
            fields = line.split()

            if len(fields) >= 10:
                assert not (
                    fields[0] == "0" * 32
                    and fields[1] == "00"
                    and fields[-1] != "lo"
                )

    nameservers = [
        line.split()[1]
        for line in Path(
            "/etc/resolv.conf"
        ).read_text().splitlines()
        if line.startswith("nameserver ")
    ]

    assert nameservers == [PRIMARY]

    assert Path(CA).is_file()


def denied(operation):
    with pytest.raises(AcquisitionError) as error:
        operation()

    assert error.value.code == ErrorCode.EXTERNAL_DISABLED


def test_ac20_production_authorization_stays_denied():
    require_isolated_scope()

    budget = Budget()

    request = RetrievalRequest(
        url=f"https://{SOURCE}/ok"
    )

    denied(
        authorization.require_live_authorization
    )

    denied(
        lambda: integrated.retrieve_live(
            request, budget
        )
    )

    denied(
        lambda: pinned._open_socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
    )

    denied(
        lambda: dns.DeadlineResolver(
            budget,
            budget.operation_deadline(),
        ).resolve(SOURCE)
    )

    denied(
        lambda: integrated.retrieve_isolated(
            request,
            budget,
            resolver=dns.DeadlineResolver(
                budget,
                budget.operation_deadline(),
            ),
        )
    )

    assert budget.snapshot().retrievals == 0


class ObservedSocket(REAL_SOCKET):
    """Actual socket with a test-only endpoint allowlist."""

    def __init__(
        self,
        family,
        kind,
        *,
        observations,
    ):
        super().__init__(family, kind)

        self.observations = observations

    def connect(self, address):
        ip, port = address[:2]

        # Numeric addresses only. No fallback hostname lookup.
        assert str(ipaddress.ip_address(ip)) == ip
        assert ip in ALLOWED_IPS
        assert port == 443

        self.observations["connects"].append(
            (ip, port)
        )

        if self.observations["force_wrong_peer"]:
            assert ip == PRIMARY

            address = (SECONDARY, port)

        return super().connect(address)


@pytest.fixture
def observed(monkeypatch):
    require_isolated_scope()

    state = {
        "dns": [],
        "connects": [],
        "peers": [],
        "raw_sockets": [],
        "tls_sockets": [],
        "tls_hostnames": [],
        "force_wrong_peer": False,
    }

    # The actual authorization module remains unchanged.
    # Only the imported resolver authorization binding is
    # replaced inside this isolated test process.
    monkeypatch.setattr(
        dns,
        "require_live_authorization",
        require_isolated_scope,
    )

    # Permit the actual DeadlineResolver through the
    # existing synthetic retrieval type gate, test-only.
    monkeypatch.setattr(
        integrated,
        "FixtureResolver",
        dns.DeadlineResolver,
    )

    def getaddrinfo(host, *args, **kwargs):
        assert host in ALLOWED_HOSTS

        # Execute the original OS resolver.
        answers = REAL_GETADDRINFO(
            host,
            *args,
            **kwargs,
        )

        state["dns"].append((
            host,
            tuple(sorted({
                answer[4][0]
                for answer in answers
            })),
        ))

        return answers

    monkeypatch.setattr(
        dns.socket,
        "getaddrinfo",
        getaddrinfo,
    )

    def open_socket(family, kind):
        require_isolated_scope()

        assert family == socket.AF_INET
        assert kind == socket.SOCK_STREAM

        sock = ObservedSocket(
            family,
            kind,
            observations=state,
        )

        state["raw_sockets"].append(sock)

        return sock

    # Socket factory seam returns a real kernel TCP socket,
    # not a mock response or an in-memory socket pair.
    monkeypatch.setattr(
        pinned,
        "_open_socket",
        open_socket,
    )

    def verify_peer(sock, expected):
        actual = sock.getpeername()[0]

        state["peers"].append(
            (actual, expected)
        )

        # Invoke original production peer validation.
        return REAL_VERIFY_PEER(
            sock,
            expected,
        )

    monkeypatch.setattr(
        pinned,
        "verify_peer",
        verify_peer,
    )

    def wrap_socket(context, sock, *args, **kwargs):
        # Real SSLContext and real OpenSSL handshake.
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED

        assert context.minimum_version >= (
            ssl.TLSVersion.TLSv1_2
        )

        state["tls_hostnames"].append(
            kwargs.get("server_hostname")
        )

        secured = REAL_WRAP_SOCKET(
            context,
            sock,
            *args,
            **kwargs,
        )

        state["tls_sockets"].append(secured)

        return secured

    monkeypatch.setattr(
        ssl.SSLContext,
        "wrap_socket",
        wrap_socket,
    )

    # Process-local CA trust only. No system trust changes.
    monkeypatch.setenv(
        "SSL_CERT_FILE",
        CA,
    )

    monkeypatch.delenv(
        "SSL_CERT_DIR",
        raising=False,
    )

    yield state

    # Every client descriptor must be closed, including
    # failed TLS handshakes and malformed HTTP processing.
    assert all(
        sock.fileno() == -1
        for sock in state["raw_sockets"]
    )

    assert all(
        sock.fileno() == -1
        for sock in state["tls_sockets"]
    )

    # The genuine production authorization function was
    # never changed, even while test seams were active.
    denied(
        authorization.require_live_authorization
    )

    print(
        "CLIENT_DESCRIPTOR_CLEANUP=PASS",
        flush=True,
    )


def retrieve(host=SOURCE, path="/ok"):
    budget = Budget()

    request = RetrievalRequest(
        url=f"https://{host}{path}"
    )

    resolver = dns.DeadlineResolver(
        budget,
        budget.operation_deadline(),
    )

    page = integrated.retrieve_isolated(
        request,
        budget,
        resolver=resolver,
    )

    return page, budget


def reject(code, host=SOURCE, path="/ok"):
    with pytest.raises(AcquisitionError) as error:
        retrieve(host, path)

    assert error.value.code == code


def test_ac14_ac16_ac17_ac20_actual_integrated_success(observed):
    page, budget = retrieve()

    assert page.synthetic is True
    assert page.body == b"s07-synthetic-page"
    assert page.content_type == "text/plain"

    assert page.source_url == (
        f"https://{SOURCE}/ok"
    )

    assert page.retrieved_url == page.source_url

    assert observed["dns"] == [
        (SOURCE, (PRIMARY,))
    ]

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]

    assert len(observed["peers"]) >= 3

    assert all(
        actual == expected == PRIMARY
        for actual, expected in observed["peers"]
    )

    assert observed["tls_hostnames"] == [SOURCE]

    assert budget.snapshot().retrievals == 1

    print("ACTUAL_OS_DNS=PASS")
    print("ACTUAL_NUMERIC_TCP=PASS")
    print("ACTUAL_PEER_VALIDATION=PASS")
    print("ACTUAL_TRUSTED_TLS=PASS")
    print("ACTUAL_HTTP_RETRIEVAL=PASS")


def test_ac15_mixed_dns_answers_fail_before_connect(observed):
    reject(
        ErrorCode.UNSAFE_DESTINATION,
        MIXED,
    )

    assert observed["dns"] == [
        (
            MIXED,
            tuple(sorted({
                PRIMARY,
                "127.0.0.1",
            })),
        )
    ]

    assert observed["connects"] == []


def test_ac15_ac18_actual_dns_rebinding_rejected(observed):
    # First resolution is globally classified fixture IP.
    # Redirect causes actual second OS lookup returning
    # a loopback answer from the DNS fixture.
    reject(
        ErrorCode.UNSAFE_DESTINATION,
        REBIND,
        "/rebind",
    )

    assert observed["dns"] == [
        (REBIND, (PRIMARY,)),
        (REBIND, ("127.0.0.1",)),
    ]

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]


def test_ac16_actual_wrong_peer_rejected(observed):
    # Fault injection changes the actual TCP endpoint
    # to the other isolated server. getpeername is real.
    observed["force_wrong_peer"] = True

    reject(
        ErrorCode.TRANSPORT_INTEGRITY
    )

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]

    assert observed["peers"] == [
        (SECONDARY, PRIMARY)
    ]

    assert observed["tls_hostnames"] == []


def test_ac17_untrusted_ca_rejected(
    observed,
    monkeypatch,
):
    monkeypatch.delenv(
        "SSL_CERT_FILE",
        raising=False,
    )

    reject(
        ErrorCode.TLS_FAILURE
    )

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]

    assert observed["tls_hostnames"] == [SOURCE]
    assert observed["tls_sockets"] == []


def test_ac17_hostname_mismatch_rejected(observed):
    reject(
        ErrorCode.TLS_FAILURE,
        WRONG,
    )

    assert observed["dns"] == [
        (WRONG, (PRIMARY,))
    ]

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]

    assert observed["tls_hostnames"] == [WRONG]
    assert observed["tls_sockets"] == []


def test_ac18_safe_redirect_revalidates_destination(observed):
    page, budget = retrieve(
        path="/safe-redirect"
    )

    assert page.synthetic is True

    assert page.source_url == (
        f"https://{SOURCE}/safe-redirect"
    )

    assert page.retrieved_url == (
        f"https://{REDIRECT}/ok"
    )

    assert observed["dns"] == [
        (SOURCE, (PRIMARY,)),
        (REDIRECT, (SECONDARY,)),
    ]

    assert observed["connects"] == [
        (PRIMARY, 443),
        (SECONDARY, 443),
    ]

    assert observed["tls_hostnames"] == [
        SOURCE,
        REDIRECT,
    ]

    assert budget.snapshot().retrievals == 2


@pytest.mark.parametrize(
    ("path", "code", "dns_hosts"),
    [
        (
            "/unsafe-redirect",
            ErrorCode.UNSAFE_DESTINATION,
            [SOURCE, MIXED],
        ),
        (
            "/private-redirect",
            ErrorCode.UNSAFE_DESTINATION,
            [SOURCE],
        ),
        (
            "/downgrade",
            ErrorCode.UNSAFE_DESTINATION,
            [SOURCE],
        ),
        (
            "/loop",
            ErrorCode.REDIRECT_LIMIT,
            [SOURCE],
        ),
    ],
)
def test_ac18_adversarial_redirects(
    observed,
    path,
    code,
    dns_hosts,
):
    reject(
        code,
        path=path,
    )

    assert [
        host for host, _ in observed["dns"]
    ] == dns_hosts

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]


@pytest.mark.parametrize(
    ("path", "code"),
    [
        (
            "/duplicate",
            ErrorCode.INVALID_RESPONSE,
        ),
        (
            "/truncated",
            ErrorCode.INVALID_RESPONSE,
        ),
        (
            "/oversized-declared",
            ErrorCode.RESPONSE_TOO_LARGE,
        ),
        (
            "/oversized-stream",
            ErrorCode.RESPONSE_TOO_LARGE,
        ),
        (
            "/compressed",
            ErrorCode.UNSUPPORTED_CONTENT,
        ),
        (
            "/chunked",
            ErrorCode.INVALID_RESPONSE,
        ),
    ],
)
def test_ac19_bounded_http_and_descriptor_cleanup(
    observed,
    path,
    code,
):
    reject(
        code,
        path=path,
    )

    assert observed["connects"] == [
        (PRIMARY, 443)
    ]

    assert len(
        observed["tls_sockets"]
    ) == 1


def test_ac20_production_denial_after_test_seams():
    require_isolated_scope()

    assert socket.getaddrinfo is REAL_GETADDRINFO
    assert pinned._open_socket is REAL_OPEN_SOCKET
    assert pinned.verify_peer is REAL_VERIFY_PEER

    assert ssl.SSLContext.wrap_socket is (
        REAL_WRAP_SOCKET
    )

    denied(
        authorization.require_live_authorization
    )

    denied(
        lambda: integrated.retrieve_live(
            RetrievalRequest(
                url=f"https://{SOURCE}/ok"
            ),
            Budget(),
        )
    )
