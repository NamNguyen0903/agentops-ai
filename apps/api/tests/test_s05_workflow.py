"""Actual compiled LangGraph execution tests for S05."""

from itertools import product
from uuid import UUID

import pytest

from langgraph.graph import END, START

from agentops_api.agent.s05 import (
    planner,
    research,
    workflow,
    writer,
)
from agentops_api.agent.s05.contract import (
    ExecutionCounters,
    ResearchPlan,
    ResearchSubquestion,
    S05GraphInput,
    S05GraphResult,
)
from agentops_api.agent.s05.validation import (
    build_initial_state,
    create_execution_context,
)


@pytest.fixture
def request_model():
    return S05GraphInput(
        task_id=UUID(int=901),
        attempt_id=UUID(int=902),
        question="Synthetic graph execution.",
        scope={
            "region": "offline",
            "publishable": True,
            "external_retrieval": True,
        },
    )


def _assert_result(result, expected, calls, coverage):
    assert type(result) is S05GraphResult
    assert result.outcome == expected
    assert result.stage == expected
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0
    assert result.fixture_coverage == coverage
    assert result.counters == ExecutionCounters(
        adapter_invocations=calls
    )
    assert result.error_category is None


def _assert_safe_failure(operation, category):
    with pytest.raises(
        workflow.S05WorkflowError
    ) as caught:
        operation()

    assert caught.value.category == category
    assert str(caught.value) == "S05 workflow failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_workflow_actual_graph_topology():
    graph = workflow._build_graph()

    assert graph.checkpointer is None
    assert graph.store is None
    assert graph.cache is None

    diagram = graph.get_graph()

    assert set(diagram.nodes) == {
        START,
        END,
        "planner",
        "research",
        "evidence_validation",
        "writer",
        "report_validation",
        "outcome",
    }

    edges = {
        (edge.source, edge.target, edge.conditional)
        for edge in diagram.edges
    }

    assert edges == {
        (START, "planner", False),
        ("planner", "research", False),
        ("research", "evidence_validation", False),
        ("evidence_validation", "writer", True),
        ("evidence_validation", "outcome", True),
        ("writer", "report_validation", False),
        ("report_validation", "outcome", False),
        ("outcome", END, False),
    }


def test_workflow_candidate_result(request_model):
    result = workflow.run_specialized_workflow(
        request_model
    )

    _assert_result(
        result, "candidate_ready", 3, 1.0
    )

    assert result.task_id == request_model.task_id
    assert result.attempt_id == request_model.attempt_id

    assert result.candidate.synthetic is True


@pytest.mark.parametrize(
    "missing",
    tuple(product((False, True), repeat=4))[1:],
)
def test_workflow_actual_writer_bypass(
    request_model, monkeypatch, missing
):
    original = planner.plan_fixture

    def incomplete(context):
        plan = original(context)

        return ResearchPlan(
            subquestions=tuple(
                ResearchSubquestion(
                    subquestion_id=item.subquestion_id,
                    question=item.question,
                    query=(
                        "fixture:missing-" + item.subquestion_id
                        if missing[index]
                        else item.query
                    ),
                )
                for index, item in enumerate(
                    plan.subquestions
                )
            ),
            assumptions=plan.assumptions,
        )

    def forbidden(*args, **kwargs):
        pytest.fail("Abstention must bypass Writer")

    monkeypatch.setattr(
        planner, "plan_fixture", incomplete
    )

    monkeypatch.setattr(
        workflow, "writer_node", forbidden
    )

    monkeypatch.setattr(
        workflow, "report_validation_node", forbidden
    )

    monkeypatch.setattr(
        writer, "writer_fixture", forbidden
    )

    result = workflow.run_specialized_workflow(
        request_model
    )

    _assert_result(
        result,
        "insufficient_evidence",
        2,
        (4 - sum(missing)) / 4,
    )

    assert result.candidate is None


def test_workflow_actual_node_order(
    request_model, monkeypatch
):
    calls = []

    names = (
        "planner_node",
        "research_node",
        "evidence_validation_node",
        "writer_node",
        "report_validation_node",
        "outcome_node",
    )

    def spy(name, original):
        def wrapped(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)

        return wrapped

    for name in names:
        monkeypatch.setattr(
            workflow,
            name,
            spy(name, getattr(workflow, name)),
        )

    result = workflow.run_specialized_workflow(
        request_model
    )

    assert result.outcome == "candidate_ready"

    # The last Outcome call independently reconstructs
    # the final result at the public output boundary.
    assert calls == [
        *names,
        "outcome_node",
    ]


def test_workflow_actual_adapter_invocations(
    request_model, monkeypatch
):
    calls = []

    def spy(name, original):
        def wrapped(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)
        return wrapped

    for module, name in (
        (planner, "plan_fixture"),
        (research, "research_fixture"),
        (writer, "writer_fixture"),
    ):
        monkeypatch.setattr(
            module,
            name,
            spy(name, getattr(module, name)),
        )

    result = workflow.run_specialized_workflow(
        request_model
    )

    assert calls == [
        "plan_fixture",
        "research_fixture",
        "writer_fixture",
    ]

    assert result.counters.adapter_invocations == 3


def test_workflow_is_deterministic(request_model):
    first = workflow.run_specialized_workflow(
        request_model
    )

    second = workflow.run_specialized_workflow(
        request_model
    )

    assert first == second
    assert first is not second
    assert first.candidate is not second.candidate


def test_workflow_keeps_requests_isolated(
    request_model
):
    first = workflow.run_specialized_workflow(
        request_model
    )

    second_request = S05GraphInput(
        task_id=UUID(int=999),
        attempt_id=None,
        question=request_model.question,
        scope={"region": "another-fixture-scope"},
    )

    second = workflow.run_specialized_workflow(
        second_request
    )

    assert first.task_id != second.task_id
    assert second.attempt_id is None

    for section in second.candidate.sections:
        for reference in section.fixture_references:
            assert reference.task_id == second.task_id
            assert reference.attempt_id is None


