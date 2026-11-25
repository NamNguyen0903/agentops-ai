"""S06 versioned offline evidence workflow.

No provider, database, worker, persistent checkpoint,
model inference, or publication operations.
"""

from typing import TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from .citations import (
    validate_candidate,
    write_candidate,
)
from .evidence_validation import (
    EvidenceAssessment,
    assess_evidence,
)
from .workflow_contracts import (
    WORKFLOW_VERSION,
    ReportCandidate,
    WorkflowInput,
    WorkflowOutcome,
    WorkflowRejected,
    validate_input,
)


RECURSION_LIMIT = 12


class WorkflowState(TypedDict, total=False):
    request: WorkflowInput
    assessment: EvidenceAssessment
    candidate: ReportCandidate
    outcome: WorkflowOutcome


def assess_node(state):
    request = validate_input(state["request"])

    return {
        "request": request,
        "assessment": assess_evidence(
            request.scope,
            request.evidence,
        ),
    }


def choose_after_assessment(state):
    assessment = state["assessment"]

    if assessment.sufficient_for_fixture:
        return "write"

    return "insufficient"


def insufficient_node(state):
    assessment = state["assessment"]

    return {
        "outcome": WorkflowOutcome(
            status="insufficient_evidence",
            workflow_version=WORKFLOW_VERSION,
            candidate=None,
            reason="insufficient_fixture_sources",
            real_evidence_count=0,
            synthetic_evidence_count=(
                assessment.synthetic_evidence_count
            ),
            publishable=False,
        )
    }


def writer_node(state):
    request = state["request"]

    return {
        "candidate": write_candidate(
            request.question,
            state["assessment"],
            request.scope,
        )
    }


def citation_node(state):
    request = state["request"]
    assessment = state["assessment"]

    candidate = validate_candidate(
        state["candidate"],
        assessment=assessment,
        scope=request.scope,
        question=request.question,
    )

    return {
        "outcome": WorkflowOutcome(
            status="synthetic_candidate",
            workflow_version=WORKFLOW_VERSION,
            candidate=candidate,
            reason=None,
            real_evidence_count=0,
            synthetic_evidence_count=(
                assessment.synthetic_evidence_count
            ),
            publishable=False,
        )
    }


def _build_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("assess", assess_node)
    graph.add_node("write", writer_node)
    graph.add_node("citations", citation_node)
    graph.add_node("insufficient", insufficient_node)

    graph.add_edge(START, "assess")

    graph.add_conditional_edges(
        "assess",
        choose_after_assessment,
        {
            "write": "write",
            "insufficient": "insufficient",
        },
    )

    graph.add_edge("write", "citations")
    graph.add_edge("citations", END)
    graph.add_edge("insufficient", END)

    return graph.compile()


def run_offline(request):
    request = validate_input(request)

    try:
        # No caller-controlled graph config, callbacks,
        # recursion setting, checkpointer or tools.
        result = _build_graph().invoke(
            {"request": request},
            config={
                "recursion_limit": RECURSION_LIMIT,
            },
        )

        outcome = result["outcome"]

        if type(outcome) is not WorkflowOutcome:
            raise WorkflowRejected()

        if (
            outcome.publishable is not False
            or type(outcome.real_evidence_count) is not int
            or outcome.real_evidence_count != 0
            or outcome.workflow_version != WORKFLOW_VERSION
        ):
            raise WorkflowRejected()

        if outcome.status == "synthetic_candidate":
            # Revalidate against the original input snapshot,
            # not exclusively graph-produced intermediate state.
            assessment = assess_evidence(
                request.scope,
                request.evidence,
            )

            candidate = validate_candidate(
                outcome.candidate,
                assessment=assessment,
                scope=request.scope,
                question=request.question,
            )

            return WorkflowOutcome(
                status="synthetic_candidate",
                workflow_version=WORKFLOW_VERSION,
                candidate=candidate,
                reason=None,
                real_evidence_count=0,
                synthetic_evidence_count=(
                    assessment.synthetic_evidence_count
                ),
                publishable=False,
            )

        if outcome.status != "insufficient_evidence":
            raise WorkflowRejected()

        assessment = assess_evidence(
            request.scope,
            request.evidence,
        )

        if (
            assessment.sufficient_for_fixture
            or outcome.candidate is not None
        ):
            raise WorkflowRejected()

        return WorkflowOutcome(
            status="insufficient_evidence",
            workflow_version=WORKFLOW_VERSION,
            candidate=None,
            reason="insufficient_fixture_sources",
            real_evidence_count=0,
            synthetic_evidence_count=(
                assessment.synthetic_evidence_count
            ),
            publishable=False,
        )

    except Exception:
        raise WorkflowRejected() from None
