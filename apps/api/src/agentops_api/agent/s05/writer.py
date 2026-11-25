"""Offline Writer and Report Validation nodes for Sprint S05."""

from typing import Literal

from typing_extensions import TypedDict

from agentops_api.agent.s05.adapters import (
    _validate_research_plan,
    validate_fixture_research_output,
    writer_fixture,
)
from agentops_api.agent.s05.controller import (
    _InvocationBoundaryError,
    _invocation_counters,
    _invoke_fixture,
    _raise_boundary_error,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
    ExecutionCounters,
    ResearchOutput,
    ResearchPlan,
    S05GraphState,
)
from agentops_api.agent.s05.evidence import (
    _verify_evidence_state,
)
from agentops_api.agent.s05.report import (
    validate_draft_report,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
    verify_protected_state,
)

from agentops_api.agent.s05.controller import (
    _current_controller,
    _verified_stage_counters,
    _verify_stage_accounting,
    _verify_incoming_accounting,
    _repair_available,
    _invoke_authorized_repair,
    _require_invocation_progress,
)

from agentops_api.agent.s05.report import (
    S05ReportError,
    _writer_repair_eligible,
)


class WriterUpdate(TypedDict):
    """Channels owned by the Writer node."""

    draft_report: DraftReport
    stage: Literal["written"]
    counters: ExecutionCounters


class ReportValidationUpdate(TypedDict):
    """Channels owned by Report Validation."""

    draft_report: DraftReport
    stage: Literal["report_validated"]


class S05WriterError(ValueError):
    """Safe Writer execution failure."""

    category = "execution_failed"

    def __init__(self) -> None:
        super().__init__("S05 writer failed")


def _require_sufficient_output(
    output: ResearchOutput,
) -> None:
    if (
        output.fixture_coverage != 1.0
        or not output.records
        or output.gaps
        or output.conflicts
    ):
        raise S05StateIntegrityError()


def _verify_writer_state(
    state: S05GraphState,
    context: ExecutionContext,
    *, incoming=None,
) -> tuple[ResearchPlan, ResearchOutput]:
    """Verify the normal evidence-validated boundary."""

    output = _verify_evidence_state(
        state,
        context,
        "evidence_validated", incoming=incoming,
    )

    _require_sufficient_output(output)

    plan = _validate_research_plan(
        state["plan"]
    )

    return plan, output


def _verify_unchanged_plan(
    actual: ResearchPlan,
    expected: ResearchPlan,
) -> None:
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


def writer_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> WriterUpdate:
    """Invoke only the approved offline Writer adapter.

    This node supports the normal unrepaired path.
    No implicit retry or publication is performed.
    """

    trusted_context = _validated_context_copy(
        context
    )

    original_plan, original_output = (
        _verify_writer_state(
            state,
            trusted_context,
        )
    )

    adapter_context = _validated_context_copy(
        trusted_context
    )

    adapter_plan = _validate_research_plan(
        original_plan
    )

    adapter_output = validate_fixture_research_output(
        trusted_context,
        original_plan,
        original_output,
    )

    incoming = _verified_stage_counters(2)
    active = _current_controller()
    previous = (
        active.invocation_history if active is not None else ()
    )

    raw_candidate = None
    adapter_failed = False
    boundary_error = None

    try:
        raw_candidate = _invoke_fixture("writer", writer_fixture,
            adapter_context,
            adapter_plan,
            adapter_output,
        )

    except _InvocationBoundaryError as error:
        boundary_error = error
        adapter_failed = True

    except Exception:
        adapter_failed = True

    # Check persistent mutations even when the adapter fails.

    current_plan, current_output = (
        _verify_writer_state(
            state,
            trusted_context,
            incoming=incoming,
        )
    )

    _verify_writer_state(state, context, incoming=incoming)
    _verify_writer_state(state, adapter_context, incoming=incoming)

    _verify_unchanged_plan(
        current_plan,
        original_plan,
    )

    _verify_unchanged_plan(
        adapter_plan,
        original_plan,
    )

    validate_fixture_research_output(
        trusted_context,
        original_plan,
        current_output,
    )

    validate_fixture_research_output(
        trusted_context,
        original_plan,
        adapter_output,
    )

    _raise_boundary_error(boundary_error)

    _require_invocation_progress(
        active, previous, "writer", repair=False
    )

    if adapter_failed:
        raise S05WriterError()

    candidate = None
    malformed = False

    try:
        candidate = validate_draft_report(
            trusted_context,
            original_plan,
            original_output,
            raw_candidate,
        )
    except S05ReportError as error:
        if type(error) is not S05ReportError:
            raise
        malformed = True

    if (
        malformed
        and active is not None
        and _writer_repair_eligible(
            trusted_context, original_plan,
            original_output, raw_candidate
        ) is True
        and _repair_available()
    ):
        repair_before = active.invocation_history
        repair_context = _validated_context_copy(trusted_context)
        repair_plan = _validate_research_plan(original_plan)
        repair_output = validate_fixture_research_output(
            trusted_context, original_plan, original_output
        )

        adapter_failed = False
        boundary_error = None
        raw_candidate = None

        try:
            raw_candidate = _invoke_authorized_repair(
                "writer", writer_fixture,
                repair_context, repair_plan, repair_output,
            )
        except _InvocationBoundaryError as error:
            boundary_error = error
            adapter_failed = True
        except Exception:
            adapter_failed = True

        _verify_writer_state(state, context, incoming=incoming)
        _verify_writer_state(
            state, repair_context, incoming=incoming
        )

        _verify_unchanged_plan(repair_plan, original_plan)

        validate_fixture_research_output(
            trusted_context, original_plan, repair_output
        )

        _raise_boundary_error(boundary_error)

        _require_invocation_progress(
            active, repair_before, "writer", repair=True
        )

        if adapter_failed:
            raise S05WriterError()

        candidate = validate_draft_report(
            trusted_context, original_plan,
            original_output, raw_candidate,
        )

    if candidate is None:
        raise S05ReportError()

    return {
        "draft_report": candidate,
        "stage": "written",
        "counters": _verified_stage_counters(3),
    }


def _verify_written_state(
    state: S05GraphState,
    context: ExecutionContext,
) -> tuple[ResearchPlan, ResearchOutput]:
    """Revalidate the written-stage workflow boundary."""

    verify_protected_state(state, context)

    valid = False
    plan = None
    output = None

    try:
        if not _strict_equal(
            state["stage"], "written"
        ):
            raise ValueError("invalid report stage")

        if state["result"] is not None:
            raise ValueError("unexpected result")

        if state["error_category"] is not None:
            raise ValueError("unexpected error state")

        _verify_stage_accounting(state, 3)

        plan = _validate_research_plan(
            state["plan"]
        )

        output = validate_fixture_research_output(
            context,
            plan,
            state["research_output"],
        )

        _require_sufficient_output(output)

        if not _strict_equal(
            state["fixture_coverage"],
            output.fixture_coverage,
        ):
            raise ValueError("invalid fixture coverage")

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

    return plan, output


def report_validation_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> ReportValidationUpdate:
    """Validate a written report without invoking adapters."""

    trusted_context = _validated_context_copy(
        context
    )

    plan, output = _verify_written_state(
        state,
        trusted_context,
    )

    candidate = validate_draft_report(
        trusted_context,
        plan,
        output,
        state["draft_report"],
    )

    return {
        "draft_report": candidate,
        "stage": "report_validated",
    }
