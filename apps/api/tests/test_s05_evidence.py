"""Evidence validation and abstention routing tests."""

from copy import deepcopy
from itertools import product
from uuid import UUID

import pytest

from agentops_api.agent.s05 import (
    adapters,
    evidence,
    planner,
    research,
)
from agentops_api.agent.s05.contract import (
    ExecutionCounters,
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
            task_id=UUID(int=301),
            attempt_id=UUID(int=302),
            question="Compare synthetic market fixtures.",
            scope={"market": {"region": "offline"}},
        )
    )


def _researched_state(
    context,
    missing=(False, False, False, False),
):
    initial = build_initial_state(context)

    planned = {
        **initial,
        **planner.planner_node(initial, context),
    }

    original_plan = planned["plan"]

    planned["plan"] = ResearchPlan(
        subquestions=tuple(
            ResearchSubquestion(
                subquestion_id=item.subquestion_id,
                question=item.question,
                query=(
                    "fixture:unregistered-" + item.subquestion_id
                    if missing[index]
                    else item.query
                ),
            )
            for index, item in enumerate(
                original_plan.subquestions
            )
        ),
        assumptions=original_plan.assumptions,
    )

    return {
        **planned,
        **research.research_node(planned, context),
    }


@pytest.fixture
def researched_state(context):
    return _researched_state(context)


def test_evidence_returns_only_owned_channels(
    context, researched_state
):
    original = deepcopy(researched_state)

    update = evidence.evidence_validation_node(
        researched_state, context
    )

    assert set(update) == {
        "research_output",
        "fixture_coverage",
        "stage",
    }

    assert update["stage"] == "evidence_validated"
    assert update["fixture_coverage"] == 1.0
    assert researched_state == original

    merged = {
        **researched_state,
        **update,
    }

    verify_protected_state(merged, context)

    assert merged["evidence_ids"] == ()
    assert merged["coverage"] == 0.0
    assert merged["draft_report"] is None
    assert merged["result"] is None

    assert merged["counters"] == ExecutionCounters(
        adapter_invocations=2
    )

    assert evidence.route_after_evidence(
        merged, context
    ) == "writer"


@pytest.mark.parametrize(
    "missing",
    tuple(product((False, True), repeat=4)),
)
def test_evidence_all_fixture_availability_masks(
    context, missing
):
    state = _researched_state(context, missing)

    before = deepcopy(state)

    update = evidence.evidence_validation_node(
        state, context
    )

    merged = {**state, **update}

    matched = 4 - sum(missing)

    assert update["fixture_coverage"] == matched / 4

    assert len(
        update["research_output"].records
    ) == matched

    assert len(
        update["research_output"].gaps
    ) == sum(missing)

    expected = "writer" if matched == 4 else "abstain"

    assert evidence.route_after_evidence(
        merged, context
    ) == expected

    assert state == before
    assert merged["counters"].adapter_invocations == 2
    assert merged["evidence_ids"] == ()
    assert merged["coverage"] == 0.0


