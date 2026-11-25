"""Deterministic offline fixture adapters for Sprint S05.

These adapters produce structured synthetic outputs only.
They have no provider, network, database, lifecycle,
publication or graph-routing authority.
"""

import hashlib
from typing import Final

from agentops_api.agent.s05.contract import (
    FIXTURE_VERSION,
    DraftReport,
    FixtureRecord,
    FixtureReference,
    ReportSection,
    ResearchOutput,
    ResearchPlan,
    ResearchSubquestion,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05BoundaryError,
    S05StateIntegrityError,
    _strict_equal,
    _validated_context_copy,
    _verify_exact_model_shape,
)


_PLANNER_TEMPLATES: Final[
    tuple[tuple[str, str, str], ...]
] = (
    (
        "q1",
        "What market characteristics are represented "
        "in the synthetic fixtures?",
        "fixture:market-overview",
    ),
    (
        "q2",
        "Which synthetic competitors are represented?",
        "fixture:competitor-landscape",
    ),
    (
        "q3",
        "What product differences are represented "
        "in the synthetic fixtures?",
        "fixture:product-differentiation",
    ),
    (
        "q4",
        "What risks and limitations are represented?",
        "fixture:risks-and-limitations",
    ),
)


_PLANNER_ASSUMPTIONS: Final[tuple[str, ...]] = (
    "Application-owned synthetic fixtures only.",
    "No external research or validated evidence collected.",
    "Fixed templates do not establish semantic relevance "
    "to the user's research question.",
)


def _validate_adapter_context(
    context: ExecutionContext,
) -> ExecutionContext:
    """Reconstruct context without accepting policy overrides."""

    return _validated_context_copy(context)


def plan_fixture(
    context: ExecutionContext,
) -> ResearchPlan:
    """Return a bounded, deterministic synthetic research plan.

    User input is validated but is not interpreted as commands,
    tool permissions or routing instructions.

    This offline baseline uses fixed application-owned templates,
    not LLM inference or semantic research planning.
    """

    _validate_adapter_context(context)

    return ResearchPlan(
        subquestions=tuple(
            ResearchSubquestion(
                subquestion_id=identifier,
                question=question,
                query=query,
            )
            for identifier, question, query
            in _PLANNER_TEMPLATES
        ),
        assumptions=_PLANNER_ASSUMPTIONS,
    )


# Immutable application-owned synthetic fixture registry.
# These records describe fictional scenarios, not real companies
# or facts obtained through external research.

_RESEARCH_FIXTURES: Final[
    tuple[tuple[str, str, str], ...]
] = (
    (
        "fixture:market-overview",
        "Synthetic market overview",
        "Synthetic scenario: a fictional software market "
        "contains small-business and enterprise segments. "
        "This is test data, not an observed market condition.",
    ),
    (
        "fixture:competitor-landscape",
        "Synthetic competitor landscape",
        "Synthetic scenario: fictional Competitor Alpha "
        "emphasizes simplicity, while fictional Competitor Beta "
        "emphasizes configurable workflows.",
    ),
    (
        "fixture:product-differentiation",
        "Synthetic product differentiation",
        "Synthetic scenario: fictional products differ in "
        "onboarding, customization and reporting features. "
        "No real product comparison was performed.",
    ),
    (
        "fixture:risks-and-limitations",
        "Synthetic risks and limitations",
        "Synthetic scenario: the fixture dataset contains no "
        "verified pricing, market-share or customer evidence. "
        "No real-world conclusion is supported.",
    ),
)


def _validate_exact_model_fields(
    value,
    expected_type,
) -> None:
    """Reject unexpected fields before model revalidation."""

    _verify_exact_model_shape(value, expected_type)


