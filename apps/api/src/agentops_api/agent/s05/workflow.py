"""Actual offline specialized LangGraph for Sprint S05.

This module implements only the normal unrepaired path.
Execution guards and global repair are deferred to WP04.
"""

from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from agentops_api.agent.s05.adapters import (
    validate_fixture_research_output,
)
from agentops_api.agent.s05.controller import (
    ExecutionController,
    S05BudgetError,
    S05DeadlineError,
    _InvalidDeadlineError,
    _ACTIVE_CONTROLLER,
    _REQUIRED_CONTROLLER,
    _current_controller,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
    ExecutionCounters,
    ExecutionPolicy,
    FixtureRecord,
    FixtureReference,
    ResearchOutput,
    ResearchPlan,
    ResearchSubquestion,
    ReportSection,
    S05Versions,
    S05GraphInput,
    S05GraphResult,
    S05GraphState,
)
from agentops_api.agent.s05.evidence import (
    _verify_evidence_state,
    evidence_validation_node,
    route_after_evidence,
)
from agentops_api.agent.s05.outcome import (
    outcome_node,
)
from agentops_api.agent.s05.planner import (
    S05PlannerError,
    planner_node,
)
from agentops_api.agent.s05.research import (
    S05ResearchError,
    _verify_research_state,
    research_node,
)
from agentops_api.agent.s05.report import (
    S05ReportError,
    validate_draft_report,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05BoundaryError,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
    build_initial_state,
    create_execution_context,
    verify_protected_state,
)
from agentops_api.agent.s05.writer import (
    S05WriterError,
    _verify_written_state,
    report_validation_node,
    writer_node,
)

from agentops_api.agent.s05.controller import (
    _approved_history,
    _strict_history_equal,
    _verified_stage_counters,
    _verify_stage_accounting,
)


_RECURSION_LIMIT = 12


class S05WorkflowError(ValueError):
    """Sanitized failure at the public workflow boundary."""

    def __init__(self, category: str) -> None:
        if category not in (
            "invalid_input",
            "invalid_output",
            "execution_failed",
            "security_violation",
            "deadline_exceeded",
            "budget_exceeded",
        ):
            category = "execution_failed"

        self.category = category

        super().__init__("S05 workflow failed")


