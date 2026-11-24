"""Application-owned deterministic fixture with no tools or I/O."""

from agentops_api.agent.contract import GraphState


FIXTURE_CANDIDATE = (
    "Offline fixture executed. No external research or "
    "validated evidence was collected."
)


def single_fixture_agent(state: GraphState) -> dict:
    """Return an unpublished candidate without side effects."""
    return {
        "plan": [],
        "evidence_ids": [],
        "coverage": 0.0,
        "draft_report": None,
        "result": FIXTURE_CANDIDATE,
        "stage": "fixture_complete",
        "repair_used": False,
        "error_category": None,
    }
