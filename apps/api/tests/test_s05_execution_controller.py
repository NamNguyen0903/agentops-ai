"""WP04-06C: Independent S05 execution accounting tests."""

import pytest

from agentops_api.agent.s05.controller import (
    ExecutionController,
    S05BudgetError,
)
from agentops_api.agent.s05.validation import (
    S05StateIntegrityError,
)


ORDER = ("planner", "research", "writer")


def _success():
    return "offline fixture result"


def _normal_prefix(controller, length):
    for name in ORDER[:length]:
        controller.invoke(name, _success)


def test_sec09_initial_accounting():
    controller = ExecutionController()

    assert controller.invocation_history == ()
    assert controller.snapshot().adapter_invocations == 0
    assert controller.snapshot().repair_attempts == 0
    assert controller.repair_used is False


@pytest.mark.parametrize("length", [2, 3])
def test_sec09_normal_paths(length):
    controller = ExecutionController()

    _normal_prefix(controller, length)

    assert controller.snapshot().adapter_invocations == length
    assert controller.snapshot().repair_attempts == 0
    assert controller.invocation_history == tuple(
        (name, False)
        for name in ORDER[:length]
    )


@pytest.mark.parametrize("target", ORDER)
def test_sec09_reservation_precedes_execution(target):
    controller = ExecutionController()
    index = ORDER.index(target)

    _normal_prefix(controller, index)

    observed = []

    def adapter():
        observed.append(controller.snapshot())
        return "result"

    assert controller.invoke(target, adapter) == "result"

    assert len(observed) == 1
    assert observed[0].adapter_invocations == index + 1
    assert observed[0].repair_attempts == 0


@pytest.mark.parametrize("target", ORDER)
def test_sec09_failed_invocation_remains_counted(target):
    controller = ExecutionController()
    index = ORDER.index(target)

    _normal_prefix(controller, index)

    calls = []

    def fail():
        calls.append(
            controller.snapshot().adapter_invocations
        )
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError):
        controller.invoke(target, fail)

    assert calls == [index + 1]
    assert controller.snapshot().adapter_invocations == index + 1

    assert controller.invocation_history[-1] == (
        target, False
    )

    with pytest.raises(S05StateIntegrityError):
        controller.invoke(target, _success)

    assert controller.snapshot().adapter_invocations == index + 1


@pytest.mark.parametrize(
    "repair_target,length,expected",
    [
        ("planner", 2, 3),
        ("planner", 3, 4),
        ("writer", 3, 4),
    ],
)
def test_sec09_repair_accounting_scenarios(
    repair_target, length, expected
):
    controller = ExecutionController()

    for name in ORDER[:length]:
        controller.invoke(name, _success)

        if name == repair_target:
            observed = []

            def repair():
                observed.append(
                    controller.snapshot()
                )
                return "repaired fixture"

            assert controller._invoke_repair(
                name, repair
            ) == "repaired fixture"

            assert len(observed) == 1
            assert observed[0].repair_attempts == 1

    assert controller.snapshot().adapter_invocations == expected
    assert controller.snapshot().repair_attempts == 1
    assert controller.repair_used is True


@pytest.mark.parametrize(
    "repair_target", ["planner", "writer"]
)
def test_sec09_fifth_invocation_blocked(repair_target):
    controller = ExecutionController()

    for name in ORDER:
        controller.invoke(name, _success)

        if name == repair_target:
            controller._invoke_repair(
                name, _success
            )

    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05BudgetError) as error:
        controller.invoke("writer", forbidden)

    assert str(error.value) == "S05 execution budget exhausted"
    assert error.value.category == "budget_exceeded"

    assert calls == []
    assert controller.snapshot().adapter_invocations == 4
    assert controller.snapshot().repair_attempts == 1


def test_sec09_second_repair_blocked_before_budget_exhaustion():
    controller = ExecutionController()

    controller.invoke("planner", _success)
    controller._invoke_repair("planner", _success)

    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05BudgetError):
        controller._invoke_repair(
            "planner", forbidden
        )

    assert calls == []
    assert controller.snapshot().adapter_invocations == 2
    assert controller.snapshot().repair_attempts == 1


def test_sec09_repair_allowance_shared_between_agents():
    controller = ExecutionController()

    controller.invoke("planner", _success)
    controller._invoke_repair("planner", _success)
    controller.invoke("research", _success)
    controller.invoke("writer", _success)

    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05BudgetError):
        controller._invoke_repair(
            "writer", forbidden
        )

    assert calls == []
    assert controller.snapshot().adapter_invocations == 4
    assert controller.snapshot().repair_attempts == 1


@pytest.mark.parametrize("target", ["planner", "writer"])
def test_sec09_failed_repair_remains_counted(target):
    controller = ExecutionController()

    _normal_prefix(
        controller,
        ORDER.index(target) + 1,
    )

    calls = []

    def fail():
        calls.append(controller.snapshot())
        raise RuntimeError("synthetic repair failure")

    with pytest.raises(RuntimeError):
        controller._invoke_repair(target, fail)

    assert len(calls) == 1
    assert calls[0].repair_attempts == 1
    assert controller.snapshot() == calls[0]
    assert controller.repair_used is True


@pytest.mark.parametrize(
    "adapter",
    [
        None,
        True,
        1,
        "",
        "unknown",
        "external_search",
        "database",
        "publication",
    ],
)
def test_sec09_unknown_adapter_rejected(adapter):
    controller = ExecutionController()
    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05StateIntegrityError):
        controller.invoke(adapter, forbidden)

    assert calls == []
    assert controller.invocation_history == ()


def test_sec09_adapter_string_subclass_rejected():
    class AdapterName(str):
        pass

    controller = ExecutionController()

    with pytest.raises(S05StateIntegrityError):
        controller.invoke(
            AdapterName("planner"),
            _success,
        )

    assert controller.invocation_history == ()


@pytest.mark.parametrize(
    "prefix,target",
    [
        (0, "research"),
        (0, "writer"),
        (1, "planner"),
        (1, "writer"),
        (2, "planner"),
        (2, "research"),
        (3, "writer"),
    ],
)
def test_sec09_invalid_normal_order(prefix, target):
    controller = ExecutionController()

    _normal_prefix(controller, prefix)

    before = controller.snapshot()
    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05StateIntegrityError):
        controller.invoke(target, forbidden)

    assert calls == []
    assert controller.snapshot() == before


@pytest.mark.parametrize(
    "prefix,target",
    [
        (0, "planner"),
        (0, "writer"),
        (1, "writer"),
        (2, "planner"),
        (2, "research"),
        (3, "planner"),
    ],
)
def test_sec09_invalid_repair_order(prefix, target):
    controller = ExecutionController()

    _normal_prefix(controller, prefix)

    before = controller.snapshot()
    calls = []

    def forbidden():
        calls.append(True)

    with pytest.raises(S05StateIntegrityError):
        controller._invoke_repair(
            target, forbidden
        )

    assert calls == []
    assert controller.snapshot() == before


def test_sec09_noncallable_operation_not_reserved():
    controller = ExecutionController()

    with pytest.raises(S05StateIntegrityError):
        controller.invoke("planner", None)

    assert controller.invocation_history == ()


def test_sec09_reentrant_invocation_rejected():
    controller = ExecutionController()
    nested_calls = []

    def nested():
        nested_calls.append(True)

    def outer():
        return controller.invoke(
            "research", nested
        )

    with pytest.raises(S05StateIntegrityError):
        controller.invoke("planner", outer)

    assert nested_calls == []
    assert controller.snapshot().adapter_invocations == 1


