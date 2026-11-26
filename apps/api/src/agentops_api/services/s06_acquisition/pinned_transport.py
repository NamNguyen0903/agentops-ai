"""Destination-bound HTTP connector; live entry remains disabled."""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

from agentops_api.agent.s06.budgets import Budget, MAX_BODY_BYTES
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.network_policy import (
    BoundDestination,
    public_ip,
    validate_url,
)
from agentops_api.agent.s06.retrieval import (
    REDIRECTS,
    validated_headers,
    read_body,
)
from agentops_api.agent.s06.transport import TransportResponse

from .authorization import require_live_authorization
from .transport_failures import transport_failure


def fail(code):
    raise AcquisitionError(code)


def validated_target(target):
    if type(target) is not BoundDestination:
        fail(ErrorCode.INVALID_INPUT)

    destination = validate_url(target.destination.url)

    if destination != target.destination:
        fail(ErrorCode.UNSAFE_DESTINATION)

    ip = public_ip(target.ip)

    try:
        literal = ipaddress.ip_address(destination.host)
    except ValueError:
        literal = None

    if literal is not None and str(literal) != ip:
        fail(ErrorCode.TRANSPORT_INTEGRITY)

    return destination, ip


def tls_context():
    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH
    )

    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED

    return context


def verify_peer(sock, expected_ip):
    actual = public_ip(sock.getpeername()[0])

    if actual != expected_ip:
        fail(ErrorCode.TRANSPORT_INTEGRITY)


def _open_socket(family, kind):
    require_live_authorization()

    return socket.socket(family, kind)


def _connect_bound(
    target,
    budget,
    deadline,
    *,
    _smoke_kind=None,
    _smoke_ticket=None,
):
    """Internal connector; no direct graph/API integration."""
    destination, ip = validated_target(target)

    address = ipaddress.ip_address(ip)

    family = (
        socket.AF_INET6
        if address.version == 6
        else socket.AF_INET
    )

    endpoint = (
        (ip, destination.port, 0, 0)
        if address.version == 6
        else (ip, destination.port)
    )

    raw = None
    active = None

    try:
        if _smoke_kind is None and _smoke_ticket is None:
            raw = _open_socket(family, socket.SOCK_STREAM)
        else:
            from agentops_api.services.smoke_runtime import authorize_network

            deadline = min(
                deadline,
                authorize_network(
                    _smoke_ticket,
                    _smoke_kind,
                    destination.url,
                    "connect",
                ),
            )
            budget.check(deadline)
            raw = socket.socket(family, socket.SOCK_STREAM)
        active = raw

        raw.settimeout(budget.remaining(deadline))

        # Numeric IP only: no second hostname resolution.
        raw.connect(endpoint)

        verify_peer(raw, ip)
        budget.check(deadline)

        if destination.scheme == "https":
            raw.settimeout(budget.remaining(deadline))

            context = tls_context()

            budget.check(deadline)

            raw.settimeout(
                budget.remaining(deadline)
            )

            active = context.wrap_socket(
                raw,
                server_hostname=destination.host,
            )

            verify_peer(active, ip)
            budget.check(deadline)

        return active

    except ssl.SSLError:
        if active is not None:
            active.close()

        fail(ErrorCode.TLS_FAILURE)

    except AcquisitionError:
        if active is not None:
            active.close()

        raise

    except OSError as exc:
        if active is not None:
            active.close()

        raise transport_failure(exc) from None

    except Exception:
        if active is not None:
            active.close()

        fail(ErrorCode.TRANSPORT_FAILURE)


def _request_bound(
    target,
    budget,
    deadline,
):
    """One controlled HTTP exchange; no automatic redirect."""
    destination, ip = validated_target(target)

    conn = http.client.HTTPConnection(
        destination.host,
        destination.port,
        timeout=budget.remaining(deadline),
    )

    response = None
    active_socket = None

    try:
        active_socket = _connect_bound(
            target,
            budget,
            deadline,
        )

        conn.sock = active_socket

        # Never let HTTPConnection reconnect to a hostname.
        conn.auto_open = 0

        verify_peer(conn.sock, ip)

        parsed = urlsplit(destination.url)
        path = parsed.path or "/"

        if parsed.query:
            path += "?" + parsed.query

        host = destination.host

        if ":" in host:
            host = "[" + host + "]"

        conn.sock.settimeout(
            budget.remaining(deadline)
        )

        conn.request(
            "GET",
            path,
            headers={
                "Host": host,
                "Accept-Encoding": "identity",
                "Accept": "text/html,text/plain,application/xhtml+xml",
                "Connection": "close",
                "User-Agent": "AgentOpsAI-Development/0.1",
            },
        )

        conn.sock.settimeout(
            budget.remaining(deadline)
        )

        response = conn.getresponse()
        budget.check(deadline)

        metadata = TransportResponse(
            status=response.status,
            headers=tuple(response.getheaders()),
            chunks=(),
            peer_ip=ip,
            tls_verified=destination.scheme == "https",
            tls_hostname=(
                destination.host
                if destination.scheme == "https"
                else None
            ),
        )

        headers = validated_headers(metadata)

        # Return redirect metadata without consuming redirect bodies.
        if response.status in REDIRECTS:
            return metadata

        if response.status != 200:
            fail(ErrorCode.INVALID_RESPONSE)

        if headers.get(
            "content-encoding", "identity"
        ).lower() != "identity":
            fail(ErrorCode.UNSUPPORTED_CONTENT)

        if "transfer-encoding" in headers:
            fail(ErrorCode.INVALID_RESPONSE)

        content_type = headers.get(
            "content-type", ""
        ).split(";", 1)[0].strip().lower()

        if content_type not in {
            "text/plain",
            "text/html",
            "application/xhtml+xml",
        }:
            fail(ErrorCode.UNSUPPORTED_CONTENT)

        declared = headers.get("content-length")

        if declared is not None:
            if (
                not declared.isascii()
                or not declared.isdecimal()
                or len(declared) > 10
            ):
                fail(ErrorCode.INVALID_RESPONSE)

            if int(declared) > MAX_BODY_BYTES:
                fail(ErrorCode.RESPONSE_TOO_LARGE)

        total = 0
        chunks = []

        while not response.isclosed():
            budget.check(deadline)

            active_socket.settimeout(
                budget.remaining(deadline)
            )

            chunk = response.read1(
                min(16384, MAX_BODY_BYTES - total + 1)
            )

            budget.check(deadline)

            if not chunk:
                break

            total += len(chunk)

            if total > MAX_BODY_BYTES:
                fail(ErrorCode.RESPONSE_TOO_LARGE)

            chunks.append(chunk)

            if len(chunks) > 4096:
                fail(ErrorCode.INVALID_RESPONSE)

        result = TransportResponse(
            status=metadata.status,
            headers=metadata.headers,
            chunks=tuple(chunks),
            peer_ip=metadata.peer_ip,
            tls_verified=metadata.tls_verified,
            tls_hostname=metadata.tls_hostname,
        )

        read_body(result, headers, budget, deadline)

        return result

    except AcquisitionError:
        raise

    except ssl.SSLError:
        fail(ErrorCode.TLS_FAILURE)

    except Exception:
        fail(ErrorCode.TRANSPORT_FAILURE)

    finally:
        if response is not None:
            response.close()

        conn.close()

        if active_socket is not None:
            active_socket.close()


def retrieve_live(request, budget):
    require_live_authorization()

    from .integrated_retrieval import retrieve_live as execute

    return execute(request, budget)