@pytest.mark.parametrize(
    "invalid",
    [None, {}, "invalid", 123],
)
def test_workflow_rejects_untyped_input(invalid):
    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            invalid
        ),
        "invalid_input",
    )


def test_workflow_rejects_mutated_request(
    request_model
):
    object.__setattr__(
        request_model,
        "question",
        "Changed after construction",
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "invalid_input",
    )


@pytest.mark.parametrize(
    "target",
    [
        "planner_node",
        "research_node",
        "writer_node",
    ],
)
def test_workflow_no_implicit_retry(
    request_model, monkeypatch, target
):
    calls = []

    def failing(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("private synthetic marker")

    monkeypatch.setattr(
        workflow, target, failing
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "execution_failed",
    )

    assert len(calls) == 1


def test_workflow_invalid_planner_output(
    request_model, monkeypatch
):
    monkeypatch.setattr(
        planner,
        "plan_fixture",
        lambda *args: {},
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "invalid_output",
    )


def test_workflow_invalid_research_output(
    request_model, monkeypatch
):
    monkeypatch.setattr(
        research,
        "research_fixture",
        lambda *args: {},
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "security_violation",
    )


def test_workflow_invalid_writer_output(
    request_model, monkeypatch
):
    monkeypatch.setattr(
        writer,
        "writer_fixture",
        lambda *args: {},
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "invalid_output",
    )


def test_workflow_rejects_protected_state_mutation(
    request_model, monkeypatch
):
    original = workflow.planner_node

    def mutate(state, context):
        update = original(state, context)

        return {
            **update,
            "evidence_ids": ("fabricated",),
        }

    monkeypatch.setattr(
        workflow, "planner_node", mutate
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "security_violation",
    )


def test_workflow_rejects_terminal_result_mutation(
    request_model, monkeypatch
):
    original = workflow.outcome_node

    def mutate(state, context):
        update = original(state, context)

        return {
            **update,
            "result": update["result"].model_copy(
                update={"publishable": True}
            ),
        }

    monkeypatch.setattr(
        workflow, "_outcome",
        lambda state, runtime: mutate(
            state, runtime.context
        ),
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "security_violation",
    )


def test_workflow_compiled_graph_finite_execution(
    request_model
):
    context = create_execution_context(
        request_model
    )

    graph = workflow._build_graph()

    updates = list(graph.stream(
        build_initial_state(context),
        config={"recursion_limit": 12},
        context=context,
        stream_mode="updates",
    ))

    assert [
        name
        for update in updates
        for name in update
    ] == [
        "planner",
        "research",
        "evidence_validation",
        "writer",
        "report_validation",
        "outcome",
    ]

    final = updates[-1]["outcome"]["result"]

    _assert_result(
        final, "candidate_ready", 3, 1.0
    )


# WP04-03C: SEC06 terminal integrity regression.

from unittest.mock import patch

from agentops_api.agent.s05.validation import (
    S05StateIntegrityError,
)

_sec06_original_plan = planner.plan_fixture

def _sec06_request():
    return S05GraphInput(task_id=UUID(int=901), attempt_id=UUID(int=902), question='Synthetic SEC06 diagnostic.', scope={'region': 'offline'})

class _sec06_StageSubclass(str):
    pass

class _sec06_TextSubclass(str):
    pass

def _sec06_incomplete_plan(context):
    plan = _sec06_original_plan(context)
    return ResearchPlan(subquestions=tuple((ResearchSubquestion(subquestion_id=item.subquestion_id, question=item.question, query='fixture:missing-' + item.subquestion_id) for item in plan.subquestions)), assumptions=plan.assumptions)

def _sec06_forbidden_writer(*args, **kwargs):
    raise AssertionError('Unexpected Writer invocation')

def _sec06_terminal(path):
    ctx = create_execution_context(_sec06_request())
    graph = workflow._build_graph()
    if path == 'candidate':
        state = graph.invoke(build_initial_state(ctx), config={'recursion_limit': 12}, context=ctx)
        expected_stage = 'candidate_ready'
    elif path == 'abstention':
        with patch.object(planner, 'plan_fixture', _sec06_incomplete_plan), patch.object(writer, 'writer_fixture', _sec06_forbidden_writer):
            state = graph.invoke(build_initial_state(ctx), config={'recursion_limit': 12}, context=ctx)
        expected_stage = 'insufficient_evidence'
    else:
        raise AssertionError('Unknown path')
    assert state['stage'] == expected_stage
    result = workflow._verify_terminal_state(state, ctx)
    assert type(result) is S05GraphResult
    assert result == state['result']
    assert result is not state['result']
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0
    return (state, ctx)

def _sec06_mutate_metadata(model):
    changed = model.model_copy()
    object.__setattr__(changed, '__pydantic_fields_set__', list(changed.model_fields_set))
    return changed

def _sec06_mutate_nested_report(result, mutation):
    candidate = result.candidate
    assert candidate is not None
    section = candidate.sections[0]
    reference = section.fixture_references[0]
    if mutation == 'report_metadata':
        changed_candidate = _sec06_mutate_metadata(candidate)
    elif mutation == 'report_title_subclass':
        changed_candidate = candidate.model_copy(update={'title': _sec06_TextSubclass(candidate.title)})
    elif mutation == 'report_synthetic_integer':
        changed_candidate = candidate.model_copy(update={'synthetic': 1})
    else:
        if mutation == 'section_metadata':
            changed_section = _sec06_mutate_metadata(section)
        elif mutation == 'section_heading_subclass':
            changed_section = section.model_copy(update={'heading': _sec06_TextSubclass(section.heading)})
        else:
            if mutation == 'reference_metadata':
                changed_reference = _sec06_mutate_metadata(reference)
            elif mutation == 'reference_id_subclass':
                changed_reference = reference.model_copy(update={'fixture_id': _sec06_TextSubclass(reference.fixture_id)})
            elif mutation == 'reference_unknown':
                changed_reference = reference.model_copy(update={'fixture_id': 'fixture-fabricated'})
            elif mutation == 'reference_cross_task':
                changed_reference = reference.model_copy(update={'task_id': UUID(int=999)})
            else:
                raise AssertionError('Unknown nested mutation')
            changed_section = section.model_copy(update={'fixture_references': (changed_reference,) + section.fixture_references[1:]})
        changed_candidate = candidate.model_copy(update={'sections': (changed_section,) + candidate.sections[1:]})
    return result.model_copy(update={'candidate': changed_candidate})

def _sec06_mutate(state, mutation):
    changed = dict(state)
    result = state['result']
    assert type(result) is S05GraphResult
    if mutation == 'state_stage_subclass':
        changed['stage'] = _sec06_StageSubclass(state['stage'])
        return changed
    if mutation == 'result_stage_subclass':
        new_result = result.model_copy(update={'stage': _sec06_StageSubclass(result.stage)})
    elif mutation == 'result_outcome_subclass':
        new_result = result.model_copy(update={'outcome': _sec06_StageSubclass(result.outcome)})
    elif mutation == 'coverage_negative_zero':
        new_result = result.model_copy(update={'coverage': -0.0})
    elif mutation == 'coverage_integer':
        new_result = result.model_copy(update={'coverage': 0})
    elif mutation == 'fixture_coverage_integer':
        new_result = result.model_copy(update={'fixture_coverage': int(result.fixture_coverage)})
    elif mutation == 'counter_boolean':
        counters = result.counters.model_copy(update={'repair_attempts': False})
        new_result = result.model_copy(update={'counters': counters})
    elif mutation == 'counter_metadata':
        new_result = result.model_copy(update={'counters': _sec06_mutate_metadata(result.counters)})
    elif mutation == 'counter_changed':
        counters = result.counters.model_copy(update={'adapter_invocations': 4})
        new_result = result.model_copy(update={'counters': counters})
    elif mutation == 'version_metadata':
        new_result = result.model_copy(update={'versions': _sec06_mutate_metadata(result.versions)})
    elif mutation == 'version_subclass':
        versions = result.versions.model_copy(update={'graph': _sec06_TextSubclass(result.versions.graph)})
        new_result = result.model_copy(update={'versions': versions})
    elif mutation == 'version_changed':
        versions = result.versions.model_copy(update={'graph': 'unexpected-version'})
        new_result = result.model_copy(update={'versions': versions})
    elif mutation == 'task_id_string':
        new_result = result.model_copy(update={'task_id': str(result.task_id)})
    elif mutation == 'task_id_changed':
        new_result = result.model_copy(update={'task_id': UUID(int=999)})
    elif mutation == 'attempt_id_changed':
        new_result = result.model_copy(update={'attempt_id': UUID(int=999)})
    elif mutation == 'publishable_integer':
        new_result = result.model_copy(update={'publishable': 0})
    elif mutation == 'publishable_true':
        new_result = result.model_copy(update={'publishable': True})
    elif mutation == 'result_metadata':
        new_result = _sec06_mutate_metadata(result)
    elif mutation == 'unexpected_result_field':
        new_result = result.model_copy()
        new_result.__dict__['unexpected'] = True
    else:
        new_result = _sec06_mutate_nested_report(result, mutation)
    changed['result'] = new_result
    return changed

_SEC06_COMMON = ('state_stage_subclass', 'result_stage_subclass', 'result_outcome_subclass', 'coverage_negative_zero', 'coverage_integer', 'fixture_coverage_integer', 'counter_boolean', 'counter_metadata', 'counter_changed', 'version_metadata', 'version_subclass', 'version_changed', 'task_id_string', 'task_id_changed', 'attempt_id_changed', 'publishable_integer', 'publishable_true', 'result_metadata', 'unexpected_result_field')
_SEC06_NESTED = ('report_metadata', 'report_title_subclass', 'report_synthetic_integer', 'section_metadata', 'section_heading_subclass', 'reference_metadata', 'reference_id_subclass', 'reference_unknown', 'reference_cross_task')
_SEC06_PUBLIC = ('coverage_negative_zero', 'counter_metadata', 'report_metadata', 'state_stage_subclass', 'publishable_true')


@pytest.mark.parametrize(
    "path", ["candidate", "abstention"]
)
def test_sec06_valid_terminal_control(path):
    state, context = _sec06_terminal(path)

    verified = workflow._verify_terminal_state(
        state, context
    )

    assert verified == state["result"]
    assert verified is not state["result"]
    assert verified.publishable is False


def _sec06_assert_rejected(state, context):
    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        workflow._verify_terminal_state(
            state, context
        )

    assert caught.value.category == "security_violation"
    assert str(caught.value) == "invalid S05 protected state"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "path", ["candidate", "abstention"]
)
@pytest.mark.parametrize(
    "mutation", _SEC06_COMMON
)
def test_sec06_common_terminal_mutations(
    path, mutation
):
    state, context = _sec06_terminal(path)

    changed = _sec06_mutate(state, mutation)

    _sec06_assert_rejected(changed, context)