def test_sec09_per_execution_isolation():
    first = ExecutionController()
    second = ExecutionController()

    first.invoke("planner", _success)
    first._invoke_repair("planner", _success)

    assert first.snapshot().adapter_invocations == 2
    assert first.repair_used is True

    assert second.snapshot().adapter_invocations == 0
    assert second.repair_used is False

    second.invoke("planner", _success)

    assert second.snapshot().adapter_invocations == 1
    assert first.snapshot().adapter_invocations == 2


def test_sec09_snapshot_is_independent():
    controller = ExecutionController()

    controller.invoke("planner", _success)

    snapshot = controller.snapshot()

    object.__setattr__(
        snapshot,
        "adapter_invocations",
        4,
    )

    assert controller.snapshot().adapter_invocations == 1
    assert controller.snapshot() is not snapshot


def test_sec09_history_is_immutable_snapshot():
    controller = ExecutionController()

    controller.invoke("planner", _success)
    old = controller.invocation_history

    controller.invoke("research", _success)

    assert old == (("planner", False),)

    assert controller.invocation_history == (
        ("planner", False),
        ("research", False),
    )


def test_sec09_operation_arguments_forwarded_once():
    controller = ExecutionController()
    calls = []

    def adapter(a, *, b):
        calls.append((a, b))
        return a + b

    assert controller.invoke(
        "planner", adapter, 2, b=3
    ) == 5

    assert calls == [(2, 3)]
    assert controller.snapshot().adapter_invocations == 1


# WP04-06D3C: Public workflow accounting integration.

from contextlib import ExitStack
from unittest.mock import patch
from uuid import UUID

from agentops_api.agent.s05 import (
    controller as accounting_controller,
    planner as accounting_planner,
    research as accounting_research,
    writer as accounting_writer,
    workflow as accounting_workflow,
)

from agentops_api.agent.s05.contract import (
    ResearchPlan,
    ResearchSubquestion,
    S05GraphInput,
    S05GraphResult,
)

from agentops_api.agent.s05.validation import (
    build_initial_state,
    create_execution_context,
)


_SEC09_ADAPTERS = {
    "planner": (
        accounting_planner,
        "plan_fixture",
    ),
    "research": (
        accounting_research,
        "research_fixture",
    ),
    "writer": (
        accounting_writer,
        "writer_fixture",
    ),
}

_SEC09_ORDER = tuple(_SEC09_ADAPTERS)


def _sec09_request():
    return S05GraphInput(
        task_id=UUID(int=1401),
        attempt_id=UUID(int=1402),
        question="Synthetic accounting integration test.",
        scope={"region": "offline"},
    )


def _sec09_assert_cleanup():
    assert (
        accounting_controller._ACTIVE_CONTROLLER.get()
        is None
    )

    assert (
        accounting_controller._REQUIRED_CONTROLLER.get()
        is None
    )

    assert (
        accounting_controller._current_controller()
        is None
    )


def _sec09_observe():
    try:
        result = (
            accounting_workflow.run_specialized_workflow(
                _sec09_request()
            )
        )

    except accounting_workflow.S05WorkflowError as error:
        assert type(error) is (
            accounting_workflow.S05WorkflowError
        )

        assert str(error) == "S05 workflow failed"
        assert error.__cause__ is None
        assert error.__context__ is None

        return error.category, None

    assert type(result) is S05GraphResult
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert type(result.coverage) is float
    assert result.coverage.hex() == 0.0.hex()
    assert result.counters.repair_attempts == 0

    return result.outcome, result


def _sec09_missing_plan(value):
    return ResearchPlan(
        subquestions=tuple(
            ResearchSubquestion(
                subquestion_id=item.subquestion_id,
                question=item.question,
                query=(
                    "fixture:missing-"
                    + item.subquestion_id
                ),
            )
            for item in value.subquestions
        ),
        assumptions=value.assumptions,
    )


def _sec09_execute(target=None, mode="normal"):
    entries = []
    instances = []
    observations = []

    def instrument(name, original):
        def wrapped(*args, **kwargs):
            active = (
                accounting_controller._current_controller()
            )

            assert type(active) is ExecutionController

            assert (
                accounting_controller._REQUIRED_CONTROLLER.get()
                is active
            )

            instances.append(active)
            entries.append(name)

            observations.append((
                name,
                active.snapshot().adapter_invocations,
                active.snapshot().repair_attempts,
                active.invocation_history,
            ))

            if name == target:
                if mode == "exception":
                    raise RuntimeError(
                        "synthetic failure"
                    )

                if mode == "budget_spoof":
                    raise S05BudgetError()

                if mode == "boundary_spoof":
                    raise accounting_controller._InvocationBoundaryError(
                        "budget_exceeded"
                    )

                if mode == "malformed":
                    return None

            value = original(*args, **kwargs)

            if name == "planner" and mode == "abstain":
                return _sec09_missing_plan(value)

            return value

        return wrapped

    _sec09_assert_cleanup()

    with ExitStack() as stack:
        for name, (module, attr) in _SEC09_ADAPTERS.items():
            stack.enter_context(
                patch.object(
                    module,
                    attr,
                    instrument(
                        name,
                        getattr(module, attr),
                    ),
                )
            )

        actual, result = _sec09_observe()

    _sec09_assert_cleanup()

    return actual, result, entries, instances, observations


def _sec09_verify_accounting(execution, expected):
    actual, result, entries, instances, observations = execution

    history = tuple(
        (name, False)
        for name in expected
    )

    assert entries == list(expected)
    assert len(instances) == len(expected)
    assert instances

    active = instances[0]

    assert all(
        item is active
        for item in instances
    )

    assert active.invocation_history == history

    assert active.snapshot().adapter_invocations == len(
        expected
    )

    assert active.snapshot().repair_attempts == 0

    assert observations == [
        (
            name,
            index + 1,
            0,
            history[:index + 1],
        )
        for index, name in enumerate(expected)
    ]

    if result is not None:
        assert result.counters == active.snapshot()

    return active


@pytest.mark.parametrize(
    "mode,outcome,length",
    [
        ("normal", "candidate_ready", 3),
        ("abstain", "insufficient_evidence", 2),
    ],
)
def test_sec09_integration_normal_paths(
    mode, outcome, length
):
    execution = _sec09_execute(mode=mode)

    assert execution[0] == outcome

    _sec09_verify_accounting(
        execution,
        _SEC09_ORDER[:length],
    )


@pytest.mark.parametrize("target", _SEC09_ORDER)
@pytest.mark.parametrize(
    "mode",
    [
        "exception",
        "budget_spoof",
        "boundary_spoof",
    ],
)
def test_sec09_integration_failed_invocation(target, mode):
    execution = _sec09_execute(target, mode)

    assert execution[0] == "execution_failed"
    assert execution[1] is None

    active = _sec09_verify_accounting(
        execution,
        _SEC09_ORDER[
            :_SEC09_ORDER.index(target) + 1
        ],
    )

    assert active._failed is True
    assert active._active is False


@pytest.mark.parametrize("target", ["planner", "writer"])
def test_sec09_integration_malformed_without_repair(target):
    execution = _sec09_execute(
        target,
        "malformed",
    )

    assert execution[0] == "invalid_output"

    _sec09_verify_accounting(
        execution,
        _SEC09_ORDER[
            :_SEC09_ORDER.index(target) + 1
        ],
    )


