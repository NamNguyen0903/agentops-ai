"""Deterministic offline Research node for Sprint S05."""

from typing import Literal

from typing_extensions import TypedDict

from agentops_api.agent.s05.adapters import (
    _validate_research_plan,
    research_fixture,
    validate_fixture_research_output,
)
from agentops_api.agent.s05.controller import (
    _InvocationBoundaryError,
    _invocation_counters,
    _invoke_fixture,
    _raise_boundary_error,
)
from agentops_api.agent.s05.contract import (
    ErrorCategory,
    ExecutionCounters,
    ResearchOutput,
    ResearchPlan,
    S05GraphState,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
    build_initial_state,
    verify_protected_state,
)

from agentops_api.agent.s05.controller import (
    _current_controller,
    _verified_stage_counters,
    _verify_stage_accounting,
    _verify_incoming_accounting,
    _require_invocation_progress,
)


class ResearchUpdate(TypedDict):
    """Only state channels owned by the Research node."""

    research_output: ResearchOutput
    fixture_coverage: float
    stage: Literal["researched"]
    counters: ExecutionCounters


class S05ResearchError(ValueError):
    """Safe allowlisted Research execution errors."""

    def __init__(self, category: ErrorCategory) -> None:
        if category not in (
            "invalid_output",
            "execution_failed",
        ):
            category = "execution_failed"

        self._category = category
        super().__init__("S05 research failed")

    @property
    def category(self) -> ErrorCategory:
        return self._category


def _verify_research_state(
    state: S05GraphState,
    context: ExecutionContext,
    *, incoming=None,
) -> ResearchPlan:
    """Validate the normal planned-state boundary."""

    verify_protected_state(state, context)

    expected = build_initial_state(context)
    validated_plan = None

    try:
        if not _strict_equal(
            state["stage"], "planned"
        ):
            raise ValueError("invalid research stage")

        for name in (
            "research_output",
            "fixture_coverage",
            "draft_report",
            "result",
            "error_category",
        ):
            if not _strict_equal(
                state[name], expected[name]
            ):
                raise ValueError("invalid research state")

        if incoming is None:
            _verify_stage_accounting(state, 1)
        else:
            _verify_incoming_accounting(state, incoming)

        validated_plan = _validate_research_plan(
            state["plan"]
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if validated_plan is None:
        raise S05StateIntegrityError()

    return validated_plan


def _verify_unchanged_plan(
    actual: ResearchPlan,
    expected: ResearchPlan,
) -> None:
    """Reject structural changes to a previously checked plan."""

    unchanged = False

    try:
        checked = _validate_research_plan(actual)

        unchanged = _strict_equal(
            checked.model_dump(),
            expected.model_dump(),
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if not unchanged:
        raise S05StateIntegrityError()


def research_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> ResearchUpdate:
    """Execute one approved offline Research invocation.

    This node supports the normal, unrepaired Planner path.
    It does not perform graph routing or publication.
    """

    original_plan = _verify_research_state(
        state, context
    )

    trusted_context = _validated_context_copy(context)

    adapter_context = _validated_context_copy(
        trusted_context
    )

    adapter_plan = _validate_research_plan(
        original_plan
    )

    incoming = _verified_stage_counters(1)
    active = _current_controller()
    previous = (
        active.invocation_history if active is not None else ()
    )

    raw_output = None
    adapter_failed = False
    boundary_error = None

    try:
        raw_output = _invoke_fixture("research", research_fixture,
            adapter_context,
            adapter_plan,
        )

    except _InvocationBoundaryError as error:
        boundary_error = error
        adapter_failed = True

    except Exception:
        adapter_failed = True

    # Detect persistent changes at the adapter boundary.
    # This is not an arbitrary-Python sandbox.

    current_plan = _verify_research_state(
        state, trusted_context, incoming=incoming
    )

    _verify_research_state(state, context, incoming=incoming)
    _verify_research_state(state, adapter_context, incoming=incoming)

    _verify_unchanged_plan(
        current_plan, original_plan
    )

    _verify_unchanged_plan(
        adapter_plan, original_plan
    )

    _raise_boundary_error(boundary_error)

    _require_invocation_progress(
        active, previous, "research", repair=False
    )

    if adapter_failed:
        raise S05ResearchError("execution_failed")

    # Reuse the WP02 registry validator to reconstruct
    # an independent, bounded output. The separate
    # Evidence Validation node will verify evidence
    # and determine routing in WP03-04.

    verified = validate_fixture_research_output(
        trusted_context,
        original_plan,
        raw_output,
    )

    return {
        "research_output": verified,
        "fixture_coverage": verified.fixture_coverage,
        "stage": "researched",
        "counters": _verified_stage_counters(2),
    }
