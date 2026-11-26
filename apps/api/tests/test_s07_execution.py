"""Pure unit tests for S07 execution policy.

Database concurrency and lifecycle behavior are tested separately
against explicitly disposable PostgreSQL infrastructure.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from agentops_api.services.execution import (
    ExecutionHandle,
    ExecutionRejected,
    ExecutionService,
    GLOBAL_RUNNING_LIMIT,
    PER_USER_RUNNING_LIMIT,
    PENDING_LIMIT,
    QUEUE_TIMEOUT,
    RUNNING_TIMEOUT,
    LEASE_DURATION,
    HEARTBEAT_INTERVAL_SECONDS,
    IDLE_POLL_SECONDS,
    RECOVERY_INSPECTION_SECONDS,
    MAX_ATTEMPTS,
    WORKER_FINISH_STATES,
    bounded_lease,
    running_deadline,
    _validate_handle,
    _validate_worker,
)

START = datetime(
    2026, 11, 25, 0, 0, 0,
    tzinfo=timezone.utc,
)


def test_approved_execution_limits():
    assert GLOBAL_RUNNING_LIMIT == 5
    assert PER_USER_RUNNING_LIMIT == 1
    assert PENDING_LIMIT == 50
    assert QUEUE_TIMEOUT == timedelta(seconds=60)
    assert RUNNING_TIMEOUT == timedelta(seconds=180)
    assert LEASE_DURATION == timedelta(seconds=30)
    assert HEARTBEAT_INTERVAL_SECONDS == 10
    assert IDLE_POLL_SECONDS == 1
    assert RECOVERY_INSPECTION_SECONDS == 5
    assert MAX_ATTEMPTS == 2


def test_worker_activation_disabled_by_default():
    with pytest.raises(
        ExecutionRejected,
        match="worker_activation_disabled",
    ):
        ExecutionService(None)


@pytest.mark.parametrize(
    "value",
    [False, None, 1, "true"],
)
def test_worker_activation_requires_exact_opt_in(value):
    with pytest.raises(ExecutionRejected):
        ExecutionService(
            None,
            isolated_test_scope=value,
        )


def test_running_deadline_is_original_start_based():
    assert running_deadline(START) == (
        START + timedelta(seconds=180)
    )


def test_initial_lease_is_thirty_seconds():
    assert bounded_lease(START, START) == (
        START + timedelta(seconds=30)
    )


def test_recovery_lease_cannot_extend_running_deadline():
    recovered_at = START + timedelta(seconds=170)

    assert bounded_lease(
        recovered_at,
        START,
    ) == START + timedelta(seconds=180)


@pytest.mark.parametrize("offset", [180, 181, 600])
def test_expired_running_deadline_rejects_lease(offset):
    with pytest.raises(
        ExecutionRejected,
        match="execution_deadline_expired",
    ):
        bounded_lease(
            START + timedelta(seconds=offset),
            START,
        )


@pytest.mark.parametrize("generation", [1, 2])
def test_valid_execution_handle(generation):
    handle = ExecutionHandle(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        generation,
    )

    _validate_handle(handle)


@pytest.mark.parametrize(
    "generation",
    [0, -1, 3, 100, True, "1"],
)
def test_invalid_generation_rejected(generation):
    handle = ExecutionHandle(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        generation,
    )

    with pytest.raises(ExecutionRejected):
        _validate_handle(handle)


def test_invalid_worker_identity_rejected():
    from uuid import UUID

    for worker_id in [
        None,
        "",
        "worker",
        UUID(int=0),
    ]:
        with pytest.raises(ExecutionRejected):
            _validate_worker(worker_id)


def test_successful_report_publication_is_not_authorized():
    assert WORKER_FINISH_STATES == {
        "failed",
        "insufficient_evidence",
    }

    assert "completed" not in WORKER_FINISH_STATES
