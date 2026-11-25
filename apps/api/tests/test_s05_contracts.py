"""Core typed-contract verification for Sprint S05 WP02."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from agentops_api.agent.contract import (
    Versions as S04Versions,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
    ExecutionCounters,
    ExecutionPolicy,
    FixtureRecord,
    FixtureReference,
    ReportSection,
    ResearchOutput,
    ResearchPlan,
    ResearchSubquestion,
    S05GraphInput,
    S05GraphResult,
    S05GraphState,
    S05Versions,
)


TASK_ID = UUID("00000000-0000-4000-8000-000000000001")


def valid_input():
    return {
        "task_id": TASK_ID,
        "question": "Compare synthetic competitor fixtures",
        "scope": {"market": "synthetic"},
    }


def test_s05_versions_are_separate_from_s04():
    s04 = S04Versions()
    s05 = S05Versions()

    assert s04.graph == "s04-single-agent-v1"
    assert s04.schema_version == "s04-state-v1"

    assert s05.graph == "s05-specialized-agent-v1"
    assert s05.schema_version == "s05-state-v1"
    assert s05.fixture == "s05-offline-fixture-v1"
    assert s05.model == "none"
    assert s05.prompt == "none"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("graph", "s04-single-agent-v1"),
        ("schema_version", "s04-state-v1"),
        ("fixture", "unapproved-fixture"),
        ("model", "live-model"),
        ("prompt", "unapproved-prompt"),
        ("unknown", "unexpected"),
    ],
)
def test_invalid_version_metadata_is_rejected(field, value):
    payload = S05Versions().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        S05Versions.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


def test_execution_policy_defaults_match_contract():
    policy = ExecutionPolicy()

    assert policy.max_subquestions == 4
    assert policy.max_adapter_invocations == 4
    assert policy.max_repair_attempts == 1
    assert policy.recursion_limit == 12
    assert policy.soft_deadline_seconds == 30

    assert policy.live_model_calls == 0
    assert policy.live_search_calls == 0
    assert policy.live_retrieval_calls == 0
    assert policy.live_tokens == 0
    assert policy.paid_cost_usd == 0
    assert policy.durable_checkpoints == 0
    assert policy.publishable is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_subquestions", 5),
        ("max_adapter_invocations", 5),
        ("max_repair_attempts", 2),
        ("max_repair_attempts", True),
        ("recursion_limit", 13),
        ("soft_deadline_seconds", 31),
        ("soft_deadline_seconds", 30.0),
        ("live_model_calls", 1),
        ("live_search_calls", 1),
        ("live_retrieval_calls", 1),
        ("live_tokens", 1),
        ("paid_cost_usd", 1),
        ("paid_cost_usd", False),
        ("durable_checkpoints", 1),
        ("publishable", True),
        ("publishable", 0),
    ],
)
def test_execution_policy_rejects_invalid_values(field, value):
    payload = ExecutionPolicy().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        ExecutionPolicy.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


def test_execution_policy_is_frozen():
    policy = ExecutionPolicy()

    with pytest.raises(ValidationError) as caught:
        policy.max_adapter_invocations = 5

    assert caught.value.errors()[0]["type"] == "frozen_instance"


def test_execution_counters_start_at_zero():
    counters = ExecutionCounters()

    assert counters.adapter_invocations == 0
    assert counters.repair_attempts == 0
    assert counters.live_model_calls == 0
    assert counters.paid_cost_usd == 0


def test_execution_counters_accept_approved_boundary():
    counters = ExecutionCounters(
        adapter_invocations=4,
        repair_attempts=1,
    )

    assert counters.adapter_invocations == 4
    assert counters.repair_attempts == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_invocations", -1),
        ("adapter_invocations", 5),
        ("adapter_invocations", True),
        ("adapter_invocations", 1.0),
        ("repair_attempts", -1),
        ("repair_attempts", 2),
        ("repair_attempts", True),
        ("live_model_calls", 1),
        ("live_search_calls", 1),
        ("live_retrieval_calls", 1),
        ("live_tokens", 1),
        ("paid_cost_usd", 1),
        ("paid_cost_usd", False),
    ],
)
def test_execution_counters_reject_invalid_values(field, value):
    payload = ExecutionCounters(
        adapter_invocations=1,
    ).model_dump()

    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        ExecutionCounters.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


def test_repair_requires_an_adapter_invocation():
    with pytest.raises(ValidationError) as caught:
        ExecutionCounters(
            adapter_invocations=0,
            repair_attempts=1,
        )

    assert caught.value.errors()[0]["type"] == "value_error"


def test_graph_input_accepts_valid_research_request():
    request = S05GraphInput.model_validate(valid_input())

    assert request.task_id == TASK_ID
    assert request.attempt_id is None
    assert request.scope == {"market": "synthetic"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", str(TASK_ID)),
        ("question", ""),
        ("question", "   "),
        ("question", 123),
        ("question", "x" * 4001),
        ("scope", []),
        ("scope", {"value": float("nan")}),
        ("scope", {"value": float("inf")}),
        ("scope", {"value": object()}),
        ("scope", {1: "invalid key"}),
    ],
)
def test_invalid_graph_input_is_rejected(field, value):
    payload = valid_input()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        S05GraphInput.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


@pytest.mark.parametrize(
    "field",
    [
        "versions",
        "policy",
        "budget",
        "publishable",
        "allowed_tools",
        "repair_attempts",
    ],
)
def test_graph_input_rejects_caller_controlled_policy(field):
    payload = valid_input()
    payload[field] = {}

    with pytest.raises(ValidationError) as caught:
        S05GraphInput.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        and error["type"] == "extra_forbidden"
        for error in caught.value.errors()
    )


def test_graph_input_does_not_alias_original_scope():
    scope = {"market": {"segments": ["synthetic"]}}

    request = S05GraphInput(
        task_id=TASK_ID,
        question="Offline research",
        scope=scope,
    )

    scope["market"]["segments"].append("modified")

    assert request.scope == {
        "market": {"segments": ["synthetic"]}
    }


def test_graph_input_rejects_oversized_scope():
    payload = valid_input()
    payload["scope"] = {"value": "x" * 8192}

    with pytest.raises(ValidationError) as caught:
        S05GraphInput.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == ("scope",)


def test_graph_input_rejects_excessive_scope_depth():
    value = "leaf"

    for _ in range(7):
        value = {"nested": value}

    payload = valid_input()
    payload["scope"] = value

    with pytest.raises(ValidationError) as caught:
        S05GraphInput.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == ("scope",)




def make_subquestion(number=1):
    return ResearchSubquestion(
        subquestion_id=f"q{number}",
        question="Compare synthetic market segments",
        query="synthetic competitor fixture",
    )


def make_reference(task_id=TASK_ID, attempt_id=None):
    return FixtureReference(
        fixture_id="fixture-q1",
        task_id=task_id,
        attempt_id=attempt_id,
    )


def make_record():
    return FixtureRecord(
        reference=make_reference(),
        subquestion_id="q1",
        title="Synthetic competitor fixture",
        content="Application-owned synthetic content.",
    )


def make_draft(reference=None):
    if reference is None:
        reference = make_reference()

    return DraftReport(
        title="Synthetic comparison",
        summary="Offline fixture-based candidate.",
        sections=(
            ReportSection(
                heading="Comparison",
                content="Synthetic comparison content.",
                fixture_references=(reference,),
            ),
        ),
        limitations=(
            "No external evidence was collected.",
        ),
    )


def make_candidate_result():
    return S05GraphResult(
        task_id=TASK_ID,
        outcome="candidate_ready",
        stage="candidate_ready",
        candidate=make_draft(),
        fixture_coverage=1.0,
    )


def test_research_plan_accepts_four_subquestions():
    plan = ResearchPlan(
        subquestions=tuple(
            make_subquestion(number)
            for number in range(1, 5)
        ),
        assumptions=("Synthetic dataset only.",),
    )

    assert len(plan.subquestions) == 4
    assert type(plan.subquestions) is tuple


def test_research_plan_rejects_empty_plan():
    with pytest.raises(ValidationError) as caught:
        ResearchPlan(subquestions=())

    assert caught.value.errors()[0]["loc"] == (
        "subquestions",
    )


def test_research_plan_rejects_five_subquestions():
    valid = ResearchPlan(
        subquestions=tuple(
            make_subquestion(number)
            for number in range(1, 5)
        ),
    )

    payload = valid.model_dump()

    payload["subquestions"] += (
        make_subquestion(1).model_dump(),
    )

    with pytest.raises(ValidationError) as caught:
        ResearchPlan.model_validate(payload)

    assert any(
        error["loc"] == ("subquestions",)
        and error["type"] == "too_long"
        for error in caught.value.errors()
    )


def test_research_plan_rejects_duplicate_subquestion_id():
    with pytest.raises(
        ValidationError,
        match="duplicate subquestion identity",
    ):
        ResearchPlan(
            subquestions=(
                make_subquestion(1),
                make_subquestion(1),
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subquestion_id", "q5"),
        ("question", " "),
        ("question", "x" * 1001),
        ("query", ""),
        ("query", "x" * 1001),
        ("query", 123),
        ("allowed_tools", ("web-search",)),
    ],
)
def test_invalid_subquestion_is_rejected(field, value):
    payload = make_subquestion().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        ResearchSubquestion.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


def test_plan_rejects_blank_assumption():
    payload = ResearchPlan(
        subquestions=(make_subquestion(),),
    ).model_dump()

    payload["assumptions"] = (" ",)

    with pytest.raises(ValidationError) as caught:
        ResearchPlan.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == (
        "assumptions",
    )


def test_fixture_provenance_is_explicit():
    fixture = make_record()

    assert fixture.synthetic is True
    assert fixture.reference.task_id == TASK_ID
    assert fixture.reference.attempt_id is None

    assert fixture.reference.fixture_version == (
        "s05-offline-fixture-v1"
    )

    assert fixture.reference.source == (
        "application-owned-synthetic-fixture"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fixture_id", "real-evidence-1"),
        ("fixture_version", "unapproved"),
        ("source", "external-web"),
        ("url", "https://example.invalid"),
        ("task_id", str(TASK_ID)),
    ],
)
def test_invalid_fixture_reference_rejected(field, value):
    payload = make_reference().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        FixtureReference.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_fixture_cannot_claim_real_evidence(value):
    payload = make_record().model_dump()
    payload["synthetic"] = value

    with pytest.raises(ValidationError) as caught:
        FixtureRecord.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == (
        "synthetic",
    )


def test_research_output_supports_empty_fixture_result():
    result = ResearchOutput()

    assert result.records == ()
    assert result.fixture_coverage == 0.0


def test_research_output_accepts_synthetic_fixture():
    result = ResearchOutput(
        records=(make_record(),),
        fixture_coverage=0.5,
    )

    assert len(result.records) == 1
    assert result.fixture_coverage == 0.5


@pytest.mark.parametrize(
    "coverage",
    [
        -0.1,
        1.1,
        float("nan"),
        float("inf"),
        True,
        1,
    ],
)
def test_invalid_fixture_coverage_rejected(coverage):
    payload = ResearchOutput(
        records=(make_record(),),
        fixture_coverage=0.5,
    ).model_dump()

    payload["fixture_coverage"] = coverage

    with pytest.raises(ValidationError) as caught:
        ResearchOutput.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == (
        "fixture_coverage",
    )


def test_empty_fixture_output_cannot_claim_coverage():
    with pytest.raises(
        ValidationError,
        match="empty fixture output must have zero coverage",
    ):
        ResearchOutput(fixture_coverage=0.5)


def test_research_output_rejects_duplicate_fixture_id():
    with pytest.raises(
        ValidationError,
        match="duplicate fixture identity",
    ):
        ResearchOutput(
            records=(make_record(), make_record()),
            fixture_coverage=0.5,
        )


def test_report_contains_explicit_synthetic_metadata():
    report = make_draft()

    assert report.synthetic is True
    assert report.limitations
    assert report.sections[0].fixture_references


def test_report_section_requires_fixture_references():
    section = make_draft().sections[0].model_dump()
    section["fixture_references"] = ()

    with pytest.raises(ValidationError) as caught:
        ReportSection.model_validate(section)

    assert caught.value.errors()[0]["loc"] == (
        "fixture_references",
    )


def test_report_rejects_duplicate_section_reference():
    section = make_draft().sections[0].model_dump()

    reference = make_reference().model_dump()

    section["fixture_references"] = (
        reference,
        reference,
    )

    with pytest.raises(
        ValidationError,
        match="duplicate section fixture reference",
    ):
        ReportSection.model_validate(section)


def test_report_requires_limitations():
    payload = make_draft().model_dump()
    payload["limitations"] = ()

    with pytest.raises(ValidationError) as caught:
        DraftReport.model_validate(payload)

    assert caught.value.errors()[0]["loc"] == (
        "limitations",
    )


def test_candidate_is_non_publishable():
    result = make_candidate_result()

    assert result.outcome == "candidate_ready"
    assert result.candidate is not None
    assert result.evidence_ids == ()
    assert result.coverage == 0.0
    assert result.fixture_coverage == 1.0
    assert result.publishable is False


def test_insufficient_evidence_outcome_has_no_candidate():
    result = S05GraphResult(
        task_id=TASK_ID,
        outcome="insufficient_evidence",
        stage="insufficient_evidence",
    )

    assert result.candidate is None
    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("publishable", True),
        ("publishable", 0),
        ("coverage", 0.5),
        ("coverage", False),
        ("coverage", 0),
        ("evidence_ids", ("fabricated-real-evidence",)),
        ("error_category", "execution_failed"),
        ("published_report_id", "fabricated-report"),
    ],
)
def test_result_rejects_unauthorized_metadata(field, value):
    payload = make_candidate_result().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError) as caught:
        S05GraphResult.model_validate(payload)

    assert any(
        error["loc"] == (field,)
        for error in caught.value.errors()
    )


def test_candidate_requires_report():
    payload = make_candidate_result().model_dump()
    payload["candidate"] = None

    with pytest.raises(
        ValidationError,
        match="candidate report is required",
    ):
        S05GraphResult.model_validate(payload)


def test_candidate_requires_positive_fixture_coverage():
    payload = make_candidate_result().model_dump()
    payload["fixture_coverage"] = 0.0

    with pytest.raises(
        ValidationError,
        match="candidate requires positive fixture coverage",
    ):
        S05GraphResult.model_validate(payload)


def test_result_outcome_must_match_stage():
    payload = make_candidate_result().model_dump()
    payload["stage"] = "insufficient_evidence"

    with pytest.raises(
        ValidationError,
        match="outcome and stage must agree",
    ):
        S05GraphResult.model_validate(payload)


def test_abstention_cannot_contain_report():
    payload = S05GraphResult(
        task_id=TASK_ID,
        outcome="insufficient_evidence",
        stage="insufficient_evidence",
    ).model_dump()

    payload["candidate"] = make_draft().model_dump()

    with pytest.raises(
        ValidationError,
        match="abstention cannot contain a report candidate",
    ):
        S05GraphResult.model_validate(payload)


def test_result_rejects_cross_task_reference():
    payload = make_candidate_result().model_dump()

    other_task = UUID(
        "00000000-0000-4000-8000-000000000002"
    )

    reference = payload["candidate"]["sections"][0][
        "fixture_references"
    ][0]

    reference["task_id"] = other_task

    with pytest.raises(
        ValidationError,
        match="cross-task fixture reference",
    ):
        S05GraphResult.model_validate(payload)


def test_result_rejects_cross_attempt_reference():
    payload = make_candidate_result().model_dump()

    reference = payload["candidate"]["sections"][0][
        "fixture_references"
    ][0]

    reference["attempt_id"] = UUID(
        "00000000-0000-4000-8000-000000000003"
    )

    with pytest.raises(
        ValidationError,
        match="cross-attempt fixture reference",
    ):
        S05GraphResult.model_validate(payload)


def test_graph_state_declares_expected_channels():
    fields = set(S05GraphState.__annotations__)

    assert fields == {
        "task_id",
        "attempt_id",
        "question",
        "scope",
        "plan",
        "research_output",
        "evidence_ids",
        "coverage",
        "fixture_coverage",
        "draft_report",
        "result",
        "stage",
        "repair_used",
        "budget_snapshot",
        "counters",
        "error_category",
        "versions",
    }


# Additional exact-boundary tests for WP02-06B.
# All negative cases start from valid baseline data.


@pytest.mark.parametrize("character", ["x", "ệ", "😀"])
def test_additional_boundary_question_character_limit(character):
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import S05GraphInput

    valid = S05GraphInput(
        task_id=UUID(int=1),
        question=character * 4000,
    )

    assert len(valid.question) == 4000

    with pytest.raises(ValidationError):
        S05GraphInput(
            task_id=valid.task_id,
            question=valid.question + character,
        )


@pytest.mark.parametrize("character", ["x", "ệ", "😀"])
def test_additional_boundary_scope_utf8_byte_limit(character):
    import json
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import S05GraphInput
    from agentops_api.agent.s05.validation import (
        create_execution_context,
    )

    def serialized_size(scope):
        return len(
            json.dumps(
                scope,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )

    overhead = serialized_size({"value": ""})
    available = 8192 - overhead

    width = len(character.encode("utf-8"))
    count, remainder = divmod(available, width)

    text = character * count + "x" * remainder

    scope = {"value": text}

    assert serialized_size(scope) == 8192

    valid = S05GraphInput(
        task_id=UUID(int=1),
        question="Synthetic UTF-8 boundary test",
        scope=scope,
    )

    context = create_execution_context(valid)

    assert len(context.scope_json.encode("utf-8")) == 8192

    invalid_scope = {"value": text + "x"}

    assert serialized_size(invalid_scope) == 8193

    with pytest.raises(ValidationError):
        S05GraphInput(
            task_id=valid.task_id,
            question=valid.question,
            scope=invalid_scope,
        )


@pytest.mark.parametrize(
    "container_type",
    ["dict", "list", "mixed"],
)
def test_additional_boundary_scope_depth(container_type):
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import S05GraphInput

    def wrap(value, index):
        if container_type == "dict":
            return {"nested": value}

        if container_type == "list":
            return [value]

        return {"nested": value} if index % 2 else [value]

    value = "leaf"

    for index in range(4):
        value = wrap(value, index)

    # Root dictionary is depth 0.
    # The leaf value is at depth 5.
    valid_scope = {"root": value}

    valid = S05GraphInput(
        task_id=UUID(int=1),
        question="Synthetic nesting boundary",
        scope=valid_scope,
    )

    assert valid.scope == valid_scope

    # Adding one wrapper moves the leaf to depth 6.
    invalid_scope = {"root": wrap(value, 4)}

    with pytest.raises(ValidationError):
        S05GraphInput(
            task_id=valid.task_id,
            question=valid.question,
            scope=invalid_scope,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        ("tuple",),
        {"set"},
        b"bytes",
    ],
)
def test_additional_boundary_nested_json_values(invalid_value):
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import S05GraphInput

    valid = S05GraphInput(
        task_id=UUID(int=1),
        question="Synthetic nested JSON validation",
        scope={"nested": [{"value": "valid"}]},
    )

    assert valid.scope["nested"][0]["value"] == "valid"

    with pytest.raises(ValidationError):
        S05GraphInput(
            task_id=valid.task_id,
            question=valid.question,
            scope={
                "nested": [
                    {"value": invalid_value},
                ],
            },
        )


def test_additional_boundary_non_string_nested_key():
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import S05GraphInput

    valid = S05GraphInput(
        task_id=UUID(int=1),
        question="Synthetic JSON key validation",
        scope={"nested": {"1": "valid"}},
    )

    assert valid.scope["nested"]["1"] == "valid"

    with pytest.raises(ValidationError):
        S05GraphInput(
            task_id=valid.task_id,
            question=valid.question,
            scope={"nested": {1: "valid"}},
        )


@pytest.mark.parametrize(
    "field",
    ["question", "query"],
)
@pytest.mark.parametrize(
    "character",
    ["x", "ệ"],
)
def test_additional_boundary_subquestion_text_limit(
    field,
    character,
):
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ResearchSubquestion,
    )

    fields = {
        "subquestion_id": "q1",
        "question": "Synthetic research question",
        "query": "fixture:market-overview",
    }

    fields[field] = character * 1000

    valid = ResearchSubquestion(**fields)

    assert len(getattr(valid, field)) == 1000

    invalid = dict(fields)
    invalid[field] += character

    with pytest.raises(ValidationError):
        ResearchSubquestion(**invalid)


def test_additional_boundary_plan_size():
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ResearchPlan,
        ResearchSubquestion,
    )

    items = tuple(
        ResearchSubquestion(
            subquestion_id=f"q{number}",
            question="Synthetic boundary question",
            query="fixture:market-overview",
        )
        for number in range(1, 5)
    )

    valid = ResearchPlan(subquestions=items)

    assert len(valid.subquestions) == 4

    # Four identifiers are allowed. A fifth entry necessarily
    # exceeds the size bound and repeats an allowed identifier.
    with pytest.raises(ValidationError) as caught:
        ResearchPlan(
            subquestions=items + (items[0],),
        )

    assert any(
        error["type"] == "too_long"
        and error["loc"] == ("subquestions",)
        for error in caught.value.errors()
    )


def test_additional_boundary_empty_plan_rejected():
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ResearchPlan,
        ResearchSubquestion,
    )

    item = ResearchSubquestion(
        subquestion_id="q1",
        question="Synthetic boundary question",
        query="fixture:market-overview",
    )

    valid = ResearchPlan(subquestions=(item,))

    assert len(valid.subquestions) == 1

    with pytest.raises(ValidationError):
        ResearchPlan(subquestions=())


def test_additional_boundary_maximum_assumptions():
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ResearchPlan,
        ResearchSubquestion,
    )

    item = ResearchSubquestion(
        subquestion_id="q1",
        question="Synthetic boundary question",
        query="fixture:market-overview",
    )

    notes = tuple(
        f"Synthetic assumption {index}"
        for index in range(4)
    )

    valid = ResearchPlan(
        subquestions=(item,),
        assumptions=notes,
    )

    assert len(valid.assumptions) == 4

    with pytest.raises(ValidationError):
        ResearchPlan(
            subquestions=valid.subquestions,
            assumptions=notes + ("Fifth assumption",),
        )


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ("adapter_invocations", 4, 5),
        ("repair_attempts", 1, 2),
        ("adapter_invocations", 0, -1),
        ("repair_attempts", 0, -1),
    ],
)
def test_additional_boundary_execution_counters(
    field,
    valid_value,
    invalid_value,
):
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ExecutionCounters,
    )

    fields = {
        "adapter_invocations": 4,
        "repair_attempts": 0,
    }

    fields[field] = valid_value

    valid = ExecutionCounters(**fields)

    assert getattr(valid, field) == valid_value

    invalid = dict(fields)
    invalid[field] = invalid_value

    with pytest.raises(ValidationError):
        ExecutionCounters(**invalid)


def test_additional_boundary_repair_requires_invocation():
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        ExecutionCounters,
    )

    valid = ExecutionCounters(
        adapter_invocations=1,
        repair_attempts=1,
    )

    assert valid.repair_attempts == 1

    with pytest.raises(ValidationError):
        ExecutionCounters(
            adapter_invocations=0,
            repair_attempts=valid.repair_attempts,
        )


@pytest.mark.parametrize("character", ["x", "ệ", "😀"])
def test_additional_boundary_fixture_content_limit(character):
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        FixtureRecord,
        FixtureReference,
    )

    reference = FixtureReference(
        fixture_id="fixture-boundary-test",
        task_id=UUID(int=1),
        attempt_id=None,
    )

    valid = FixtureRecord(
        reference=reference,
        subquestion_id="q1",
        title="Synthetic boundary fixture",
        content=character * 4000,
    )

    assert len(valid.content) == 4000

    with pytest.raises(ValidationError):
        FixtureRecord(
            reference=reference,
            subquestion_id=valid.subquestion_id,
            title=valid.title,
            content=valid.content + character,
        )


@pytest.mark.parametrize(
    "invalid_coverage",
    [
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        1,
        "1.0",
    ],
)
def test_additional_boundary_fixture_coverage(invalid_coverage):
    from uuid import UUID
    from pydantic import ValidationError
    from agentops_api.agent.s05.contract import (
        FixtureRecord,
        FixtureReference,
        ResearchOutput,
    )

    record = FixtureRecord(
        reference=FixtureReference(
            fixture_id="fixture-boundary-test",
            task_id=UUID(int=1),
            attempt_id=None,
        ),
        subquestion_id="q1",
        title="Synthetic coverage fixture",
        content="Synthetic test data only.",
    )

    valid = ResearchOutput(
        records=(record,),
        gaps=(),
        conflicts=(),
        fixture_coverage=1.0,
    )

    assert valid.fixture_coverage == 1.0

    with pytest.raises(ValidationError):
        ResearchOutput(
            records=valid.records,
            gaps=valid.gaps,
            conflicts=valid.conflicts,
            fixture_coverage=invalid_coverage,
        )