@pytest.mark.parametrize("target", _SEC09_ORDER)
def test_sec09_integration_reservation_rejection(target):
    entries = []
    rejected = []

    original = ExecutionController._reserve

    def reserve(self, adapter, repair=False):
        if adapter == target:
            rejected.append(self.invocation_history)
            raise S05BudgetError()

        return original(self, adapter, repair)

    def spy(name, operation):
        def wrapped(*args, **kwargs):
            entries.append(name)
            return operation(*args, **kwargs)

        return wrapped

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                ExecutionController,
                "_reserve",
                reserve,
            )
        )

        for name, (module, attr) in _SEC09_ADAPTERS.items():
            stack.enter_context(
                patch.object(
                    module,
                    attr,
                    spy(name, getattr(module, attr)),
                )
            )

        actual, result = _sec09_observe()

    prefix = _SEC09_ORDER[
        :_SEC09_ORDER.index(target)
    ]

    assert actual == "budget_exceeded"
    assert result is None
    assert entries == list(prefix)

    assert rejected == [
        tuple((name, False) for name in prefix)
    ]

    _sec09_assert_cleanup()


def test_sec09_integration_counter_without_invocation():
    context = create_execution_context(
        _sec09_request()
    )

    prebuilt = accounting_planner.planner_node(
        build_initial_state(context),
        context,
    )

    with patch.object(
        accounting_workflow,
        "planner_node",
        return_value=prebuilt,
    ), patch.object(
        accounting_research,
        "research_fixture",
    ) as forbidden:
        actual, result = _sec09_observe()

    assert actual == "security_violation"
    assert result is None
    forbidden.assert_not_called()

    _sec09_assert_cleanup()


@pytest.mark.parametrize("target", _SEC09_ORDER)
@pytest.mark.parametrize(
    "mode",
    [
        "missing_active",
        "missing_required",
        "replacement_active",
    ],
)
def test_sec09_integration_invalid_binding(target, mode):
    module, attr = _SEC09_ADAPTERS[target]

    node_name = target + "_node"

    original = getattr(
        accounting_workflow,
        node_name,
    )

    entries = []

    def forbidden(*args, **kwargs):
        entries.append(True)
        return None

    def corrupt(state, context):
        if mode == "missing_required":
            binding = (
                accounting_controller._REQUIRED_CONTROLLER
            )
        else:
            binding = (
                accounting_controller._ACTIVE_CONTROLLER
            )

        replacement = (
            ExecutionController()
            if mode == "replacement_active"
            else None
        )

        token = binding.set(replacement)

        try:
            return original(state, context)

        finally:
            binding.reset(token)

    with patch.object(
        accounting_workflow,
        node_name,
        corrupt,
    ), patch.object(
        module,
        attr,
        forbidden,
    ):
        actual, result = _sec09_observe()

    assert actual == "security_violation"
    assert result is None
    assert entries == []

    _sec09_assert_cleanup()


def test_sec09_integration_sequential_isolation():
    first = _sec09_execute()
    second = _sec09_execute()

    assert first[0] == second[0] == "candidate_ready"

    first_controller = _sec09_verify_accounting(
        first, _SEC09_ORDER
    )

    second_controller = _sec09_verify_accounting(
        second, _SEC09_ORDER
    )

    assert first_controller is not second_controller

    _sec09_assert_cleanup()


@pytest.mark.parametrize("target", _SEC09_ORDER)
def test_sec09_integration_security_precedes_adapter_failure(
    target
):
    module, attr = _SEC09_ADAPTERS[target]
    captured = []

    def corrupt(adapter_context, *args, **kwargs):
        active = (
            accounting_controller._current_controller()
        )

        captured.append(active)

        object.__setattr__(
            adapter_context,
            "task_id",
            UUID(int=9999),
        )

        raise accounting_controller._InvocationBoundaryError(
            "budget_exceeded"
        )

    with patch.object(module, attr, corrupt):
        actual, result = _sec09_observe()

    assert actual == "security_violation"
    assert result is None
    assert len(captured) == 1

    assert captured[0].snapshot().adapter_invocations == (
        _SEC09_ORDER.index(target) + 1
    )

    assert captured[0]._failed is True

    _sec09_assert_cleanup()



# WP04-06E2: Positive malformed-output eligibility.

from agentops_api.agent.s05.adapters import (
    plan_fixture as _eligibility_plan_fixture,
    research_fixture as _eligibility_research_fixture,
    writer_fixture as _eligibility_writer_fixture,
)

from agentops_api.agent.s05.planner import (
    _planner_repair_eligible,
)

from agentops_api.agent.s05.report import (
    _writer_repair_eligible,
    validate_draft_report,
    S05ReportError,
)


def _eligibility_inputs():
    context = create_execution_context(
        _sec09_request()
    )

    plan = _eligibility_plan_fixture(context)

    output = _eligibility_research_fixture(
        context, plan
    )

    report = _eligibility_writer_fixture(
        context, plan, output
    )

    return context, plan, output, report


def test_sec09_eligibility_valid_outputs_not_eligible():
    context, plan, output, report = _eligibility_inputs()

    assert _planner_repair_eligible(plan) is False

    assert _writer_repair_eligible(
        context, plan, output, report
    ) is False


@pytest.mark.parametrize(
    "field",
    ["question", "query", "subquestion_id"],
)
def test_sec09_eligibility_planner_malformed_text(field):
    _, plan, _, _ = _eligibility_inputs()

    first = plan.subquestions[0].model_copy(
        update={field: ""}
    )

    malformed = plan.model_copy(
        update={
            "subquestions": (
                first,
                *plan.subquestions[1:],
            ),
        }
    )

    assert _planner_repair_eligible(malformed) is True


def test_sec09_eligibility_duplicate_subquestion():
    _, plan, _, _ = _eligibility_inputs()

    malformed = plan.model_copy(
        update={
            "subquestions": (
                plan.subquestions[0],
                plan.subquestions[0],
            ),
        }
    )

    assert _planner_repair_eligible(malformed) is True


@pytest.mark.parametrize(
    "mode",
    [
        "none",
        "list",
        "oversized",
        "unknown_field",
        "nested_object",
        "wrong_text_type",
        "oversized_text",
        "invalid_metadata",
    ],
)
def test_sec09_eligibility_planner_uninspectable(mode):
    _, plan, _, _ = _eligibility_inputs()

    if mode == "none":
        candidate = None

    elif mode == "list":
        candidate = plan.model_copy(
            update={
                "subquestions": list(plan.subquestions)
            }
        )

    elif mode == "oversized":
        candidate = plan.model_copy(
            update={
                "subquestions": plan.subquestions * 2
            }
        )

    elif mode == "unknown_field":
        candidate = plan.model_copy(
            update={"tool_permission": True}
        )

    elif mode == "nested_object":
        candidate = plan.model_copy(
            update={"subquestions": (object(),)}
        )

    elif mode in ("wrong_text_type", "oversized_text"):
        first = plan.subquestions[0].model_copy(
            update={
                "question": (
                    1 if mode == "wrong_text_type"
                    else "x" * 1001
                )
            }
        )

        candidate = plan.model_copy(
            update={"subquestions": (first,)}
        )

    else:
        candidate = plan.model_copy()

        object.__setattr__(
            candidate,
            "__pydantic_fields_set__",
            {"unapproved"},
        )

    assert _planner_repair_eligible(candidate) is False


@pytest.mark.parametrize(
    "field",
    ["title", "summary", "heading", "content", "limitations"],
)
def test_sec09_eligibility_writer_malformed_text(field):
    context, plan, output, report = _eligibility_inputs()

    if field in ("heading", "content"):
        section = report.sections[0].model_copy(
            update={field: ""}
        )

        candidate = report.model_copy(
            update={
                "sections": (
                    section,
                    *report.sections[1:],
                )
            }
        )

    else:
        candidate = report.model_copy(
            update={
                field: ("",) if field == "limitations"
                else ""
            }
        )

    assert _writer_repair_eligible(
        context, plan, output, candidate
    ) is True


