"""Single-node LangGraph execution; no API or database integration."""

from langgraph.graph import END, START, StateGraph

from agentops_api.agent.contract import (
    GraphInput,
    GraphResult,
    GraphState,
)
from agentops_api.agent.fixture import single_fixture_agent


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("single_fixture_agent", single_fixture_agent)
    graph.add_edge(START, "single_fixture_agent")
    graph.add_edge("single_fixture_agent", END)
    return graph.compile()


def run_offline_graph(request: GraphInput) -> GraphResult:
    """Run an offline graph and return a non-publishable proposal."""
    initial: GraphState = {
        "task_id": str(request.task_id),
        "attempt_id": (
            str(request.attempt_id)
            if request.attempt_id is not None else None
        ),
        "question": request.question,
        "scope": request.scope,
        "plan": [],
        "evidence_ids": [],
        "coverage": 0.0,
        "draft_report": None,
        "result": None,
        "stage": "pending",
        "repair_used": False,
        "budget_snapshot": request.budget.model_dump(),
        "error_category": None,
        "versions": request.versions.model_dump(),
    }

    graph = build_graph()
    result = graph.invoke(
        initial,
        config={"recursion_limit": request.budget.max_steps},
    )

    # Validate the returned candidate; no lifecycle/publication writes.
    return GraphResult.model_validate({
        "task_id": request.task_id,
        "attempt_id": request.attempt_id,
        "outcome": "insufficient_evidence",
        "stage": result["stage"],
        "candidate": result["result"],
        "evidence_ids": result["evidence_ids"],
        "coverage": result["coverage"],
        "publishable": False,
        "error_category": result["error_category"],
        "versions": request.versions,
    })
