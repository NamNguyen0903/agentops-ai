"""Internal synthetic subprocess primitive.

Not a durable dispatch authority. Application callers must obtain
a committed reservation and consume its one-shot dispatch authority
before entering this primitive.

No remote cancellation claim follows from local child termination.
"""

import asyncio
import json
import math
import os
import signal
import sys

from dataclasses import dataclass
from pathlib import Path
from time import monotonic


MAX_OUTPUT_BYTES = 1024
MAX_TIMEOUT_SECONDS = 45.0
TERMINATE_GRACE_SECONDS = 0.20
KILL_GRACE_SECONDS = 0.50

_ALLOWED_KINDS = frozenset({
    "search", "retrieval", "model", "adapter",
})

_ALLOWED_MODES = frozenset({
    "success",
    "retryable_failure",
    "invalid_stage_output",
    "hang",
    "ignore_term",
    "malformed_output",
    "unexpected_exit",
})


class RunnerRejected(RuntimeError):
    """Fixed sanitized runner rejection."""


@dataclass(frozen=True, slots=True)
class SyntheticRequest:
    kind: str
    mode: str


@dataclass(frozen=True, slots=True)
class SyntheticResult:
    outcome: str
    tokens: int | None
    cost_microusd: int | None
    process_exit_verified: bool
    termination_escalated: bool


def _unknown(*, verified=False, escalated=False):
    return SyntheticResult(
        "indeterminate",
        None,
        None,
        verified,
        escalated,
    )


def validate_synthetic_request(request):
    if type(request) is not SyntheticRequest:
        raise RunnerRejected("invalid_synthetic_request")

    if (
        type(request.kind) is not str
        or request.kind not in _ALLOWED_KINDS
    ):
        raise RunnerRejected("invalid_synthetic_kind")

    if (
        type(request.mode) is not str
        or request.mode not in _ALLOWED_MODES
    ):
        raise RunnerRejected("invalid_synthetic_mode")

    if (
        request.mode == "retryable_failure"
        and request.kind not in {"search", "retrieval"}
    ):
        raise RunnerRejected("invalid_retry_fixture")

    if (
        request.mode == "invalid_stage_output"
        and request.kind != "adapter"
    ):
        raise RunnerRejected("invalid_stage_fixture")


def validate_timeout(value):
    if type(value) not in {int, float}:
        raise RunnerRejected("invalid_timeout")

    if (
        not math.isfinite(value)
        or not 0 < value <= MAX_TIMEOUT_SECONDS
    ):
        raise RunnerRejected("invalid_timeout")

    return float(value)


def classify_output(request, raw, returncode):
    validate_synthetic_request(request)

    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAX_OUTPUT_BYTES
        or type(returncode) is not int
        or returncode != 0
    ):
        return _unknown(verified=True)

    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError, TypeError):
        return _unknown(verified=True)

    if (
        type(value) is not dict
        or set(value) != {
            "outcome", "tokens", "cost_microusd",
        }
    ):
        return _unknown(verified=True)

    if (
        type(value["outcome"]) is not str
        or type(value["tokens"]) is not int
        or type(value["cost_microusd"]) is not int
    ):
        return _unknown(verified=True)

    expected = {
        "success": "succeeded",
        "retryable_failure": "retryable_failure",
        "invalid_stage_output": "invalid_stage_output",
    }.get(request.mode)

    if expected is None or value["outcome"] != expected:
        return _unknown(verified=True)

    expected_tokens = 10 if (
        request.kind == "model"
        and expected == "succeeded"
    ) else 0

    if (
        value["tokens"] != expected_tokens
        or value["cost_microusd"] != 0
    ):
        return _unknown(verified=True)

    return SyntheticResult(
        expected,
        value["tokens"],
        value["cost_microusd"],
        True,
        False,
    )


async def _read_bounded(stream):
    result = bytearray()

    while True:
        remaining = MAX_OUTPUT_BYTES + 1 - len(result)

        if remaining <= 0:
            raise RunnerRejected("output_limit_exceeded")

        block = await stream.read(min(remaining, 256))

        if not block:
            return bytes(result)

        result.extend(block)

        if len(result) > MAX_OUTPUT_BYTES:
            raise RunnerRejected("output_limit_exceeded")


async def _wait_exit(process, timeout):
    try:
        await asyncio.wait_for(process.wait(), timeout)
    except asyncio.TimeoutError:
        return False

    return process.returncode is not None


async def _terminate_and_reap(process):
    escalated = False

    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError:
            return False, escalated

    if await _wait_exit(
        process, TERMINATE_GRACE_SECONDS
    ):
        return True, escalated

    escalated = True

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        return False, escalated

    verified = await _wait_exit(
        process, KILL_GRACE_SECONDS
    )

    return verified, escalated


