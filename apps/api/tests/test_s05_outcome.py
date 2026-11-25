"""Terminal Outcome tests for the offline S05 workflow."""

from copy import deepcopy
from itertools import product
from uuid import UUID

import pytest

from agentops_api.agent.s05 import (
    adapters,
    evidence,
    outcome,
    planner,
    research,
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
    S05StateIntegrityError,
    build_initial_state,
    create_execution_context,
    verify_protected_state,
)


@pytest.fixture
def context():
    return create_execution_context(
        S05GraphInput(
            task_id=UUID(int=701),
            attempt_id=UUID(int=702),
            question="Synthetic terminal outcome.",
            scope={"region": "offline"},
        )
    )


def _evidence_state(
    context,
    missing=(False, False, False, False),
):
    state = build_initial_state(context)

    state = {
        **state,
        **planner.planner_node(state, context),
    }

    plan = state["plan"]

    state["plan"] = ResearchPlan(
        subquestions=tuple(
            ResearchSubquestion(
                subquestion_id=item.subquestion_id,
                question=item.question,
                query=(
                    "fixture:unregistered-" + item.subquestion_id
                    if missing[index]
                    else item.query
                ),
            )
            for index, item in enumerate(plan.subquestions)
        ),
        assumptions=plan.assumptions,
    )

    state = {
        **state,
        **research.research_node(state, context),
    }

    return {
        **state,
        **evidence.evidence_validation_node(
            state, context
        ),
    }


@pytest.fixture
def ready_state(context):
    state = _evidence_state(context)

    state = {
        **state,
        **writer.writer_node(state, context),
    }

    return {
        **state,
        **writer.report_validation_node(
            state, context
        ),
    }


def _assert_security_error(operation):
    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        operation()

    assert type(caught.value) is S05StateIntegrityError
    assert caught.value.category == "security_violation"
    assert str(caught.value) == "invalid S05 protected state"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def _assert_result_boundary(
    result,
    context,
    expected_outcome,
    expected_calls,
    expected_coverage,
):
    assert type(result) is S05GraphResult

    assert result.task_id == context.task_id
    assert result.attempt_id == context.attempt_id

    assert result.stage == expected_outcome
    assert result.outcome == expected_outcome

    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0

    assert result.fixture_coverage == expected_coverage

    assert result.counters == ExecutionCounters(
        adapter_invocations=expected_calls
    )

    assert result.error_category is None


def test_outcome_candidate_returns_only_owned_channels(
    context, ready_state
):
    before = deepcopy(ready_state)

    update = outcome.outcome_node(
        ready_state, context
    )

    assert set(update) == {"result", "stage"}

    assert update["stage"] == "candidate_ready"

    result = update["result"]

    _assert_result_boundary(
        result,
        context,
        "candidate_ready",
        3,
        1.0,
    )

    assert result.candidate == ready_state["draft_report"]

    assert (
        result.candidate
        is not ready_state["draft_report"]
    )

    assert result.candidate.synthetic is True

    assert ready_state == before

    merged = {**ready_state, **update}

    verify_protected_state(merged, context)

    assert merged["counters"] == result.counters


@pytest.mark.parametrize(
    "missing",
    tuple(product((False, True), repeat=4))[1:],
)
def test_outcome_abstains_for_all_incomplete_masks(
    context, missing
):
    state = _evidence_state(context, missing)

    before = deepcopy(state)

    update = outcome.outcome_node(
        state, context
    )

    assert set(update) == {"result", "stage"}

    assert update["stage"] == "insufficient_evidence"

    result = update["result"]

    expected_coverage = (4 - sum(missing)) / 4

    _assert_result_boundary(
        result,
        context,
        "insufficient_evidence",
        2,
        expected_coverage,
    )

    assert result.candidate is None
    assert state["draft_report"] is None

    assert state == before

    merged = {**state, **update}

    verify_protected_state(merged, context)

    assert merged["counters"] == result.counters