@pytest.mark.parametrize(
    "mutation", _SEC06_NESTED
)
def test_sec06_nested_terminal_mutations(mutation):
    state, context = _sec06_terminal("candidate")

    changed = _sec06_mutate(state, mutation)

    _sec06_assert_rejected(changed, context)


@pytest.mark.parametrize(
    "mutation", _SEC06_PUBLIC
)
def test_sec06_actual_public_workflow_mutations(
    mutation, monkeypatch
):
    original = workflow._outcome
    calls = []

    def changed_outcome(state, runtime):
        calls.append(True)

        return _sec06_mutate(
            original(state, runtime),
            mutation,
        )

    monkeypatch.setattr(
        workflow, "_outcome", changed_outcome
    )

    _assert_safe_failure(
        lambda: workflow.run_specialized_workflow(
            _sec06_request()
        ),
        "security_violation",
    )

    assert calls == [True]


@pytest.mark.parametrize(
    "mutation",
    [
        "counter_private_metadata",
        "version_extra_metadata",
        "report_private_metadata",
        "section_extra_raw_field",
        "references_list",
        "sections_list",
        "reference_attempt_changed",
        "fixture_coverage_negative_zero",
    ],
)
def test_sec06_additional_nested_integrity(mutation):
    path = (
        "abstention"
        if mutation == "fixture_coverage_negative_zero"
        else "candidate"
    )

    state, context = _sec06_terminal(path)
    result = state["result"]

    if mutation == "counter_private_metadata":
        counters = result.counters.model_copy()

        object.__setattr__(
            counters,
            "__pydantic_private__",
            {"unexpected": True},
        )

        changed_result = result.model_copy(
            update={"counters": counters}
        )

    elif mutation == "version_extra_metadata":
        versions = result.versions.model_copy()

        object.__setattr__(
            versions,
            "__pydantic_extra__",
            {"unexpected": True},
        )

        changed_result = result.model_copy(
            update={"versions": versions}
        )

    elif mutation == "fixture_coverage_negative_zero":
        changed_result = result.model_copy(
            update={"fixture_coverage": -0.0}
        )

    else:
        candidate = result.candidate
        assert candidate is not None

        first = candidate.sections[0]

        if mutation == "report_private_metadata":
            changed_candidate = candidate.model_copy()

            object.__setattr__(
                changed_candidate,
                "__pydantic_private__",
                {"unexpected": True},
            )

        elif mutation == "sections_list":
            changed_candidate = candidate.model_copy(
                update={
                    "sections": list(candidate.sections),
                }
            )

        else:
            if mutation == "section_extra_raw_field":
                changed_section = first.model_copy()
                changed_section.__dict__["unexpected"] = True

            elif mutation == "references_list":
                changed_section = first.model_copy(
                    update={
                        "fixture_references": list(
                            first.fixture_references
                        ),
                    }
                )

            else:
                reference = first.fixture_references[0]

                changed_reference = reference.model_copy(
                    update={"attempt_id": UUID(int=999)}
                )

                changed_section = first.model_copy(
                    update={
                        "fixture_references": (
                            changed_reference,
                        ) + first.fixture_references[1:],
                    }
                )

            changed_candidate = candidate.model_copy(
                update={
                    "sections": (
                        changed_section,
                    ) + candidate.sections[1:],
                }
            )

        changed_result = result.model_copy(
            update={"candidate": changed_candidate}
        )

    changed = {
        **state,
        "result": changed_result,
    }

    _sec06_assert_rejected(changed, context)


