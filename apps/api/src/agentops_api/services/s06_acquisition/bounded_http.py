"""Bounded HTTP wire processing for isolated pinned retrieval.

One exchange exclusively owns one connected socket.
No proxy, automatic redirects, implicit reconnect, connection
pool, compression, or socket.makefile buffering is used.

The underlying connector remains independently default-deny.
"""

import re
import socket
import ssl
from urllib.parse import urlsplit

from agentops_api.agent.s06.budgets import MAX_BODY_BYTES
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.agent.s06.retrieval import (
    REDIRECTS,
    CONTENT_TYPES,
    validated_headers,
    read_body,
)
from agentops_api.agent.s06.transport import TransportResponse

from . import pinned_transport as pinned
from .transport_failures import transport_failure


MAX_HEADER_BYTES = 16384
MAX_HEADERS = 64
READ_SIZE = 16384

CRLF = bytes((13, 10))
HEADER_END = CRLF * 2


def fail(code):
    raise AcquisitionError(code) from None


def receive(sock, budget, deadline, size):
    budget.check(deadline)

    try:
        sock.settimeout(
            budget.remaining(deadline)
        )

        data = sock.recv(size)

    except (TimeoutError, socket.timeout):
        fail(ErrorCode.DEADLINE_EXCEEDED)

    budget.check(deadline)

    if type(data) is not bytes or len(data) > size:
        fail(ErrorCode.INVALID_RESPONSE)

    return data


