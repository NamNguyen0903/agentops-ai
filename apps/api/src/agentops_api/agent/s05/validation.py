"""Application-owned execution context and safe input boundary.

This module performs no provider calls, persistence, publication,
task lifecycle transitions or workflow orchestration.
"""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agentops_api.agent.s05.contract import (
    ErrorCategory,
    ExecutionCounters,
    ExecutionPolicy,
    S05GraphInput,
    S05GraphState,
    S05Versions,
    _canonical_scope_json,
)


class S05BoundaryError(ValueError):
    """Safe public error without original input or exception details."""

    __slots__ = ("_category",)

    def __init__(self) -> None:
        self._category: ErrorCategory = "invalid_input"
        super().__init__("invalid S05 input")

    @property
    def category(self) -> ErrorCategory:
        return self._category


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionContext:
    """Independent, application-owned input snapshot.

    Only immutable scalar values are retained. Scope, policy and
    version objects are reconstructed independently when requested.
    """

    task_id: UUID
    attempt_id: UUID | None
    question: str
    scope_json: str

    def __post_init__(self) -> None:
        """Validate context construction, including direct construction."""

        validated = None

        try:
            if type(self.task_id) is not UUID:
                raise ValueError("invalid identity")

            if (
                self.attempt_id is not None
                and type(self.attempt_id) is not UUID
            ):
                raise ValueError("invalid identity")

            if type(self.question) is not str:
                raise ValueError("invalid question")

            if type(self.scope_json) is not str:
                raise ValueError("invalid canonical scope")

            if len(self.scope_json.encode("utf-8")) > 8192:
                raise ValueError("scope exceeds maximum size")

            scope = json.loads(self.scope_json)

            if _canonical_scope_json(scope) != self.scope_json:
                raise ValueError("noncanonical scope")

            validated = S05GraphInput(
                task_id=self.task_id,
                attempt_id=self.attempt_id,
                question=self.question,
                scope=scope,
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
            OverflowError,
            RecursionError,
        ):
            pass

        # Raise outside the exception handler to avoid retaining
        # an implicit exception context with input details.
        if validated is None:
            raise S05BoundaryError()

    def scope_copy(self) -> dict[str, Any]:
        """Return a fresh scope object without mutable aliases."""

        return json.loads(self.scope_json)

    @property
    def versions(self) -> S05Versions:
        """Return independent application-owned version metadata."""

        return S05Versions()

    @property
    def policy(self) -> ExecutionPolicy:
        """Return independent application-owned execution limits."""

        return ExecutionPolicy()

    def __repr__(self) -> str:
        """Avoid exposing task identity, question or scope in repr."""

        return "ExecutionContext(<redacted>)"


