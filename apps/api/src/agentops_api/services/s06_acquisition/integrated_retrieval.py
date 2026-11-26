"""Integrated fixture DNS, redirect and bounded wire retrieval.

No public live resolver or external connector is enabled.
Only the existing fixture resolver is accepted.
"""

from agentops_api.agent.s06.budgets import (
    Budget,
    MAX_REDIRECTS,
    MAX_RETRIES,
)
from agentops_api.agent.s06.contracts import (
    RetrievalRequest,
    RetrievedPage,
    validate_contract,
)
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.agent.s06.network_policy import (
    bind_destination,
    public_ip,
    redirect_url,
    validate_url,
)
from agentops_api.agent.s06.retrieval import (
    REDIRECTS,
    validated_headers,
    read_body,
)
from agentops_api.agent.s06.transport import (
    FixtureResolver,
    TransportResponse,
)

from .authorization import require_live_authorization
from agentops_api.agent.durable_hooks import acquisition_boundary
from .bounded_http import exchange
from .resolver import DeadlineResolver
from .transport_failures import RetryableTransportFailure


def fail(code):
    raise AcquisitionError(code) from None


def retrieve_live(request, budget):
    require_live_authorization()

    if type(budget) is not Budget:
        fail(ErrorCode.INVALID_INPUT)

    request = validate_contract(
        RetrievalRequest,
        request,
    )

    deadline = budget.operation_deadline()

    resolver = DeadlineResolver(
        budget,
        deadline,
    )

    return _retrieve(
        request,
        budget,
        resolver=resolver,
        deadline=deadline,
    )


def retrieve_isolated(
    request,
    budget,
    *,
    resolver,
):
    if type(resolver) is not FixtureResolver:
        fail(ErrorCode.EXTERNAL_DISABLED)

    if type(budget) is not Budget:
        fail(ErrorCode.INVALID_INPUT)

    request = validate_contract(
        RetrievalRequest,
        request,
    )

    return _retrieve(
        request,
        budget,
        resolver=resolver,
        deadline=budget.operation_deadline(),
        synthetic=True,
    )


def _retrieve(
    request,
    budget,
    *,
    resolver,
    deadline,
    synthetic=False,
):
    if synthetic is True:
        if type(resolver) is not FixtureResolver:
            fail(ErrorCode.EXTERNAL_DISABLED)
    elif synthetic is False:
        require_live_authorization()

        if type(resolver) is not DeadlineResolver:
            fail(ErrorCode.EXTERNAL_DISABLED)
    else:
        fail(ErrorCode.INVALID_INPUT)

    source = validate_url(request.url)
    current = source


    redirects = 0
    retries = 0
    visited = {source.url}

    while True:
        budget.check(deadline)

        try:
            target, response = _accounted_hop(
                current, budget, resolver, deadline,
                redirects=redirects,
            )

        except AcquisitionError as exc:
            budget.check(deadline)

            if (
                type(exc) is RetryableTransportFailure
                and retries < MAX_RETRIES
            ):
                retries += 1
                continue

            raise

        budget.check(deadline)

        if type(response) is not TransportResponse:
            fail(ErrorCode.INVALID_RESPONSE)

        if (
            type(response.status) is not int
            or not 200 <= response.status <= 599
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

            location = headers.get("location")

            if not location:
                fail(ErrorCode.INVALID_RESPONSE)

            destination = redirect_url(
                current,
                location,
            )

            if type(destination) is str:
                destination = validate_url(destination)
            else:
                destination = validate_url(destination.url)

            if destination.url in visited:
                fail(ErrorCode.REDIRECT_LIMIT)

            visited.add(destination.url)

            current = destination
            redirects += 1

            continue

        if response.status != 200:
            fail(ErrorCode.INVALID_RESPONSE)

        content_type, body = read_body(
            response,
            headers,
            budget,
            deadline,
        )

        if not synthetic:
            # Real-evidence contracts are not enabled in S06.
            fail(ErrorCode.EXTERNAL_DISABLED)

        return validate_contract(
            RetrievedPage,
            {
                "source_url": source.url,
                "retrieved_url": current.url,
                "content_type": content_type,
                "body": body,
                "synthetic": synthetic,
            },
            output=True,
        )


@acquisition_boundary("retrieval", hop=True)
def _accounted_hop(current, budget, resolver, deadline, *, redirects):
    budget.check(deadline)
    budget.reserve_retrieval(deadline)
    target = bind_destination(current.url, resolver)
    budget.check(deadline)
    response = exchange(target, budget, deadline)
    return target, response