# WP04-04C: SEC07 safe exception mapping regression.

from agentops_api.agent.s05 import report
from agentops_api.agent.s05.validation import S05BoundaryError


_SEC07_MARKER = "synthetic-sec07-private-marker"


class _Sec07CategorySubclass(str):
    pass


class _Sec07UnknownError(Exception):
    def __init__(self, category):
        super().__init__(_SEC07_MARKER)
        self.category = category


def _sec07_assert_safe(operation, expected, caplog):
    caplog.clear()

    with pytest.raises(
        workflow.S05WorkflowError
    ) as caught:
        operation()

    error = caught.value

    assert type(error) is workflow.S05WorkflowError
    assert error.category == expected
    assert type(error.category) is str
    assert str(error) == "S05 workflow failed"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert _SEC07_MARKER not in str(error)
    assert _SEC07_MARKER not in repr(error)
    assert _SEC07_MARKER not in caplog.text


def _sec07_inject(
    request_model, monkeypatch, error, expected, caplog,
    target="_build_graph",
):
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise error

    monkeypatch.setattr(
        workflow, target, fail
    )

    _sec07_assert_safe(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        expected,
        caplog,
    )

    assert calls == [True]


@pytest.mark.parametrize(
    "category",
    [
        "invalid_input",
        "invalid_output",
        "execution_failed",
        "security_violation",
        "deadline_exceeded",
        "budget_exceeded",
        "unknown-category",
        123,
        _Sec07CategorySubclass("invalid_output"),
        None,
    ],
)
def test_sec07_unknown_categories_are_not_trusted(
    request_model, monkeypatch, caplog, category
):
    _sec07_inject(
        request_model,
        monkeypatch,
        _Sec07UnknownError(category),
        "execution_failed",
        caplog,
    )


@pytest.mark.parametrize(
    "property_behavior",
    ["return", "raise"],
)
def test_sec07_unknown_category_property_not_accessed(
    request_model, monkeypatch, caplog,
    property_behavior,
):
    reads = []

    class HostileError(Exception):
        @property
        def category(self):
            reads.append(True)

            if property_behavior == "raise":
                raise RuntimeError(_SEC07_MARKER)

            return "invalid_output"

    _sec07_inject(
        request_model,
        monkeypatch,
        HostileError(_SEC07_MARKER),
        "execution_failed",
        caplog,
    )

    assert reads == []


@pytest.mark.parametrize(
    "error_type, arguments, expected",
    [
        (
            S05StateIntegrityError,
            (),
            "security_violation",
        ),
        (
            report.S05ReportError,
            (),
            "invalid_output",
        ),
        (
            writer.S05WriterError,
            (),
            "execution_failed",
        ),
        (
            planner.S05PlannerError,
            ("invalid_output",),
            "invalid_output",
        ),
        (
            planner.S05PlannerError,
            ("execution_failed",),
            "execution_failed",
        ),
        (
            research.S05ResearchError,
            ("invalid_output",),
            "invalid_output",
        ),
        (
            research.S05ResearchError,
            ("execution_failed",),
            "execution_failed",
        ),
    ],
)
def test_sec07_exact_trusted_error_mapping(
    request_model, monkeypatch, caplog,
    error_type, arguments, expected,
):
    _sec07_inject(
        request_model,
        monkeypatch,
        error_type(*arguments),
        expected,
        caplog,
    )


