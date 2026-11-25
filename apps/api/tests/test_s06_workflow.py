"""S06 offline workflow verification."""

from dataclasses import replace
from uuid import uuid4

import pytest

from agentops_api.agent.s06.evidence_validation import (
    assess_evidence,
    validate_assessment,
)
from agentops_api.agent.s06.workflow_contracts import (
    WORKFLOW_VERSION,
    WorkflowInput,
    WorkflowRejected,
)
from agentops_api.agent.s06.workflow import (
    run_offline,
)

from test_s06_evidence_domain import (
    scope,
    record,
    page,
)


QUESTION = "Synthetic competitor research"


def snapshot(context, count=2):
    return tuple(
        record(
            context,
            page=page(
                source_url=f"https://example.com/source-{i}",
                retrieved_url=f"https://example.com/source-{i}",
                body=f"Synthetic evidence {i}".encode(),
            ),
        )
        for i in range(count)
    )


def request(context, count=2):
    return WorkflowInput(
        scope=context,
        question=QUESTION,
        evidence=snapshot(context, count),
    )


@pytest.mark.parametrize("count", [0, 1])
def test_insufficient_fixture_evidence(count):
    outcome = run_offline(
        request(scope(), count)
    )

    assert outcome.status == "insufficient_evidence"
    assert outcome.candidate is None
    assert outcome.publishable is False
    assert outcome.real_evidence_count == 0
    assert outcome.synthetic_evidence_count == count


@pytest.mark.parametrize("count", [2, 3, 20])
def test_valid_fixture_workflow(count):
    context = scope()
    value = request(context, count)

    outcome = run_offline(value)

    assert outcome.status == "synthetic_candidate"
    assert outcome.workflow_version == WORKFLOW_VERSION
    assert outcome.publishable is False
    assert outcome.real_evidence_count == 0
    assert outcome.synthetic_evidence_count == count

    candidate = outcome.candidate

    assert candidate.scope == context
    assert candidate.question == QUESTION
    assert candidate.synthetic is True
    assert candidate.publishable is False
    assert len(candidate.claims) == count

    for claim, evidence in zip(
        candidate.claims,
        value.evidence,
    ):
        assert claim.text == evidence.excerpt
        assert len(claim.citations) == 1

        citation = claim.citations[0]

        assert citation.evidence_id == evidence.id
        assert citation.content_hash == evidence.content_hash


def test_workflow_deterministic():
    value = request(scope())

    assert run_offline(value) == run_offline(value)


def test_repeated_evidence_not_distinct_sources():
    context = scope()
    value = record(context)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=(value, value),
        )
    )

    assert outcome.status == "insufficient_evidence"
    assert outcome.synthetic_evidence_count == 1


def test_same_page_multiple_excerpts_not_distinct_sources():
    context = scope()

    records = (
        record(
            context,
            page=page(body=b"First excerpt"),
        ),
        record(
            context,
            page=page(body=b"Second excerpt"),
        ),
    )

    assessment = assess_evidence(
        context,
        records,
    )

    assert assessment.distinct_source_count == 1
    assert assessment.synthetic_evidence_count == 2
    assert assessment.sufficient_for_fixture is False


def test_redirect_aliases_not_distinct_sources():
    context = scope()

    records = tuple(
        record(
            context,
            page=page(
                source_url=f"https://example.org/alias-{i}",
                retrieved_url="https://example.com/final",
            ),
        )
        for i in range(2)
    )

    assessment = assess_evidence(
        context,
        records,
    )

    assert assessment.distinct_source_count == 1
    assert assessment.sufficient_for_fixture is False


def test_synthetic_never_real_coverage():
    context = scope()

    assessment = assess_evidence(
        context,
        snapshot(context, 20),
    )

    assert assessment.sufficient_for_fixture
    assert assessment.real_evidence_count == 0
    assert not assessment.sufficient_for_real_report


@pytest.mark.parametrize("question", [
    "",
    " ",
    "x" * 4001,
    123,
    True,
    "question" + chr(0),
])
def test_invalid_question(question):
    value = replace(
        request(scope()),
        question=question,
    )

    with pytest.raises(WorkflowRejected):
        run_offline(value)


@pytest.mark.parametrize("field", [
    "owner_id",
    "task_id",
    "execution_id",
])
def test_cross_scope_snapshot_rejected(field):
    context = scope()

    another = replace(
        context,
        **{field: uuid4()},
    )

    value = replace(
        request(context),
        evidence=(
            record(context),
            record(another),
        ),
    )

    with pytest.raises(WorkflowRejected):
        run_offline(value)


def test_evidence_snapshot_limit():
    value = request(scope(), 21)

    with pytest.raises(WorkflowRejected):
        run_offline(value)


def test_mapping_input_rejected():
    with pytest.raises(WorkflowRejected):
        run_offline({
            "question": QUESTION,
            "scope": scope(),
            "evidence": (),
        })


def test_list_snapshot_rejected():
    value = request(scope())

    value = replace(
        value,
        evidence=list(value.evidence),
    )

    with pytest.raises(WorkflowRejected):
        run_offline(value)


@pytest.mark.parametrize("field,value", [
    ("real_evidence_count", 1),
    ("distinct_source_count", True),
    ("synthetic_evidence_count", 999),
    ("sufficient_for_real_report", True),
    ("sufficient_for_fixture", 1),
])
def test_forged_assessment_rejected(field, value):
    context = scope()

    assessment = assess_evidence(
        context,
        snapshot(context),
    )

    forged = replace(
        assessment,
        **{field: value},
    )

    with pytest.raises(WorkflowRejected):
        validate_assessment(forged, context)