@pytest.mark.parametrize(
    "complete",
    [True, False],
)
def test_outcome_invokes_no_adapters(
    context, ready_state, monkeypatch, complete
):
    state = (
        ready_state
        if complete
        else _evidence_state(
            context,
            (True, False, False, False),
        )
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Outcome must not invoke adapters")

    for module, names in (
        (
            adapters,
            (
                "plan_fixture",
                "research_fixture",
                "writer_fixture",
            ),
        ),
        (planner, ("plan_fixture",)),
        (research, ("research_fixture",)),
        (writer, ("writer_fixture",)),
    ):
        for name in names:
            monkeypatch.setattr(
                module, name, forbidden
            )

    result = outcome.outcome_node(
        state, context
    )["result"]

    assert result.counters.adapter_invocations == (
        3 if complete else 2
    )


def test_outcome_rejects_premature_complete_evidence(
    context,
):
    state = _evidence_state(context)

    assert evidence.route_after_evidence(
        state, context
    ) == "writer"

    _assert_security_error(
        lambda: outcome.outcome_node(
            state, context
        )
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "pending"),
        ("stage", "planned"),
        ("stage", "researched"),
        ("stage", "written"),
        ("stage", "candidate_ready"),
        ("stage", "insufficient_evidence"),
        ("stage", "failed"),
        ("stage", None),
        ("result", {}),
        ("draft_report", None),
        ("draft_report", {}),
        ("plan", None),
        ("research_output", None),
        ("fixture_coverage", 0.75),
        ("fixture_coverage", 1),
        ("coverage", 1.0),
        ("evidence_ids", ("fabricated",)),
        ("repair_used", True),
        ("repair_used", 0),
        ("error_category", "execution_failed"),
        ("counters", ExecutionCounters()),
        (
            "counters",
            ExecutionCounters(adapter_invocations=2),
        ),
        (
            "counters",
            ExecutionCounters(adapter_invocations=4),
        ),
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("question", "Changed question"),
        ("scope", {"changed": True}),
    ],
)
def test_outcome_rejects_invalid_candidate_state(
    context, ready_state, field, value
):
    ready_state[field] = value

    _assert_security_error(
        lambda: outcome.outcome_node(
            ready_state, context
        )
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("draft_report", {}),
        ("result", {}),
        ("fixture_coverage", 1.0),
        ("coverage", 1.0),
        ("evidence_ids", ("fabricated",)),
        ("repair_used", True),
        ("counters", ExecutionCounters()),
        ("error_category", "execution_failed"),
    ],
)
def test_outcome_rejects_invalid_abstention_state(
    context, field, value
):
    state = _evidence_state(
        context,
        (True, False, False, False),
    )

    assert evidence.route_after_evidence(
        state, context
    ) == "abstain"

    state[field] = value

    _assert_security_error(
        lambda: outcome.outcome_node(
            state, context
        )
    )


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "cross_task", "cross_attempt"],
)
def test_outcome_rejects_tampered_report_reference(
    context, ready_state, mutation
):
    draft = ready_state["draft_report"]

    section = draft.sections[0]
    reference = section.fixture_references[0]

    changes = {
        "unknown": {
            "fixture_id": "fixture-fabricated",
        },
        "cross_task": {
            "task_id": UUID(int=999),
        },
        "cross_attempt": {
            "attempt_id": UUID(int=999),
        },
    }

    changed_reference = reference.model_copy(
        update=changes[mutation]
    )

    changed_section = section.model_copy(
        update={
            "fixture_references": (
                changed_reference,
            ) + section.fixture_references[1:],
        }
    )

    ready_state["draft_report"] = draft.model_copy(
        update={
            "sections": (
                changed_section,
            ) + draft.sections[1:],
        }
    )

    _assert_security_error(
        lambda: outcome.outcome_node(
            ready_state, context
        )
    )


def test_outcome_rejects_malformed_validated_report(
    context, ready_state
):
    draft = ready_state["draft_report"]

    ready_state["draft_report"] = draft.model_copy(
        update={"title": ""}
    )

    _assert_security_error(
        lambda: outcome.outcome_node(
            ready_state, context
        )
    )


def test_outcome_rejects_tampered_incomplete_evidence(
    context,
):
    state = _evidence_state(
        context,
        (True, False, False, False),
    )

    output = state["research_output"]

    state["research_output"] = output.model_copy(
        update={"fixture_coverage": 1.0}
    )

    _assert_security_error(
        lambda: outcome.outcome_node(
            state, context
        )
    )


def test_outcome_rejects_duplicate_terminal_execution(
    context, ready_state
):
    update = outcome.outcome_node(
        ready_state, context
    )

    terminal = {**ready_state, **update}

    _assert_security_error(
        lambda: outcome.outcome_node(
            terminal, context
        )
    )


@pytest.mark.parametrize(
    "attempt_id",
    [UUID(int=802), None],
)
def test_outcome_is_deterministic_and_task_scoped(
    attempt_id,
):
    context = create_execution_context(
        S05GraphInput(
            task_id=UUID(int=801),
            attempt_id=attempt_id,
            question="Synthetic terminal identity.",
            scope={"region": "offline"},
        )
    )

    state = _evidence_state(context)

    state = {
        **state,
        **writer.writer_node(state, context),
    }

    state = {
        **state,
        **writer.report_validation_node(
            state, context
        ),
    }

    first = outcome.outcome_node(
        state, context
    )["result"]

    second = outcome.outcome_node(
        state, context
    )["result"]

    assert first == second
    assert first is not second

    _assert_result_boundary(
        first,
        context,
        "candidate_ready",
        3,
        1.0,
    )


def test_outcome_rejects_cross_task_state(
    context, ready_state
):
    other = create_execution_context(
        S05GraphInput(
            task_id=UUID(int=999),
            attempt_id=context.attempt_id,
            question=context.question,
            scope=context.scope_copy(),
        )
    )

    _assert_security_error(
        lambda: outcome.outcome_node(
            ready_state, other
        )
    )