@pytest.mark.parametrize(
    "error_type, arguments",
    [
        (S05StateIntegrityError, ()),
        (report.S05ReportError, ()),
        (writer.S05WriterError, ()),
        (planner.S05PlannerError, ("invalid_output",)),
        (research.S05ResearchError, ("invalid_output",)),
    ],
)
def test_sec07_trusted_exception_subclasses_not_trusted(
    request_model, monkeypatch, caplog,
    error_type, arguments,
):
    reads = []

    class UntrustedSubclass(error_type):
        @property
        def category(self):
            reads.append(True)
            raise RuntimeError(_SEC07_MARKER)

    error = UntrustedSubclass(*arguments)

    _sec07_inject(
        request_model,
        monkeypatch,
        error,
        "execution_failed",
        caplog,
    )

    assert reads == []


@pytest.mark.parametrize(
    "error_type",
    [
        planner.S05PlannerError,
        research.S05ResearchError,
    ],
)
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "security_violation",
        "deadline_exceeded",
        "budget_exceeded",
        "invalid_input",
        "integer",
        "string_subclass",
        "hostile_object",
    ],
)
def test_sec07_internal_category_validation(
    request_model, monkeypatch, caplog,
    error_type, mutation,
):
    reads = []

    class HostileCategory:
        def __eq__(self, other):
            reads.append(True)
            raise RuntimeError(_SEC07_MARKER)

        def __str__(self):
            reads.append(True)
            raise RuntimeError(_SEC07_MARKER)

    error = error_type("invalid_output")

    if mutation == "missing":
        del error.__dict__["_category"]

    elif mutation == "integer":
        error.__dict__["_category"] = 123

    elif mutation == "string_subclass":
        error.__dict__["_category"] = (
            _Sec07CategorySubclass("invalid_output")
        )

    elif mutation == "hostile_object":
        error.__dict__["_category"] = HostileCategory()

    else:
        error.__dict__["_category"] = mutation

    _sec07_inject(
        request_model,
        monkeypatch,
        error,
        "execution_failed",
        caplog,
    )

    assert reads == []


@pytest.mark.parametrize(
    "error_type, expected",
    [
        (
            S05StateIntegrityError,
            "security_violation",
        ),
        (
            report.S05ReportError,
            "invalid_output",
        ),
        (
            writer.S05WriterError,
            "execution_failed",
        ),
    ],
)
def test_sec07_static_mapping_ignores_instance_category(
    request_model, monkeypatch, caplog,
    error_type, expected,
):
    error = error_type()

    error.__dict__["category"] = "budget_exceeded"
    error.__dict__["_category"] = "deadline_exceeded"

    _sec07_inject(
        request_model,
        monkeypatch,
        error,
        expected,
        caplog,
    )


@pytest.mark.parametrize(
    "target",
    [
        "planner_node",
        "research_node",
        "evidence_validation_node",
        "writer_node",
        "report_validation_node",
        "outcome_node",
    ],
)
def test_sec07_actual_graph_exception_spoofing(
    request_model, monkeypatch, caplog, target
):
    nodes = (
        "planner_node",
        "research_node",
        "evidence_validation_node",
        "writer_node",
        "report_validation_node",
        "outcome_node",
    )

    calls = []

    def instrument(name, original):
        def wrapped(*args, **kwargs):
            calls.append(name)

            if name == target:
                raise _Sec07UnknownError(
                    "invalid_output"
                )

            return original(*args, **kwargs)

        return wrapped

    for name in nodes:
        monkeypatch.setattr(
            workflow,
            name,
            instrument(
                name,
                getattr(workflow, name),
            ),
        )

    _sec07_assert_safe(
        lambda: workflow.run_specialized_workflow(
            request_model
        ),
        "execution_failed",
        caplog,
    )

    assert calls == list(
        nodes[:nodes.index(target) + 1]
    )


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("trusted_input", "invalid_input"),
        ("input_subclass", "execution_failed"),
        ("unknown_input", "execution_failed"),
    ],
)
def test_sec07_input_exception_boundary(
    request_model, monkeypatch, caplog,
    kind, expected,
):
    reads = []

    class UntrustedInputSubclass(S05BoundaryError):
        @property
        def category(self):
            reads.append(True)
            raise RuntimeError(_SEC07_MARKER)

    if kind == "trusted_input":
        error = S05BoundaryError()

    elif kind == "input_subclass":
        error = UntrustedInputSubclass()

    else:
        error = _Sec07UnknownError("invalid_input")

    def forbidden_graph():
        pytest.fail(
            "Graph must not start after input failure"
        )

    monkeypatch.setattr(
        workflow, "_build_graph", forbidden_graph
    )

    _sec07_inject(
        request_model,
        monkeypatch,
        error,
        expected,
        caplog,
        target="create_execution_context",
    )

    assert reads == []


def test_sec07_unknown_attribute_hook_not_accessed(
    request_model, monkeypatch, caplog,
):
    reads = []

    class HookError(Exception):
        def __getattribute__(self, name):
            if name in (
                "category",
                "_category",
            ):
                reads.append(name)
                raise RuntimeError(_SEC07_MARKER)

            return super().__getattribute__(name)

    _sec07_inject(
        request_model,
        monkeypatch,
        HookError(_SEC07_MARKER),
        "execution_failed",
        caplog,
    )

    assert reads == []


# WP04-05C: SEC08 node update ownership regression.

from contextlib import ExitStack

_SEC08_NODES = ('planner_node', 'research_node', 'evidence_validation_node', 'writer_node', 'report_validation_node', 'outcome_node')