def _runtime_context(
    runtime: Runtime[ExecutionContext],
) -> ExecutionContext:
    context = None

    try:
        context = _validated_context_copy(
            runtime.context
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

    if context is None:
        raise S05StateIntegrityError()

    return context


_NODE_OWNERSHIP = {
    "planner": (
        "plan", "stage", "counters",
    ),
    "research": (
        "research_output", "fixture_coverage",
        "stage", "counters",
    ),
    "evidence": (
        "research_output", "fixture_coverage", "stage",
    ),
    "writer": (
        "draft_report", "stage", "counters",
    ),
    "report_validation": (
        "draft_report", "stage",
    ),
    "outcome": (
        "result", "stage",
    ),
}

_SNAPSHOT_MODEL_TYPES = (
    ExecutionPolicy,
    ExecutionCounters,
    S05Versions,
    ResearchSubquestion,
    ResearchPlan,
    FixtureReference,
    FixtureRecord,
    ResearchOutput,
    ReportSection,
    DraftReport,
    S05GraphResult,
)


_MAX_SNAPSHOT_VISITS = 32768


def _integrity_snapshot(value, depth=0, budget=None):
    """Capture bounded, immutable, exact-type state evidence.

    No arbitrary object serialization, deepcopy hooks or
    caller-controlled equality methods are used.
    """

    if budget is None:
        budget = [_MAX_SNAPSHOT_VISITS]

    budget[0] -= 1

    if budget[0] < 0:
        raise ValueError("snapshot work bound exceeded")

    if depth > 16:
        raise ValueError("snapshot depth exceeded")

    kind = type(value)

    if kind is type(None):
        return ("none",)

    if kind is bool:
        return ("bool", value)

    if kind is int:
        return ("int", value)

    if kind is str:
        if len(value) > 8192:
            raise ValueError("snapshot text exceeds bounds")

        return ("str", value)

    if kind is float:
        return ("float", value.hex())

    if kind is UUID:
        integer = value.int

        if type(integer) is not int:
            raise ValueError("invalid UUID value")

        return ("uuid", integer)

    if kind is tuple or kind is list:
        if len(value) > 8192:
            raise ValueError("snapshot collection exceeds bounds")

        return (
            "tuple" if kind is tuple else "list",
            tuple(
                _integrity_snapshot(item, depth + 1, budget)
                for item in value
            ),
        )

    if kind is dict:
        if len(value) > 8192:
            raise ValueError("snapshot mapping exceeds bounds")

        if any(
            type(key) is not str or len(key) > 8192
            for key in value
        ):
            raise ValueError("invalid snapshot keys")

        return (
            "dict",
            tuple(
                (
                    key,
                    _integrity_snapshot(
                        value[key], depth + 1, budget
                    ),
                )
                for key in sorted(value)
            ),
        )

    if kind is ExecutionContext:
        return (
            "context",
            _integrity_snapshot(
                value.task_id, depth + 1, budget
            ),
            _integrity_snapshot(
                value.attempt_id, depth + 1, budget
            ),
            _integrity_snapshot(
                value.question, depth + 1, budget
            ),
            _integrity_snapshot(
                value.scope_json, depth + 1, budget
            ),
        )

    for contract_type in _SNAPSHOT_MODEL_TYPES:
        if kind is contract_type:
            fields = value.__dict__
            metadata = value.model_fields_set
            expected_count = len(
                contract_type.model_fields
            )

            if (
                type(fields) is not dict
                or len(fields) != expected_count
                or type(metadata) is not set
                or len(metadata) > expected_count
            ):
                raise ValueError("invalid snapshot model shape")

            _verify_exact_model_shape(
                value, contract_type
            )

            if value.__pydantic_private__ is not None:
                raise ValueError("invalid private metadata")

            return (
                "contract",
                contract_type.__name__,
                tuple(sorted(value.model_fields_set)),
                _integrity_snapshot(
                    value.__dict__, depth + 1, budget
                ),
            )

    raise ValueError("unsupported snapshot type")


def _checked_snapshot(value):
    """Convert snapshot failures into sanitized integrity errors."""

    snapshot = None

    try:
        snapshot = _integrity_snapshot(value)
    except Exception:
        pass

    if snapshot is None:
        raise S05StateIntegrityError()

    return snapshot


def _require_unchanged(value, before):
    if _checked_snapshot(value) != before:
        raise S05StateIntegrityError()


def _expected_route(state):
    output = state["research_output"]

    if type(output) is not ResearchOutput:
        raise S05StateIntegrityError()

    if (
        output.fixture_coverage == 1.0
        and output.records
        and not output.gaps
        and not output.conflicts
    ):
        return "writer"

    return "abstain"


def _expected_terminal_result(state, context):
    """Build terminal authority independently of node output."""

    verify_protected_state(state, context)

    trusted = _validated_context_copy(context)

    if _strict_equal(
        state["stage"], "report_validated"
    ):
        written = {
            **state,
            "stage": "written",
        }

        plan, output = _verify_written_state(
            written, trusted
        )

        candidate = validate_draft_report(
            trusted,
            plan,
            output,
            state["draft_report"],
        )

        stage = "candidate_ready"
        count = 3

    elif _strict_equal(
        state["stage"], "evidence_validated"
    ):
        output = _verify_evidence_state(
            state, trusted, "evidence_validated"
        )

        if _expected_route(state) != "abstain":
            raise S05StateIntegrityError()

        candidate = None
        stage = "insufficient_evidence"
        count = 2

    else:
        raise S05StateIntegrityError()

    return S05GraphResult(
        task_id=trusted.task_id,
        attempt_id=trusted.attempt_id,
        stage=stage,
        outcome=stage,
        candidate=candidate,
        evidence_ids=(),
        coverage=0.0,
        fixture_coverage=output.fixture_coverage,
        publishable=False,
        versions=trusted.versions,
        counters=_verified_stage_counters(count),
    )


def _verify_update_payload(
    name, state, proposed, update, context
):
    """Validate successful node payloads before merge.

    A node returning a malformed validated-channel update
    violates the graph boundary. Adapter errors raised
    before the node returns retain their existing categories.
    """

    valid = False

    try:
        if name == "planner":
            _verify_research_state(
                proposed, context
            )

        elif name in ("research", "evidence"):
            checked = _verify_evidence_state(
                proposed,
                context,
                proposed["stage"],
            )

            # The fixture registry determines the complete
            # research payload, including its provenance.
            validate_fixture_research_output(
                context,
                proposed["plan"],
                checked,
            )

        elif name in ("writer", "report_validation"):
            written = {
                **proposed,
                "stage": "written",
            }

            plan, output = _verify_written_state(
                written, context
            )

            report = validate_draft_report(
                context,
                plan,
                output,
                update["draft_report"],
            )

            if not _strict_terminal_equal(
                update["draft_report"], report
            ):
                raise S05StateIntegrityError()

            if name == "report_validation":
                # Validation may reconstruct the report,
                # but cannot replace its approved content.
                if not _strict_terminal_equal(
                    report, state["draft_report"]
                ):
                    raise S05StateIntegrityError()

        elif name == "outcome":
            expected = _expected_terminal_result(
                state, context
            )

            if not _strict_terminal_equal(
                update["result"], expected
            ):
                raise S05StateIntegrityError()

        else:
            raise S05StateIntegrityError()

        valid = True

    except Exception:
        pass

    if not valid:
        raise S05StateIntegrityError()


def _validate_node_update(name, state, update, context):
    """Reject unauthorized updates before graph merge."""

    if type(update) is not dict:
        raise S05StateIntegrityError()

    allowed = _NODE_OWNERSHIP[name]

    if len(update) != len(allowed):
        raise S05StateIntegrityError()

    if any(type(key) is not str for key in update):
        raise S05StateIntegrityError()

    if set(update) != set(allowed):
        raise S05StateIntegrityError()

    _checked_snapshot(update)

    transitions = {
        "planner": ("pending", "planned"),
        "research": ("planned", "researched"),
        "evidence": ("researched", "evidence_validated"),
        "writer": ("evidence_validated", "written"),
        "report_validation": ("written", "report_validated"),
    }

    if name == "outcome":
        if _strict_equal(
            state["stage"], "report_validated"
        ):
            expected_stage = "candidate_ready"

        elif _strict_equal(
            state["stage"], "evidence_validated"
        ):
            expected_stage = "insufficient_evidence"

        else:
            raise S05StateIntegrityError()

    else:
        prior_stage, expected_stage = transitions[name]

        if not _strict_equal(state["stage"], prior_stage):
            raise S05StateIntegrityError()

    if not _strict_equal(
        update["stage"], expected_stage
    ):
        raise S05StateIntegrityError()

    required_types = {
        "plan": ResearchPlan,
        "research_output": ResearchOutput,
        "fixture_coverage": float,
        "draft_report": DraftReport,
        "counters": ExecutionCounters,
        "result": S05GraphResult,
    }

    for key, expected_type in required_types.items():
        if key in update:
            if type(update[key]) is not expected_type:
                raise S05StateIntegrityError()

    # This ticket supports only the normal unrepaired
    # path. Controller-owned accounting follows in WP04-06.
    expected_counts = {
        "planner": 1,
        "research": 2,
        "writer": 3,
    }

    if name in expected_counts:
        expected = _verified_stage_counters(
            expected_counts[name]
        )

        if not _strict_terminal_equal(
            update["counters"], expected
        ):
            raise S05StateIntegrityError()

    if "fixture_coverage" in update:
        coverage = update["fixture_coverage"]
        output = update["research_output"]

        if not 0.0 <= coverage <= 1.0:
            raise S05StateIntegrityError()

        if not _strict_equal(
            coverage, output.fixture_coverage
        ):
            raise S05StateIntegrityError()

    proposed = dict(state)
    proposed.update(update)

    active = _current_controller()

    if active is not None:
        proposed["repair_used"] = active.repair_used

    verify_protected_state(proposed, context)

    _verify_update_payload(
        name, state, proposed, update, context
    )

    if name == "outcome":
        result = update["result"]

        if not _strict_equal(
            result.stage, expected_stage
        ):
            raise S05StateIntegrityError()

        if not _strict_equal(
            result.outcome, expected_stage
        ):
            raise S05StateIntegrityError()

    return update


def _verify_accounting_snapshot(state):
    """Reconcile graph accounting with execution authority."""

    controller = _current_controller()

    if controller is None:
        return

    expected = controller.snapshot()

    if not _strict_terminal_equal(
        state["counters"], expected
    ):
        raise S05StateIntegrityError()

    if state["repair_used"] is not controller.repair_used:
        raise S05StateIntegrityError()

    if expected.repair_attempts not in (0, 1):
        raise S05StateIntegrityError()


def _guarded_call(name, operation, state, runtime):
    """Verify node ownership and input integrity on all paths."""

    context = _runtime_context(runtime)

    _verify_accounting_snapshot(state)

    controller = _current_controller()

    history_before = (
        controller.invocation_history
        if controller is not None
        else None
    )

    state_before = _checked_snapshot(state)
    context_before = _checked_snapshot(context)

    runtime_context_before = _checked_snapshot(
        runtime.context
    )

    verify_protected_state(state, context)

    if controller is not None:
        controller.check_deadline()

    update = None
    failed = False

    try:
        update = operation(state, context)

    except Exception as error:
        failed = True

        # Integrity failures outrank an ordinary node error.
        # Re-raise the original exception only when all
        # application-owned inputs remain unchanged.
        try:
            _require_unchanged(state, state_before)
            _require_unchanged(context, context_before)

            _require_unchanged(
                runtime.context, runtime_context_before
            )

            if (
                _current_controller()
                is not controller
            ):
                raise S05StateIntegrityError()

        except Exception:
            pass

        else:
            if (
                controller is not None
                and type(error) is not S05StateIntegrityError
            ):
                controller.check_deadline()

            raise

    # Repeat the checks outside any exception handler so
    # integrity errors do not retain raw exception context.
    _require_unchanged(state, state_before)
    _require_unchanged(context, context_before)

    _require_unchanged(
        runtime.context, runtime_context_before
    )

    verify_protected_state(state, context)

    if failed:
        raise S05StateIntegrityError()

    if controller is not None:
        if _current_controller() is not controller:
            raise S05StateIntegrityError()

        expected_history = history_before

        if name in ("planner", "research", "writer"):
            expected_history = (
                *history_before,
                (name, False),
            )

        permitted = [expected_history]

        if name in ("planner", "writer"):
            permitted.append(
                (*expected_history, (name, True))
            )

        if not any(
            _strict_history_equal(
                controller.invocation_history, history
            )
            for history in permitted
        ):
            raise S05StateIntegrityError()

    if name == "route":
        expected = _expected_route(state)

        if not _strict_equal(update, expected):
            raise S05StateIntegrityError()

        if controller is not None:
            controller.check_deadline()

        return update

    validated = _validate_node_update(
        name, state, update, context
    )

    # The node cannot declare repair_used; only this
    # application-owned guard may add the channel.
    if controller is not None:
        if state["repair_used"] is not controller.repair_used:
            validated = {
                **validated,
                "repair_used": controller.repair_used,
            }

    _verify_accounting_snapshot(
        {**state, **validated}
    )

    if controller is not None:
        controller.check_deadline()

    return validated


def _planner(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "planner", planner_node, state, runtime
    )


def _research(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "research", research_node, state, runtime
    )


def _evidence(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "evidence", evidence_validation_node, state, runtime
    )


def _route(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "route", route_after_evidence, state, runtime
    )


def _writer(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "writer", writer_node, state, runtime
    )


def _report_validation(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "report_validation", report_validation_node, state, runtime
    )


def _outcome(
    state: S05GraphState,
    runtime: Runtime[ExecutionContext],
):
    return _guarded_call(
        "outcome", outcome_node, state, runtime
    )


def _build_graph():
    """Build a finite ephemeral graph using approved nodes."""

    builder = StateGraph(
        S05GraphState,
        context_schema=ExecutionContext,
    )

    builder.add_node("planner", _planner)
    builder.add_node("research", _research)
    builder.add_node("evidence_validation", _evidence)
    builder.add_node("writer", _writer)
    builder.add_node(
        "report_validation", _report_validation
    )
    builder.add_node("outcome", _outcome)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "research")
    builder.add_edge(
        "research", "evidence_validation"
    )

    builder.add_conditional_edges(
        "evidence_validation",
        _route,
        {
            "writer": "writer",
            "abstain": "outcome",
        },
    )

    builder.add_edge(
        "writer", "report_validation"
    )

    builder.add_edge(
        "report_validation", "outcome"
    )

    builder.add_edge("outcome", END)

    return builder.compile(
        checkpointer=None,
        store=None,
        cache=None,
    )


