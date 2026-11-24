"""S04-WP03 output validation negative tests."""

from uuid import uuid4

import pytest

from agentops_api.agent.contract import GraphInput
from agentops_api.agent import workflow


def make_request():
    return GraphInput(
        task_id=uuid4(),
        question="Offline research only",
    )


def inject_graph(monkeypatch, changes):
    """Simulate an untrusted graph result without network or DB."""

    class MaliciousGraph:
        def invoke(self, initial, config=None):
            state = dict(initial)
            state.update({
                "plan": [],
                "evidence_ids": [],
                "coverage": 0.0,
                "draft_report": None,
                "result": "Offline fixture candidate",
                "stage": "fixture_complete",
                "repair_used": False,
                "error_category": None,
            })
            state.update(changes)
            return state

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: MaliciousGraph(),
    )


def test_reject_fabricated_evidence(monkeypatch):
    inject_graph(
        monkeypatch,
        {"evidence_ids": ["invented-source-001"]},
    )

    with pytest.raises(ValueError):
        workflow.run_offline_graph(make_request())


def test_reject_unexpected_tool_permissions(monkeypatch):
    inject_graph(
        monkeypatch,
        {"allowed_tools": ["external_network"]},
    )

    with pytest.raises(ValueError):
        workflow.run_offline_graph(make_request())


def test_reject_graph_publication_claim(monkeypatch):
    inject_graph(
        monkeypatch,
        {"publishable": True},
    )

    with pytest.raises(ValueError):
        workflow.run_offline_graph(make_request())


@pytest.mark.parametrize(
    "changes",
    [
        {"task_id": "00000000-0000-0000-0000-000000000000"},
        {"attempt_id": "unauthorized-attempt"},
        {"versions": {"graph": "unapproved-graph"}},
        {"budget_snapshot": {"max_steps": 999}},
        {"stage": "published"},
        {"coverage": True},
        {"evidence_ids": "not-a-list"},
        {"draft_report": "fabricated report"},
        {"repair_used": True},
    ],
)
def test_reject_mutated_graph_state(monkeypatch, changes):
    inject_graph(monkeypatch, changes)

    with pytest.raises(
        ValueError,
        match="invalid offline graph output",
    ):
        workflow.run_offline_graph(make_request())


def test_reject_missing_graph_state_field(monkeypatch):
    class MissingFieldGraph:
        def invoke(self, initial, config=None):
            state = dict(initial)
            state.update({
                "plan": [],
                "evidence_ids": [],
                "coverage": 0.0,
                "draft_report": None,
                "result": "Offline fixture candidate",
                "stage": "fixture_complete",
                "repair_used": False,
                "error_category": None,
            })
            del state["versions"]
            return state

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: MissingFieldGraph(),
    )

    with pytest.raises(
        ValueError,
        match="invalid offline graph output",
    ):
        workflow.run_offline_graph(make_request())


def test_reject_graph_mutation_of_input_scope(monkeypatch):
    class MutatingGraph:
        def invoke(self, initial, config=None):
            # An untrusted node changes application-owned input.
            initial["scope"]["filters"]["region"] = "UNAPPROVED"

            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: MutatingGraph(),
    )

    request = GraphInput(
        task_id=uuid4(),
        question="Offline graph state integrity",
        scope={"filters": {"region": "VN"}},
    )

    with pytest.raises(
        workflow.GraphExecutionError,
    ) as caught:
        workflow.run_offline_graph(request)

    assert caught.value.category == "invalid_output"
    assert str(caught.value) == "invalid offline graph output"


@pytest.mark.parametrize(
    "field,key,value",
    [
        ("budget_snapshot", "max_steps", 999),
        ("versions", "graph", "UNAPPROVED_VERSION"),
    ],
)
def test_reject_graph_mutation_of_budget_or_versions(
    monkeypatch,
    field,
    key,
    value,
):
    class MutatingGraph:
        def invoke(self, initial, config=None):
            initial[field][key] = value

            return {
                **initial,
                **workflow.single_fixture_agent(initial),
            }

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: MutatingGraph(),
    )

    request = GraphInput(
        task_id=uuid4(),
        question="Offline nested state integrity",
    )

    with pytest.raises(
        workflow.GraphExecutionError,
    ) as caught:
        workflow.run_offline_graph(request)

    assert caught.value.category == "invalid_output"
    assert str(caught.value) == "invalid offline graph output"
