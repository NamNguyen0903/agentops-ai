"""Unit tests for the initial S05 Research node."""

from copy import deepcopy
from uuid import UUID

import pytest

from agentops_api.agent.s05 import (
    adapters,
    planner,
    research,
)
from agentops_api.agent.s05.contract import (
    ExecutionCounters,
    ResearchOutput,
    ResearchPlan,
    ResearchSubquestion,
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
            task_id=UUID(int=201),
            attempt_id=UUID(int=202),
            question="Compare synthetic market fixtures.",
            scope={"market": {"region": "offline"}},
        )
    )


@pytest.fixture
def planned_state(context):
    state = build_initial_state(context)

    return {
        **state,
        **planner.planner_node(state, context),
    }


def test_research_returns_only_owned_channels(
    context, planned_state
):
    original = deepcopy(planned_state)

    result = research.research_node(
        planned_state, context
    )

    assert set(result) == {
        "research_output",
        "fixture_coverage",
        "stage",
        "counters",
    }

    output = result["research_output"]

    assert type(output) is ResearchOutput
    assert len(output.records) == 4
    assert output.fixture_coverage == 1.0
    assert result["fixture_coverage"] == 1.0

    assert result["stage"] == "researched"

    assert result["counters"] == ExecutionCounters(
        adapter_invocations=2
    )

    assert planned_state == original

    merged = {**planned_state, **result}

    verify_protected_state(merged, context)

    assert merged["evidence_ids"] == ()
    assert merged["coverage"] == 0.0
    assert merged["draft_report"] is None
    assert merged["result"] is None


def test_research_is_deterministic(
    context, planned_state
):
    first = research.research_node(
        planned_state, context
    )

    second = research.research_node(
        planned_state, context
    )

    assert first == second

    assert (
        first["research_output"]
        is not second["research_output"]
    )


def test_research_calls_approved_adapter_once(
    context, planned_state, monkeypatch
):
    original = research.research_fixture
    calls = []

    def spy(adapter_context, adapter_plan):
        calls.append(True)

        assert adapter_context is not context
        assert adapter_plan is not planned_state["plan"]

        assert (
            adapter_plan.subquestions[0]
            is not planned_state["plan"].subquestions[0]
        )

        return original(
            adapter_context, adapter_plan
        )

    monkeypatch.setattr(
        research, "research_fixture", spy
    )

    result = research.research_node(
        planned_state, context
    )

    assert len(calls) == 1
    assert result["counters"].adapter_invocations == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "pending"),
        ("stage", "researched"),
        ("stage", "failed"),
        ("stage", None),
        ("plan", None),
        ("plan", {}),
        ("research_output", {}),
        ("fixture_coverage", 0.5),
        ("fixture_coverage", -0.0),
        ("fixture_coverage", 0),
        ("repair_used", True),
        ("repair_used", 0),
        ("draft_report", {}),
        ("result", {}),
        ("error_category", "execution_failed"),
        ("counters", ExecutionCounters()),
        (
            "counters",
            ExecutionCounters(adapter_invocations=2),
        ),
        (
            "counters",
            ExecutionCounters(
                adapter_invocations=1
            ).model_copy(
                update={"adapter_invocations": True}
            ),
        ),
        ("counters", {}),
    ],
)
def test_research_rejects_invalid_initial_channels(
    context, planned_state, monkeypatch, field, value
):
    planned_state[field] = value

    def forbidden(*args, **kwargs):
        pytest.fail("Research adapter must not run")

    monkeypatch.setattr(
        research, "research_fixture", forbidden
    )

    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        research.research_node(
            planned_state, context
        )

    assert caught.value.category == "security_violation"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("question", "Changed question"),
        ("scope", {"changed": True}),
        ("evidence_ids", ("fabricated",)),
        ("coverage", 1.0),
    ],
)
def test_research_rejects_protected_state_changes(
    context, planned_state, monkeypatch, field, value
):
    planned_state[field] = value

    def forbidden(*args, **kwargs):
        pytest.fail("Research adapter must not run")

    monkeypatch.setattr(
        research, "research_fixture", forbidden
    )

    with pytest.raises(S05StateIntegrityError):
        research.research_node(
            planned_state, context
        )


