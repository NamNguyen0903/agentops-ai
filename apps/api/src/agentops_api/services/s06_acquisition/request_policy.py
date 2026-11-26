"""Application-owned S08 Basic Search request policy."""

import json

from agentops_api.agent.s06.contracts import (
    SearchRequest,
    validate_contract,
)
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)

MAX_REQUEST_BYTES = 16384


def prepare_basic_request(request):
    request = validate_contract(SearchRequest, request)

    return {
        "query": request.query,
        "search_depth": "basic",
        "topic": "general",
        "max_results": request.max_results,
        "auto_parameters": False,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_favicon": False,
        "include_usage": True,
    }


def _reject():
    raise AcquisitionError(ErrorCode.INVALID_INPUT) from None


def _unique_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            _reject()

        result[key] = value

    return result


def _reject_constant(_value):
    _reject()


def validate_basic_wire_request(body):
    """Validate the wire payload without granting authorization."""

    if (
        type(body) is not bytes
        or not 1 <= len(body) <= MAX_REQUEST_BYTES
    ):
        _reject()

    try:
        value = json.loads(
            body.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )

        if type(value) is not dict:
            _reject()

        if (
            type(value.get("query")) is not str
            or type(value.get("max_results")) is not int
        ):
            _reject()

        request = SearchRequest(
            query=value["query"],
            max_results=value["max_results"],
        )

        expected = prepare_basic_request(request)

        if set(value) != set(expected):
            _reject()

        for key, required in expected.items():
            actual = value[key]

            if (
                type(actual) is not type(required)
                or actual != required
            ):
                _reject()

    except Exception:
        _reject()

    return request
