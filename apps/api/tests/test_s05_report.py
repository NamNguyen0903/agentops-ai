"""Strict report structure and provenance tests."""

from uuid import UUID

import pytest

from agentops_api.agent.s05 import (
    adapters,
    report,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
    ResearchPlan,
    ResearchSubquestion,
    S05GraphInput,
)
from agentops_api.agent.s05.validation import (
    S05StateIntegrityError,
    create_execution_context,
)


@pytest.fixture
def pipeline():
    context = create_execution_context(
        S05GraphInput(
            task_id=UUID(int=401),
            attempt_id=UUID(int=402),
            question="Synthetic report validation.",
            scope={"region": "offline"},
        )
    )

    plan = adapters.plan_fixture(context)

    output = adapters.research_fixture(
        context, plan
    )

    candidate = adapters.writer_fixture(
        context, plan, output
    )

    assert type(candidate) is DraftReport

    return context, plan, output, candidate


def _assert_safe_error(operation, error_type, category):
    with pytest.raises(error_type) as caught:
        operation()

    assert type(caught.value) is error_type
    assert caught.value.category == category
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_report_reconstructs_independent_candidate(
    pipeline
):
    context, plan, output, candidate = pipeline

    checked = report.validate_draft_report(
        context, plan, output, candidate
    )

    assert checked == candidate
    assert checked is not candidate
    assert checked.synthetic is True

    assert checked.sections[0] is not candidate.sections[0]

    assert (
        checked.sections[0].fixture_references[0]
        is not
        candidate.sections[0].fixture_references[0]
    )


def test_report_validation_does_not_invoke_adapters(
    pipeline, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected adapter invocation")

    for name in (
        "plan_fixture",
        "research_fixture",
        "writer_fixture",
    ):
        monkeypatch.setattr(
            adapters, name, forbidden
        )

    assert report.validate_draft_report(
        *pipeline
    ) is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "   "),
        ("title", "x" * 201),
        ("title", 123),
        ("summary", ""),
        ("summary", "x" * 4001),
        ("summary", None),
        ("summary", chr(0xD800)),
        ("sections", ()),
        ("sections", []),
        ("sections", None),
        ("limitations", ()),
        ("limitations", []),
        ("limitations", ("",)),
        ("limitations", ("x" * 1001,)),
        ("limitations", (123,)),
    ],
)
def test_report_rejects_invalid_structure(
    pipeline, field, value
):
    context, plan, output, candidate = pipeline

    bad = candidate.model_copy(
        update={field: value}
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        report.S05ReportError,
        "invalid_output",
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "heading_blank",
        "heading_too_long",
        "content_blank",
        "content_too_long",
        "references_empty",
        "references_list",
        "references_duplicate",
        "sections_excessive",
        "limitations_excessive",
        "section_mapping",
    ],
)
def test_report_rejects_invalid_nested_structure(
    pipeline, mutation
):
    context, plan, output, candidate = pipeline

    section = candidate.sections[0]
    refs = section.fixture_references

    changes = {
        "heading_blank": {"heading": " "},
        "heading_too_long": {"heading": "x" * 201},
        "content_blank": {"content": ""},
        "content_too_long": {"content": "x" * 4001},
        "references_empty": {"fixture_references": ()},
        "references_list": {
            "fixture_references": list(refs)
        },
        "references_duplicate": {
            "fixture_references": refs + refs
        },
    }

    if mutation in changes:
        changed_section = section.model_copy(
            update=changes[mutation]
        )

        bad = candidate.model_copy(
            update={
                "sections": (
                    changed_section,
                ) + candidate.sections[1:]
            }
        )

    elif mutation == "sections_excessive":
        bad = candidate.model_copy(
            update={
                "sections": (section,) * 9
            }
        )

    elif mutation == "limitations_excessive":
        bad = candidate.model_copy(
            update={
                "limitations": ("offline",) * 9
            }
        )

    else:
        bad = candidate.model_copy(
            update={
                "sections": (
                    section.model_dump(),
                ) + candidate.sections[1:]
            }
        )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        report.S05ReportError,
        "invalid_output",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"fixture_id": "fixture-fabricated"},
        {"task_id": UUID(int=999)},
        {"attempt_id": UUID(int=999)},
        {"attempt_id": None},
        {"fixture_version": "unknown-version"},
        {"source": "unknown-source"},
    ],
)
def test_report_rejects_unapproved_references(
    pipeline, changes
):
    context, plan, output, candidate = pipeline

    section = candidate.sections[0]
    reference = section.fixture_references[0]

    bad_reference = reference.model_copy(
        update=changes
    )

    bad_section = section.model_copy(
        update={
            "fixture_references": (bad_reference,)
        }
    )

    bad = candidate.model_copy(
        update={
            "sections": (
                bad_section,
            ) + candidate.sections[1:]
        }
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "synthetic",
    [False, 1, "true", None],
)
def test_report_rejects_synthetic_flag_mutation(
    pipeline, synthetic
):
    context, plan, output, candidate = pipeline

    bad = candidate.model_copy(
        update={"synthetic": synthetic}
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "target",
    ["report", "section", "reference"],
)
@pytest.mark.parametrize(
    "container_type",
    [list, tuple, frozenset],
)
def test_report_rejects_malformed_model_metadata(
    pipeline, target, container_type
):
    context, plan, output, candidate = pipeline

    section = candidate.sections[0]

    objects = {
        "report": candidate,
        "section": section,
        "reference": section.fixture_references[0],
    }

    selected = objects[target]

    object.__setattr__(
        selected,
        "__pydantic_fields_set__",
        container_type(selected.model_fields_set),
    )

    error_type = (
        S05StateIntegrityError
        if target == "reference"
        else report.S05ReportError
    )

    category = (
        "security_violation"
        if target == "reference"
        else "invalid_output"
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, candidate
        ),
        error_type,
        category,
    )


