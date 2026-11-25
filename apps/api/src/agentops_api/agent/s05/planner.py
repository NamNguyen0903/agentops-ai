"""Deterministic offline Planner node for Sprint S05."""

from typing_extensions import TypedDict

from agentops_api.agent.s05.adapters import (
    _validate_research_plan,
    plan_fixture,
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
    ResearchPlan,
    ResearchSubquestion,
    S05GraphState,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _repair_model_fields,
    _repair_text_inspectable,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
    build_initial_state,
    verify_protected_state,
)

from agentops_api.agent.s05.controller import (
    _current_controller,
    _verified_stage_counters,
    _repair_available,
    _invoke_authorized_repair,
    _require_invocation_progress,
)


class PlannerUpdate(TypedDict):
    """Only the state channels owned by the Planner."""

    plan: ResearchPlan
    stage: str
    counters: ExecutionCounters


class S05PlannerError(ValueError):
    """Allowlisted Planner failures without raw details."""

    def __init__(self, category: ErrorCategory) -> None:
        if category not in (
            "invalid_output",
            "execution_failed",
        ):
            category = "execution_failed"

        self._category = category

        super().__init__("S05 planner failed")

    @property
    def category(self) -> ErrorCategory:
        return self._category


def _verify_initial_planner_state(
    state: S05GraphState,
    context: ExecutionContext,
) -> None:
    """Reject invalid initial mutable channels."""

    verify_protected_state(state, context)

    expected = build_initial_state(context)

    valid = False

    try:
        fields = (
            "plan",
            "research_output",
            "fixture_coverage",
            "draft_report",
            "result",
            "stage",
            "repair_used",
            "error_category",
        )

        for name in fields:
            if not _strict_equal(
                state[name], expected[name]
            ):
                raise ValueError("invalid initial state")

        counters = state["counters"]

        _verify_exact_model_shape(
            counters,
            ExecutionCounters,
        )

        if not _strict_equal(
            counters.__dict__,
            expected["counters"].__dict__,
        ):
            raise ValueError("invalid initial counters")

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


def planner_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> PlannerUpdate:
    """Create one structured plan without mutating input state.

    This node supports the initial normal Planner path only.
    Global repair routing and graph-wide deadline enforcement
    remain separate execution-guard responsibilities.
    """

    _verify_initial_planner_state(state, context)

    adapter_context = _validated_context_copy(context)

    active = _current_controller()
    previous = (
        active.invocation_history if active is not None else ()
    )

    raw_plan = None
    adapter_failed = False
    boundary_error = None

    try:
        raw_plan = _invoke_fixture("planner", plan_fixture, adapter_context)

    except _InvocationBoundaryError as error:
        boundary_error = error
        adapter_failed = True

    except Exception:
        adapter_failed = True

    # Verify both contexts and the incoming state after the
    # adapter boundary, including the adapter failure path.

    _verify_initial_planner_state(state, context)
    _verify_initial_planner_state(state, adapter_context)

    _raise_boundary_error(boundary_error)

    _require_invocation_progress(
        active, previous, "planner", repair=False
    )

    if adapter_failed:
        raise S05PlannerError("execution_failed")

    validated_plan = None

    try:
        validated_plan = _validate_research_plan(raw_plan)

    except Exception:
        pass

    if (
        validated_plan is None
        and active is not None
        and _planner_repair_eligible(raw_plan) is True
        and _repair_available()
    ):
        repair_before = active.invocation_history
        repair_context = _validated_context_copy(context)
        raw_plan = None
        adapter_failed = False
        boundary_error = None

        try:
            raw_plan = _invoke_authorized_repair(
                "planner", plan_fixture, repair_context
            )
        except _InvocationBoundaryError as error:
            boundary_error = error
            adapter_failed = True
        except Exception:
            adapter_failed = True

        _verify_initial_planner_state(state, context)
        _verify_initial_planner_state(state, repair_context)

        _raise_boundary_error(boundary_error)

        _require_invocation_progress(
            active, repair_before, "planner", repair=True
        )

        if adapter_failed:
            raise S05PlannerError("execution_failed")

        try:
            validated_plan = _validate_research_plan(raw_plan)
        except Exception:
            pass

    if validated_plan is None:
        raise S05PlannerError("invalid_output")

    return {
        "plan": validated_plan,
        "stage": "planned",
        "counters": _verified_stage_counters(1),
    }



def _planner_repair_eligible(candidate):
    """Positively identify a bounded malformed plan.

    This decision does not authorize adapter invocation.
    Public repair remains disabled.
    """

    raw = _repair_model_fields(
        candidate, ResearchPlan
    )

    if raw is None:
        return False

    questions = raw["subquestions"]
    assumptions = raw["assumptions"]

    if type(questions) is not tuple:
        return False

    if not 1 <= len(questions) <= 4:
        return False

    if type(assumptions) is not tuple:
        return False

    if len(assumptions) > 4:
        return False

    if not all(
        _repair_text_inspectable(item, 1000)
        for item in assumptions
    ):
        return False

    for question in questions:
        fields = _repair_model_fields(
            question, ResearchSubquestion
        )

        if fields is None:
            return False

        if not _repair_text_inspectable(
            fields["subquestion_id"], 2
        ):
            return False

        if not _repair_text_inspectable(
            fields["question"], 1000
        ):
            return False

        if not _repair_text_inspectable(
            fields["query"], 1000
        ):
            return False

    # Positive evidence is independent of validator
    # exception categories.
    malformed = any(
        not note.strip()
        for note in assumptions
    )

    identifiers = []

    for question in questions:
        fields = _repair_model_fields(
            question, ResearchSubquestion
        )

        if fields is None:
            return False

        identifier = fields["subquestion_id"]
        identifiers.append(identifier)

        if identifier not in ("q1", "q2", "q3", "q4"):
            malformed = True

        if not fields["question"].strip():
            malformed = True

        if not fields["query"].strip():
            malformed = True

    if len(identifiers) != len(set(identifiers)):
        malformed = True

    if not malformed:
        return False

    # The existing strict validator must independently
    # reject the positively identified malformed output.

    from agentops_api.agent.s05.validation import (
        S05BoundaryError,
    )

    try:
        _validate_research_plan(candidate)

    except S05BoundaryError as error:
        return type(error) is S05BoundaryError

    except Exception:
        return False

    return False