def parse_head(data):
    if type(data) is not bytes:
        fail(ErrorCode.INVALID_RESPONSE)

    if len(data) > MAX_HEADER_BYTES:
        fail(ErrorCode.INVALID_RESPONSE)

    lines = data.split(CRLF)

    match = re.fullmatch(
        rb"HTTP/1[.]([01]) ([1-5][0-9]{2})(?: [ -~]*)?",
        lines[0],
    )

    if match is None:
        fail(ErrorCode.INVALID_RESPONSE)

    status = int(match.group(2))

    if status < 200:
        fail(ErrorCode.INVALID_RESPONSE)

    if len(lines) - 1 > MAX_HEADERS:
        fail(ErrorCode.INVALID_RESPONSE)

    headers = []

    for line in lines[1:]:
        if (
            not line
            or line.startswith((b" ", bytes((9,))))
            or b":" not in line
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        name, value = line.split(b":", 1)

        if not re.fullmatch(
            rb"[A-Za-z0-9-]+",
            name,
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        try:
            name = name.decode("ascii")
            value = value.decode("ascii")
        except UnicodeError:
            fail(ErrorCode.INVALID_RESPONSE)

        headers.append(
            (name, value.strip(" "))
        )

    return status, tuple(headers)


def read_head(sock, budget, deadline):
    buffer = bytearray()

    while True:
        budget.check(deadline)

        position = buffer.find(HEADER_END)

        if position >= 0:
            if position + 4 > MAX_HEADER_BYTES:
                fail(ErrorCode.INVALID_RESPONSE)

            status, headers = parse_head(
                bytes(buffer[:position])
            )

            tail = bytes(
                buffer[position + 4:]
            )

            return status, headers, tail

        if len(buffer) >= MAX_HEADER_BYTES:
            fail(ErrorCode.INVALID_RESPONSE)

        chunk = receive(
            sock,
            budget,
            deadline,
            min(
                4096,
                MAX_HEADER_BYTES - len(buffer),
            ),
        )

        if not chunk:
            fail(ErrorCode.INVALID_RESPONSE)

        buffer.extend(chunk)


def declared_length(headers):
    value = headers.get("content-length")

    if value is None:
        return None

    if (
        not value.isascii()
        or not value.isdecimal()
        or len(value) > 10
    ):
        fail(ErrorCode.INVALID_RESPONSE)

    length = int(value)

    if length > MAX_BODY_BYTES:
        fail(ErrorCode.RESPONSE_TOO_LARGE)

    return length


def bounded_body(
    sock,
    initial,
    headers,
    budget,
    deadline,
    *,
    accepted_types=CONTENT_TYPES,
):
    if "transfer-encoding" in headers:
        fail(ErrorCode.INVALID_RESPONSE)

    if headers.get(
        "content-encoding", "identity"
    ).lower() != "identity":
        fail(ErrorCode.UNSUPPORTED_CONTENT)

    content_type = headers.get(
        "content-type", ""
    ).split(";", 1)[0].strip().lower()

    if content_type not in accepted_types:
        fail(ErrorCode.UNSUPPORTED_CONTENT)

    expected = declared_length(headers)

    if len(initial) > MAX_BODY_BYTES:
        fail(ErrorCode.RESPONSE_TOO_LARGE)

    if expected is not None and len(initial) > expected:
        fail(ErrorCode.INVALID_RESPONSE)

    body = bytearray(initial)

    while expected is None or len(body) < expected:
        budget.check(deadline)

        size = min(
            READ_SIZE,
            MAX_BODY_BYTES - len(body) + 1,
        )

        if expected is not None:
            size = min(
                size,
                expected - len(body),
            )

        chunk = receive(
            sock,
            budget,
            deadline,
            size,
        )

        if not chunk:
            if expected is not None:
                fail(ErrorCode.INVALID_RESPONSE)

            break

        body.extend(chunk)

        if len(body) > MAX_BODY_BYTES:
            fail(ErrorCode.RESPONSE_TOO_LARGE)

    budget.check(deadline)

    return bytes(body)


def request_bytes(destination):
    parsed = urlsplit(destination.url)

    path = parsed.path or "/"

    if parsed.query:
        path += "?" + parsed.query

    if (
        not path.startswith("/")
        or not path.isascii()
        or any(ord(char) <= 32 for char in path)
        or chr(127) in path
    ):
        fail(ErrorCode.UNSAFE_DESTINATION)

    host = destination.host

    if ":" in host:
        host = "[" + host + "]"

    return CRLF.join([
        ("GET " + path + " HTTP/1.1").encode("ascii"),
        ("Host: " + host).encode("ascii"),
        b"Accept-Encoding: identity",
        b"Accept: text/plain,text/html,application/xhtml+xml",
        b"Connection: close",
        b"User-Agent: AgentOpsAI-Development/0.1",
        b"",
        b"",
    ])


def exchange(target, budget, deadline):
    destination, ip = pinned.validated_target(target)

    sock = None

    try:
        sock = pinned._connect_bound(
            target,
            budget,
            deadline,
        )

        pinned.verify_peer(sock, ip)

        budget.check(deadline)

        sock.settimeout(
            budget.remaining(deadline)
        )

        sock.sendall(
            request_bytes(destination)
        )

        budget.check(deadline)

        status, pairs, initial = read_head(
            sock,
            budget,
            deadline,
        )

        metadata = TransportResponse(
            status=status,
            headers=pairs,
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

        if status in REDIRECTS:
            if "transfer-encoding" in headers:
                fail(ErrorCode.INVALID_RESPONSE)

            if headers.get(
                "content-encoding", "identity"
            ).lower() != "identity":
                fail(ErrorCode.UNSUPPORTED_CONTENT)

            declared_length(headers)

            budget.check(deadline)

            return metadata

        if status != 200:
            fail(ErrorCode.INVALID_RESPONSE)

        body = bounded_body(
            sock,
            initial,
            headers,
            budget,
            deadline,
        )

        response = TransportResponse(
            status=status,
            headers=pairs,
            chunks=(body,) if body else (),
            peer_ip=ip,
            tls_verified=metadata.tls_verified,
            tls_hostname=metadata.tls_hostname,
        )

        read_body(
            response,
            headers,
            budget,
            deadline,
        )

        budget.check(deadline)

        return response

    except AcquisitionError:
        raise

    except (TimeoutError, socket.timeout):
        fail(ErrorCode.DEADLINE_EXCEEDED)

    except ssl.SSLError:
        fail(ErrorCode.TLS_FAILURE)

    except OSError as exc:
        raise transport_failure(exc) from None

    except Exception:
        fail(ErrorCode.INVALID_RESPONSE)

    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