@pytest.mark.parametrize(
    "mode",
    [
        "none",
        "list_sections",
        "oversized_sections",
        "unknown_field",
        "nested_object",
        "list_references",
        "oversized_references",
        "wrong_text_type",
        "oversized_text",
        "invalid_metadata",
    ],
)
def test_sec09_eligibility_writer_uninspectable(mode):
    context, plan, output, report = _eligibility_inputs()

    first = report.sections[0]

    if mode == "none":
        candidate = None

    elif mode == "list_sections":
        candidate = report.model_copy(
            update={"sections": list(report.sections)}
        )

    elif mode == "oversized_sections":
        candidate = report.model_copy(
            update={"sections": (first,) * 9}
        )

    elif mode == "unknown_field":
        candidate = report.model_copy(
            update={"publishable": False}
        )

    elif mode == "nested_object":
        candidate = report.model_copy(
            update={"sections": (object(),)}
        )

    elif mode in (
        "list_references",
        "oversized_references",
    ):
        refs = first.fixture_references

        section = first.model_copy(
            update={
                "fixture_references": (
                    list(refs)
                    if mode == "list_references"
                    else (refs[0],) * 21
                )
            }
        )

        candidate = report.model_copy(
            update={"sections": (section,)}
        )

    elif mode in (
        "wrong_text_type",
        "oversized_text",
    ):
        candidate = report.model_copy(
            update={
                "title": (
                    1 if mode == "wrong_text_type"
                    else "x" * 201
                )
            }
        )

    else:
        candidate = report.model_copy()

        object.__setattr__(
            candidate,
            "__pydantic_fields_set__",
            {"unapproved"},
        )

    assert _writer_repair_eligible(
        context, plan, output, candidate
    ) is False


@pytest.mark.parametrize(
    "mode",
    [
        "unknown_reference",
        "cross_task",
        "cross_attempt",
        "wrong_source",
        "wrong_version",
        "oversized_reference_id",
    ],
)
@pytest.mark.parametrize(
    "container",
    ["normal", "oversized_sections", "oversized_references"],
)
def test_sec09_eligibility_security_precedence(mode, container):
    context, plan, output, report = _eligibility_inputs()

    first = report.sections[0]

    reference = first.fixture_references[0]

    updates = {
        "unknown_reference": {
            "fixture_id": "fixture-unknown"
        },
        "cross_task": {"task_id": UUID(int=9999)},
        "cross_attempt": {"attempt_id": UUID(int=9999)},
        "wrong_source": {"source": "external"},
        "wrong_version": {"fixture_version": "external"},
        "oversized_reference_id": {
            "fixture_id": "x" * 81
        },
    }

    reference = reference.model_copy(
        update=updates[mode]
    )

    references = (reference,)

    if container == "oversized_references":
        references += first.fixture_references * 21

    section = first.model_copy(
        update={"fixture_references": references}
    )

    sections = (section,)

    if container == "oversized_sections":
        sections += (first,) * 8

    candidate = report.model_copy(
        update={
            "title": "",
            "sections": sections,
        }
    )

    with pytest.raises(S05StateIntegrityError):
        _writer_repair_eligible(
            context, plan, output, candidate
        )

    with pytest.raises(S05StateIntegrityError):
        validate_draft_report(
            context, plan, output, candidate
        )


def test_sec09_eligibility_synthetic_flag_precedes_text():
    context, plan, output, report = _eligibility_inputs()

    candidate = report.model_copy(
        update={"synthetic": False, "title": ""}
    )

    with pytest.raises(S05StateIntegrityError):
        _writer_repair_eligible(
            context, plan, output, candidate
        )


def test_sec09_eligibility_insufficient_evidence_denied():
    context, plan, _, report = _eligibility_inputs()

    missing = _sec09_missing_plan(plan)

    output = _eligibility_research_fixture(
        context, missing
    )

    with pytest.raises(S05StateIntegrityError):
        _writer_repair_eligible(
            context, missing, output, report
        )


def test_sec09_eligibility_does_not_consume_allowance():
    context, plan, output, report = _eligibility_inputs()

    controller = ExecutionController()

    before = controller.snapshot()

    malformed = report.model_copy(
        update={"title": ""}
    )

    assert _writer_repair_eligible(
        context, plan, output, malformed
    ) is True

    assert controller.snapshot() == before

    _sec09_assert_cleanup()



# WP04-06E3B: Independent positive eligibility and
# mixed structural/provenance error precedence.

from agentops_api.agent.s05 import (
    report as eligibility_report_module,
)

from agentops_api.agent.s05.validation import (
    S05BoundaryError,
)


@pytest.mark.parametrize("malformed", [False, True])
def test_sec09_eligibility_review_writer_internal_error(
    malformed,
):
    context, plan, output, candidate = _eligibility_inputs()

    if malformed:
        candidate = candidate.model_copy(
            update={"title": ""}
        )

    with patch.object(
        eligibility_report_module,
        "_reconstruct_report",
        side_effect=ValueError("synthetic failure"),
    ):
        assert _writer_repair_eligible(
            context, plan, output, candidate
        ) is False


def test_sec09_eligibility_review_planner_valid_exception():
    _, plan, _, _ = _eligibility_inputs()

    with patch.object(
        accounting_planner,
        "_validate_research_plan",
        side_effect=S05BoundaryError(),
    ):
        assert _planner_repair_eligible(plan) is False


@pytest.mark.parametrize("location", ["report", "section"])
@pytest.mark.parametrize(
    "defect", ["missing", "unexpected"]
)
@pytest.mark.parametrize(
    "security", ["cross_task", "unknown_id"]
)
def test_sec09_eligibility_review_mixed_provenance(
    location, defect, security
):
    context, plan, output, candidate = _eligibility_inputs()

    first = candidate.sections[0]
    reference = first.fixture_references[0]

    mutation = (
        {"task_id": UUID(int=9999)}
        if security == "cross_task"
        else {"fixture_id": "fixture-unknown"}
    )

    forged = reference.model_copy(
        update=mutation
    )

    section = first.model_copy(
        update={"fixture_references": (forged,)}
    )

    candidate = candidate.model_copy(
        update={
            "title": "",
            "sections": (section,),
        }
    )

    target = (
        candidate
        if location == "report"
        else section
    )

    raw = object.__getattribute__(
        target, "__dict__"
    )

    if defect == "missing":
        raw.pop(
            "summary"
            if location == "report"
            else "heading"
        )
    else:
        raw["unexpected_field"] = True

    with pytest.raises(S05StateIntegrityError):
        _writer_repair_eligible(
            context, plan, output, candidate
        )

    with pytest.raises(S05StateIntegrityError):
        validate_draft_report(
            context, plan, output, candidate
        )


@pytest.mark.parametrize(
    "defect", ["missing", "unexpected"]
)
def test_sec09_eligibility_review_synthetic_precedence(
    defect,
):
    context, plan, output, candidate = _eligibility_inputs()

    candidate = candidate.model_copy(
        update={
            "title": "",
            "synthetic": False,
        }
    )

    raw = object.__getattribute__(
        candidate, "__dict__"
    )

    if defect == "missing":
        raw.pop("summary")
    else:
        raw["unexpected_field"] = True

    with pytest.raises(S05StateIntegrityError):
        _writer_repair_eligible(
            context, plan, output, candidate
        )

    with pytest.raises(S05StateIntegrityError):
        validate_draft_report(
            context, plan, output, candidate
        )