def _validated_context_copy(
    context: ExecutionContext,
) -> ExecutionContext:
    """Safely reconstruct an independent execution context."""

    validated = None

    try:
        if type(context) is not ExecutionContext:
            raise ValueError("unexpected context type")

        validated = ExecutionContext(
            task_id=context.task_id,
            attempt_id=context.attempt_id,
            question=context.question,
            scope_json=context.scope_json,
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        pass

    if validated is None:
        raise S05BoundaryError()

    return validated


def _verify_exact_model_shape(
    value: Any,
    expected_type: type,
) -> None:
    """Check raw model structure before normalization."""

    if type(value) is not expected_type:
        raise ValueError("invalid model type")

    expected = set(expected_type.model_fields)

    raw_fields = value.__dict__

    if type(raw_fields) is not dict:
        raise ValueError("invalid model fields")

    if any(type(name) is not str for name in raw_fields):
        raise ValueError("invalid model fields")

    if set(raw_fields) != expected:
        raise ValueError("invalid model fields")

    if value.model_extra is not None:
        raise ValueError("unexpected model fields")

    fields_set = value.model_fields_set

    if type(fields_set) is not set:
        raise ValueError("invalid model metadata")

    if any(type(name) is not str for name in fields_set):
        raise ValueError("invalid model metadata")

    if not fields_set.issubset(expected):
        raise ValueError("invalid model metadata")


def _verify_request_shape(request: S05GraphInput) -> None:
    """Reject bypassed or unexpected instance fields."""

    _verify_exact_model_shape(request, S05GraphInput)


def create_execution_context(
    request: S05GraphInput,
) -> ExecutionContext:
    """Verify original request integrity before independent validation.

    This boundary is designed for normal application inputs and
    accidental or unvalidated model changes. It is not a sandbox
    against arbitrary Python code with unrestricted object access.
    """

    context = None

    try:
        _verify_request_shape(request)

        original = request.verified_input_snapshot()

        task_id, attempt_id, question, scope_json = original

        # Reconstruct from immutable verified values, not from the
        # original model or its potentially mutable scope object.
        validated = S05GraphInput(
            task_id=task_id,
            attempt_id=attempt_id,
            question=question,
            scope=json.loads(scope_json),
        )

        if validated.verified_input_snapshot() != original:
            raise ValueError("independent validation mismatch")

        # Confirm the original request was not changed during
        # independent validation.
        _verify_request_shape(request)

        if request.verified_input_snapshot() != original:
            raise ValueError("input changed during validation")

        context = ExecutionContext(
            task_id=task_id,
            attempt_id=attempt_id,
            question=question,
            scope_json=scope_json,
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        pass

    if context is None:
        raise S05BoundaryError()

    return context


class S05StateIntegrityError(ValueError):
    """Safe error for unauthorized protected-state changes."""

    @property
    def category(self) -> ErrorCategory:
        return "security_violation"

    def __init__(self) -> None:
        super().__init__("invalid S05 protected state")


def build_initial_state(
    context: ExecutionContext,
) -> S05GraphState:
    """Create independent ephemeral state from trusted context.

    This function initializes data only. It does not execute
    LangGraph nodes, allocate provider budgets or persist state.
    """

    verified = _validated_context_copy(context)

    return {
        "task_id": str(verified.task_id),
        "attempt_id": (
            str(verified.attempt_id)
            if verified.attempt_id is not None
            else None
        ),
        "question": verified.question,
        "scope": verified.scope_copy(),
        "plan": None,
        "research_output": None,
        "evidence_ids": (),
        "coverage": 0.0,
        "fixture_coverage": 0.0,
        "draft_report": None,
        "result": None,
        "stage": "pending",
        "repair_used": False,
        "budget_snapshot": verified.policy,
        "counters": ExecutionCounters(),
        "error_category": None,
        "versions": verified.versions,
    }


def _strict_equal(actual: Any, expected: Any) -> bool:
    """Compare supported values without numeric type coercion."""

    if type(actual) is not type(expected):
        return False

    if type(expected) is dict:
        if actual.keys() != expected.keys():
            return False

        if any(type(key) is not str for key in actual):
            return False

        return all(
            _strict_equal(actual[key], expected[key])
            for key in expected
        )

    if type(expected) in (tuple, list):
        return (
            len(actual) == len(expected)
            and all(
                _strict_equal(left, right)
                for left, right in zip(actual, expected)
            )
        )

    if type(expected) is float:
        # Preserve exact float representation, including
        # the sign of zero, without accepting NaN equality.
        return (
            actual == expected
            and actual.hex() == expected.hex()
        )

    if type(expected) in (
        str, int, bool, type(None)
    ):
        return actual == expected

    return False


def verify_protected_state(
    state: S05GraphState,
    context: ExecutionContext,
) -> None:
    """Verify protected state fields against trusted context.

    The trusted context must be held independently by the
    application, not taken from an adapter-provided state.

    This is not full graph-state or output validation.
    Mutable workflow channels are validated separately.
    """

    valid = False

    try:
        expected = build_initial_state(context)

        if type(state) is not dict:
            raise ValueError("invalid state type")

        if any(type(key) is not str for key in state):
            raise ValueError("invalid state keys")

        if set(state) != set(expected):
            raise ValueError("unexpected state fields")

        protected_fields = (
            "task_id",
            "attempt_id",
            "question",
            "scope",
            "evidence_ids",
            "coverage",
        )

        for name in protected_fields:
            if not _strict_equal(
                state[name],
                expected[name],
            ):
                raise ValueError("protected field changed")

        for name, contract_type in (
            ("budget_snapshot", ExecutionPolicy),
            ("versions", S05Versions),
        ):
            actual = state[name]
            reference = expected[name]

            _verify_exact_model_shape(
                actual,
                contract_type,
            )

            # Compare raw fields first to avoid normalization
            # hiding an invalid model_copy update.
            if not _strict_equal(
                actual.__dict__,
                reference.__dict__,
            ):
                raise ValueError("protected metadata changed")

            validated = contract_type.model_validate(
                dict(actual.__dict__)
            )

            if not _strict_equal(
                validated.__dict__,
                reference.__dict__,
            ):
                raise ValueError("metadata validation mismatch")

        valid = True

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if not valid:
        raise S05StateIntegrityError()



def _repair_model_fields(value, expected_type):
    """Return completely inspectable raw model fields.

    None means repair eligibility cannot be established.
    This helper does not normalize malformed values.
    """

    if type(value) is not expected_type:
        return None

    try:
        expected = set(expected_type.model_fields)

        raw = object.__getattribute__(
            value, "__dict__"
        )

        if type(raw) is not dict:
            return None

        if len(raw) != len(expected):
            return None

        if any(
            type(key) is not str
            for key in raw
        ):
            return None

        if set(raw) != expected:
            return None

        extra = object.__getattribute__(
            value, "__pydantic_extra__"
        )

        if extra is not None:
            return None

        private = object.__getattribute__(
            value, "__pydantic_private__"
        )

        if private is not None:
            return None

        fields_set = object.__getattribute__(
            value, "__pydantic_fields_set__"
        )

        if type(fields_set) is not set:
            return None

        if len(fields_set) > len(expected):
            return None

        if any(
            type(key) is not str
            for key in fields_set
        ):
            return None

        if not fields_set.issubset(expected):
            return None

    except Exception:
        return None

    return raw


def _repair_text_inspectable(value, maximum):
    """Accept only bounded, exact, UTF-8 text values.

    Blank text remains inspectable but may be invalid.
    Oversized, arbitrary objects and invalid Unicode
    are not eligible for repair under this policy.
    """

    if type(value) is not str:
        return False

    if len(value) > maximum:
        return False

    try:
        value.encode("utf-8")
    except UnicodeError:
        return False

    return True