_SEC08_OWNERSHIP = {'planner_node': {'plan', 'stage', 'counters'}, 'research_node': {'research_output', 'fixture_coverage', 'stage', 'counters'}, 'evidence_validation_node': {'research_output', 'fixture_coverage', 'stage'}, 'writer_node': {'draft_report', 'stage', 'counters'}, 'report_validation_node': {'draft_report', 'stage'}, 'outcome_node': {'result', 'stage'}}

def _sec08_request():
    return S05GraphInput(task_id=UUID(int=1101), attempt_id=UUID(int=1102), question='Synthetic SEC08 diagnostic.', scope={'region': 'offline'})

def _sec08_observe(operation):
    try:
        result = operation()
    except workflow.S05WorkflowError as error:
        assert type(error) is workflow.S05WorkflowError
        assert str(error) == 'S05 workflow failed'
        assert error.__cause__ is None
        assert error.__context__ is None
        return error.category
    assert type(result) is S05GraphResult
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0
    return result.outcome

def _sec08_execute(target=None, mutation=None, incomplete=False):
    calls = []
    injected = []
    original_plan = planner.plan_fixture

    def incomplete_plan(context):
        plan = original_plan(context)
        return ResearchPlan(subquestions=tuple((ResearchSubquestion(subquestion_id=item.subquestion_id, question=item.question, query='fixture:missing-' + item.subquestion_id) for item in plan.subquestions)), assumptions=plan.assumptions)

    def instrument(name, original):

        def wrapped(state, context):
            calls.append(name)
            if name != target:
                return original(state, context)
            injected.append(name)
            if mutation == 'ordinary_failure':
                raise RuntimeError('synthetic SEC08 failure')
            if mutation == 'scope_mutation_failure':
                state['scope']['region'] = 'unauthorized-change'
                raise RuntimeError('synthetic SEC08 failure')
            update = original(state, context)
            assert type(update) is dict
            assert set(update) == _SEC08_OWNERSHIP[name], name
            changed = dict(update)
            if mutation == 'unknown_key':
                changed['sec08_unknown_channel'] = True
            elif mutation == 'protected_key':
                changed['task_id'] = state['task_id']
            elif mutation == 'missing_stage':
                del changed['stage']
            elif mutation == 'foreign_known_channel':
                foreign = 'plan' if name != 'planner_node' else 'draft_report'
                assert foreign not in _SEC08_OWNERSHIP[name]
                changed[foreign] = state[foreign]
            elif mutation == 'scope_mutation_success':
                state['scope']['region'] = 'unauthorized-change'
            else:
                raise AssertionError('Unknown diagnostic mutation')
            return changed
        return wrapped
    with ExitStack() as stack:
        if incomplete:
            stack.enter_context(patch.object(planner, 'plan_fixture', incomplete_plan))
        for name in _SEC08_NODES:
            stack.enter_context(patch.object(workflow, name, instrument(name, getattr(workflow, name))))
        actual = _sec08_observe(lambda: workflow.run_specialized_workflow(_sec08_request()))
    if target is not None:
        assert injected, target
    return (actual, calls)


@pytest.mark.parametrize(
    "incomplete,expected,expected_calls",
    [
        (
            False,
            "candidate_ready",
            [
                *_SEC08_NODES,
                "outcome_node",
            ],
        ),
        (
            True,
            "insufficient_evidence",
            [
                "planner_node",
                "research_node",
                "evidence_validation_node",
                "outcome_node",
                "outcome_node",
            ],
        ),
    ],
)
def test_sec08_valid_graph_controls(
    incomplete, expected, expected_calls
):
    actual, calls = _sec08_execute(
        incomplete=incomplete
    )

    assert actual == expected
    assert calls == expected_calls


def test_sec08_ordinary_failure_control():
    actual, calls = _sec08_execute(
        "planner_node",
        "ordinary_failure",
    )

    assert actual == "execution_failed"
    assert calls == ["planner_node"]


@pytest.mark.parametrize(
    "target", _SEC08_NODES
)
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_key",
        "protected_key",
        "missing_stage",
        "foreign_known_channel",
        "scope_mutation_success",
        "scope_mutation_failure",
    ],
)
def test_sec08_original_ownership_mutations(
    target, mutation
):
    actual, calls = _sec08_execute(
        target, mutation
    )

    assert actual == "security_violation"

    assert calls == list(
        _SEC08_NODES[
            :_SEC08_NODES.index(target) + 1
        ]
    )


def _sec08_assert_public_violation(
    monkeypatch, target, mutation
):
    calls = []

    originals = {
        name: getattr(workflow, name)
        for name in _SEC08_NODES
    }

    def instrument(name, operation):
        def wrapped(state, context):
            calls.append(name)

            if name == target:
                return mutation(
                    operation, state, context
                )

            return operation(state, context)

        return wrapped

    for name, operation in originals.items():
        monkeypatch.setattr(
            workflow,
            name,
            instrument(name, operation),
        )

    assert _sec08_observe(
        lambda: workflow.run_specialized_workflow(
            _sec08_request()
        )
    ) == "security_violation"

    assert calls == list(
        _SEC08_NODES[
            :_SEC08_NODES.index(target) + 1
        ]
    )


@pytest.mark.parametrize(
    "target", _SEC08_NODES
)
@pytest.mark.parametrize(
    "kind",
    [
        "dict_subclass",
        "list",
        "none",
        "key_subclass",
        "wrong_stage",
        "stage_subclass",
        "missing_payload",
    ],
)
def test_sec08_exact_update_structure(
    monkeypatch, target, kind
):
    class UpdateSubclass(dict):
        pass

    class TextSubclass(str):
        pass

    def mutate(operation, state, context):
        update = operation(state, context)

        if kind == "dict_subclass":
            return UpdateSubclass(update)

        if kind == "list":
            return list(update.items())

        if kind == "none":
            return None

        if kind == "key_subclass":
            stage = update.pop("stage")
            update[TextSubclass("stage")] = stage

        elif kind == "wrong_stage":
            update["stage"] = "pending"

        elif kind == "stage_subclass":
            update["stage"] = TextSubclass(
                update["stage"]
            )

        else:
            name = next(
                key
                for key in update
                if key != "stage"
            )

            del update[name]

        return update

    _sec08_assert_public_violation(
        monkeypatch, target, mutate
    )