@pytest.mark.parametrize("location", ["report", "section"])
def test_sec09_eligibility_review_extra_fields_deny_repair(
    location,
):
    context, plan, output, candidate = _eligibility_inputs()

    candidate = candidate.model_copy(
        update={"title": ""}
    )

    target = (
        candidate
        if location == "report"
        else candidate.sections[0]
    )

    object.__getattribute__(
        target, "__dict__"
    )["unexpected_field"] = True

    assert _writer_repair_eligible(
        context, plan, output, candidate
    ) is False


@pytest.mark.parametrize("location", ["sections", "references"])
def test_sec09_eligibility_review_uninspectable_tail(
    location,
):
    context, plan, output, candidate = _eligibility_inputs()

    first = candidate.sections[0]

    reference = first.fixture_references[0]

    forged = reference.model_copy(
        update={"task_id": UUID(int=9999)}
    )

    if location == "sections":
        bad_section = first.model_copy(
            update={"fixture_references": (forged,)}
        )

        sections = (
            *((first,) * 8),
            bad_section,
        )

    else:
        section = first.model_copy(
            update={
                "fixture_references": (
                    *((reference,) * 20),
                    forged,
                )
            }
        )

        sections = (section,)

    candidate = candidate.model_copy(
        update={
            "title": "",
            "sections": sections,
        }
    )

    assert _writer_repair_eligible(
        context, plan, output, candidate
    ) is False

    with pytest.raises(S05ReportError):
        validate_draft_report(
            context, plan, output, candidate
        )


def test_sec09_eligibility_review_valid_outputs_no_validation():
    context, plan, output, candidate = _eligibility_inputs()

    with patch.object(
        accounting_planner,
        "_validate_research_plan",
        side_effect=AssertionError("unexpected call"),
    ) as planner_validation:
        assert _planner_repair_eligible(plan) is False

    planner_validation.assert_not_called()

    with patch.object(
        eligibility_report_module,
        "_reconstruct_report",
        side_effect=AssertionError("unexpected call"),
    ) as writer_validation:
        assert _writer_repair_eligible(
            context, plan, output, candidate
        ) is False

    writer_validation.assert_not_called()



# WP04-07B: Monotonic soft deadline enforcement.
# All tests use a deterministic clock, not real sleep.

from agentops_api.agent.s05 import (
    controller as deadline_controller_module,
)

from agentops_api.agent.s05.controller import (
    S05DeadlineError,
)


class _SEC10Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _sec10_observe(deadline=None):
    try:
        result = accounting_workflow.run_specialized_workflow(
            _sec09_request(),
            deadline_monotonic=deadline,
        )

    except accounting_workflow.S05WorkflowError as error:
        assert type(error) is (
            accounting_workflow.S05WorkflowError
        )

        assert str(error) == "S05 workflow failed"
        assert error.__cause__ is None
        assert error.__context__ is None

        return error.category, None

    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage.hex() == 0.0.hex()
    assert result.counters.repair_attempts == 0

    return result.outcome, result


@pytest.mark.parametrize(
    "deadline",
    [99.0, 100.0],
)
def test_sec10_expired_entry_blocks_graph(deadline):
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_workflow,
        "_build_graph",
    ) as forbidden:

        assert _sec10_observe(deadline) == (
            "deadline_exceeded",
            None,
        )

    forbidden.assert_not_called()
    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "deadline",
    [
        True,
        False,
        "101",
        object(),
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_sec10_invalid_deadline_rejected(deadline):
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_workflow,
        "_build_graph",
    ) as forbidden:

        assert _sec10_observe(deadline) == (
            "invalid_input",
            None,
        )

    forbidden.assert_not_called()
    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "caller,expected",
    [
        (None, 130.0),
        (110.0, 110.0),
        (110, 110),
        (1000000.0, 130.0),
    ],
)
def test_sec10_effective_deadline(caller, expected):
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController(
            deadline_monotonic=caller
        )

        clock.now = float(expected) - 0.001
        active.check_deadline()

        clock.now = float(expected)

        with pytest.raises(S05DeadlineError):
            active.check_deadline()


def test_sec10_expired_reservation_not_consumed():
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController(
            deadline_monotonic=110.0
        )

        clock.now = 110.0

        with patch.object(
            deadline_controller_module,
            "_current_controller",
            return_value=active,
        ), patch.object(
            accounting_planner,
            "plan_fixture",
        ) as forbidden:

            with pytest.raises(
                deadline_controller_module._InvocationBoundaryError
            ) as caught:

                deadline_controller_module._invoke_fixture(
                    "planner",
                    forbidden,
                )

            with pytest.raises(S05DeadlineError):
                deadline_controller_module._raise_boundary_error(
                    caught.value
                )

        forbidden.assert_not_called()
        assert active.invocation_history == ()


@pytest.mark.parametrize(
    "target",
    _SEC09_ORDER,
)
@pytest.mark.parametrize(
    "mode",
    ["normal", "exception"],
)
def test_sec10_adapter_expiry(target, mode):
    clock = _SEC10Clock()

    entries = []
    controllers = []

    def instrument(name, original):
        def wrapped(*args, **kwargs):
            entries.append(name)

            active = (
                deadline_controller_module._current_controller()
            )

            controllers.append(active)

            if name == target:
                clock.now = 110.0

                if mode == "exception":
                    raise RuntimeError(
                        "synthetic adapter failure"
                    )

            return original(*args, **kwargs)

        return wrapped

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                deadline_controller_module,
                "monotonic",
                clock,
            )
        )

        for name, (module, attr) in _SEC09_ADAPTERS.items():
            stack.enter_context(
                patch.object(
                    module,
                    attr,
                    instrument(
                        name,
                        getattr(module, attr),
                    ),
                )
            )

        assert _sec10_observe(110.0) == (
            "deadline_exceeded",
            None,
        )

    expected = _SEC09_ORDER[
        :_SEC09_ORDER.index(target) + 1
    ]

    assert entries == list(expected)

    active = controllers[0]

    assert all(
        item is active
        for item in controllers
    )

    assert active.invocation_history == tuple(
        (name, False)
        for name in expected
    )

    assert active.snapshot().repair_attempts == 0

    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "target",
    _SEC09_ORDER,
)
def test_sec10_security_precedes_expiry(target):
    clock = _SEC10Clock()

    module, attr = _SEC09_ADAPTERS[target]

    def corrupt(adapter_context, *args, **kwargs):
        clock.now = 110.0

        object.__setattr__(
            adapter_context,
            "task_id",
            UUID(int=9999),
        )

        raise RuntimeError("synthetic failure")

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(module, attr, corrupt):

        assert _sec10_observe(110.0) == (
            "security_violation",
            None,
        )

    _sec09_assert_cleanup()


def test_sec10_writer_provenance_precedes_expiry():
    clock = _SEC10Clock()

    original = accounting_writer.writer_fixture

    def corrupt(*args, **kwargs):
        candidate = original(*args, **kwargs)

        section = candidate.sections[0]

        reference = section.fixture_references[0]

        forged = reference.model_copy(
            update={"task_id": UUID(int=9999)}
        )

        section = section.model_copy(
            update={"fixture_references": (forged,)}
        )

        clock.now = 110.0

        return candidate.model_copy(
            update={
                "title": "",
                "sections": (section,),
            }
        )

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_writer,
        "writer_fixture",
        corrupt,
    ):

        assert _sec10_observe(110.0) == (
            "security_violation",
            None,
        )

    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "target",
    [
        "evidence_validation_node",
        "report_validation_node",
        "outcome_node",
        "route_after_evidence",
    ],
)
def test_sec10_non_adapter_boundary_expiry(target):
    clock = _SEC10Clock()

    original = getattr(
        accounting_workflow,
        target,
    )

    def late(*args, **kwargs):
        value = original(*args, **kwargs)
        clock.now = 110.0
        return value

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_workflow,
        target,
        late,
    ):

        assert _sec10_observe(110.0) == (
            "deadline_exceeded",
            None,
        )

    _sec09_assert_cleanup()


