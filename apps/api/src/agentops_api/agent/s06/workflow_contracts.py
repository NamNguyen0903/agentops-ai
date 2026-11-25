"""S06 versioned offline workflow contracts."""

from dataclasses import dataclass
from uuid import UUID

from .evidence import (
    EvidenceRecord,
    EvidenceScope,
    normalize_text,
    validate_scope,
    valid_uuid,
)


WORKFLOW_VERSION = "s06.evidence.v1"
MAX_CLAIMS = 20
MAX_CLAIM_CHARS = 4096
MAX_CITATIONS_PER_CLAIM = 4
MAX_QUESTION_CHARS = 4000


class WorkflowRejected(ValueError):
    def __init__(self):
        super().__init__("invalid_workflow_input")


class CitationRejected(ValueError):
    def __init__(self):
        super().__init__("invalid_citation")


@dataclass(frozen=True, slots=True)
class WorkflowInput:
    scope: EvidenceScope
    question: str
    evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class Citation:
    evidence_id: UUID
    content_hash: bytes


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ReportCandidate:
    scope: EvidenceScope
    question: str
    claims: tuple[Claim, ...]
    workflow_version: str
    synthetic: bool
    publishable: bool
    real_evidence_count: int


@dataclass(frozen=True, slots=True)
class WorkflowOutcome:
    status: str
    workflow_version: str
    candidate: ReportCandidate | None
    reason: str | None
    real_evidence_count: int
    synthetic_evidence_count: int
    publishable: bool


def validate_input(value):
    if type(value) is not WorkflowInput:
        raise WorkflowRejected()

    try:
        scope = validate_scope(value.scope)

        question = normalize_text(
            value.question,
            MAX_QUESTION_CHARS,
        )

        if type(value.evidence) is not tuple:
            raise WorkflowRejected()

        if len(value.evidence) > 20:
            raise WorkflowRejected()

        return WorkflowInput(
            scope=scope,
            question=question,
            evidence=value.evidence,
        )

    except Exception:
        raise WorkflowRejected() from None


def validate_citation(value):
    if type(value) is not Citation:
        raise CitationRejected()

    try:
        evidence_id = valid_uuid(value.evidence_id)

        if (
            type(value.content_hash) is not bytes
            or len(value.content_hash) != 32
        ):
            raise CitationRejected()

        return Citation(
            evidence_id=evidence_id,
            content_hash=value.content_hash,
        )

    except Exception:
        raise CitationRejected() from None


def validate_claim(value):
    if type(value) is not Claim:
        raise CitationRejected()

    try:
        text = normalize_text(
            value.text,
            MAX_CLAIM_CHARS,
        )

        if text != value.text:
            raise CitationRejected()

        if (
            type(value.citations) is not tuple
            or not 1 <= len(value.citations)
            <= MAX_CITATIONS_PER_CLAIM
        ):
            raise CitationRejected()

        citations = tuple(
            validate_citation(item)
            for item in value.citations
        )

        if len({
            item.evidence_id for item in citations
        }) != len(citations):
            raise CitationRejected()

        return Claim(
            text=text,
            citations=citations,
        )

    except Exception:
        raise CitationRejected() from None