def _strict_terminal_equal(
    actual,
    expected,
    depth: int = 0,
) -> bool:
    """Compare raw terminal values against trusted bounded shapes.

    The expected result controls traversal. No serialization or
    normalization of the untrusted result is performed here.
    """

    if depth > 12:
        return False

    expected_type = type(expected)

    if type(actual) is not expected_type:
        return False

    if expected_type in (
        S05GraphResult,
        S05Versions,
        ExecutionCounters,
        DraftReport,
        ReportSection,
        FixtureReference,
    ):
        _verify_exact_model_shape(
            actual, expected_type
        )

        _verify_exact_model_shape(
            expected, expected_type
        )

        # Terminal contracts have no application private fields.
        if actual.__pydantic_private__ is not None:
            return False

        if expected.__pydantic_private__ is not None:
            return False

        return all(
            _strict_terminal_equal(
                actual.__dict__[name],
                expected.__dict__[name],
                depth + 1,
            )
            for name in expected_type.model_fields
        )

    if expected_type is tuple:
        if len(actual) != len(expected):
            return False

        return all(
            _strict_terminal_equal(
                left, right, depth + 1
            )
            for left, right in zip(actual, expected)
        )

    if expected_type is UUID:
        # Exact UUID types have already been established.
        return (
            type(actual.int) is int
            and type(expected.int) is int
            and actual.int == expected.int
        )

    if expected_type in (
        str, int, float, bool, type(None)
    ):
        return _strict_equal(actual, expected)

    # Unexpected types are never considered equivalent.
    return False


