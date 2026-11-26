"""S07 synthetic subprocess and cancellation verification."""

import asyncio
import json
import os

import pytest

from agentops_api.services.execution_runner import (
    RunnerRejected,
    SyntheticRequest,
    classify_output,
    run_synthetic,
    validate_synthetic_request,
    validate_timeout,
)


def run(request, timeout=2.0):
    return asyncio.run(
        run_synthetic(
            request,
            timeout_seconds=timeout,
            isolated_test_scope=True,
        )
    )


@pytest.mark.parametrize(
    "value",
    [0, -1, True, 46, float("inf"), float("nan"), "1"],
)
def test_invalid_timeout(value):
    with pytest.raises(RunnerRejected):
        validate_timeout(value)


@pytest.mark.parametrize(
    ("kind", "mode"),
    [
        ("unknown", "success"),
        ("search", "unknown"),
        ("model", "retryable_failure"),
        ("retrieval", "invalid_stage_output"),
    ],
)
def test_invalid_request(kind, mode):
    with pytest.raises(RunnerRejected):
        validate_synthetic_request(
            SyntheticRequest(kind, mode)
        )


@pytest.mark.parametrize("scope", [False, 1, None])
def test_default_execution_denied(scope):
    with pytest.raises(RunnerRejected):
        asyncio.run(
            run_synthetic(
                SyntheticRequest("search", "success"),
                timeout_seconds=1,
                isolated_test_scope=scope,
            )
        )


@pytest.mark.parametrize(
    "kind",
    ["search", "retrieval", "model", "adapter"],
)
def test_actual_synthetic_success(kind):
    result = run(
        SyntheticRequest(kind, "success")
    )

    assert result.outcome == "succeeded"
    assert result.process_exit_verified is True
    assert result.tokens == (
        10 if kind == "model" else 0
    )
    assert result.cost_microusd == 0


@pytest.mark.parametrize(
    "kind", ["search", "retrieval"]
)
def test_actual_retryable_failure(kind):
    result = run(
        SyntheticRequest(kind, "retryable_failure")
    )

    assert result.outcome == "retryable_failure"
    assert result.process_exit_verified is True


def test_actual_invalid_stage_output():
    result = run(
        SyntheticRequest(
            "adapter", "invalid_stage_output"
        )
    )

    assert result.outcome == "invalid_stage_output"
    assert result.process_exit_verified is True


def test_actual_timeout_terminates_child():
    result = run(
        SyntheticRequest("search", "hang"),
        timeout=0.5,
    )

    assert result.outcome == "timed_out"
    assert result.process_exit_verified is True


def test_actual_sigterm_resistant_child():
    result = run(
        SyntheticRequest("search", "ignore_term"),
        timeout=1.0,
    )

    assert result.outcome == "timed_out"
    assert result.process_exit_verified is True
    assert result.termination_escalated is True


@pytest.mark.parametrize(
    "mode", ["malformed_output", "unexpected_exit"]
)
def test_unknown_result_fails_closed(mode):
    result = run(
        SyntheticRequest("search", mode)
    )

    assert result.outcome == "indeterminate"
    assert result.process_exit_verified is True


def test_parent_credentials_not_inherited(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY", "synthetic-marker"
    )

    result = run(
        SyntheticRequest("search", "success")
    )

    assert result.outcome == "succeeded"


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"x" * 1025,
        b"not-json",
        b"null",
        b"{}",
        b'{"outcome":"succeeded","tokens":true,"cost_microusd":0}',
        b'{"outcome":"retryable_failure","tokens":0,"cost_microusd":0}',
    ],
)
def test_malformed_output_never_grants_success(payload):
    result = classify_output(
        SyntheticRequest("search", "success"),
        payload,
        0,
    )

    assert result.outcome == "indeterminate"


def test_nonzero_exit_cannot_grant_success():
    payload = json.dumps({
        "outcome": "succeeded",
        "tokens": 0,
        "cost_microusd": 0,
    }).encode()

    result = classify_output(
        SyntheticRequest("search", "success"),
        payload,
        65,
    )

    assert result.outcome == "indeterminate"


def test_model_usage_mismatch_fails_closed():
    payload = json.dumps({
        "outcome": "succeeded",
        "tokens": 11,
        "cost_microusd": 0,
    }).encode()

    result = classify_output(
        SyntheticRequest("model", "success"),
        payload,
        0,
    )

    assert result.outcome == "indeterminate"


def test_repeated_cancellation_does_not_cancel_cleanup():
    from agentops_api.services.execution_runner import (
        _await_cleanup,
    )

    async def scenario():
        completed = asyncio.Event()

        async def cleanup():
            await asyncio.sleep(0.05)
            completed.set()
            return True

        owned = asyncio.create_task(cleanup())

        waiter = asyncio.create_task(
            _await_cleanup(owned)
        )

        await asyncio.sleep(0)

        waiter.cancel()
        await asyncio.sleep(0)

        waiter.cancel()

        result = await waiter

        assert result is True
        assert completed.is_set()
        assert not owned.cancelled()

    asyncio.run(scenario())


def test_cancellation_during_actual_child_execution():
    async def scenario():
        operation = asyncio.create_task(
            run_synthetic(
                SyntheticRequest(
                    "search", "ignore_term"
                ),
                timeout_seconds=5.0,
                isolated_test_scope=True,
            )
        )

        await asyncio.sleep(0.2)
        operation.cancel()

        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())


def test_bounded_cleanup_observation_retains_pending_task():
    from agentops_api.services.execution_runner import (
        _observe_cleanup,
        _PENDING_CLEANUPS,
    )

    async def scenario():
        released = asyncio.Event()

        async def cleanup():
            await released.wait()
            return True, False

        owned = asyncio.create_task(cleanup())

        try:
            result = await _observe_cleanup(
                owned, timeout_seconds=0.02
            )

            assert result == (False, False)
            assert not owned.cancelled()
            assert owned in _PENDING_CLEANUPS

        finally:
            released.set()
            await owned
            await asyncio.sleep(0)

        assert owned not in _PENDING_CLEANUPS

    asyncio.run(scenario())


def test_cleanup_observation_propagates_caller_cancellation():
    from agentops_api.services.execution_runner import (
        _observe_cleanup,
    )

    async def scenario():
        async def cleanup():
            await asyncio.sleep(0.05)
            return True, False

        owned = asyncio.create_task(cleanup())

        observer = asyncio.create_task(
            _observe_cleanup(
                owned, timeout_seconds=0.5
            )
        )

        await asyncio.sleep(0)
        observer.cancel()

        await asyncio.sleep(0)
        observer.cancel()

        with pytest.raises(asyncio.CancelledError):
            await observer

        assert await owned == (True, False)

    asyncio.run(scenario())


def test_cleanup_observation_error_is_indeterminate():
    from agentops_api.services.execution_runner import (
        _observe_cleanup,
    )

    async def scenario():
        async def cleanup():
            raise RuntimeError("synthetic cleanup failure")

        owned = asyncio.create_task(cleanup())

        assert await _observe_cleanup(
            owned, timeout_seconds=0.5
        ) == (False, False)

    asyncio.run(scenario())
