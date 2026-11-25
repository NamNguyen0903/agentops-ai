"""Scoped citation integrity and offline extractive writing.

Structural validation does not establish semantic
truth, relevance, or source independence.
"""

from .evidence import (
    validate_scope,
)
from .evidence_validation import (
    validate_assessment,
)
from .workflow_contracts import (
    WORKFLOW_VERSION,
    MAX_CLAIMS,
    MAX_QUESTION_CHARS,
    Citation,
    CitationRejected,
    Claim,
    ReportCandidate,
    validate_claim,
)
from .evidence import normalize_text


def write_candidate(question, assessment, scope):
    scope = validate_scope(scope)

    assessment = validate_assessment(
        assessment,
        scope,
    )

    if not assessment.sufficient_for_fixture:
        raise CitationRejected()

    question = normalize_text(
        question,
        MAX_QUESTION_CHARS,
    )

    claims = tuple(
        Claim(
            text=item.excerpt,
            citations=(
                Citation(
                    evidence_id=item.id,
                    content_hash=item.content_hash,
                ),
            ),
        )
        for item in assessment.records
    )

    candidate = ReportCandidate(
        scope=scope,
        question=question,
        claims=claims,
        workflow_version=WORKFLOW_VERSION,
        synthetic=True,
        publishable=False,
        real_evidence_count=0,
    )

    return validate_candidate(
        candidate,
        assessment=assessment,
        scope=scope,
        question=question,
    )


def validate_candidate(
    candidate,
    *,
    assessment,
    scope,
    question,
):
    if type(candidate) is not ReportCandidate:
        raise CitationRejected()

    try:
        scope = validate_scope(scope)

        assessment = validate_assessment(
            assessment,
            scope,
        )

        if not assessment.sufficient_for_fixture:
            raise CitationRejected()

        question = normalize_text(
            question,
            MAX_QUESTION_CHARS,
        )

        if (
            type(candidate.scope) is not type(scope)
            or validate_scope(candidate.scope) != scope
            or candidate.question != question
            or type(candidate.question) is not str
            or candidate.workflow_version != WORKFLOW_VERSION
            or type(candidate.workflow_version) is not str
            or candidate.synthetic is not True
            or candidate.publishable is not False
            or type(candidate.real_evidence_count) is not int
            or candidate.real_evidence_count != 0
            or type(candidate.claims) is not tuple
            or not 1 <= len(candidate.claims) <= MAX_CLAIMS
        ):
            raise CitationRejected()

        inventory = {
            item.id: item
            for item in assessment.records
        }

        accepted = []
        used = set()

        for original in candidate.claims:
            claim = validate_claim(original)

            # The offline writer is strictly extractive.
            # No generated claim may be passed off as an
            # exact source excerpt.
            if len(claim.citations) != 1:
                raise CitationRejected()

            citation = claim.citations[0]
            evidence = inventory.get(citation.evidence_id)

            if evidence is None:
                raise CitationRejected()

            if citation.content_hash != evidence.content_hash:
                raise CitationRejected()

            if claim.text != evidence.excerpt:
                raise CitationRejected()

            if evidence.id in used:
                raise CitationRejected()

            used.add(evidence.id)
            accepted.append(claim)

        # Do not silently omit approved fixture evidence.
        if used != set(inventory):
            raise CitationRejected()

        return ReportCandidate(
            scope=scope,
            question=question,
            claims=tuple(accepted),
            workflow_version=WORKFLOW_VERSION,
            synthetic=True,
            publishable=False,
            real_evidence_count=0,
        )

    except Exception:
        raise CitationRejected() from None