def _verify_terminal_state(
    state: S05GraphState,
    context: ExecutionContext,
) -> S05GraphResult:
    """Verify terminal state and independently rebuild result."""

    _checked_snapshot(state)
    verify_protected_state(state, context)

    valid = False
    expected = None

    try:
        result = state["result"]

        _verify_exact_model_shape(
            result, S05GraphResult
        )

        if _strict_equal(
            state["stage"], "candidate_ready"
        ):
            previous_stage = "report_validated"

        elif _strict_equal(
            state["stage"], "insufficient_evidence"
        ):
            previous_stage = "evidence_validated"

        else:
            raise ValueError("invalid terminal stage")

        previous = {
            **state,
            "stage": previous_stage,
            "result": None,
        }

        expected = _expected_terminal_result(
            previous, context
        )

        reconstructed = _guarded_call(
            "outcome",
            outcome_node,
            previous,
            Runtime(context=context),
        )

        if not _strict_terminal_equal(
            reconstructed["result"], expected
        ):
            raise ValueError(
                "invalid reconstructed result"
            )

        if not _strict_terminal_equal(
            result, expected
        ):
            raise ValueError("invalid terminal result")

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

    if not valid or expected is None:
        raise S05StateIntegrityError()

    return expected


def _classify_execution_error(
    error: Exception,
) -> str:
    """Map exact trusted exception types to safe categories.

    Unknown exceptions and subclasses are never inspected
    for category attributes, messages or traceback data.
    """

    error_type = type(error)

    if error_type is S05StateIntegrityError:
        return "security_violation"

    if error_type is S05DeadlineError:
        return "deadline_exceeded"

    if error_type is S05BudgetError:
        return "budget_exceeded"

    if error_type is S05ReportError:
        return "invalid_output"

    if error_type is S05WriterError:
        return "execution_failed"

    if (
        error_type is S05PlannerError
        or error_type is S05ResearchError
    ):
        # Only these exact application-owned classes
        # have a variable internal error category.
        # Read the known storage field, not a property.
        fields = object.__getattribute__(
            error, "__dict__"
        )

        if type(fields) is not dict:
            return "execution_failed"

        # Do not invoke equality on unexpected keys.
        if any(
            type(key) is not str
            for key in fields
        ):
            return "execution_failed"

        category = fields.get("_category")

        if type(category) is str and category in (
            "invalid_output",
            "execution_failed",
        ):
            return category

    return "execution_failed"


