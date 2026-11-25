"""Tavily REST adapter with isolated verification entry point."""

import json
from dataclasses import dataclass
from math import isfinite

import httpx

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import (
    SearchHit,
    SearchRequest,
    validate_contract,
)
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.agent.s06.network_policy import validate_url

from .authorization import require_live_authorization
from .provider_transport import TavilyPinnedTransport
from .credentials import (
    read_tavily_credential,
    authorization_header,
)


ENDPOINT = "https://api.tavily.com/search"
MAX_JSON_BYTES = 1048576


@dataclass(frozen=True, slots=True)
class VerifiedSearchResponse:
    hits: tuple[SearchHit, ...]
    credits: int
    synthetic: bool


def fail(code):
    raise AcquisitionError(code)


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            fail(ErrorCode.INVALID_RESPONSE)

        result[key] = value

    return result


def reject_constant(value):
    fail(ErrorCode.INVALID_RESPONSE)


def decode_json(body):
    try:
        return json.loads(
            body.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except Exception:
        fail(ErrorCode.INVALID_RESPONSE)


def map_response(payload, max_results):
    if type(payload) is not dict:
        fail(ErrorCode.INVALID_RESPONSE)

    for name in ("answer", "raw_content"):
        if payload.get(name) not in (None, ""):
            fail(ErrorCode.INVALID_RESPONSE)

    if payload.get("images") not in (None, []):
        fail(ErrorCode.INVALID_RESPONSE)

    parameters = payload.get("auto_parameters")

    if parameters is not None:
        if type(parameters) is not dict:
            fail(ErrorCode.INVALID_RESPONSE)

        if parameters.get("search_depth", "basic") != "basic":
            fail(ErrorCode.INVALID_RESPONSE)

    usage = payload.get("usage")

    if (
        type(usage) is not dict
        or type(usage.get("credits")) is not int
        or usage["credits"] != 1
    ):
        fail(ErrorCode.INVALID_RESPONSE)

    results = payload.get("results")

    if type(results) is not list or len(results) > max_results:
        fail(ErrorCode.INVALID_RESPONSE)

    hits = []

    for item in results:
        if type(item) is not dict:
            fail(ErrorCode.INVALID_RESPONSE)

        if item.get("raw_content") not in (None, ""):
            fail(ErrorCode.INVALID_RESPONSE)

        if item.get("images") not in (None, []):
            fail(ErrorCode.INVALID_RESPONSE)

        score = item.get("score")

        if (
            type(score) not in {int, float}
            or not 0 <= score <= 1
            or not isfinite(score)
        ):
            fail(ErrorCode.INVALID_RESPONSE)

        hit = validate_contract(
            SearchHit,
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content"),
            },
            output=True,
        )

        validate_url(hit.url)
        hits.append(hit)

    return VerifiedSearchResponse(
        hits=tuple(hits),
        credits=1,
        synthetic=True,
    )


def search_live(request, budget):
    require_live_authorization()

    if type(budget) is not Budget:
        fail(ErrorCode.INVALID_INPUT)

    request = validate_contract(
        SearchRequest,
        request,
    )

    deadline = budget.operation_deadline()

    credential = read_tavily_credential()

    budget.check(deadline)

    return _execute(
        request,
        budget,
        deadline=deadline,
        header=authorization_header(credential),
        transport=None,
        synthetic=False,
    )


def search_isolated(
    request,
    budget,
    *,
    transport,
):
    if type(transport) is not httpx.MockTransport:
        fail(ErrorCode.EXTERNAL_DISABLED)

    if type(budget) is not Budget:
        fail(ErrorCode.INVALID_INPUT)

    request = validate_contract(
        SearchRequest,
        request,
    )

    return _execute(
        request,
        budget,
        deadline=budget.operation_deadline(),
        header="Bearer isolated-test-token",
        transport=transport,
        synthetic=True,
    )


def prepare_basic_request(request):
    """Build the existing basic request without I/O."""
    request = validate_contract(SearchRequest, request)
    return {'query': request.query, 'search_depth': 'basic', 'topic': 'general', 'max_results': request.max_results, 'auto_parameters': False, 'include_answer': False, 'include_raw_content': False, 'include_images': False, 'include_image_descriptions': False, 'include_favicon': False, 'include_usage': True}


def _execute(
    request,
    budget,
    *,
    deadline,
    header,
    transport,
    synthetic,
):
    if synthetic is not True:
        require_live_authorization()
    elif type(transport) is not httpx.MockTransport:
        fail(ErrorCode.EXTERNAL_DISABLED)

    if synthetic is not True:
        if transport is not None:
            fail(ErrorCode.EXTERNAL_DISABLED)

        transport = TavilyPinnedTransport(
            budget,
            deadline,
        )

    budget.reserve_search(deadline)
    timeout = budget.remaining(deadline)

    payload = prepare_basic_request(request)

    try:
        with httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=timeout,
        ) as client:
            with client.stream(
                "POST",
                ENDPOINT,
                headers={
                    "Authorization": header,
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
                json=payload,
            ) as response:
                budget.check(deadline)

                pairs = response.headers.multi_items()

                if (
                    len(pairs) > 64
                    or sum(
                        len(key) + len(value)
                        for key, value in pairs
                    ) > 16384
                    or len({
                        key.lower()
                        for key, value in pairs
                    }) != len(pairs)
                ):
                    fail(ErrorCode.INVALID_RESPONSE)

                if response.status_code != 200:
                    fail(ErrorCode.PROVIDER_FAILURE)

                if (
                    response.headers.get(
                        "content-encoding", "identity"
                    ).lower() != "identity"
                ):
                    fail(ErrorCode.UNSUPPORTED_CONTENT)

                content_type = response.headers.get(
                    "content-type", ""
                ).split(";", 1)[0].strip().lower()

                if content_type != "application/json":
                    fail(ErrorCode.UNSUPPORTED_CONTENT)

                declared = response.headers.get("content-length")

                if declared is not None:
                    if (
                        not declared.isascii()
                        or not declared.isdecimal()
                        or len(declared) > 10
                    ):
                        fail(ErrorCode.INVALID_RESPONSE)

                    if int(declared) > MAX_JSON_BYTES:
                        fail(ErrorCode.RESPONSE_TOO_LARGE)

                body = bytearray()

                # MockTransport may supply preloaded content.
                # Streaming here verifies adapter processing,
                # not network-side allocation behavior.
                iterator = (
                    response.iter_bytes(chunk_size=16384)
                    if response.is_stream_consumed
                    else response.iter_raw(chunk_size=16384)
                )

                for chunk in iterator:
                    budget.check(deadline)

                    if len(body) + len(chunk) > MAX_JSON_BYTES:
                        fail(ErrorCode.RESPONSE_TOO_LARGE)

                    body.extend(chunk)

                if declared is not None and len(body) != int(declared):
                    fail(ErrorCode.INVALID_RESPONSE)

                budget.check(deadline)

    except AcquisitionError:
        raise
    except Exception:
        raise AcquisitionError(
            ErrorCode.PROVIDER_FAILURE
        ) from None

    result = map_response(
        decode_json(bytes(body)),
        request.max_results,
    )

    budget.check(deadline)
    return VerifiedSearchResponse(
        hits=result.hits,
        credits=result.credits,
        synthetic=synthetic,
    )