def test_report_rejects_insufficient_fixture_input(
    pipeline
):
    context, plan, output, candidate = pipeline

    first = plan.subquestions[0]

    changed = ResearchSubquestion(
        subquestion_id=first.subquestion_id,
        question=first.question,
        query="fixture:unregistered-report-test",
    )

    incomplete_plan = ResearchPlan(
        subquestions=(
            changed,
        ) + plan.subquestions[1:],
        assumptions=plan.assumptions,
    )

    incomplete_output = adapters.research_fixture(
        context,
        incomplete_plan,
    )

    assert incomplete_output.fixture_coverage == 0.75

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context,
            incomplete_plan,
            incomplete_output,
            candidate,
        ),
        S05StateIntegrityError,
        "security_violation",
    )


def test_report_rejects_tampered_research_input(
    pipeline
):
    context, plan, output, candidate = pipeline

    bad_output = output.model_copy(
        update={"fixture_coverage": 0.25}
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, bad_output, candidate
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "candidate",
    [None, {}, "unstructured report"],
)
def test_report_rejects_unstructured_candidate(
    pipeline, candidate
):
    context, plan, output, original = pipeline

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, candidate
        ),
        report.S05ReportError,
        "invalid_output",
    )


# WP03-05A-R2: UUID comparator compatibility regression.


@pytest.mark.parametrize(
    "attempt_id",
    [UUID(int=502), None],
    ids=["with-attempt", "without-attempt"],
)
def test_report_uuid_identity_regression(attempt_id):
    context = create_execution_context(
        S05GraphInput(
            task_id=UUID(int=501),
            attempt_id=attempt_id,
            question="Synthetic UUID regression.",
            scope={"region": "offline"},
        )
    )

    plan = adapters.plan_fixture(context)

    output = adapters.research_fixture(
        context,
        plan,
    )

    candidate = adapters.writer_fixture(
        context,
        plan,
        output,
    )

    assert type(candidate) is DraftReport

    checked = report.validate_draft_report(
        context,
        plan,
        output,
        candidate,
    )

    assert checked == candidate
    assert checked is not candidate

    for section in checked.sections:
        for reference in section.fixture_references:
            assert type(reference.task_id) is UUID
            assert reference.task_id == context.task_id
            assert reference.attempt_id == attempt_id

            if attempt_id is None:
                assert reference.attempt_id is None
            else:
                assert type(reference.attempt_id) is UUID


