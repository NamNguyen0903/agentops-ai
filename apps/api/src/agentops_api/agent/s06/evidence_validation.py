"""Pure scoped evidence validation, no I/O."""

from dataclasses import dataclass

from .evidence import (
    EvidenceRecord,
    EvidenceScope,
    deduplicate,
    validate_scope,
)
from .workflow_contracts import (
    WorkflowRejected,
)


MIN_SYNTHETIC_SOURCES = 2


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    scope: EvidenceScope
    records: tuple[EvidenceRecord, ...]
    distinct_source_count: int
    synthetic_evidence_count: int
    real_evidence_count: int
    sufficient_for_fixture: bool
    sufficient_for_real_report: bool


def assess_evidence(scope, records):
    try:
        scope = validate_scope(scope)
        records = deduplicate(records, scope)

        # Count canonical retrieved URLs, not repeated
        # excerpts or redirect aliases of the same page.
        distinct_sources = {
            item.retrieved_url
            for item in records
        }

        count = len(distinct_sources)

        return EvidenceAssessment(
            scope=scope,
            records=records,
            distinct_source_count=count,
            synthetic_evidence_count=len(records),
            real_evidence_count=0,
            sufficient_for_fixture=(
                count >= MIN_SYNTHETIC_SOURCES
            ),
            sufficient_for_real_report=False,
        )

    except Exception:
        raise WorkflowRejected() from None


def validate_assessment(value, scope):
    if type(value) is not EvidenceAssessment:
        raise WorkflowRejected()

    try:
        scope = validate_scope(scope)

        if value.scope != scope:
            raise WorkflowRejected()

        rebuilt = assess_evidence(
            scope,
            value.records,
        )

        for name in (
            "distinct_source_count",
            "synthetic_evidence_count",
            "real_evidence_count",
        ):
            if type(getattr(value, name)) is not int:
                raise WorkflowRejected()

        if (
            type(value.sufficient_for_fixture) is not bool
            or type(value.sufficient_for_real_report) is not bool
            or rebuilt != value
        ):
            raise WorkflowRejected()

        return rebuilt

    except Exception:
        raise WorkflowRejected() from None
