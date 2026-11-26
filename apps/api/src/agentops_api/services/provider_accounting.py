"""S08 provider scope assessment and synthetic accounting.

No credentials, grant issuance, external I/O or live dispatch
authority is exposed by this module.
"""

import json
from datetime import timedelta
from hashlib import sha256

from agentops_api.agent.s06.contracts import (
    SearchRequest,
    validate_contract,
)
from agentops_api.services.s06_acquisition.request_policy import (
    prepare_basic_request,
)
from agentops_api.services.execution_budget import BudgetRejected


PROVIDER = "tavily"
ENDPOINT = "https://api.tavily.com/search"


def request_digest(request):
    payload = prepare_basic_request(request)
    wire = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(wire).digest()


def query_digest(request):
    request = validate_contract(SearchRequest, request)
    return sha256(request.query.encode("utf-8")).digest()


def synthetic_reservation_fields(request):
    return {
        "acquisition_origin": "synthetic",
        "provider_name": PROVIDER,
        "reserved_provider_credits": 1,
        "observed_provider_credits": None,
        "request_sha256": request_digest(request),
        "smoke_grant_id": None,
    }


def assess_search_scope(grant, task, rows, request, now, deadline):
    """Assess policy only; the result cannot authorize dispatch.

    A future live path must obtain and consume its own committed
    authority within a separately approved execution boundary.
    """
    if grant is None:
        raise BudgetRejected("smoke_grant_missing")

    if (
        grant.owner_id != task.owner_id
        or grant.task_id != task.id
        or grant.provider_name != PROVIDER
        or grant.endpoint != ENDPOINT
        or grant.query_sha256 != query_digest(request)
        or grant.lock_marker != 0
        or not grant.issued_at <= now < grant.expires_at
        or grant.expires_at > grant.issued_at + timedelta(minutes=15)
        or type(grant.max_search_requests) is not int
        or not 1 <= grant.max_search_requests <= 6
        or type(grant.max_provider_credits) is not int
        or grant.max_provider_credits != grant.max_search_requests
    ):
        raise BudgetRejected("smoke_scope_rejected")

    count = 0
    credits = 0

    for row in rows:
        if row.smoke_grant_id != grant.id:
            if row.acquisition_origin == "live":
                raise BudgetRejected("provider_accounting_integrity")
            continue

        if (
            row.owner_id != task.owner_id
            or row.task_id != task.id
            or row.acquisition_origin != "live"
        ):
            raise BudgetRejected("provider_accounting_integrity")

        if row.kind == "retrieval":
            continue

        if (
            row.kind != "search"
            or row.provider_name != PROVIDER
            or type(row.reserved_provider_credits) is not int
            or row.reserved_provider_credits != 1
            or row.retry_ordinal != 0
            or row.retry_eligible
            or row.status not in {
                "reserved", "dispatching", "succeeded",
                "failed", "indeterminate",
            }
        ):
            raise BudgetRejected("provider_accounting_integrity")

        # Every reservation consumes allowance permanently.
        # No refund based on failure or unknown remote outcome.
        count += 1
        credits += row.reserved_provider_credits

    if (
        count >= grant.max_search_requests
        or credits >= grant.max_provider_credits
    ):
        raise BudgetRejected("provider_allowance_exhausted")

    bounded_deadline = min(deadline, grant.expires_at)

    if bounded_deadline <= now:
        raise BudgetRejected("operation_deadline_expired")

    return bounded_deadline


def plan_smoke_search(grant, task, rows, request, now, deadline):
    """Calculate reservation fields under the caller's DB locks.

    This function grants no permission and performs no I/O.
    The execution service must enforce its independent live gate.
    """
    from agentops_api.services.execution_budget import require_uuid

    bounded_deadline = assess_search_scope(
        grant, task, rows, request, now, deadline
    )

    require_uuid(grant.id)

    fields = synthetic_reservation_fields(request)
    fields["acquisition_origin"] = "live"
    fields["smoke_grant_id"] = grant.id

    return bounded_deadline, fields


def observed_provider_credits(result, *, expected_origin):
    """Validate a locally observed result without authorizing settlement."""
    from agentops_api.services.s06_acquisition.tavily import (
        VerifiedSearchResponse,
    )

    if expected_origin not in {"synthetic", "live"}:
        raise BudgetRejected("provider_origin_invalid")

    if (
        type(result) is not VerifiedSearchResponse
        or result.synthetic is not (expected_origin == "synthetic")
        or type(result.credits) is not int
        or result.credits != 1
    ):
        raise BudgetRejected("provider_usage_invalid")

    return result.credits


def observed_synthetic_credits(result):
    return observed_provider_credits(
        result, expected_origin="synthetic"
    )