@pytest.mark.parametrize(
    "target", _SEC08_NODES
)
@pytest.mark.parametrize(
    "failure", [False, True]
)
def test_sec08_context_mutation(
    monkeypatch, target, failure
):
    def mutate(operation, state, context):
        update = None

        if not failure:
            update = operation(state, context)

        object.__setattr__(
            context,
            "question",
            "unauthorized context change",
        )

        if failure:
            raise RuntimeError(
                "synthetic context failure"
            )

        return update

    _sec08_assert_public_violation(
        monkeypatch, target, mutate
    )


@pytest.mark.parametrize(
    "target", _SEC08_NODES
)
@pytest.mark.parametrize(
    "failure", [False, True]
)
def test_sec08_nested_counter_mutation(
    monkeypatch, target, failure
):
    def mutate(operation, state, context):
        update = None

        if not failure:
            update = operation(state, context)

        object.__setattr__(
            state["counters"],
            "repair_attempts",
            False,
        )

        if failure:
            raise RuntimeError(
                "synthetic counter failure"
            )

        return update

    _sec08_assert_public_violation(
        monkeypatch, target, mutate
    )


@pytest.mark.parametrize(
    "target",
    [
        "research_node",
        "evidence_validation_node",
        "writer_node",
        "report_validation_node",
        "outcome_node",
    ],
)
@pytest.mark.parametrize(
    "failure", [False, True]
)
def test_sec08_nested_plan_mutation(
    monkeypatch, target, failure
):
    def mutate(operation, state, context):
        update = None

        if not failure:
            update = operation(state, context)

        first = state["plan"].subquestions[0]

        object.__setattr__(
            first,
            "question",
            "unauthorized nested change",
        )

        if failure:
            raise RuntimeError(
                "synthetic nested plan failure"
            )

        return update

    _sec08_assert_public_violation(
        monkeypatch, target, mutate
    )


@pytest.mark.parametrize(
    "kind",
    [
        "invalid_route",
        "wrong_allowed_route",
        "route_subclass",
        "scope_mutation",
        "context_mutation",
        "mutation_then_failure",
    ],
)
def test_sec08_conditional_route_integrity(
    monkeypatch, kind
):
    original = workflow.route_after_evidence
    downstream = []

    class RouteSubclass(str):
        pass

    def mutate(state, context):
        route = original(state, context)

        if kind == "invalid_route":
            return "unknown-route"

        if kind == "wrong_allowed_route":
            return (
                "abstain"
                if route == "writer"
                else "writer"
            )

        if kind == "route_subclass":
            return RouteSubclass(route)

        if kind == "context_mutation":
            object.__setattr__(
                context,
                "question",
                "unauthorized route context",
            )

        else:
            state["scope"]["region"] = (
                "unauthorized-route-change"
            )

            if kind == "mutation_then_failure":
                raise RuntimeError(
                    "synthetic route failure"
                )

        return route

    def forbidden(*args, **kwargs):
        downstream.append(True)
        raise AssertionError(
            "Downstream node must not execute"
        )

    monkeypatch.setattr(
        workflow, "route_after_evidence", mutate
    )

    monkeypatch.setattr(
        workflow, "writer_node", forbidden
    )

    monkeypatch.setattr(
        workflow, "outcome_node", forbidden
    )

    assert _sec08_observe(
        lambda: workflow.run_specialized_workflow(
            _sec08_request()
        )
    ) == "security_violation"

    assert downstream == []


# WP04-05C-R1B: Additional SEC08 boundary tests.

_SEC08R1_TARGETS = {'planner': 'planner_node', 'research': 'research_node', 'evidence': 'evidence_validation_node', 'writer': 'writer_node', 'report_validation': 'report_validation_node', 'outcome': 'outcome_node'}

def _sec08r1_request():
    return S05GraphInput(task_id=UUID(int=1201), attempt_id=UUID(int=1202), question='Synthetic SEC08 final review.', scope={'region': 'offline'})

def _sec08r1_observe(operation):
    try:
        result = operation()
    except workflow.S05WorkflowError as error:
        assert type(error) is workflow.S05WorkflowError
        assert str(error) == 'S05 workflow failed'
        assert error.__cause__ is None
        assert error.__context__ is None
        return error.category
    if type(result) is not S05GraphResult:
        return 'unsafe_result_type'
    if result.publishable is not False:
        return 'unsafe_result_publishable'
    if type(result.evidence_ids) is not tuple:
        return 'unsafe_result_evidence_type'
    if result.evidence_ids != ():
        return 'unsafe_result_evidence'
    if type(result.coverage) is not float or result.coverage.hex() != 0.0.hex():
        return 'unsafe_result_coverage'
    return result.outcome

def _sec08r1_malformed_payload(name, update):
    changed = dict(update)
    if name == 'planner':
        plan = update['plan']
        first = plan.subquestions[0]
        bad_first = first.model_copy(update={'question': 123})
        changed['plan'] = plan.model_copy(update={'subquestions': (bad_first,) + plan.subquestions[1:]})
    elif name in ('research', 'evidence'):
        output = update['research_output']
        changed['research_output'] = output.model_copy(update={'records': list(output.records)})
    elif name in ('writer', 'report_validation'):
        changed['draft_report'] = update['draft_report'].model_copy(update={'title': 123})
    elif name == 'outcome':
        changed['result'] = update['result'].model_copy(update={'publishable': True})
    else:
        raise AssertionError('Unexpected target')
    return changed