def test_evidence_calls_no_adapters(
    context, researched_state, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Validation must not invoke adapters")

    for module, names in (
        (
            adapters,
            (
                "plan_fixture",
                "research_fixture",
                "writer_fixture",
            ),
        ),
        (planner, ("plan_fixture",)),
        (research, ("research_fixture",)),
    ):
        for name in names:
            monkeypatch.setattr(
                module, name, forbidden
            )

    update = evidence.evidence_validation_node(
        researched_state, context
    )

    merged = {**researched_state, **update}

    assert evidence.route_after_evidence(
        merged, context
    ) == "writer"

    assert merged["counters"].adapter_invocations == 2


def test_evidence_returns_independent_output(
    context, researched_state
):
    original = researched_state["research_output"]

    update = evidence.evidence_validation_node(
        researched_state, context
    )

    checked = update["research_output"]

    assert checked == original
    assert checked is not original
    assert checked.records[0] is not original.records[0]

    assert (
        checked.records[0].reference
        is not original.records[0].reference
    )


def _assert_integrity_error(operation):
    with pytest.raises(
        S05StateIntegrityError
    ) as caught:
        operation()

    assert caught.value.category == "security_violation"

    assert str(caught.value) == (
        "invalid S05 protected state"
    )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "pending"),
        ("stage", "planned"),
        ("stage", "written"),
        ("stage", None),
        ("plan", None),
        ("plan", {}),
        ("research_output", None),
        ("research_output", {}),
        ("fixture_coverage", 0.25),
        ("fixture_coverage", 1),
        ("fixture_coverage", True),
        ("fixture_coverage", float("nan")),
        ("draft_report", {}),
        ("result", {}),
        ("repair_used", True),
        ("repair_used", 0),
        ("error_category", "execution_failed"),
        ("counters", ExecutionCounters()),
        (
            "counters",
            ExecutionCounters(adapter_invocations=1),
        ),
        (
            "counters",
            ExecutionCounters(adapter_invocations=3),
        ),
        (
            "counters",
            ExecutionCounters(
                adapter_invocations=2,
            ).model_copy(
                update={"adapter_invocations": 2.0}
            ),
        ),
        ("counters", {}),
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("question", "Changed question"),
        ("scope", {"changed": True}),
        ("evidence_ids", ("fabricated",)),
        ("coverage", 1.0),
    ],
)
def test_evidence_rejects_invalid_state(
    context, researched_state, field, value
):
    researched_state[field] = value

    _assert_integrity_error(
        lambda: evidence.evidence_validation_node(
            researched_state, context
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_reference",
        "cross_task",
        "cross_attempt",
        "wrong_fixture_version",
        "wrong_source",
        "changed_content",
        "missing_record",
        "duplicate_record",
        "wrong_coverage",
        "fabricated_gap",
        "fabricated_conflict",
    ],
)
def test_evidence_rejects_tampered_research_output(
    context, researched_state, mutation
):
    output = researched_state["research_output"]

    record = output.records[0]
    reference = record.reference

    reference_updates = {
        "unknown_reference": {
            "fixture_id": "fixture-fabricated",
        },
        "cross_task": {
            "task_id": UUID(int=999),
        },
        "cross_attempt": {
            "attempt_id": UUID(int=999),
        },
        "wrong_fixture_version": {
            "fixture_version": "unapproved-version",
        },
        "wrong_source": {
            "source": "unapproved-source",
        },
    }

    if mutation in reference_updates:
        # Mutate one field in a valid reference.
        changed_reference = reference.model_copy(
            update=reference_updates[mutation]
        )

        changed_record = record.model_copy(
            update={"reference": changed_reference}
        )

        changed = output.model_copy(
            update={
                "records": (
                    changed_record,
                ) + output.records[1:]
            }
        )

    elif mutation == "changed_content":
        changed_record = record.model_copy(
            update={"content": "Fabricated content"}
        )

        changed = output.model_copy(
            update={
                "records": (
                    changed_record,
                ) + output.records[1:]
            }
        )

    elif mutation == "missing_record":
        changed = output.model_copy(
            update={"records": output.records[:-1]}
        )

    elif mutation == "duplicate_record":
        changed = output.model_copy(
            update={
                "records": (
                    output.records[0],
                    output.records[0],
                ) + output.records[2:]
            }
        )

    elif mutation == "wrong_coverage":
        changed = output.model_copy(
            update={"fixture_coverage": 0.25}
        )

    elif mutation == "fabricated_gap":
        changed = output.model_copy(
            update={"gaps": ("Fabricated gap",)}
        )

    else:
        changed = output.model_copy(
            update={"conflicts": ("Fabricated conflict",)}
        )

    researched_state["research_output"] = changed

    _assert_integrity_error(
        lambda: evidence.evidence_validation_node(
            researched_state, context
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_stage",
        "changed_coverage",
        "fabricated_evidence",
        "missing_output",
        "changed_counters",
        "changed_task",
    ],
)
def test_router_revalidates_merged_state(
    context, researched_state, mutation
):
    update = evidence.evidence_validation_node(
        researched_state, context
    )

    merged = {**researched_state, **update}

    assert evidence.route_after_evidence(
        merged, context
    ) == "writer"

    if mutation == "wrong_stage":
        merged["stage"] = "researched"

    elif mutation == "changed_coverage":
        merged["fixture_coverage"] = 0.0

    elif mutation == "fabricated_evidence":
        merged["evidence_ids"] = ("fabricated",)

    elif mutation == "missing_output":
        merged["research_output"] = None

    elif mutation == "changed_counters":
        merged["counters"] = ExecutionCounters(
            adapter_invocations=3
        )

    else:
        merged["task_id"] = str(UUID(int=999))

    _assert_integrity_error(
        lambda: evidence.route_after_evidence(
            merged, context
        )
    )


def test_invalid_evidence_is_not_abstention(
    context
):
    state = _researched_state(
        context,
        (True, True, True, True),
    )

    update = evidence.evidence_validation_node(
        state, context
    )

    merged = {**state, **update}

    assert evidence.route_after_evidence(
        merged, context
    ) == "abstain"

    merged["research_output"] = (
        merged["research_output"].model_copy(
            update={"fixture_coverage": 1.0}
        )
    )

    _assert_integrity_error(
        lambda: evidence.route_after_evidence(
            merged, context
        )
    )