def _validate_research_plan(
    plan: ResearchPlan,
) -> ResearchPlan:
    """Reconstruct a bounded plan from checked raw fields.

    Raw fields are checked before serialization so that an
    invalid model_copy update cannot be silently normalized.
    """

    validated = None

    try:
        _validate_exact_model_fields(
            plan,
            ResearchPlan,
        )

        if type(plan.subquestions) is not tuple:
            raise ValueError("invalid subquestion collection")

        if type(plan.assumptions) is not tuple:
            raise ValueError("invalid assumption collection")

        if not 1 <= len(plan.subquestions) <= 4:
            raise ValueError("invalid subquestion count")

        if len(plan.assumptions) > 4:
            raise ValueError("invalid assumption count")

        if any(
            type(note) is not str
            for note in plan.assumptions
        ):
            raise ValueError("invalid assumption type")

        questions = []

        for item in plan.subquestions:
            _validate_exact_model_fields(
                item,
                ResearchSubquestion,
            )

            if any(
                type(value) is not str
                for value in item.__dict__.values()
            ):
                raise ValueError("invalid subquestion field type")

            questions.append(
                ResearchSubquestion.model_validate(
                    dict(item.__dict__)
                )
            )

        validated = ResearchPlan(
            subquestions=tuple(questions),
            assumptions=plan.assumptions,
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        pass

    if validated is None:
        raise S05BoundaryError()

    return validated


def _lookup_fixture(
    query: str,
) -> tuple[str, str] | None:
    """Match an exact application-owned fixture identifier."""

    for identifier, title, content in _RESEARCH_FIXTURES:
        if query == identifier:
            return title, content

    return None


def _fixture_reference(
    context: ExecutionContext,
    subquestion: ResearchSubquestion,
) -> FixtureReference:
    """Bind deterministic fixture identity to task and attempt."""

    identity = "|".join((
        FIXTURE_VERSION,
        str(context.task_id),
        (
            str(context.attempt_id)
            if context.attempt_id is not None
            else "none"
        ),
        subquestion.subquestion_id,
        subquestion.query,
    ))

    fixture_id = "fixture-" + hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return FixtureReference(
        fixture_id=fixture_id,
        task_id=context.task_id,
        attempt_id=context.attempt_id,
    )


def research_fixture(
    context: ExecutionContext,
    plan: ResearchPlan,
) -> ResearchOutput:
    """Process a bounded plan in one offline adapter invocation.

    Unknown queries become structural gaps. They never trigger
    a network request, tool invocation or external retrieval.

    Coverage describes synthetic fixture availability only.
    It does not establish semantic evidence or real-world facts.
    """

    verified_context = _validate_adapter_context(context)
    verified_plan = _validate_research_plan(plan)

    records = []
    gaps = []
    covered_questions = set()

    for item in verified_plan.subquestions:
        fixture = _lookup_fixture(item.query)

        if fixture is None:
            gaps.append(
                f"No approved synthetic fixture for "
                f"{item.subquestion_id}."
            )
            continue

        title, content = fixture

        records.append(
            FixtureRecord(
                reference=_fixture_reference(
                    verified_context,
                    item,
                ),
                subquestion_id=item.subquestion_id,
                title=title,
                content=content,
            )
        )

        covered_questions.add(item.subquestion_id)

    coverage = (
        len(covered_questions)
        / len(verified_plan.subquestions)
    )

    return ResearchOutput(
        records=tuple(records),
        gaps=tuple(gaps),
        conflicts=(),
        fixture_coverage=coverage,
    )


def _expected_research_output(
    context: ExecutionContext,
    plan: ResearchPlan,
) -> ResearchOutput:
    """Reconstruct expected output without invoking Research."""

    records = []
    gaps = []

    for item in plan.subquestions:
        fixture = _lookup_fixture(item.query)

        if fixture is None:
            gaps.append(
                f"No approved synthetic fixture for "
                f"{item.subquestion_id}."
            )
            continue

        title, content = fixture

        records.append(
            FixtureRecord(
                reference=_fixture_reference(context, item),
                subquestion_id=item.subquestion_id,
                title=title,
                content=content,
            )
        )

    return ResearchOutput(
        records=tuple(records),
        gaps=tuple(gaps),
        conflicts=(),
        fixture_coverage=(
            len(records) / len(plan.subquestions)
        ),
    )


def _verify_fixture_reference(
    actual: FixtureReference,
    expected: FixtureReference,
) -> None:
    """Verify raw reference values and exact types."""

    _validate_exact_model_fields(
        actual,
        FixtureReference,
    )

    for name in FixtureReference.model_fields:
        actual_value = actual.__dict__[name]
        expected_value = expected.__dict__[name]

        if type(actual_value) is not type(expected_value):
            raise ValueError("invalid fixture provenance type")

        if actual_value != expected_value:
            raise ValueError("fixture provenance mismatch")


def _verify_fixture_record(
    actual: FixtureRecord,
    expected: FixtureRecord,
) -> None:
    """Verify complete fixture record against registry."""

    _validate_exact_model_fields(
        actual,
        FixtureRecord,
    )

    _verify_fixture_reference(
        actual.reference,
        expected.reference,
    )

    for name in (
        "subquestion_id",
        "title",
        "content",
        "synthetic",
    ):
        if not _strict_equal(
            actual.__dict__[name],
            expected.__dict__[name],
        ):
            raise ValueError("fixture record mismatch")


def validate_fixture_research_output(
    context: ExecutionContext,
    plan: ResearchPlan,
    output: ResearchOutput,
) -> ResearchOutput:
    """Return independently verified fixture output."""

    verified_context = _validate_adapter_context(context)
    verified_plan = _validate_research_plan(plan)

    validated = None

    try:
        expected = _expected_research_output(
            verified_context,
            verified_plan,
        )

        _validate_exact_model_fields(
            output,
            ResearchOutput,
        )

        if type(output.records) is not tuple:
            raise ValueError("invalid fixture collection")

        if len(output.records) != len(expected.records):
            raise ValueError("fixture count mismatch")

        for actual, reference in zip(
            output.records,
            expected.records,
        ):
            _verify_fixture_record(actual, reference)

        for name in (
            "gaps",
            "conflicts",
            "fixture_coverage",
        ):
            if not _strict_equal(
                output.__dict__[name],
                expected.__dict__[name],
            ):
                raise ValueError("research metadata mismatch")

        validated = expected

    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        pass

    if validated is None:
        raise S05StateIntegrityError()

    return validated


_WRITER_LIMITATIONS: Final[tuple[str, ...]] = (
    "Application-owned synthetic fixture data only.",
    "No external research or verified real evidence collected.",
    "Structural fixture coverage is not semantic groundedness.",
    "This offline report candidate is not publishable.",
)


def writer_fixture(
    context: ExecutionContext,
    plan: ResearchPlan,
    research_output: ResearchOutput,
) -> DraftReport | None:
    """Produce a deterministic offline draft or abstain."""

    verified = validate_fixture_research_output(
        context,
        plan,
        research_output,
    )

    if (
        not verified.records
        or verified.fixture_coverage != 1.0
        or verified.gaps
        or verified.conflicts
    ):
        return None

    return DraftReport(
        title="Synthetic market research candidate",
        summary=(
            "Offline comparison assembled from approved "
            "synthetic fixtures. No real-world conclusions "
            "are supported."
        ),
        sections=tuple(
            ReportSection(
                heading=record.title,
                content=record.content,
                fixture_references=(record.reference,),
            )
            for record in verified.records
        ),
        limitations=_WRITER_LIMITATIONS,
    )
