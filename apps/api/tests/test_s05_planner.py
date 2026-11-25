"""Unit tests for the initial S05 Planner node."""

from copy import deepcopy
from uuid import UUID

import pytest

from agentops_api.agent.s05 import planner
from agentops_api.agent.s05.contract import (
    ExecutionCounters,
    ResearchPlan,
    S05GraphInput,
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
            task_id=UUID(int=101),
            attempt_id=UUID(int=102),
            question="Compare synthetic market fixtures.",
            scope={"market": {"region": "offline"}},
        )
    )


def test_planner_returns_only_owned_channels(context):
    state = build_initial_state(context)
    original = deepcopy(state)

    result = planner.planner_node(state, context)

    assert set(result) == {
        "plan", "stage", "counters"
    }

    assert type(result["plan"]) is ResearchPlan
    assert 1 <= len(result["plan"].subquestions) <= 4
    assert result["stage"] == "planned"

    assert result["counters"] == ExecutionCounters(
        adapter_invocations=1
    )

    assert state == original

    verify_protected_state(state, context)

    merged = {**state, **result}

    verify_protected_state(merged, context)


def test_planner_is_deterministic(context):
    state = build_initial_state(context)

    first = planner.planner_node(state, context)
    second = planner.planner_node(state, context)

    assert first == second
    assert first["plan"] is not second["plan"]


def test_planner_calls_adapter_once(
    context, monkeypatch
):
    state = build_initial_state(context)

    original = planner.plan_fixture
    calls = []

    def spy(adapter_context):
        calls.append(adapter_context)

        assert adapter_context is not context

        return original(adapter_context)

    monkeypatch.setattr(
        planner, "plan_fixture", spy
    )

    result = planner.planner_node(state, context)

    assert len(calls) == 1
    assert result["counters"].adapter_invocations == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "planned"),
        ("stage", "failed"),
        ("stage", None),
        ("repair_used", True),
        ("repair_used", 0),
        ("fixture_coverage", 0.5),
        ("fixture_coverage", -0.0),
        ("fixture_coverage", 0),
        ("plan", {}),
        ("research_output", {}),
        ("draft_report", {}),
        ("result", {}),
        ("error_category", "execution_failed"),
        (
            "counters",
            ExecutionCounters(adapter_invocations=1),
        ),
        (
            "counters",
            ExecutionCounters().model_copy(
                update={"adapter_invocations": False}
            ),
        ),
        ("counters", {}),
    ],
)
def test_planner_rejects_invalid_initial_channels(
    context, monkeypatch, field, value
):
    state = build_initial_state(context)
    state[field] = value

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Adapter must not be invoked")

    monkeypatch.setattr(
        planner, "plan_fixture", forbidden
    )

    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        planner.planner_node(state, context)

    assert caught.value.category == "security_violation"
    assert calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("question", "Unexpected change"),
        ("scope", {"changed": True}),
        ("evidence_ids", ("fabricated",)),
        ("coverage", 1.0),
    ],
)
def test_planner_rejects_protected_state_changes(
    context, monkeypatch, field, value
):
    state = build_initial_state(context)
    state[field] = value

    def forbidden(*args, **kwargs):
        pytest.fail("Adapter must not be invoked")

    monkeypatch.setattr(
        planner, "plan_fixture", forbidden
    )

    with pytest.raises(S05StateIntegrityError):
        planner.planner_node(state, context)


@pytest.mark.parametrize(
    "mutation",
    ["none", "mapping", "empty", "too_many", "duplicate"],
)
def test_planner_rejects_malformed_adapter_output(
    context, monkeypatch, mutation
):
    state = build_initial_state(context)
    original = deepcopy(state)

    good = planner.plan_fixture(context)

    if mutation == "none":
        bad = None

    elif mutation == "mapping":
        bad = good.model_dump()

    elif mutation == "empty":
        bad = good.model_copy(
            update={"subquestions": ()}
        )

    elif mutation == "too_many":
        bad = good.model_copy(
            update={
                "subquestions": good.subquestions * 2
            }
        )

    else:
        bad = good.model_copy(
            update={
                "subquestions": (
                    good.subquestions[0],
                    good.subquestions[0],
                )
            }
        )

    calls = []

    def adapter(adapter_context):
        calls.append(True)
        return bad

    monkeypatch.setattr(
        planner, "plan_fixture", adapter
    )

    with pytest.raises(
        planner.S05PlannerError
    ) as caught:
        planner.planner_node(state, context)

    assert caught.value.category == "invalid_output"
    assert str(caught.value) == "S05 planner failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert len(calls) == 1
    assert state == original


def test_planner_sanitizes_adapter_exception(
    context, monkeypatch
):
    state = build_initial_state(context)
    original = deepcopy(state)
    calls = []

    def failing(adapter_context):
        calls.append(True)
        raise RuntimeError("private synthetic marker")

    monkeypatch.setattr(
        planner, "plan_fixture", failing
    )

    with pytest.raises(
        planner.S05PlannerError
    ) as caught:
        planner.planner_node(state, context)

    assert caught.value.category == "execution_failed"

    assert "private synthetic marker" not in str(
        caught.value
    )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None

    assert len(calls) == 1
    assert state == original


def test_planner_rejects_adapter_context_mutation(
    context, monkeypatch
):
    state = build_initial_state(context)
    original = deepcopy(state)

    good = planner.plan_fixture(context)

    def mutate(adapter_context):
        object.__setattr__(
            adapter_context,
            "question",
            "Unauthorized replacement",
        )
        return good

    monkeypatch.setattr(
        planner, "plan_fixture", mutate
    )

    with pytest.raises(S05StateIntegrityError):
        planner.planner_node(state, context)

    assert state == original
    assert context.question == (
        "Compare synthetic market fixtures."
    )


def test_planner_rejects_post_adapter_state_mutation(
    context, monkeypatch
):
    state = build_initial_state(context)
    good = planner.plan_fixture(context)

    def mutate(adapter_context):
        state["stage"] = "written"
        return good

    monkeypatch.setattr(
        planner, "plan_fixture", mutate
    )

    with pytest.raises(S05StateIntegrityError):
        planner.planner_node(state, context)


def test_planner_returns_independent_validated_plan(
    context, monkeypatch
):
    state = build_initial_state(context)
    original = planner.plan_fixture(context)

    monkeypatch.setattr(
        planner,
        "plan_fixture",
        lambda adapter_context: original,
    )

    update = planner.planner_node(state, context)

    assert update["plan"] == original
    assert update["plan"] is not original

    assert (
        update["plan"].subquestions[0]
        is not original.subquestions[0]
    )