def test_report_accepts_independent_equal_uuid_values(
    pipeline,
):
    context, plan, output, candidate = pipeline

    section = candidate.sections[0]
    reference = section.fixture_references[0]

    task_id = UUID(str(reference.task_id))
    attempt_id = UUID(str(reference.attempt_id))

    assert task_id == reference.task_id
    assert task_id is not reference.task_id

    assert attempt_id == reference.attempt_id
    assert attempt_id is not reference.attempt_id

    changed_reference = reference.model_copy(
        update={
            "task_id": task_id,
            "attempt_id": attempt_id,
        }
    )

    changed_section = section.model_copy(
        update={
            "fixture_references": (
                changed_reference,
            ) + section.fixture_references[1:],
        }
    )

    changed_candidate = candidate.model_copy(
        update={
            "sections": (
                changed_section,
            ) + candidate.sections[1:],
        }
    )

    checked = report.validate_draft_report(
        context,
        plan,
        output,
        changed_candidate,
    )

    assert checked == candidate


@pytest.mark.parametrize(
    "mutation",
    [
        "task_string",
        "attempt_string",
        "cross_task",
        "cross_attempt",
        "attempt_boolean",
    ],
)
def test_report_uuid_provenance_rejects_mutation(
    pipeline,
    mutation,
):
    context, plan, output, candidate = pipeline

    section = candidate.sections[0]
    reference = section.fixture_references[0]

    # Confirm the untouched baseline is valid first.

    assert report.validate_draft_report(
        context,
        plan,
        output,
        candidate,
    ) == candidate

    mutations = {
        "task_string": {
            "task_id": str(reference.task_id),
        },
        "attempt_string": {
            "attempt_id": str(reference.attempt_id),
        },
        "cross_task": {
            "task_id": UUID(int=999),
        },
        "cross_attempt": {
            "attempt_id": UUID(int=999),
        },
        "attempt_boolean": {
            "attempt_id": True,
        },
    }

    changed_reference = reference.model_copy(
        update=mutations[mutation]
    )

    changed_section = section.model_copy(
        update={
            "fixture_references": (
                changed_reference,
            ) + section.fixture_references[1:],
        }
    )

    changed_candidate = candidate.model_copy(
        update={
            "sections": (
                changed_section,
            ) + candidate.sections[1:],
        }
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context,
            plan,
            output,
            changed_candidate,
        ),
        S05StateIntegrityError,
        "security_violation",
    )


# WP04-02C: SEC05 mixed-error security regression.


def _sec05_replace_reference(
    candidate,
    mutation,
    section_index=0,
):
    sections = list(candidate.sections)
    section = sections[section_index]
    reference = section.fixture_references[0]

    changes = {
        "unknown": {
            "fixture_id": "fixture-fabricated",
        },
        "cross_task": {
            "task_id": UUID(int=999),
        },
        "cross_attempt": {
            "attempt_id": UUID(int=999),
        },
        "wrong_source": {
            "source": "unapproved-source",
        },
        "wrong_version": {
            "fixture_version": "unknown-version",
        },
    }

    changed = reference.model_copy(
        update=changes[mutation]
    )

    sections[section_index] = section.model_copy(
        update={
            "fixture_references": (
                changed,
            ) + section.fixture_references[1:]
        }
    )

    return candidate.model_copy(
        update={"sections": tuple(sections)}
    )


