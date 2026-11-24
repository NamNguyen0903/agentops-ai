"""Single-node LangGraph execution; no API or database integration."""

import copy
import math
import time

from langgraph.graph import END, START, StateGraph

from agentops_api.agent.contract import (
    GraphInput,
    GraphResult,
    GraphState,
)
from agentops_api.agent.fixture import (
    single_fixture_agent,
)


S04_MAX_RUNTIME_SECONDS = 30.0


class GraphExecutionError(ValueError):
    """Safe, categorized offline graph boundary failure."""

    MESSAGES = {
        "execution_failed": "offline graph execution failed",
        "invalid_output": "invalid offline graph output",
        "deadline_exceeded": "offline graph deadline exceeded",
    }

    def __init__(self, category: str):
        if category not in self.MESSAGES:
            raise ValueError("unsupported graph error category")

        self.category = category
        super().__init__(self.MESSAGES[category])


def _strict_state_equal(actual, expected) -> bool:
    """Compare the complete offline state without type coercion."""
    if type(actual) is not type(expected):
        return False

    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            return False
        return all(
            _strict_state_equal(actual[key], value)
            for key, value in expected.items()
        )

    if isinstance(expected, list):
        if len(actual) != len(expected):
            return False
        return all(
            _strict_state_equal(left, right)
            for left, right in zip(actual, expected)
        )

    return actual == expected


def _validate_offline_state(
    actual: object,
    initial: GraphState,
) -> GraphState:
    """Fail closed if fixture output differs from the approved state."""
    expected = dict(initial)
    expected.update(single_fixture_agent(initial))

    if not _strict_state_equal(actual, expected):
        raise ValueError("invalid offline graph output")

    return expected


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("single_fixture_agent", single_fixture_agent)
    graph.add_edge(START, "single_fixture_agent")
    graph.add_edge("single_fixture_agent", END)
    return graph.compile()


def run_offline_graph(
    request: GraphInput,
    *,
    deadline_monotonic: float | None = None,
) -> GraphResult:
    """Run an offline graph and return a non-publishable proposal."""
    # Pydantic models may contain mutable nested dictionaries.
    # Revalidate and snapshot request data at execution entry.
    validated_request = GraphInput.model_validate(
        request.model_dump(mode="python")
    )

    if not request.scope_matches_snapshot():
        raise ValueError("scope changed after validation")

    request = validated_request

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

    if deadline_monotonic is not None:
        if (
            isinstance(deadline_monotonic, bool)
            or not isinstance(deadline_monotonic, (int, float))
            or not math.isfinite(deadline_monotonic)
        ):
            raise ValueError("invalid graph deadline")

    started_at = time.monotonic()
    local_deadline = started_at + S04_MAX_RUNTIME_SECONDS

    effective_deadline = (
        min(local_deadline, deadline_monotonic)
        if deadline_monotonic is not None
        else local_deadline
    )

    if started_at >= effective_deadline:
        raise GraphExecutionError("deadline_exceeded")

    # Keep validation evidence independent from node-owned state.
    expected_initial = copy.deepcopy(initial)
    graph_input = copy.deepcopy(initial)

    try:
        graph = build_graph()
        result = graph.invoke(
            graph_input,
            config={"recursion_limit": request.budget.max_steps},
        )
    except Exception:
        # Never expose provider, environment or internal exception text.
        raise GraphExecutionError("execution_failed") from None

    if time.monotonic() >= effective_deadline:
        raise GraphExecutionError("deadline_exceeded")

    try:
        # Reject missing, unexpected or mutated graph state fields.
        result = _validate_offline_state(result, expected_initial)

        # Only application-validated values become a result proposal.
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
    except Exception:
        raise GraphExecutionError("invalid_output") from None
