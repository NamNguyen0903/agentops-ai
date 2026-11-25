"""Focused offline acquisition tests."""

from dataclasses import replace
from uuid import uuid4

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import (
    AcquisitionContext,
    SearchRequest,
    RetrievalRequest,
    validate_contract,
)
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.agent.s06.providers import (
    FixtureSearchProvider,
    search_offline,
)
from agentops_api.agent.s06.retrieval import retrieve_offline
from agentops_api.agent.s06.transport import (
    FixtureResolver,
    FixtureTransport,
    TransportResponse,
    TransientTransportError,
)


def expect(code, function, *args, **kwargs):
    with pytest.raises(AcquisitionError) as exc:
        function(*args, **kwargs)

    assert exc.value.code is code
    assert str(exc.value) == code.value


def resolver():
    return FixtureResolver({
        "example.com": ("93.184.216.34",),
        "example.org": ("1.1.1.1",),
    })


def response(**changes):
    base = TransportResponse(
        status=200,
        headers=(("Content-Type", "text/plain"),),
        chunks=(b"synthetic fixture",),
        peer_ip="93.184.216.34",
        tls_verified=True,
        tls_hostname="example.com",
    )
    return replace(base, **changes)


def fetch(responses, budget=None):
    transport = FixtureTransport(tuple(responses))

    page = retrieve_offline(
        RetrievalRequest(url="https://example.com/"),
        budget if budget is not None else Budget(),
        resolver=resolver(),
        transport=transport,
    )

    return page, transport


@pytest.mark.parametrize("payload", [
    {"query": ""},
    {"query": "   "},
    {"query": 12},
    {"query": "test", "max_results": True},
    {"query": "test", "max_results": "3"},
    {"query": "test", "max_results": 11},
    {"query": "test", "max_results": 0},
    {"query": "x" * 1025},
    {"query": "a" + chr(10) + "b"},
    {"query": "test", "allow_external": True},
])
def test_strict_request(payload):
    expect(
        ErrorCode.INVALID_INPUT,
        validate_contract,
        SearchRequest,
        payload,
    )


def test_context():
    context = AcquisitionContext(
        task_id=uuid4(),
        execution_id=uuid4(),
    )
    assert context.task_id != context.execution_id


def test_construct_bypass_rejected():
    value = SearchRequest.model_construct(
        query="", max_results=10
    )
    expect(
        ErrorCode.INVALID_INPUT,
        search_offline,
        value,
        Budget(),
    )


def test_deterministic_search():
    request = SearchRequest(query="market research")

    first = search_offline(request, Budget())
    second = search_offline(request, Budget())

    assert first == second
    assert first.synthetic is True


def test_unknown_provider():
    expect(
        ErrorCode.EXTERNAL_DISABLED,
        search_offline,
        SearchRequest(query="test"),
        Budget(),
        provider=object(),
    )


@pytest.mark.parametrize("payload", [
    {"hits": "invalid"},
    {"hits": (), "synthetic": False},
    {"hits": (), "unexpected": True},
])
def test_invalid_provider_output(monkeypatch, payload):
    monkeypatch.setattr(
        FixtureSearchProvider,
        "search",
        lambda *args, **kwargs: payload,
    )

    expect(
        ErrorCode.INVALID_RESPONSE,
        search_offline,
        SearchRequest(query="test"),
        Budget(),
    )


def test_provider_failure_sanitized(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_SECRET")

    monkeypatch.setattr(
        FixtureSearchProvider, "search", broken
    )

    expect(
        ErrorCode.PROVIDER_FAILURE,
        search_offline,
        SearchRequest(query="test"),
        Budget(),
    )


def test_search_budget():
    budget = Budget()

    for _ in range(6):
        search_offline(
            SearchRequest(query="test"), budget
        )

    expect(
        ErrorCode.BUDGET_EXHAUSTED,
        search_offline,
        SearchRequest(query="test"),
        budget,
    )

    assert budget.snapshot().searches == 6


def test_retrieval_budget():
    budget = Budget()

    for _ in range(12):
        fetch([response()], budget)

    expect(
        ErrorCode.BUDGET_EXHAUSTED,
        fetch,
        [response()],
        budget,
    )

    assert budget.snapshot().retrievals == 12


def test_valid_retrieval():
    page, transport = fetch([response()])

    assert page.synthetic is True
    assert page.body == b"synthetic fixture"
    assert transport.requests[0].ip == "93.184.216.34"


def test_redirect_rebinds():
    budget = Budget()

    page, transport = fetch([
        response(
            status=302,
            headers=(
                ("Location", "https://example.org/page"),
            ),
            chunks=(),
        ),
        response(
            peer_ip="1.1.1.1",
            tls_hostname="example.org",
        ),
    ], budget)

    assert page.retrieved_url == "https://example.org/page"
    assert transport.requests[1].ip == "1.1.1.1"
    assert budget.snapshot().retrievals == 2


def test_retry_counted():
    budget = Budget()

    fetch([
        TransientTransportError(),
        response(),
    ], budget)

    assert budget.snapshot().retrievals == 2


def test_retry_exhaustion():
    budget = Budget()

    expect(
        ErrorCode.TRANSPORT_FAILURE,
        fetch,
        [
            TransientTransportError(),
            TransientTransportError(),
        ],
        budget,
    )

    assert budget.snapshot().retrievals == 2


def test_operation_deadline():
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    deadline = budget.operation_deadline()

    now[0] = 15.0

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        budget.check,
        deadline,
    )


def test_execution_deadline():
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 180.0

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        budget.operation_deadline,
    )


def test_delayed_response(monkeypatch):
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    original = FixtureTransport.send

    def delayed(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        now[0] = 16.0
        return result

    monkeypatch.setattr(
        FixtureTransport, "send", delayed
    )

    expect(
        ErrorCode.DEADLINE_EXCEEDED,
        fetch,
        [response()],
        budget,
    )