def test_sec10_terminal_verification_expiry():
    clock = _SEC10Clock()

    original = (
        accounting_workflow._verify_terminal_state
    )

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        clock.now = 110.0
        return result

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_workflow,
        "_verify_terminal_state",
        late,
    ):

        assert _sec10_observe(110.0) == (
            "deadline_exceeded",
            None,
        )

    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "deadline",
    [None, 1000000.0],
)
def test_sec10_default_cap_public_execution(deadline):
    clock = _SEC10Clock()

    original = accounting_planner.plan_fixture

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        clock.now = 130.0
        return result

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_planner,
        "plan_fixture",
        late,
    ), patch.object(
        accounting_research,
        "research_fixture",
    ) as forbidden:

        assert _sec10_observe(deadline) == (
            "deadline_exceeded",
            None,
        )

    forbidden.assert_not_called()
    _sec09_assert_cleanup()


def test_sec10_clock_regression_fails_closed():
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController()

        clock.now = 99.0

        with pytest.raises(S05StateIntegrityError):
            active.check_deadline()


def test_sec10_expired_clock_cannot_reopen():
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController()

        clock.now = 130.0

        with pytest.raises(S05DeadlineError):
            active.check_deadline()

        clock.now = 129.0

        with pytest.raises(S05StateIntegrityError):
            active.check_deadline()


def test_sec10_repair_reservation_after_deadline():
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController(
            deadline_monotonic=110.0
        )

        assert active.invoke(
            "planner",
            lambda: "normal",
        ) == "normal"

        clock.now = 110.0

        entries = []

        with pytest.raises(S05DeadlineError):
            active._invoke_repair(
                "planner",
                lambda: entries.append(True),
            )

        assert entries == []

        assert active.invocation_history == (
            ("planner", False),
        )

        assert active.snapshot().repair_attempts == 0


def test_sec10_failed_repair_counts_before_expiry():
    clock = _SEC10Clock()

    def late_failure():
        clock.now = 110.0
        raise RuntimeError("synthetic repair failure")

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        active = ExecutionController(
            deadline_monotonic=110.0
        )

        active.invoke("planner", lambda: None)

        with pytest.raises(S05DeadlineError):
            active._invoke_repair(
                "planner",
                late_failure,
            )

        assert active.invocation_history == (
            ("planner", False),
            ("planner", True),
        )

        assert active.snapshot().adapter_invocations == 2
        assert active.snapshot().repair_attempts == 1
        assert active._failed is True


def test_sec10_normal_workflow_preserved():
    clock = _SEC10Clock()

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ):
        outcome, result = _sec10_observe()

    assert outcome == "candidate_ready"
    assert result.counters.adapter_invocations == 3
    assert result.counters.repair_attempts == 0

    _sec09_assert_cleanup()



# WP04-07C2A: Repair-aware accounting authority.

from agentops_api.agent.s05.contract import ExecutionCounters

from agentops_api.agent.s05.controller import (
    _approved_history,
    _verified_stage_counters,
    _verify_stage_accounting,
)


@pytest.mark.parametrize(
    "normal_count,repair_at",
    [
        (0, None),
        (1, None),
        (2, None),
        (3, None),
        (1, "planner"),
        (2, "planner"),
        (3, "planner"),
        (3, "writer"),
    ],
)
def test_sec10_repair_authoritative_history(
    normal_count, repair_at
):
    active = ExecutionController()

    for name in ("planner", "research", "writer")[
        :normal_count
    ]:
        active.invoke(name, lambda: None)

        if name == repair_at:
            active._invoke_repair(
                name, lambda: None
            )

    with patch.object(
        deadline_controller_module,
        "_current_controller",
        return_value=active,
    ):
        counters = _verified_stage_counters(
            normal_count
        )

        assert active.invocation_history == (
            _approved_history(
                normal_count, repair_at
            )
        )

        assert counters.adapter_invocations == (
            normal_count + int(repair_at is not None)
        )

        assert counters.repair_attempts == (
            int(repair_at is not None)
        )

        state = {
            "counters": counters,
            "repair_used": repair_at is not None,
        }

        assert _verify_stage_accounting(
            state, normal_count
        ) == counters


@pytest.mark.parametrize(
    "normal_count,repair_at",
    [
        (True, None),
        (-1, None),
        (4, None),
        (0, "planner"),
        (1, "writer"),
        (2, "writer"),
        (3, "research"),
        (3, object()),
    ],
)
def test_sec10_repair_invalid_history_request(
    normal_count, repair_at
):
    with pytest.raises(S05StateIntegrityError):
        _approved_history(
            normal_count, repair_at
        )


@pytest.mark.parametrize(
    "normal_count",
    [1, 2, 3],
)
def test_sec10_repair_unbound_state_rejected(
    normal_count,
):
    state = {
        "counters": ExecutionCounters(
            adapter_invocations=normal_count + 1,
            repair_attempts=1,
        ),
        "repair_used": True,
    }

    with pytest.raises(S05StateIntegrityError):
        _verify_stage_accounting(
            state, normal_count
        )


@pytest.mark.parametrize(
    "history,normal_count",
    [
        ((("planner", 0),), 1),
        ((("planner", True),), 1),
        ((("research", False),), 1),
        ((("planner", False),
          ("research", False),
          ("research", True)), 2),
        ((("planner", False),
          ("planner", True),
          ("research", False),
          ("writer", False),
          ("writer", True)), 3),
        ([("planner", False)], 1),
    ],
)
def test_sec10_repair_forged_ledger_rejected(
    history, normal_count
):
    active = ExecutionController()

    active._ledger = history

    with patch.object(
        deadline_controller_module,
        "_current_controller",
        return_value=active,
    ):
        with pytest.raises(S05StateIntegrityError):
            _verified_stage_counters(normal_count)


@pytest.mark.parametrize(
    "flag",
    ["_active", "_failed"],
)
def test_sec10_repair_unfinished_controller_rejected(
    flag,
):
    active = ExecutionController()

    active.invoke("planner", lambda: None)

    setattr(active, flag, True)

    with patch.object(
        deadline_controller_module,
        "_current_controller",
        return_value=active,
    ):
        with pytest.raises(S05StateIntegrityError):
            _verified_stage_counters(1)


@pytest.mark.parametrize(
    "flag",
    [False, 1, "true", None],
)
def test_sec10_repair_forged_state_flag_rejected(flag):
    active = ExecutionController()

    active.invoke("planner", lambda: None)
    active._invoke_repair("planner", lambda: None)

    with patch.object(
        deadline_controller_module,
        "_current_controller",
        return_value=active,
    ):
        state = {
            "counters": active.snapshot(),
            "repair_used": flag,
        }

        with pytest.raises(S05StateIntegrityError):
            _verify_stage_accounting(state, 1)


def test_sec10_repair_forged_counters_rejected():
    active = ExecutionController()

    active.invoke("planner", lambda: None)
    active._invoke_repair("planner", lambda: None)

    with patch.object(
        deadline_controller_module,
        "_current_controller",
        return_value=active,
    ):
        state = {
            "counters": ExecutionCounters(
                adapter_invocations=1
            ),
            "repair_used": True,
        }

        with pytest.raises(S05StateIntegrityError):
            _verify_stage_accounting(state, 1)



