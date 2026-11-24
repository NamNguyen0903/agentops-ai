"""S04-WP03 application-boundary deadline tests."""

from uuid import uuid4

import pytest

from agentops_api.agent import workflow
from agentops_api.agent.contract import GraphInput


def make_request():
    return GraphInput(
        task_id=uuid4(),
        question="Offline deadline test",
    )


def test_expired_deadline_prevents_graph_execution(monkeypatch):
    invoked = []

    class FakeGraph:
        def invoke(self, initial, config=None):
            invoked.append(True)
            raise AssertionError("graph must not execute")

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: FakeGraph(),
    )
    monkeypatch.setattr(
        workflow.time,
        "monotonic",
        lambda: 101.0,
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(
            make_request(),
            deadline_monotonic=100.0,
        )

    assert caught.value.category == "deadline_exceeded"
    assert invoked == []


def test_result_after_deadline_is_rejected(monkeypatch):
    clock = {"now": 99.0}
    invoked = []

    class LateGraph:
        def invoke(self, initial, config=None):
            invoked.append(True)
            clock["now"] = 101.0
            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: LateGraph(),
    )
    monkeypatch.setattr(
        workflow.time,
        "monotonic",
        lambda: clock["now"],
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(
            make_request(),
            deadline_monotonic=100.0,
        )

    assert caught.value.category == "deadline_exceeded"
    assert invoked == [True]


@pytest.mark.parametrize(
    "deadline",
    [float("nan"), float("inf"), float("-inf")],
)
def test_nonfinite_deadline_is_rejected(deadline):
    with pytest.raises(ValueError):
        workflow.run_offline_graph(
            make_request(),
            deadline_monotonic=deadline,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_steps", 0),
        ("max_steps", 5),
        ("model_calls", 1),
        ("searches", 1),
        ("retrievals", 1),
        ("tokens", 1),
        ("cost_usd", 1),
    ],
)
def test_reject_invalid_budget(field, value):
    from pydantic import ValidationError
    from agentops_api.agent.contract import BudgetSnapshot

    with pytest.raises(ValidationError):
        BudgetSnapshot(**{field: value})


def test_valid_budget_defaults():
    from agentops_api.agent.contract import BudgetSnapshot

    budget = BudgetSnapshot()

    assert budget.max_steps == 4
    assert budget.model_calls == 0
    assert budget.searches == 0
    assert budget.retrievals == 0
    assert budget.tokens == 0
    assert budget.cost_usd == 0


def test_graph_receives_configured_step_limit(monkeypatch):
    from agentops_api.agent.contract import BudgetSnapshot

    received = []

    class FakeGraph:
        def invoke(self, initial, config=None):
            received.append(config)
            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: FakeGraph(),
    )

    request = GraphInput(
        task_id=uuid4(),
        question="Offline step-limit test",
        budget=BudgetSnapshot(max_steps=3),
    )

    result = workflow.run_offline_graph(request)

    assert received == [{"recursion_limit": 3}]
    assert result.publishable is False


def test_actual_langgraph_rejects_one_step():
    from agentops_api.agent.contract import BudgetSnapshot

    request = GraphInput(
        task_id=uuid4(),
        question="Offline one-step limit",
        budget=BudgetSnapshot(max_steps=1),
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(request)

    assert caught.value.category == "execution_failed"


def test_actual_langgraph_accepts_two_steps():
    from agentops_api.agent.contract import BudgetSnapshot

    request = GraphInput(
        task_id=uuid4(),
        question="Offline two-step limit",
        budget=BudgetSnapshot(max_steps=2),
    )

    result = workflow.run_offline_graph(request)

    assert result.stage == "fixture_complete"
    assert result.outcome == "insufficient_evidence"
    assert result.publishable is False
    assert result.evidence_ids == []


def test_default_deadline_rejects_late_result(monkeypatch):
    clock = {"now": 100.0}
    invoked = []

    class SlowGraph:
        def invoke(self, initial, config=None):
            invoked.append(True)
            clock["now"] = 131.0
            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: SlowGraph(),
    )
    monkeypatch.setattr(
        workflow.time,
        "monotonic",
        lambda: clock["now"],
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(make_request())

    assert invoked == [True]
    assert caught.value.category == "deadline_exceeded"


def test_caller_cannot_extend_default_deadline(monkeypatch):
    clock = {"now": 100.0}

    class SlowGraph:
        def invoke(self, initial, config=None):
            clock["now"] = 131.0
            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: SlowGraph(),
    )
    monkeypatch.setattr(
        workflow.time,
        "monotonic",
        lambda: clock["now"],
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(
            make_request(),
            deadline_monotonic=1_000_000.0,
        )

    assert caught.value.category == "deadline_exceeded"
