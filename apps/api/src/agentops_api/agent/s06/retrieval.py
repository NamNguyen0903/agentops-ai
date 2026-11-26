"""Bounded offline retrieval pipeline."""

from .budgets import (
    Budget,
    MAX_BODY_BYTES,
    MAX_REDIRECTS,
    MAX_RETRIES,
)
from .contracts import (
    RetrievalRequest,
    RetrievedPage,
    validate_contract,
)
from .errors import AcquisitionError, ErrorCode
from .budgets import acquisition_boundary
from .network_policy import (
    validate_url,
    bind_destination,
    public_ip,
    redirect_url,
)
from .transport import (
    FixtureResolver,
    FixtureTransport,
    TransportResponse,
    TransientTransportError,
)


REDIRECTS = {301, 302, 303, 307, 308}
CONTENT_TYPES = {
    "text/plain",
    "text/html",
    "application/xhtml+xml",
}


def fail(code):
    raise AcquisitionError(code)


def validated_headers(response):
    if (
        type(response.headers) is not tuple
        or len(response.headers) > 64
    ):
        fail(ErrorCode.INVALID_RESPONSE)

    headers = {}
    total = 0

    for pair in response.headers:
        if type(pair) is not tuple or len(pair) != 2:
            fail(ErrorCode.INVALID_RESPONSE)

        key, value = pair

        if type(key) is not str or type(value) is not str:
            fail(ErrorCode.INVALID_RESPONSE)

        total += len(key) + len(value)

        if (
            total > 16384
            or not key
            or not key.isascii()
            or not value.isascii()
            or any(
                not (c.isalnum() or c == "-")
                for c in key
            )
            or any(
                ord(c) < 32 or ord(c) == 127
                for c in value
            )
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        key = key.lower()

        if key in headers:
            fail(ErrorCode.INVALID_RESPONSE)

        headers[key] = value.strip()

    return headers


def read_body(response, headers, budget, deadline):
    encoding = headers.get(
        "content-encoding", "identity"
    ).lower()

    if encoding != "identity":
        fail(ErrorCode.UNSUPPORTED_CONTENT)

    content_type = headers.get(
        "content-type", ""
    ).split(";", 1)[0].strip().lower()

    if content_type not in CONTENT_TYPES:
        fail(ErrorCode.UNSUPPORTED_CONTENT)

    if "transfer-encoding" in headers:
        fail(ErrorCode.INVALID_RESPONSE)

    expected_length = None

    if "content-length" in headers:
        value = headers["content-length"]

        if (
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 10
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        expected_length = int(value)

        if expected_length > MAX_BODY_BYTES:
            fail(ErrorCode.RESPONSE_TOO_LARGE)

    if (
        type(response.chunks) is not tuple
        or len(response.chunks) > 4096
    ):
        fail(ErrorCode.INVALID_RESPONSE)

    body = bytearray()

    for chunk in response.chunks:
        budget.check(deadline)

        if type(chunk) is not bytes:
            fail(ErrorCode.INVALID_RESPONSE)

        if len(body) + len(chunk) > MAX_BODY_BYTES:
            fail(ErrorCode.RESPONSE_TOO_LARGE)

        body.extend(chunk)

    if (
        expected_length is not None
        and len(body) != expected_length
    ):
        fail(ErrorCode.INVALID_RESPONSE)

    budget.check(deadline)

    return content_type, bytes(body)


def retrieve_offline(
    request,
    budget,
    *,
    resolver,
    transport,
):
    request = validate_contract(
        RetrievalRequest, request
    )

    if (
        type(resolver) is not FixtureResolver
        or type(transport) is not FixtureTransport
    ):
        fail(ErrorCode.EXTERNAL_DISABLED)

    if type(budget) is not Budget:
        fail(ErrorCode.INVALID_INPUT)

    source = validate_url(request.url)
    current = source

    deadline = budget.operation_deadline()
    redirects = 0
    retries = 0
    visited = {source.url}

    while True:
        budget.check(deadline)

        try:
            target, response = _accounted_hop(
                current, budget, resolver, transport, deadline,
                redirects=redirects,
            )
        except TransientTransportError:
            budget.check(deadline)

            if retries >= MAX_RETRIES:
                fail(ErrorCode.TRANSPORT_FAILURE)

            retries += 1
            continue

        budget.check(deadline)

        if type(response) is not TransportResponse:
            fail(ErrorCode.INVALID_RESPONSE)

        if (
            type(response.status) is not int
            or not 100 <= response.status <= 599
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        if public_ip(response.peer_ip) != target.ip:
            fail(ErrorCode.TRANSPORT_INTEGRITY)

        if current.scheme == "https":
            if (
                response.tls_verified is not True
                or type(response.tls_hostname) is not str
                or response.tls_hostname != current.host
            ):
                fail(ErrorCode.TLS_FAILURE)

        headers = validated_headers(response)

        if response.status in REDIRECTS:
            if redirects >= MAX_REDIRECTS:
                fail(ErrorCode.REDIRECT_LIMIT)

            if "location" not in headers:
                fail(ErrorCode.INVALID_RESPONSE)

            next_destination = redirect_url(
                current,
                headers["location"],
            )

            if next_destination.url in visited:
                fail(ErrorCode.REDIRECT_LIMIT)

            visited.add(next_destination.url)
            redirects += 1
            current = next_destination
            continue

        if response.status != 200:
            fail(ErrorCode.INVALID_RESPONSE)

        content_type, body = read_body(
            response,
            headers,
            budget,
            deadline,
        )

        return RetrievedPage(
            source_url=source.url,
            retrieved_url=current.url,
            content_type=content_type,
            body=body,
            synthetic=True,
        )


@acquisition_boundary("retrieval", hop=True)
def _accounted_hop(current, budget, resolver, transport, deadline, *, redirects):
    budget.check(deadline)
    budget.reserve_retrieval(deadline)
    target = bind_destination(current.url, resolver)
    budget.check(deadline)
    timeout = budget.remaining(deadline)
    try:
        response = transport.send(target, timeout=timeout)
    except TransientTransportError:
        raise
    except Exception:
        # Only transport-body failures are sanitized here. Budget, deadline
        # and DNS policy errors above retain their original error codes.
        raise AcquisitionError(ErrorCode.TRANSPORT_FAILURE) from None
    return target, response