def _sec08r1_fabricated_reference(name, update):
    changed = dict(update)
    report = update['draft_report']
    section = report.sections[0]
    reference = section.fixture_references[0]
    bad_reference = reference.model_copy(update={'fixture_id': 'fixture-fabricated', 'task_id': UUID(int=9999)})
    bad_section = section.model_copy(update={'fixture_references': (bad_reference,) + section.fixture_references[1:]})
    changed['draft_report'] = report.model_copy(update={'sections': (bad_section,) + report.sections[1:]})
    return changed

def _sec08r1_inspect_update(target, mutation):
    function_name = _SEC08R1_TARGETS[target]
    original_node = getattr(workflow, function_name)
    original_guard = workflow._validate_node_update
    injected = []
    guard_entered = []
    passed_guard = []

    def corrupt(state, context):
        update = original_node(state, context)
        injected.append(True)
        return mutation(target, update)

    def observe_guard(name, state, update, context):
        if name == target:
            guard_entered.append(True)
        value = original_guard(name, state, update, context)
        if name == target:
            passed_guard.append(True)
        return value
    with patch.object(workflow, function_name, corrupt), patch.object(workflow, '_validate_node_update', observe_guard):
        actual = _sec08r1_observe(lambda: workflow.run_specialized_workflow(_sec08r1_request()))
    assert injected
    assert guard_entered == [True]
    if target == 'outcome':
        assert len(injected) in (1, 2)
    else:
        assert injected == [True]
    return (actual, bool(passed_guard))

def _sec08r1_inspect_reconstruction(mutation):
    original = workflow.outcome_node
    calls = []
    injected = []

    def changed_outcome(state, context):
        calls.append(True)
        update = original(state, context)
        if len(calls) == 1:
            return update
        assert len(calls) == 2
        injected.append(True)
        if mutation in ('scope_success', 'scope_failure'):
            state['scope']['region'] = 'unauthorized-reconstruction-change'
        elif mutation in ('context_success', 'context_failure'):
            object.__setattr__(context, 'question', 'unauthorized reconstruction context')
        elif mutation == 'extra_key':
            update = dict(update)
            update['sec08_unauthorized_reconstruction_key'] = True
        elif mutation == 'missing_stage':
            update = dict(update)
            del update['stage']
        else:
            raise AssertionError('Unexpected mutation')
        if mutation.endswith('_failure'):
            raise RuntimeError('synthetic reconstruction failure')
        return update
    with patch.object(workflow, 'outcome_node', changed_outcome):
        actual = _sec08r1_observe(lambda: workflow.run_specialized_workflow(_sec08r1_request()))
    assert calls == [True, True]
    assert injected == [True]
    return actual


def test_sec08r1_valid_control():
    result = workflow.run_specialized_workflow(
        _sec08r1_request()
    )

    assert type(result) is S05GraphResult
    assert result.outcome == "candidate_ready"
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage.hex() == 0.0.hex()


@pytest.mark.parametrize(
    "target", tuple(_SEC08R1_TARGETS)
)
def test_sec08r1_nested_payload(target):
    actual, passed = _sec08r1_inspect_update(
        target, _sec08r1_malformed_payload
    )

    assert actual == "security_violation"
    assert passed is False


@pytest.mark.parametrize(
    "target", ("writer", "report_validation")
)
def test_sec08r1_fabricated_provenance(target):
    actual, passed = _sec08r1_inspect_update(
        target, _sec08r1_fabricated_reference
    )

    assert actual == "security_violation"
    assert passed is False


def test_sec08r1_first_outcome_only():
    original = workflow.outcome_node
    calls = []

    def mutate(state, context):
        calls.append(True)
        update = original(state, context)

        if len(calls) == 1:
            return _sec08r1_malformed_payload(
                "outcome", update
            )

        return update

    with patch.object(
        workflow, "outcome_node", mutate
    ):
        actual = _sec08r1_observe(
            lambda: workflow.run_specialized_workflow(
                _sec08r1_request()
            )
        )

    assert actual == "security_violation"
    assert calls == [True]


@pytest.mark.parametrize(
    "mutation",
    [
        "scope_success",
        "scope_failure",
        "context_success",
        "context_failure",
        "extra_key",
        "missing_stage",
    ],
)
def test_sec08r1_reconstruction(mutation):
    assert _sec08r1_inspect_reconstruction(
        mutation
    ) == "security_violation"


def test_sec08r1_aggregate_snapshot_rejected():
    leaf = tuple(range(40))
    middle = (leaf,) * 40

    with pytest.raises(S05StateIntegrityError):
        workflow._checked_snapshot(
            (middle,) * 40
        )


def test_sec08r1_aggregate_snapshot_valid_control():
    value = tuple(range(4096))

    assert (
        workflow._checked_snapshot(value)
        == workflow._checked_snapshot(value)
    )


def test_sec08r1_snapshot_budget_is_per_call():
    value = tuple(range(8192))

    for _ in range(5):
        assert workflow._checked_snapshot(
            value
        ) is not None


def test_sec08r1_valid_large_scope():
    request = S05GraphInput(
        task_id=UUID(int=1203),
        attempt_id=UUID(int=1204),
        question="x" * 4000,
        scope={"values": [0] * 4000},
    )

    result = workflow.run_specialized_workflow(
        request
    )

    assert result.outcome == "candidate_ready"
    assert result.publishable is False


def test_sec08r1_reconstruction_both_results_unsafe():
    original = workflow.outcome_node

    def mutate(state, context):
        update = original(state, context)

        return _sec08r1_malformed_payload(
            "outcome", update
        )

    with patch.object(
        workflow, "outcome_node", mutate
    ):
        actual = _sec08r1_observe(
            lambda: workflow.run_specialized_workflow(
                _sec08r1_request()
            )
        )

    assert actual == "security_violation"