@pytest.mark.parametrize(
    "missing_count",
    [1, 2, 3, 4],
)
def test_research_preserves_insufficient_fixture_result(
    context, planned_state, missing_count
):
    original_plan = planned_state["plan"]

    questions = tuple(
        ResearchSubquestion(
            subquestion_id=item.subquestion_id,
            question=item.question,
            query=(
                "fixture:unregistered-" + item.subquestion_id
                if index < missing_count
                else item.query
            ),
        )
        for index, item
        in enumerate(original_plan.subquestions)
    )

    planned_state["plan"] = ResearchPlan(
        subquestions=questions,
        assumptions=original_plan.assumptions,
    )

    result = research.research_node(
        planned_state, context
    )

    output = result["research_output"]

    assert len(output.records) == 4 - missing_count
    assert len(output.gaps) == missing_count

    assert result["fixture_coverage"] == (
        (4 - missing_count) / 4
    )

    assert result["stage"] == "researched"

    assert result["counters"].adapter_invocations == 2


@pytest.mark.parametrize(
    "mutation",
    ["none", "mapping", "missing_records", "coverage"],
)
def test_research_rejects_malformed_adapter_output(
    context, planned_state, monkeypatch, mutation
):
    good = adapters.research_fixture(
        context, planned_state["plan"]
    )

    if mutation == "none":
        bad = None

    elif mutation == "mapping":
        bad = good.model_dump()

    elif mutation == "missing_records":
        bad = good.model_copy(
            update={"records": good.records[:-1]}
        )

    else:
        bad = good.model_copy(
            update={"fixture_coverage": 0.25}
        )

    monkeypatch.setattr(
        research,
        "research_fixture",
        lambda ctx, plan: bad,
    )

    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        research.research_node(
            planned_state, context
        )

    assert caught.value.category == "security_violation"


def test_research_sanitizes_adapter_exception(
    context, planned_state, monkeypatch
):
    original = deepcopy(planned_state)
    calls = []

    def failing(adapter_context, adapter_plan):
        calls.append(True)
        raise RuntimeError("private synthetic marker")

    monkeypatch.setattr(
        research, "research_fixture", failing
    )

    with pytest.raises(
        research.S05ResearchError
    ) as caught:
        research.research_node(
            planned_state, context
        )

    assert caught.value.category == "execution_failed"
    assert str(caught.value) == "S05 research failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert len(calls) == 1
    assert planned_state == original


def test_research_rejects_adapter_context_mutation(
    context, planned_state, monkeypatch
):
    good = adapters.research_fixture(
        context, planned_state["plan"]
    )

    def mutate(adapter_context, adapter_plan):
        object.__setattr__(
            adapter_context,
            "question",
            "Unauthorized replacement",
        )

        return good

    monkeypatch.setattr(
        research, "research_fixture", mutate
    )

    with pytest.raises(S05StateIntegrityError):
        research.research_node(
            planned_state, context
        )


def test_research_rejects_adapter_plan_mutation(
    context, planned_state, monkeypatch
):
    good = adapters.research_fixture(
        context, planned_state["plan"]
    )

    def mutate(adapter_context, adapter_plan):
        object.__setattr__(
            adapter_plan.subquestions[0],
            "query",
            "fixture:unauthorized-replacement",
        )

        return good

    monkeypatch.setattr(
        research, "research_fixture", mutate
    )

    with pytest.raises(S05StateIntegrityError):
        research.research_node(
            planned_state, context
        )


def test_research_rejects_post_adapter_state_mutation(
    context, planned_state, monkeypatch
):
    good = adapters.research_fixture(
        context, planned_state["plan"]
    )

    def mutate(adapter_context, adapter_plan):
        planned_state["stage"] = "written"
        return good

    monkeypatch.setattr(
        research, "research_fixture", mutate
    )

    with pytest.raises(S05StateIntegrityError):
        research.research_node(
            planned_state, context
        )


def test_research_returns_independent_output(
    context, planned_state, monkeypatch
):
    original = adapters.research_fixture(
        context, planned_state["plan"]
    )

    monkeypatch.setattr(
        research,
        "research_fixture",
        lambda ctx, plan: original,
    )

    result = research.research_node(
        planned_state, context
    )

    verified = result["research_output"]

    assert verified == original
    assert verified is not original
    assert verified.records[0] is not original.records[0]

    assert (
        verified.records[0].reference
        is not original.records[0].reference
    )
