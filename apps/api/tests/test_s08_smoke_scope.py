"""Offline scope policy tests; no external I/O."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agentops_api.agent.s06.contracts import (
    SearchRequest, RetrievalRequest,
)
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.provider_accounting import query_digest
from agentops_api.services.real_evidence import retrieval_digest
from agentops_api.services.smoke_scope import (
    prepare_scope, proposed_requests,
)
from agentops_api.services.s06_acquisition.authorization import (
    require_live_authorization,
)


def fixture():
    now = datetime.now(timezone.utc)
    search, retrieval = proposed_requests()

    handle = SimpleNamespace(
        owner_id=uuid4(), task_id=uuid4(),
        attempt_id=uuid4(), generation=1,
    )

    grant = SimpleNamespace(
        id=uuid4(),
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        provider_name="tavily",
        endpoint="https://api.tavily.com/search",
        query_sha256=query_digest(search),
        retrieval_url_sha256=retrieval_digest(retrieval),
        lock_marker=0,
        max_search_requests=1,
        max_provider_credits=1,
        max_retrieval_requests=1,
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(seconds=60),
    )
    return handle, grant, search, retrieval, now


def test_exact_scope():
    h, g, s, r, now = fixture()
    scope = prepare_scope(h, g, s, r, now)
    assert scope.grant_id == g.id
    scope.check(h, "search", s)
    scope.check(h, "retrieval", r)


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "attempt_id", "generation",
])
def test_handle_substitution_rejected(field):
    h, g, s, r, now = fixture()
    scope = prepare_scope(h, g, s, r, now)
    setattr(h, field, 2 if field == "generation" else uuid4())

    with pytest.raises(BudgetRejected):
        scope.check(h, "search", s)


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "query_sha256",
    "retrieval_url_sha256", "max_search_requests",
    "max_provider_credits", "max_retrieval_requests",
])
def test_grant_substitution_rejected(field):
    h, g, s, r, now = fixture()

    if field.endswith("_id"):
        value = uuid4()
    elif field.endswith("sha256"):
        value = bytes(32)
    else:
        value = 2

    setattr(g, field, value)

    with pytest.raises(BudgetRejected):
        prepare_scope(h, g, s, r, now)


@pytest.mark.parametrize("case", ["query", "max_results", "url"])
def test_request_substitution_rejected(case):
    h, g, s, r, now = fixture()
    scope = prepare_scope(h, g, s, r, now)

    if case == "query":
        kind, request = "search", SearchRequest(query="Another query")
    elif case == "max_results":
        kind, request = "search", SearchRequest(
            query=s.query, max_results=6
        )
    else:
        kind, request = "retrieval", RetrievalRequest(
            url="https://example.com/"
        )

    with pytest.raises(BudgetRejected):
        scope.check(h, kind, request)


def test_expired_scope_rejected():
    h, g, s, r, now = fixture()

    scope = replace(
        prepare_scope(h, g, s, r, now),
        deadline=monotonic() - 1,
    )

    with pytest.raises(BudgetRejected):
        scope.check(h, "search", s)


def test_scope_does_not_activate_external_execution():
    h, g, s, r, now = fixture()
    prepare_scope(h, g, s, r, now)

    with pytest.raises(AcquisitionError) as error:
        require_live_authorization()

    assert error.value.code is ErrorCode.EXTERNAL_DISABLED