def run_specialized_workflow(
    request: S05GraphInput,
    *,
    deadline_monotonic: int | float | None = None,
) -> S05GraphResult:
    """Execute the approved synthetic workflow in memory.

    No caller-supplied graph config, durable checkpoint,
    provider access, publication or task mutation.
    """

    context = None
    controller = None
    input_category = "execution_failed"

    try:
        controller = ExecutionController(
            deadline_monotonic=deadline_monotonic
        )

    except Exception as error:
        if type(error) is _InvalidDeadlineError:
            input_category = "invalid_input"
        else:
            input_category = _classify_execution_error(
                error
            )

    if controller is None:
        raise S05WorkflowError(input_category)

    try:
        context = create_execution_context(
            request
        )

    except Exception as error:
        if type(error) is S05BoundaryError:
            input_category = "invalid_input"

    if context is None:
        raise S05WorkflowError(input_category)

    result = None
    category = "execution_failed"

    required_token = _REQUIRED_CONTROLLER.set(
        controller
    )
    token = _ACTIVE_CONTROLLER.set(controller)

    try:
        controller.check_deadline()

        graph_context = _validated_context_copy(
            context
        )

        graph = _build_graph()

        controller.check_deadline()

        final_state = graph.invoke(
            build_initial_state(context),
            config={
                "recursion_limit": _RECURSION_LIMIT,
            },
            context=graph_context,
        )

        verify_protected_state(
            final_state, graph_context
        )

        if _current_controller() is not controller:
            raise S05StateIntegrityError()

        _verify_accounting_snapshot(final_state)

        verified = _verify_terminal_state(
            final_state, context
        )

        _verify_accounting_snapshot(final_state)

        if not _strict_terminal_equal(
            verified.counters,
            controller.snapshot(),
        ):
            raise S05StateIntegrityError()

        if verified.outcome == "candidate_ready":
            expected_history = (
                ("planner", False),
                ("research", False),
                ("writer", False),
            )

        elif verified.outcome == "insufficient_evidence":
            expected_history = (
                ("planner", False),
                ("research", False),
            )

        else:
            raise S05StateIntegrityError()

        normal_count = len(expected_history)

        _verify_stage_accounting(final_state, normal_count)

        controller.check_deadline()

        result = verified

    except Exception as error:
        category = _classify_execution_error(error)

        if category != "security_violation":
            try:
                controller.check_deadline()

            except Exception as deadline_error:
                category = _classify_execution_error(
                    deadline_error
                )

    finally:
        try:
            _ACTIVE_CONTROLLER.reset(token)
        finally:
            _REQUIRED_CONTROLLER.reset(
                required_token
            )

    if result is None:
        raise S05WorkflowError(category)

    return result
