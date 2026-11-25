"""Terminal synthetic outcomes for Sprint S05."""

from typing import Literal

from typing_extensions import TypedDict

from agentops_api.agent.s05.contract import (
    ExecutionCounters,
    S05GraphResult,
    S05GraphState,
)
from agentops_api.agent.s05.evidence import (
    _verify_evidence_state,
    route_after_evidence,
)
from agentops_api.agent.s05.report import (
    validate_draft_report,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    verify_protected_state,
)
from agentops_api.agent.s05.writer import (
    _verify_written_state,
)

from agentops_api.agent.s05.controller import (
    _verified_stage_counters,
)


class OutcomeUpdate(TypedDict):
    """Channels owned by terminal Outcome."""

    result: S05GraphResult
    stage: Literal[
        "candidate_ready",
        "insufficient_evidence",
    ]


def outcome_node(
    state: S05GraphState,
    context: ExecutionContext,
) -> OutcomeUpdate:
    """Construct a nonpublishable terminal synthetic result.

    Only the normal unrepaired execution path is supported.

    Invalid state or evidence must fail closed rather than
    becoming an apparently successful abstention.
    """

    verify_protected_state(state, context)

    trusted_context = _validated_context_copy(
        context
    )

    result = None

    try:
        if _strict_equal(
            state["stage"],
            "report_validated",
        ):
            # Reuse the verified written-state boundary
            # through a new mapping. The original state
            # remains unchanged.
            written = {
                **state,
                "stage": "written",
            }

            plan, output = _verify_written_state(
                written,
                trusted_context,
            )

            candidate = validate_draft_report(
                trusted_context,
                plan,
                output,
                state["draft_report"],
            )

            result = S05GraphResult(
                task_id=trusted_context.task_id,
                attempt_id=trusted_context.attempt_id,
                outcome="candidate_ready",
                stage="candidate_ready",
                candidate=candidate,
                evidence_ids=(),
                coverage=0.0,
                fixture_coverage=output.fixture_coverage,
                publishable=False,
                versions=trusted_context.versions,
                counters=_verified_stage_counters(3),
            )

        elif _strict_equal(
            state["stage"],
            "evidence_validated",
        ):
            output = _verify_evidence_state(
                state,
                trusted_context,
                "evidence_validated",
            )

            if route_after_evidence(
                state,
                trusted_context,
            ) != "abstain":
                raise S05StateIntegrityError()

            result = S05GraphResult(
                task_id=trusted_context.task_id,
                attempt_id=trusted_context.attempt_id,
                outcome="insufficient_evidence",
                stage="insufficient_evidence",
                candidate=None,
                evidence_ids=(),
                coverage=0.0,
                fixture_coverage=output.fixture_coverage,
                publishable=False,
                versions=trusted_context.versions,
                counters=_verified_stage_counters(2),
            )

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if result is None:
        raise S05StateIntegrityError()

    return {
        "result": result,
        "stage": result.stage,
    }
