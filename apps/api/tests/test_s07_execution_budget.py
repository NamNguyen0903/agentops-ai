"""Pure accounting policy tests; database verification follows separately."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agentops_api.services.execution import ExecutionRejected

from agentops_api.services.execution_budget import (
    BudgetRejected,
    ExecutionBudgetService,
    LIMITS,
    ReservationRequest,
    calculate_charge,
    close_unresolved,
    reservation_deadline,
    validate_context_identity,
    validate_ledger,
    validate_request,
    validate_retry,
)


NOW = datetime(
    2026, 11, 26, tzinfo=timezone.utc
)


def context(**changes):
    values = {
        "task_id": uuid4(),
        "owner_id": uuid4(),
        "started_at": NOW,
        "deadline_at": NOW + timedelta(seconds=180),
        "updated_at": NOW,
        "blocked_at": None,
        "block_reason": None,
        **{name: 0 for name in LIMITS},
    }

    values.update(changes)

    return SimpleNamespace(**values)


def request(kind="search", **changes):
    values = {
        "operation_id": uuid4(),
        "kind": kind,
    }

    values.update(changes)

    return ReservationRequest(**values)


def row(value, **changes):
    fields = {
        "task_id": value.task_id,
        "owner_id": value.owner_id,
        "operation_id": uuid4(),
        "kind": "search",
        "retry_ordinal": 0,
        "reserved_tokens": 0,
        "reserved_cost_microusd": 0,
        "is_repair": False,
        "status": "succeeded",
        "retry_eligible": False,
        "reserved_at": NOW,
        "deadline_at": NOW + timedelta(seconds=15),
        "dispatched_at": NOW,
        "resolved_at": NOW,
    }

    fields.update(changes)

    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retry_ordinal", True),
        ("retry_ordinal", -1),
        ("retry_ordinal", 2),
        ("reserved_tokens", True),
        ("reserved_tokens", -1),
        ("reserved_tokens", 40001),
        ("reserved_cost_microusd", -1),
        ("reserved_cost_microusd", 1000001),
        ("reserved_cost_microusd", 1.0),
        ("kind", "adapter"),
        ("kind", "unknown"),
        ("operation_id", "invalid"),
    ],
)
def test_invalid_requests(field, value):
    arguments = {
        "operation_id": uuid4(),
        "kind": "search",
    }

    arguments[field] = value

    with pytest.raises(BudgetRejected):
        validate_request(
            ReservationRequest(**arguments)
        )


@pytest.mark.parametrize(
    ("kind", "counter", "maximum"),
    [
        ("search", "search_calls", 6),
        ("retrieval", "retrieval_calls", 12),
        ("model", "model_calls", 8),
    ],
)
def test_cumulative_call_limits(kind, counter, maximum):
    value = context(
        **{counter: maximum - 1}
    )

    result = calculate_charge(
        value, request(kind)
    )

    assert result[counter] == maximum
    assert getattr(value, counter) == maximum - 1

    setattr(value, counter, maximum)

    with pytest.raises(BudgetRejected):
        calculate_charge(value, request(kind))


def test_model_usage_is_cumulative():
    value = context(
        reserved_tokens=39000,
        reserved_cost_microusd=990000,
    )

    result = calculate_charge(
        value,
        request(
            "model",
            reserved_tokens=1000,
            reserved_cost_microusd=10000,
        ),
    )

    assert result["reserved_tokens"] == 40000
    assert result["reserved_cost_microusd"] == 1000000
    assert result["model_calls"] == 1


@pytest.mark.parametrize(
    "usage",
    [
        {"reserved_tokens": 1001},
        {"reserved_cost_microusd": 10001},
    ],
)
def test_usage_exhaustion(usage):
    value = context(
        reserved_tokens=39000,
        reserved_cost_microusd=990000,
    )

    with pytest.raises(BudgetRejected):
        calculate_charge(
            value, request("model", **usage)
        )


def test_non_model_token_charge_denied():
    with pytest.raises(BudgetRejected):
        validate_request(
            request(reserved_tokens=1)
        )


def test_model_retry_denied():
    with pytest.raises(BudgetRejected):
        validate_request(
            request("model", retry_ordinal=1)
        )


def test_operation_deadline_bound():
    value = context()

    attempt = SimpleNamespace(
        lease_expires_at=NOW + timedelta(seconds=30)
    )

    assert reservation_deadline(
        value, attempt, NOW, "search"
    ) == NOW + timedelta(seconds=15)


def test_lease_deadline_bound():
    value = context()

    attempt = SimpleNamespace(
        lease_expires_at=NOW + timedelta(seconds=5)
    )

    assert reservation_deadline(
        value, attempt, NOW, "model"
    ) == NOW + timedelta(seconds=5)


def test_workflow_deadline_survives_recovery():
    value = context()

    now = NOW + timedelta(seconds=28)

    attempt = SimpleNamespace(
        lease_expires_at=now + timedelta(seconds=30)
    )

    assert reservation_deadline(
        value, attempt, now, "search"
    ) == NOW + timedelta(seconds=30)


def test_expired_workflow_deadline_denied():
    value = context()

    now = NOW + timedelta(seconds=30)

    attempt = SimpleNamespace(
        lease_expires_at=now + timedelta(seconds=30)
    )

    with pytest.raises(BudgetRejected):
        reservation_deadline(
            value, attempt, now, "model"
        )


def test_context_identity_and_original_deadline():
    value = context()

    task = SimpleNamespace(
        id=value.task_id,
        owner_id=value.owner_id,
        started_at=value.started_at,
    )

    validate_context_identity(value, task, NOW)

    value.deadline_at += timedelta(seconds=1)

    with pytest.raises(BudgetRejected):
        validate_context_identity(value, task, NOW)


def test_missing_context_denied():
    with pytest.raises(BudgetRejected):
        validate_context_identity(
            None, SimpleNamespace(), NOW
        )


def test_ledger_counter_reset_detected():
    value = context()

    with pytest.raises(BudgetRejected):
        validate_ledger(
            value, [row(value)]
        )


def test_ledger_matches_retained_charge():
    value = context(search_calls=1)

    validate_ledger(
        value, [row(value)]
    )


def test_duplicate_reservation_detected():
    value = context(search_calls=2)

    record = row(value)

    with pytest.raises(BudgetRejected):
        validate_ledger(
            value, [record, record]
        )


def test_multiple_unresolved_operations_denied():
    value = context(search_calls=2)

    with pytest.raises(BudgetRejected):
        validate_ledger(
            value,
            [
                row(value, status="reserved"),
                row(value, status="dispatching"),
            ],
        )


def test_retry_requires_initial_operation():
    with pytest.raises(BudgetRejected):
        validate_retry(
            request(retry_ordinal=1), []
        )


@pytest.mark.parametrize(
    "status",
    [
        "succeeded",
        "reserved",
        "dispatching",
        "indeterminate",
    ],
)
def test_retry_requires_known_failure(status):
    value = context()

    operation = request(retry_ordinal=1)

    prior = row(
        value,
        operation_id=operation.operation_id,
        status=status,
        retry_eligible=True,
    )

    with pytest.raises(BudgetRejected):
        validate_retry(operation, [prior])


def test_retry_requires_trusted_eligibility():
    value = context()

    operation = request(retry_ordinal=1)

    prior = row(
        value,
        operation_id=operation.operation_id,
        status="failed",
        retry_eligible=False,
    )

    with pytest.raises(BudgetRejected):
        validate_retry(operation, [prior])


def test_first_eligible_retry_policy():
    value = context()

    operation = request(retry_ordinal=1)

    prior = row(
        value,
        operation_id=operation.operation_id,
        status="failed",
        retry_eligible=True,
    )

    validate_retry(operation, [prior])


def test_second_retry_denied():
    value = context()

    operation = request(retry_ordinal=1)

    records = [
        row(
            value,
            operation_id=operation.operation_id,
            retry_ordinal=ordinal,
            status="failed",
            retry_eligible=(ordinal == 0),
        )
        for ordinal in (0, 1)
    ]

    with pytest.raises(BudgetRejected):
        validate_retry(operation, records)


@pytest.mark.parametrize(
    "status", ["reserved", "dispatching"]
)
def test_unresolved_charge_is_retained(status):
    value = context(search_calls=1)

    record = row(
        value,
        status=status,
        resolved_at=None,
    )

    now = NOW + timedelta(seconds=20)

    assert close_unresolved(
        value, [record], now
    ) is True

    assert record.status == "indeterminate"
    assert record.resolved_at == now
    assert record.retry_eligible is False
    assert value.search_calls == 1
    assert value.blocked_at == now


def test_resolved_charge_is_not_refunded():
    value = context(search_calls=1)

    record = row(value)

    assert close_unresolved(
        value,
        [record],
        NOW + timedelta(seconds=1),
    ) is False

    assert value.search_calls == 1
    assert record.status == "succeeded"


def test_worker_activation_denied_by_default():
    with pytest.raises(ExecutionRejected):
        ExecutionBudgetService(None)


def test_truthy_scope_does_not_authorize_worker():
    with pytest.raises(ExecutionRejected):
        ExecutionBudgetService(
            None, isolated_test_scope=1
        )


def test_stage_operation_identity_is_deterministic():
    from agentops_api.services.execution_budget import (
        stage_operation_id,
    )

    task = uuid4()

    assert stage_operation_id(
        task, "planner"
    ) == stage_operation_id(task, "planner")

    assert stage_operation_id(
        task, "planner"
    ) != stage_operation_id(task, "planner", True)

    assert stage_operation_id(
        task, "planner"
    ) != stage_operation_id(task, "writer")


def test_initial_stage_is_planner():
    from agentops_api.services.execution_budget import (
        validate_stage_history,
    )

    assert validate_stage_history(
        context(), []
    ) == ("planner", False)


def test_known_planner_failure_permits_shared_repair():
    from agentops_api.services.execution_budget import (
        stage_operation_id,
        validate_stage_history,
    )

    value = context(adapter_invocations=1)

    record = row(
        value,
        id=uuid4(),
        kind="adapter",
        status="failed",
        operation_id=stage_operation_id(
            value.task_id, "planner"
        ),
    )

    assert validate_stage_history(
        value, [record]
    ) == ("planner", True)


def test_indeterminate_stage_does_not_permit_repair():
    from agentops_api.services.execution_budget import (
        stage_operation_id,
        validate_stage_history,
    )

    value = context(adapter_invocations=1)

    record = row(
        value,
        id=uuid4(),
        kind="adapter",
        status="indeterminate",
        operation_id=stage_operation_id(
            value.task_id, "planner"
        ),
    )

    with pytest.raises(BudgetRejected):
        validate_stage_history(value, [record])


def test_research_stage_cannot_receive_repair():
    from agentops_api.services.execution_budget import (
        stage_operation_id,
    )

    with pytest.raises(BudgetRejected):
        stage_operation_id(
            uuid4(), "research", True
        )


def test_caller_outcome_cannot_reconcile():
    import asyncio

    service = object.__new__(
        ExecutionBudgetService
    )

    with pytest.raises(
        BudgetRejected,
        match="caller_outcome_not_authorized",
    ):
        asyncio.run(
            service.reconcile(
                None, None, outcome="succeeded"
            )
        )


def test_unverified_exit_cannot_be_success():
    from agentops_api.services.execution_runner import (
        SyntheticResult,
    )

    from agentops_api.services.execution_budget import (
        validate_synthetic_result,
    )

    value = SyntheticResult(
        "succeeded", 0, 0, False, False
    )

    assert validate_synthetic_result(
        value, "search"
    ) == "indeterminate"


def test_known_retry_failure_is_kind_restricted():
    from agentops_api.services.execution_runner import (
        SyntheticResult,
    )

    from agentops_api.services.execution_budget import (
        validate_synthetic_result,
    )

    value = SyntheticResult(
        "retryable_failure", 0, 0, True, False
    )

    assert validate_synthetic_result(
        value, "search"
    ) == "failed"

    assert validate_synthetic_result(
        value, "model"
    ) == "indeterminate"


def test_local_timeout_remains_conservative():
    from agentops_api.services.execution_runner import (
        SyntheticResult,
    )

    from agentops_api.services.execution_budget import (
        validate_synthetic_result,
    )

    value = SyntheticResult(
        "timed_out", None, None, True, True
    )

    assert validate_synthetic_result(
        value, "retrieval"
    ) == "indeterminate"


def test_retry_deadline_cannot_extend_initial_operation():
    from agentops_api.services.execution_budget import (
        retry_deadline,
    )

    value = context()
    operation = request(retry_ordinal=1)

    prior = row(
        value,
        operation_id=operation.operation_id,
        retry_ordinal=0,
        status="failed",
        retry_eligible=True,
        deadline_at=NOW + timedelta(seconds=15),
    )

    assert retry_deadline(
        operation,
        [prior],
        NOW + timedelta(seconds=25),
        NOW + timedelta(seconds=10),
    ) == NOW + timedelta(seconds=15)


def test_expired_initial_operation_cannot_retry():
    from agentops_api.services.execution_budget import (
        retry_deadline,
    )

    value = context()
    operation = request(retry_ordinal=1)

    prior = row(
        value,
        operation_id=operation.operation_id,
        retry_ordinal=0,
        status="failed",
        retry_eligible=True,
        deadline_at=NOW + timedelta(seconds=15),
    )

    with pytest.raises(
        BudgetRejected,
        match="operation_deadline_expired",
    ):
        retry_deadline(
            operation,
            [prior],
            NOW + timedelta(seconds=30),
            NOW + timedelta(seconds=15),
        )


def test_ledger_rejects_retry_deadline_extension():
    value = context(search_calls=2)
    operation_id = uuid4()

    initial = row(
        value,
        operation_id=operation_id,
        status="failed",
        retry_eligible=True,
    )

    retry = row(
        value,
        operation_id=operation_id,
        retry_ordinal=1,
        reserved_at=NOW + timedelta(seconds=1),
        deadline_at=NOW + timedelta(seconds=16),
        dispatched_at=NOW + timedelta(seconds=1),
        resolved_at=NOW + timedelta(seconds=2),
    )

    with pytest.raises(BudgetRejected):
        validate_ledger(
            value, [initial, retry]
        )
