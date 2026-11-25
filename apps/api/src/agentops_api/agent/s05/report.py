"""Strict synthetic report validation for Sprint S05."""

from agentops_api.agent.s05.adapters import (
    _validate_research_plan,
    _verify_fixture_reference,
    validate_fixture_research_output,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
    FixtureReference,
    ReportSection,
    ResearchOutput,
    ResearchPlan,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05StateIntegrityError,
    _repair_model_fields,
    _repair_text_inspectable,
    _validated_context_copy,
    _verify_exact_model_shape,
)


class S05ReportError(ValueError):
    """Safe malformed-report error."""

    category = "invalid_output"

    def __init__(self) -> None:
        super().__init__("invalid S05 draft report")


def _verify_reference(
    reference: FixtureReference,
    approved: dict[str, FixtureReference],
) -> FixtureReference:
    """Reject references not matching current verified records."""

    checked = None

    try:
        _verify_exact_model_shape(
            reference,
            FixtureReference,
        )

        raw = reference.__dict__

        fixture_id = raw["fixture_id"]

        if (
            type(fixture_id) is not str
            or not 1 <= len(fixture_id) <= 80
        ):
            raise ValueError("invalid fixture identity")

        expected = approved.get(fixture_id)

        if expected is None:
            raise ValueError("unknown fixture identity")

        _verify_fixture_reference(
            reference,
            expected,
        )

        checked = FixtureReference(
            **expected.__dict__
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

    if checked is None:
        raise S05StateIntegrityError()

    return checked


class _MalformedReportTextError(ValueError):
    """Known repairable blank report text."""

    def __init__(self) -> None:
        super().__init__("invalid S05 report content")


def _verify_report_text(
    value: str,
    maximum: int,
) -> str:
    if type(value) is not str:
        raise ValueError("invalid report text")

    if len(value) == 0:
        raise _MalformedReportTextError()

    if len(value) > maximum:
        raise ValueError("invalid report text length")

    if not value.strip():
        raise _MalformedReportTextError()

    value.encode("utf-8")

    return value


def _bounded_provenance_fields(value, expected_type):
    """Inspect known fields without accepting model shape.

    This is security preflight only, not repair eligibility.
    Oversized or uninspectable raw dictionaries remain
    ineligible under the independent exact-model checks.
    """

    if type(value) is not expected_type:
        return None

    try:
        raw = object.__getattribute__(
            value, "__dict__"
        )

        if type(raw) is not dict:
            return None

        expected = expected_type.model_fields

        # Bound traversal independently of arbitrary
        # additional fields. Do not perform raw lookups
        # while untrusted dictionary keys are present.

        checked = {}

        for index, (key, item) in enumerate(raw.items()):
            if index >= len(expected) + 8:
                break

            if type(key) is not str:
                continue

            if len(key) > 80:
                continue

            if key in expected:
                checked[key] = item

        return checked

    except Exception:
        return None


def _inspect_report_provenance(candidate, approved):
    """Bounded security inspection before reconstruction."""

    fields = _bounded_provenance_fields(
        candidate, DraftReport
    )

    if fields is None:
        return

    if (
        "synthetic" in fields
        and fields["synthetic"] is not True
    ):
        raise S05StateIntegrityError()

    sections = fields.get("sections")

    if type(sections) not in (tuple, list):
        return

    for section in sections[:8]:
        fields = _bounded_provenance_fields(
            section, ReportSection
        )

        if fields is None:
            continue

        references = fields.get("fixture_references")

        if type(references) not in (tuple, list):
            continue

        for reference in references[:20]:
            _verify_reference(reference, approved)


def _reconstruct_report(
    candidate: DraftReport,
    approved: dict[str, FixtureReference],
) -> DraftReport:
    """Validate raw model fields before independent reconstruction."""

    _inspect_report_provenance(
        candidate,
        approved,
    )

    _verify_exact_model_shape(
        candidate,
        DraftReport,
    )

    raw = candidate.__dict__

    if raw["synthetic"] is not True:
        raise S05StateIntegrityError()

    title = _verify_report_text(
        raw["title"], 200
    )

    summary = _verify_report_text(
        raw["summary"], 4000
    )

    sections = raw["sections"]
    limitations = raw["limitations"]

    if type(sections) is not tuple:
        raise ValueError("invalid sections")

    if not 1 <= len(sections) <= 8:
        raise ValueError("invalid section count")

    if type(limitations) is not tuple:
        raise ValueError("invalid limitations")

    if not 1 <= len(limitations) <= 8:
        raise ValueError("invalid limitation count")

    checked_limitations = tuple(
        _verify_report_text(item, 1000)
        for item in limitations
    )

    checked_sections = []

    for section in sections:
        _verify_exact_model_shape(
            section,
            ReportSection,
        )

        fields = section.__dict__

        heading = _verify_report_text(
            fields["heading"], 200
        )

        content = _verify_report_text(
            fields["content"], 4000
        )

        references = fields["fixture_references"]

        if type(references) is not tuple:
            raise ValueError("invalid section references")

        if not 1 <= len(references) <= 20:
            raise ValueError("invalid reference count")

        checked_references = tuple(
            _verify_reference(reference, approved)
            for reference in references
        )

        checked_sections.append(
            ReportSection(
                heading=heading,
                content=content,
                fixture_references=checked_references,
            )
        )

    return DraftReport(
        title=title,
        summary=summary,
        sections=tuple(checked_sections),
        limitations=checked_limitations,
        synthetic=True,
    )


def validate_draft_report(
    context: ExecutionContext,
    plan: ResearchPlan,
    research_output: ResearchOutput,
    candidate: DraftReport,
) -> DraftReport:
    """Verify report structure and approved fixture references.

    This validator checks structural integrity and provenance.
    It does not establish semantic grounding, factual accuracy,
    publication eligibility or real evidence coverage.
    """

    trusted_context = _validated_context_copy(
        context
    )

    checked_plan = _validate_research_plan(plan)

    verified = validate_fixture_research_output(
        trusted_context,
        checked_plan,
        research_output,
    )

    if (
        verified.fixture_coverage != 1.0
        or not verified.records
        or verified.gaps
        or verified.conflicts
    ):
        raise S05StateIntegrityError()

    approved = {
        record.reference.fixture_id: record.reference
        for record in verified.records
    }

    checked_report = None

    try:
        checked_report = _reconstruct_report(
            candidate,
            approved,
        )

    except S05StateIntegrityError:
        raise

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if checked_report is None:
        raise S05ReportError()

    return checked_report



def _writer_repair_eligible(
    context,
    plan,
    research_output,
    candidate,
):
    """Check complete provenance before positive eligibility.

    False means either valid output or no safe basis for
    repair. Security violations remain exceptions.

    No fixture adapter is invoked by this function.
    """

    trusted = _validated_context_copy(context)
    checked_plan = _validate_research_plan(plan)

    verified = validate_fixture_research_output(
        trusted,
        checked_plan,
        research_output,
    )

    if (
        verified.fixture_coverage != 1.0
        or not verified.records
        or verified.gaps
        or verified.conflicts
    ):
        raise S05StateIntegrityError()

    approved = {
        record.reference.fixture_id: record.reference
        for record in verified.records
    }

    # Perform security inspection before considering
    # malformed ordinary content.

    _inspect_report_provenance(
        candidate, approved
    )

    raw = _repair_model_fields(
        candidate, DraftReport
    )

    if raw is None:
        return False

    if raw["synthetic"] is not True:
        raise S05StateIntegrityError()

    sections = raw["sections"]
    limitations = raw["limitations"]

    if type(sections) is not tuple:
        return False

    if not 1 <= len(sections) <= 8:
        return False

    if type(limitations) is not tuple:
        return False

    if not 1 <= len(limitations) <= 8:
        return False

    if not all(
        _repair_text_inspectable(item, 1000)
        for item in limitations
    ):
        return False

    if not _repair_text_inspectable(
        raw["title"], 200
    ):
        return False

    if not _repair_text_inspectable(
        raw["summary"], 4000
    ):
        return False

    for section in sections:
        fields = _repair_model_fields(
            section, ReportSection
        )

        if fields is None:
            return False

        references = fields["fixture_references"]

        if type(references) is not tuple:
            return False

        if not 1 <= len(references) <= 20:
            return False

        for reference in references:
            if _repair_model_fields(
                reference, FixtureReference
            ) is None:
                return False

            _verify_reference(
                reference, approved
            )

        if not _repair_text_inspectable(
            fields["heading"], 200
        ):
            return False

        if not _repair_text_inspectable(
            fields["content"], 4000
        ):
            return False

    # Identify known, repairable content defects only
    # after complete structure and provenance inspection.

    malformed = (
        not raw["title"].strip()
        or not raw["summary"].strip()
        or any(
            not note.strip()
            for note in limitations
        )
    )

    for section in sections:
        fields = _repair_model_fields(
            section, ReportSection
        )

        if fields is None:
            return False

        if not fields["heading"].strip():
            malformed = True

        if not fields["content"].strip():
            malformed = True

        identifiers = [
            reference.fixture_id
            for reference in fields["fixture_references"]
        ]

        if len(identifiers) != len(set(identifiers)):
            malformed = True

    if not malformed:
        return False

    # The strict validator must independently confirm
    # that the positively identified defect is invalid.

    try:
        _reconstruct_report(
            candidate, approved
        )

    except S05StateIntegrityError:
        raise

    except Exception as error:
        from pydantic import ValidationError

        return type(error) in (
            _MalformedReportTextError,
            ValidationError,
        )

    return False