async def _exchange(process, payload):
    process.stdin.write(payload)
    await process.stdin.drain()

    process.stdin.close()
    await process.stdin.wait_closed()

    raw = await _read_bounded(process.stdout)
    await process.wait()

    return raw


async def run_synthetic(
    request,
    *,
    timeout_seconds,
    isolated_test_scope=False,
):
    """Execute only the fixed synthetic child.

    This primitive is not a production execution authority.
    """

    if isolated_test_scope is not True:
        raise RunnerRejected("synthetic_execution_disabled")

    validate_synthetic_request(request)
    timeout = validate_timeout(timeout_seconds)

    if os.name != "posix":
        raise RunnerRejected("unsupported_execution_platform")

    deadline = monotonic() + timeout

    child = Path(__file__).with_name(
        "synthetic_operations.py"
    ).resolve()

    payload = json.dumps({
        "kind": request.kind,
        "mode": request.mode,
    }, separators=(",", ":")).encode("ascii")

    child_env = {
        "AGENTOPS_S07_SYNTHETIC_CHILD": "1",
        "LANG": "C",
    }

    process = None
    exchange = None

    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-B",
            str(child),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=child_env,
            cwd="/",
            start_new_session=True,
            limit=MAX_OUTPUT_BYTES + 1,
        )
    )

    try:
        process = await asyncio.wait_for(
            asyncio.shield(spawn),
            max(0.0, deadline - monotonic()),
        )

        remaining = deadline - monotonic()

        if remaining <= 0:
            verified, escalated = await _observe_cleanup(
                asyncio.create_task(
                    _terminate_and_reap(process)
                )
            )

            return SyntheticResult(
                "timed_out" if verified else "indeterminate",
                None, None, verified, escalated,
            )

        exchange = asyncio.create_task(
            _exchange(process, payload)
        )

        raw = await asyncio.wait_for(
            exchange, remaining
        )

        if monotonic() >= deadline:
            return SyntheticResult(
                "timed_out",
                None,
                None,
                process.returncode is not None,
                False,
            )

        return classify_output(
            request, raw, process.returncode
        )

    except asyncio.TimeoutError:
        if process is None:
            cleanup = asyncio.create_task(
                _cleanup_spawn(spawn)
            )

            await _observe_cleanup(cleanup)

            # Spawn timeout is not certified cancellation.
            return _unknown()

        verified, escalated = await _observe_cleanup(
            asyncio.create_task(
                _terminate_and_reap(process)
            )
        )

        return SyntheticResult(
            "timed_out" if verified else "indeterminate",
            None, None, verified, escalated,
        )

    except asyncio.CancelledError:
        cleanup = asyncio.create_task(
            _cleanup_spawn(spawn)
            if process is None
            else _terminate_and_reap(process)
        )

        try:
            await _observe_cleanup(cleanup)
        except Exception:
            pass

        raise

    except Exception:
        if process is None:
            return _unknown()

        verified, escalated = await _observe_cleanup(
            asyncio.create_task(
                _terminate_and_reap(process)
            )
        )

        return _unknown(
            verified=verified,
            escalated=escalated,
        )

    finally:
        if exchange is not None and not exchange.done():
            exchange.cancel()

            async def drain_exchange():
                await asyncio.gather(
                    exchange, return_exceptions=True
                )

            await _observe_cleanup(
                asyncio.create_task(drain_exchange())
            )


async def _await_cleanup(task):
    """Wait for one owned cleanup task despite repeated cancellation."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue

    return task.result()


async def _cleanup_spawn(spawn):
    """Retain ownership of a subprocess created during cancellation."""
    process = await spawn
    return await _terminate_and_reap(process)


_PENDING_CLEANUPS = set()


def _retain_cleanup(task):
    _PENDING_CLEANUPS.add(task)

    def completed(value):
        _PENDING_CLEANUPS.discard(value)

        if not value.cancelled():
            value.exception()

    task.add_done_callback(completed)


async def _observe_cleanup(task, timeout_seconds=1.0):
    """Bound observation without cancelling the owned cleanup.

    An observation timeout is indeterminate. Caller cancellation
    is remembered and propagated after bounded observation.
    """
    timeout = validate_timeout(timeout_seconds)
    deadline = monotonic() + timeout
    cancelled = False

    _retain_cleanup(task)

    while not task.done():
        remaining = deadline - monotonic()

        if remaining <= 0:
            break

        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                remaining,
            )
        except asyncio.TimeoutError:
            break
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break

    if cancelled:
        raise asyncio.CancelledError

    if not task.done():
        return False, False

    if task.cancelled():
        return False, False

    try:
        return task.result()
    except Exception:
        return False, False