# WP04-07C2B: actual public repaired workflow paths.

@pytest.mark.parametrize("target", ["planner", "writer"])
@pytest.mark.parametrize("repeat", [False, True])
def test_sec10_public_guarded_repair(target, repeat):
    module, attr = _SEC09_ADAPTERS[target]
    original_adapter = getattr(module, attr)
    entries = []
    captured = []

    def malformed_once(*args, **kwargs):
        entries.append(target)
        captured.append(
            deadline_controller_module._current_controller()
        )

        result = original_adapter(*args, **kwargs)

        if len(entries) > 1 and not repeat:
            return result

        if target == "planner":
            first = result.subquestions[0].model_copy(
                update={"question": ""}
            )
            return result.model_copy(
                update={
                    "subquestions": (
                        first, *result.subquestions[1:]
                    )
                }
            )

        return result.model_copy(update={"title": ""})

    with patch.object(module, attr, malformed_once):
        if repeat:
            with pytest.raises(
                accounting_workflow.S05WorkflowError
            ) as caught:
                accounting_workflow.run_specialized_workflow(
                    _sec09_request()
                )

            assert caught.value.category == "invalid_output"
        else:
            result = accounting_workflow.run_specialized_workflow(
                _sec09_request()
            )

            assert result.outcome == "candidate_ready"
            assert result.publishable is False
            assert result.evidence_ids == ()
            assert result.coverage.hex() == 0.0.hex()
            assert result.counters.adapter_invocations == 4
            assert result.counters.repair_attempts == 1

    assert len(entries) == 2
    assert captured[0] is captured[1]
    assert captured[0].snapshot().repair_attempts == 1

    expected_count = 2 if repeat and target == "planner" else 4

    assert captured[0].snapshot().adapter_invocations == expected_count
    _sec09_assert_cleanup()


def test_sec10_public_global_repair_allowance():
    planner_original = accounting_planner.plan_fixture
    writer_original = accounting_writer.writer_fixture

    planner_calls = []
    writer_calls = []
    captured = []

    def plan(*args, **kwargs):
        planner_calls.append(True)
        result = planner_original(*args, **kwargs)

        if len(planner_calls) == 1:
            first = result.subquestions[0].model_copy(
                update={"question": ""}
            )
            return result.model_copy(
                update={
                    "subquestions": (
                        first, *result.subquestions[1:]
                    )
                }
            )

        return result

    def write(*args, **kwargs):
        writer_calls.append(True)
        captured.append(
            deadline_controller_module._current_controller()
        )
        return writer_original(*args, **kwargs).model_copy(
            update={"title": ""}
        )

    with patch.object(
        accounting_planner, "plan_fixture", plan
    ), patch.object(
        accounting_writer, "writer_fixture", write
    ):
        with pytest.raises(
            accounting_workflow.S05WorkflowError
        ):
            accounting_workflow.run_specialized_workflow(
                _sec09_request()
            )

    assert len(planner_calls) == 2
    assert len(writer_calls) == 1
    assert captured[0].snapshot().adapter_invocations == 4
    assert captured[0].snapshot().repair_attempts == 1
    _sec09_assert_cleanup()


@pytest.mark.parametrize("target", ["planner", "writer"])
def test_sec10_public_expiry_blocks_repair(target):
    clock = _SEC10Clock()
    module, attr = _SEC09_ADAPTERS[target]
    original_adapter = getattr(module, attr)
    entries = []

    def late(*args, **kwargs):
        entries.append(True)
        result = original_adapter(*args, **kwargs)
        clock.now = 110.0

        if target == "planner":
            first = result.subquestions[0].model_copy(
                update={"question": ""}
            )
            return result.model_copy(
                update={
                    "subquestions": (
                        first, *result.subquestions[1:]
                    )
                }
            )

        return result.model_copy(update={"title": ""})

    with patch.object(
        deadline_controller_module, "monotonic", clock
    ), patch.object(module, attr, late):

        assert _sec10_observe(110.0) == (
            "deadline_exceeded", None
        )

    assert len(entries) == 1
    _sec09_assert_cleanup()


# WP04-07/08: final repaired execution and forbidden-I/O tests.

import socket as _sec11_socket
import subprocess as _sec11_subprocess
import psycopg as _sec11_psycopg

from sqlalchemy.engine import Engine as _SEC11Engine
from sqlalchemy.engine import Connection as _SEC11Connection
from sqlalchemy.orm import Session as _SEC11Session


def _sec11_malformed(target, value):
    if target == "planner":
        first = value.subquestions[0].model_copy(
            update={"question": ""}
        )

        return value.model_copy(
            update={
                "subquestions": (
                    first,
                    *value.subquestions[1:],
                )
            }
        )

    return value.model_copy(update={"title": ""})


@pytest.mark.parametrize("target", ["planner", "writer"])
@pytest.mark.parametrize(
    "failure",
    ["exception", "deadline", "mutation", "mutation_deadline"],
)
def test_sec10_final_repair_failure(target, failure):
    clock = _SEC10Clock()

    module, attr = _SEC09_ADAPTERS[target]
    original = getattr(module, attr)

    calls = []
    captured = []

    def adapter(*args, **kwargs):
        calls.append(True)

        captured.append(
            deadline_controller_module._current_controller()
        )

        if len(calls) == 1:
            return _sec11_malformed(
                target, original(*args, **kwargs)
            )

        if failure in ("deadline", "mutation_deadline"):
            clock.now = 110.0

        if failure in ("mutation", "mutation_deadline"):
            object.__setattr__(
                args[0],
                "task_id",
                UUID(int=99999),
            )

        if failure != "deadline":
            raise RuntimeError("synthetic repair failure")

        return original(*args, **kwargs)

    expected = {
        "exception": "execution_failed",
        "deadline": "deadline_exceeded",
        "mutation": "security_violation",
        "mutation_deadline": "security_violation",
    }[failure]

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(module, attr, adapter):

        with pytest.raises(
            accounting_workflow.S05WorkflowError
        ) as caught:
            accounting_workflow.run_specialized_workflow(
                _sec09_request(),
                deadline_monotonic=110.0,
            )

    assert caught.value.category == expected
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None

    assert len(calls) == 2
    assert captured[0] is captured[1]

    active = captured[0]

    assert active.snapshot().repair_attempts == 1
    assert active.snapshot().adapter_invocations == (
        2 if target == "planner" else 4
    )

    assert active.invocation_history[-1] == (target, True)
    assert active._active is False

    _sec09_assert_cleanup()


@pytest.mark.parametrize("expired", [False, True])
def test_sec10_final_repaired_writer_provenance(expired):
    clock = _SEC10Clock()

    original = accounting_writer.writer_fixture
    entries = []

    def adapter(*args, **kwargs):
        entries.append(True)

        result = original(*args, **kwargs)

        if len(entries) == 1:
            return result.model_copy(update={"title": ""})

        section = result.sections[0]

        forged = section.fixture_references[0].model_copy(
            update={"task_id": UUID(int=99999)}
        )

        section = section.model_copy(
            update={"fixture_references": (forged,)}
        )

        if expired:
            clock.now = 110.0

        return result.model_copy(
            update={
                "title": "",
                "sections": (section,),
            }
        )

    with patch.object(
        deadline_controller_module,
        "monotonic",
        clock,
    ), patch.object(
        accounting_writer,
        "writer_fixture",
        adapter,
    ):
        with pytest.raises(
            accounting_workflow.S05WorkflowError
        ) as caught:
            accounting_workflow.run_specialized_workflow(
                _sec09_request(),
                deadline_monotonic=110.0,
            )

    assert caught.value.category == "security_violation"
    assert len(entries) == 2

    _sec09_assert_cleanup()


