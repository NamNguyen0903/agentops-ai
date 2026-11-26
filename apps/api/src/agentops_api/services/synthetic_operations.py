"""Fixed, isolated synthetic child operations.

No provider, database, network, arbitrary callable, user code,
filesystem operation or subprocess creation is permitted here.

This module is an internal test fixture, not a worker entrypoint.
"""

import json
import os
import signal
import sys
import time


MODES = frozenset({
    "success",
    "retryable_failure",
    "invalid_stage_output",
    "hang",
    "ignore_term",
    "malformed_output",
    "unexpected_exit",
})

KINDS = frozenset({
    "search", "retrieval", "model", "adapter",
})

MAX_INPUT_BYTES = 1024
MAX_OUTPUT_BYTES = 1024


def reject():
    raise SystemExit(64)


def validate_input(value):
    if type(value) is not dict:
        reject()

    if set(value) != {"kind", "mode"}:
        reject()

    if (
        type(value["kind"]) is not str
        or value["kind"] not in KINDS
    ):
        reject()

    if (
        type(value["mode"]) is not str
        or value["mode"] not in MODES
    ):
        reject()

    if (
        value["mode"] == "retryable_failure"
        and value["kind"] not in {"search", "retrieval"}
    ):
        reject()

    if (
        value["mode"] == "invalid_stage_output"
        and value["kind"] != "adapter"
    ):
        reject()

    return value


def emit(value):
    data = json.dumps(
        value, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")

    if len(data) > MAX_OUTPUT_BYTES:
        reject()

    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main():
    if os.environ.get("AGENTOPS_S07_SYNTHETIC_CHILD") != "1":
        reject()

    # Only the allowlisted parent environment is expected.
    if any(
        key in os.environ
        for key in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "OPENAI_API_KEY",
            "TAVILY_API_KEY",
            "DATABASE_URL",
            "AGENTOPS_DATABASE_URL",
        )
    ):
        reject()

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)

    if not raw or len(raw) > MAX_INPUT_BYTES:
        reject()

    try:
        request = validate_input(json.loads(raw))
    except (UnicodeError, ValueError, TypeError):
        reject()

    kind = request["kind"]
    mode = request["mode"]

    if mode == "unexpected_exit":
        raise SystemExit(65)

    if mode == "malformed_output":
        sys.stdout.buffer.write(b"invalid-result")
        sys.stdout.buffer.flush()
        return

    if mode == "ignore_term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        emit({"ready": True})
        while True:
            time.sleep(0.05)

    if mode == "hang":
        while True:
            time.sleep(0.05)

    if mode == "retryable_failure":
        emit({
            "outcome": "retryable_failure",
            "tokens": 0,
            "cost_microusd": 0,
        })
        return

    if mode == "invalid_stage_output":
        emit({
            "outcome": "invalid_stage_output",
            "tokens": 0,
            "cost_microusd": 0,
        })
        return

    emit({
        "outcome": "succeeded",
        "tokens": 10 if kind == "model" else 0,
        "cost_microusd": 0,
    })


if __name__ == "__main__":
    main()