@pytest.mark.parametrize(
    "reference_mutation",
    [
        "unknown",
        "cross_task",
        "cross_attempt",
        "wrong_source",
        "wrong_version",
    ],
)
@pytest.mark.parametrize(
    "text_mutation",
    [
        "title",
        "summary",
        "limitations",
        "heading",
        "content",
    ],
)
def test_sec05_mixed_error_security_precedence(
    pipeline,
    reference_mutation,
    text_mutation,
):
    context, plan, output, candidate = pipeline

    assert report.validate_draft_report(
        context, plan, output, candidate
    ) == candidate

    bad = _sec05_replace_reference(
        candidate,
        reference_mutation,
    )

    if text_mutation == "title":
        bad = bad.model_copy(
            update={"title": ""}
        )

    elif text_mutation == "summary":
        bad = bad.model_copy(
            update={"summary": None}
        )

    elif text_mutation == "limitations":
        bad = bad.model_copy(
            update={"limitations": ("",)}
        )

    else:
        section = bad.sections[0].model_copy(
            update={text_mutation: ""}
        )

        bad = bad.model_copy(
            update={
                "sections": (
                    section,
                ) + bad.sections[1:]
            }
        )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "earlier_mutation",
    [
        "blank_heading",
        "blank_content",
        "empty_references",
        "duplicate_references",
        "section_mapping",
        "invalid_section_metadata",
    ],
)
@pytest.mark.parametrize(
    "reference_mutation",
    ["unknown", "cross_task"],
)
def test_sec05_later_section_security_precedence(
    pipeline,
    earlier_mutation,
    reference_mutation,
):
    context, plan, output, candidate = pipeline

    assert report.validate_draft_report(
        context, plan, output, candidate
    ) == candidate

    assert len(candidate.sections) >= 2

    bad = _sec05_replace_reference(
        candidate,
        reference_mutation,
        section_index=len(candidate.sections) - 1,
    )

    first = bad.sections[0]

    if earlier_mutation == "section_mapping":
        changed = first.model_dump()

    elif earlier_mutation == "invalid_section_metadata":
        changed = first.model_copy()

        object.__setattr__(
            changed,
            "__pydantic_fields_set__",
            list(changed.model_fields_set),
        )

    else:
        updates = {
            "blank_heading": {"heading": ""},
            "blank_content": {"content": ""},
            "empty_references": {
                "fixture_references": (),
            },
            "duplicate_references": {
                "fixture_references": (
                    first.fixture_references
                    + first.fixture_references
                ),
            },
        }

        changed = first.model_copy(
            update=updates[earlier_mutation]
        )

    bad = bad.model_copy(
        update={
            "sections": (
                changed,
            ) + bad.sections[1:]
        }
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "container_type",
    [tuple, list],
    ids=["tuple", "list"],
)
def test_sec05_later_reference_security_precedence(
    pipeline,
    container_type,
):
    context, plan, output, candidate = pipeline

    assert report.validate_draft_report(
        context, plan, output, candidate
    ) == candidate

    section = candidate.sections[0]
    reference = section.fixture_references[0]

    forged = reference.model_copy(
        update={"task_id": UUID(int=999)}
    )

    changed = section.model_copy(
        update={
            "heading": "",
            "fixture_references": container_type(
                (reference, reference, forged)
            ),
        }
    )

    bad = candidate.model_copy(
        update={
            "sections": (
                changed,
            ) + candidate.sections[1:]
        }
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


def test_sec05_inspects_bounded_sections_list(
    pipeline,
):
    context, plan, output, candidate = pipeline

    bad = _sec05_replace_reference(
        candidate,
        "cross_task",
    )

    bad = bad.model_copy(
        update={
            "title": "",
            "sections": list(bad.sections),
        }
    )

    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        S05StateIntegrityError,
        "security_violation",
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "oversized_sections",
        "oversized_references",
        "custom_sections",
        "custom_references",
    ],
)
def test_sec05_uninspectable_structure_fails_closed(
    pipeline,
    mutation,
):
    context, plan, output, candidate = pipeline

    assert report.validate_draft_report(
        context, plan, output, candidate
    ) == candidate

    class UntrustedList(list):
        def __iter__(self):
            pytest.fail("Unexpected custom iteration")

        def __len__(self):
            pytest.fail("Unexpected custom length")

    first = candidate.sections[0]

    if mutation == "oversized_sections":
        bad = candidate.model_copy(
            update={"sections": (first,) * 9}
        )

    elif mutation == "custom_sections":
        bad = candidate.model_copy(
            update={
                "sections": UntrustedList(
                    candidate.sections
                ),
            }
        )

    else:
        references = first.fixture_references

        if mutation == "oversized_references":
            changed_references = references * 21
        else:
            changed_references = UntrustedList(
                references
            )

        changed = first.model_copy(
            update={
                "fixture_references": changed_references
            }
        )

        bad = candidate.model_copy(
            update={
                "sections": (
                    changed,
                ) + candidate.sections[1:]
            }
        )

    # Rejection is required. This category by itself
    # must not authorize a future repair attempt.
    _assert_safe_error(
        lambda: report.validate_draft_report(
            context, plan, output, bad
        ),
        report.S05ReportError,
        "invalid_output",
    )