def test_sec10_final_repaired_abstention():
    original = accounting_planner.plan_fixture
    calls = []
    captured = []

    def adapter(*args, **kwargs):
        calls.append(True)

        captured.append(
            deadline_controller_module._current_controller()
        )

        value = original(*args, **kwargs)

        if len(calls) == 1:
            return _sec11_malformed("planner", value)

        return _sec09_missing_plan(value)

    with patch.object(
        accounting_planner,
        "plan_fixture",
        adapter,
    ), patch.object(
        accounting_writer,
        "writer_fixture",
    ) as forbidden:

        result = accounting_workflow.run_specialized_workflow(
            _sec09_request()
        )

    assert result.outcome == "insufficient_evidence"
    assert result.candidate is None
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage.hex() == 0.0.hex()

    assert result.counters.adapter_invocations == 3
    assert result.counters.repair_attempts == 1

    assert len(calls) == 2
    assert captured[0] is captured[1]

    assert captured[0].invocation_history == (
        ("planner", False),
        ("planner", True),
        ("research", False),
    )

    forbidden.assert_not_called()

    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "scenario",
    [
        "candidate",
        "abstention",
        "planner_repair",
        "writer_repair",
        "repaired_abstention",
        "planner_failure",
        "research_failure",
        "writer_failure",
        "repair_failure",
        "expired",
        "security_failure",
    ],
)
def test_sec11_graph_wide_forbidden_io(scenario):
    """Exercise actual graph paths with forbidden I/O tripwires."""

    clock = _SEC10Clock()

    forbidden_calls = []
    calls = []

    def forbidden(name):
        def reject(*args, **kwargs):
            forbidden_calls.append(name)
            raise AssertionError(
                "forbidden external operation"
            )

        return reject

    boundaries = (
        (_sec11_socket.socket, "connect"),
        (_sec11_socket.socket, "connect_ex"),
        (_sec11_socket.socket, "send"),
        (_sec11_socket.socket, "sendall"),
        (_sec11_socket.socket, "sendto"),
        (_sec11_socket, "create_connection"),
        (_sec11_socket, "getaddrinfo"),
        (_sec11_socket, "gethostbyname"),
        (_sec11_socket, "gethostbyname_ex"),
        (_sec11_socket, "gethostbyaddr"),
        (_sec11_subprocess, "Popen"),
        (_sec11_psycopg, "connect"),
        (_SEC11Engine, "connect"),
        (_SEC11Engine, "begin"),
        (_SEC11Connection, "execute"),
        (_SEC11Connection, "exec_driver_sql"),
        (_SEC11Session, "execute"),
        (_SEC11Session, "flush"),
        (_SEC11Session, "commit"),
        (_SEC11Session, "add"),
        (_SEC11Session, "delete"),
    )

    def instrument(name, original):
        def adapter(*args, **kwargs):
            calls.append(name)
            count = calls.count(name)

            if scenario == f"{name}_failure":
                raise RuntimeError("synthetic fixture failure")

            if scenario == "repair_failure":
                if name == "planner" and count == 2:
                    raise RuntimeError(
                        "synthetic repair failure"
                    )

            if scenario == "security_failure":
                if name == "planner":
                    object.__setattr__(
                        args[0],
                        "task_id",
                        UUID(int=99999),
                    )

                    raise RuntimeError(
                        "synthetic mutation failure"
                    )

            value = original(*args, **kwargs)

            if name == "planner":
                if scenario == "abstention":
                    return _sec09_missing_plan(value)

                if scenario in (
                    "planner_repair",
                    "repaired_abstention",
                    "repair_failure",
                ):
                    if count == 1:
                        return _sec11_malformed(name, value)

                    if scenario == "repaired_abstention":
                        return _sec09_missing_plan(value)

            if name == "writer":
                if scenario == "writer_repair" and count == 1:
                    return _sec11_malformed(name, value)

            return value

        return adapter

    success = {
        "candidate": ("candidate_ready", 3, 0),
        "abstention": ("insufficient_evidence", 2, 0),
        "planner_repair": ("candidate_ready", 4, 1),
        "writer_repair": ("candidate_ready", 4, 1),
        "repaired_abstention": (
            "insufficient_evidence", 3, 1
        ),
    }

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                deadline_controller_module,
                "monotonic",
                clock,
            )
        )

        for obj, attribute in boundaries:
            stack.enter_context(
                patch.object(
                    obj,
                    attribute,
                    forbidden(attribute),
                )
            )

        for name, (module, attr) in _SEC09_ADAPTERS.items():
            stack.enter_context(
                patch.object(
                    module,
                    attr,
                    instrument(
                        name,
                        getattr(module, attr),
                    ),
                )
            )

        if scenario in success:
            result = accounting_workflow.run_specialized_workflow(
                _sec09_request(),
                deadline_monotonic=110.0,
            )

            expected, invocations, repairs = success[scenario]

            assert result.outcome == expected
            assert result.publishable is False
            assert result.evidence_ids == ()
            assert result.coverage.hex() == 0.0.hex()

            assert result.counters.adapter_invocations == invocations
            assert result.counters.repair_attempts == repairs
            assert len(calls) == invocations

        else:
            with pytest.raises(
                accounting_workflow.S05WorkflowError
            ) as caught:

                accounting_workflow.run_specialized_workflow(
                    _sec09_request(),
                    deadline_monotonic=(
                        100.0 if scenario == "expired"
                        else 110.0
                    ),
                )

            expected = {
                "expired": "deadline_exceeded",
                "security_failure": "security_violation",
            }.get(scenario, "execution_failed")

            assert caught.value.category == expected

            expected_calls = {
                "planner_failure": ["planner"],
                "research_failure": ["planner", "research"],
                "writer_failure": [
                    "planner", "research", "writer"
                ],
                "repair_failure": ["planner", "planner"],
                "expired": [],
                "security_failure": ["planner"],
            }

            assert calls == expected_calls[scenario]

    assert forbidden_calls == []

    _sec09_assert_cleanup()


@pytest.mark.parametrize(
    "boundary",
    ["network", "dns", "database", "subprocess"],
)
def test_sec11_tripwire_detects_forbidden_adapter_call(boundary):
    """Positive controls: tripwire failures cannot be swallowed."""

    detected = []

    def reject(*args, **kwargs):
        detected.append(boundary)
        raise AssertionError("synthetic forbidden I/O")

    targets = {
        "network": (_sec11_socket.socket, "connect"),
        "dns": (_sec11_socket, "getaddrinfo"),
        "database": (_sec11_psycopg, "connect"),
        "subprocess": (_sec11_subprocess, "Popen"),
    }

    obj, attribute = targets[boundary]

    def injected(*args, **kwargs):
        if boundary == "network":
            _sec11_socket.socket.connect(None, None)

        elif boundary == "dns":
            _sec11_socket.getaddrinfo("synthetic.invalid", 0)

        elif boundary == "database":
            _sec11_psycopg.connect()

        else:
            _sec11_subprocess.Popen([])

    with patch.object(
        obj, attribute, reject
    ), patch.object(
        accounting_planner,
        "plan_fixture",
        injected,
    ):
        with pytest.raises(
            accounting_workflow.S05WorkflowError
        ) as caught:
            accounting_workflow.run_specialized_workflow(
                _sec09_request()
            )

    assert caught.value.category == "execution_failed"
    assert detected == [boundary]

    _sec09_assert_cleanup()
