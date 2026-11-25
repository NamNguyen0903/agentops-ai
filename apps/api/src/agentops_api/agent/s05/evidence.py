"""Offline evidence validation and routing for Sprint S05."""

from typing import Literal

from typing_extensions import TypedDict

from agentops_api.agent.s05.adapters import (
    _validate_research_plan,
    validate_fixture_research_output,
)
from agentops_api.agent.s05.contract import (
    ExecutionCounters,
    ResearchOutput,
    S05GraphState,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
    build_initial_state,
    verify_protected_state,
)

from agentops_api.agent.s05.controller import (
    _verify_stage_accounting,
    _verify_incoming_accounting,
)


class EvidenceUpdate(TypedDict):
    """Only channels owned by Evidence Validation."""

    research_output: ResearchOutput
    fixture_coverage: float
    stage: Literal["evidence_validated"]


EvidenceRoute = Literal["writer", "abstain"]


def _verify_evidence_state(
    state: S05GraphState,
    context: ExecutionContext,
    expected_stage: Literal[
        "researched", "evidence_validated"
    ],
    *, incoming=None,
) -> ResearchOutput:
    """Reconstruct independently verified synthetic evidence.

    Only the normal unrepaired execution path is supported.
    This validation performs no provider or fixture adapter
    invocation and grants no publication authority.
    """

    verify_protected_state(state, context)

    verified_output = None

    try:
        trusted_context = _validated_context_copy(
            context
        )

        initial = build_initial_state(
            trusted_context
        )

        if not _strict_equal(
            state["stage"], expected_stage
        ):
            raise ValueError("invalid evidence stage")

        for name in (
            "draft_report",
            "result",
            "error_category",
        ):
            if not _strict_equal(
                state[name], initial[name]
            ):
                raise ValueError("invalid evidence state")

        if incoming is None:
            _verify_stage_accounting(state, 2)
        else:
            _verify_incoming_accounting(state, incoming)

        plan = _validate_research_plan(
            state["plan"]
        )

        output = validate_fixture_research_output(
            trusted_context,
            plan,
            state["research_output"],
        )

        if not _strict_equal(
            state["fixture_coverage"],
            output.fixture_coverage,
        ):
            raise ValueError("invalid fixture coverage")

        verified_output = output

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if verified_output is None:
        raise S05StateIntegrityError()

    return verified_output


def evidence_validation_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> EvidenceUpdate:
    """Validate Research output before downstream routing."""

    verified = _verify_evidence_state(
        state,
        context,
        "researched",
    )

    return {
        "research_output": verified,
        "fixture_coverage": verified.fixture_coverage,
        "stage": "evidence_validated",
    }


def route_after_evidence(
    state: S05GraphState,
    context: ExecutionContext,
) -> EvidenceRoute:
    """Choose a bounded route from verified synthetic data.

    Revalidate the merged state rather than trusting a
    caller-provided routing flag.

    Invalid evidence raises a safe integrity error.
    Valid incomplete fixtures select abstention.
    """

    verified = _verify_evidence_state(
        state,
        context,
        "evidence_validated",
    )

    if (
        verified.fixture_coverage == 1.0
        and bool(verified.records)
        and not verified.gaps
        and not verified.conflicts
    ):
        return "writer"

    return "abstain"
