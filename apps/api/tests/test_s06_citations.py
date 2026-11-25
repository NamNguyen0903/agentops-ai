"""Scoped citation integrity and writer tests."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from agentops_api.agent.s06.citations import (
    validate_candidate,
    write_candidate,
)
from agentops_api.agent.s06.evidence_validation import (
    assess_evidence,
)
from agentops_api.agent.s06.workflow_contracts import (
    Citation,
    CitationRejected,
    Claim,
    validate_citation,
    validate_claim,
)

from test_s06_evidence_domain import scope
from test_s06_workflow import QUESTION, snapshot


def fixture():
    context = scope()

    assessment = assess_evidence(
        context,
        snapshot(context),
    )

    candidate = write_candidate(
        QUESTION,
        assessment,
        context,
    )

    return context, assessment, candidate


def verify(context, assessment, candidate):
    return validate_candidate(
        candidate,
        assessment=assessment,
        scope=context,
        question=QUESTION,
    )


def replace_first_claim(candidate, claim):
    return replace(
        candidate,
        claims=(claim, *candidate.claims[1:]),
    )


def test_valid_candidate_round_trip():
    context, assessment, candidate = fixture()

    validated = verify(
        context,
        assessment,
        candidate,
    )

    assert validated == candidate
    assert validated is not candidate


@pytest.mark.parametrize("evidence_id", [
    UUID(int=0),
    uuid4(),
    "fake-id",
    None,
])
def test_unknown_or_invalid_citation(evidence_id):
    context, assessment, candidate = fixture()

    claim = candidate.claims[0]

    forged = replace(
        claim.citations[0],
        evidence_id=evidence_id,
    )

    candidate = replace_first_claim(
        candidate,
        replace(claim, citations=(forged,)),
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, candidate)


@pytest.mark.parametrize("digest", [
    b"x" * 32,
    b"x",
    "fake-hash",
    None,
])
def test_forged_citation_hash(digest):
    context, assessment, candidate = fixture()

    claim = candidate.claims[0]

    citation = replace(
        claim.citations[0],
        content_hash=digest,
    )

    candidate = replace_first_claim(
        candidate,
        replace(claim, citations=(citation,)),
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, candidate)


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "execution_id",
])
def test_cross_scope_citation(field):
    context, assessment, candidate = fixture()

    foreign_scope = replace(
        context,
        **{field: uuid4()},
    )

    foreign = snapshot(foreign_scope)[0]

    claim = Claim(
        text=foreign.excerpt,
        citations=(
            Citation(
                evidence_id=foreign.id,
                content_hash=foreign.content_hash,
            ),
        ),
    )

    forged = replace_first_claim(candidate, claim)

    with pytest.raises(CitationRejected):
        verify(context, assessment, forged)


def test_missing_snapshot_reference_rejected():
    context, assessment, candidate = fixture()

    updated = assess_evidence(
        context,
        snapshot(context, 3)[1:],
    )

    with pytest.raises(CitationRejected):
        verify(context, updated, candidate)


def test_unsupported_claim_rejected():
    context, assessment, candidate = fixture()

    claim = replace(
        candidate.claims[0],
        text="Unsupported competitor revenue claim",
    )

    with pytest.raises(CitationRejected):
        verify(
            context,
            assessment,
            replace_first_claim(candidate, claim),
        )


def test_claim_cannot_reference_different_excerpt():
    context, assessment, candidate = fixture()

    claim = replace(
        candidate.claims[0],
        citations=candidate.claims[1].citations,
    )

    with pytest.raises(CitationRejected):
        verify(
            context,
            assessment,
            replace_first_claim(candidate, claim),
        )


def test_omitted_evidence_rejected():
    context, assessment, candidate = fixture()

    forged = replace(
        candidate,
        claims=candidate.claims[:1],
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, forged)


def test_repeated_claim_rejected():
    context, assessment, candidate = fixture()

    forged = replace(
        candidate,
        claims=(candidate.claims[0],) * 2,
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, forged)


@pytest.mark.parametrize("field,value", [
    ("publishable", True),
    ("publishable", 0),
    ("synthetic", False),
    ("synthetic", 1),
    ("real_evidence_count", 1),
    ("real_evidence_count", False),
    ("workflow_version", "unknown"),
    ("question", "Different question"),
    ("claims", ()),
])
def test_forged_candidate_fields(field, value):
    context, assessment, candidate = fixture()

    forged = replace(
        candidate,
        **{field: value},
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, forged)


def test_candidate_scope_mismatch():
    context, assessment, candidate = fixture()

    forged = replace(
        candidate,
        scope=scope(),
    )

    with pytest.raises(CitationRejected):
        verify(context, assessment, forged)


def test_writer_denied_insufficient_evidence():
    context = scope()

    assessment = assess_evidence(
        context,
        snapshot(context, 1),
    )

    with pytest.raises(CitationRejected):
        write_candidate(
            QUESTION,
            assessment,
            context,
        )


def test_duplicate_citation_rejected():
    citation = Citation(
        evidence_id=uuid4(),
        content_hash=b"x" * 32,
    )

    with pytest.raises(CitationRejected):
        validate_claim(
            Claim(
                text="Synthetic excerpt",
                citations=(citation, citation),
            )
        )


@pytest.mark.parametrize("text", [
    "",
    " ",
    "x" * 4097,
    123,
    "  not normalized  ",
])
def test_invalid_claim_text(text):
    citation = Citation(
        evidence_id=uuid4(),
        content_hash=b"x" * 32,
    )

    with pytest.raises(CitationRejected):
        validate_claim(
            Claim(
                text=text,
                citations=(citation,),
            )
        )


def test_citation_mapping_rejected():
    with pytest.raises(CitationRejected):
        validate_citation({
            "evidence_id": uuid4(),
            "content_hash": b"x" * 32,
        })


def test_multiple_citations_not_allowed_in_extractive_candidate():
    context, assessment, candidate = fixture()

    claim = replace(
        candidate.claims[0],
        citations=(
            candidate.claims[0].citations[0],
            candidate.claims[1].citations[0],
        ),
    )

    with pytest.raises(CitationRejected):
        verify(
            context,
            assessment,
            replace_first_claim(candidate, claim),
        )
