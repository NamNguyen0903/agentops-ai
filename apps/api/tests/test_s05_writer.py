"""Writer and Report Validation node tests."""

from copy import deepcopy
from uuid import UUID

import pytest

from agentops_api.agent.s05 import (
    adapters,
    evidence,
    planner,
    report,
    research,
    writer,
)
from agentops_api.agent.s05.contract import (
    DraftReport,
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
            task_id=UUID(int=601),
            attempt_id=UUID(int=602),
            question="Synthetic writer workflow.",
            scope={"region": "offline"},
        )
    )


def _validated_state(context, incomplete=False):
    initial = build_initial_state(context)

    planned = {
        **initial,
        **planner.planner_node(initial, context),
    }

    if incomplete:
        plan = planned["plan"]
        first = plan.subquestions[0]

        changed = ResearchSubquestion(
            subquestion_id=first.subquestion_id,
            question=first.question,
            query="fixture:unregistered-writer-test",
        )

        planned["plan"] = ResearchPlan(
            subquestions=(
                changed,
            ) + plan.subquestions[1:],
            assumptions=plan.assumptions,
        )

    researched = {
        **planned,
        **research.research_node(planned, context),
    }

    return {
        **researched,
        **evidence.evidence_validation_node(
            researched,
            context,
        ),
    }


@pytest.fixture
def validated_state(context):
    return _validated_state(context)


@pytest.fixture
def written_state(context, validated_state):
    return {
        **validated_state,
        **writer.writer_node(
            validated_state,
            context,
        ),
    }


def _assert_safe_error(operation, error_type, category):
    with pytest.raises(error_type) as caught:
        operation()

    assert type(caught.value) is error_type
    assert caught.value.category == category
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def _assert_security_error(operation):
    _assert_safe_error(
        operation,
        S05StateIntegrityError,
        "security_violation",
    )


def test_writer_returns_only_owned_channels(
    context, validated_state
):
    original = deepcopy(validated_state)

    update = writer.writer_node(
        validated_state,
        context,
    )

    assert set(update) == {
        "draft_report",
        "stage",
        "counters",
    }

    assert type(update["draft_report"]) is DraftReport
    assert update["draft_report"].synthetic is True
    assert update["stage"] == "written"

    assert update["counters"] == ExecutionCounters(
        adapter_invocations=3,
    )

    assert validated_state == original

    merged = {**validated_state, **update}

    verify_protected_state(merged, context)

    assert merged["evidence_ids"] == ()
    assert merged["coverage"] == 0.0
    assert merged["result"] is None


def test_writer_is_deterministic(
    context, validated_state
):
    first = writer.writer_node(
        validated_state, context
    )

    second = writer.writer_node(
        validated_state, context
    )

    assert first == second

    assert (
        first["draft_report"]
        is not second["draft_report"]
    )


def test_writer_invokes_adapter_once_with_independent_inputs(
    context, validated_state, monkeypatch
):
    original = writer.writer_fixture
    calls = []

    def spy(adapter_context, plan, output):
        calls.append(True)

        assert adapter_context is not context
        assert plan is not validated_state["plan"]

        assert (
            output
            is not validated_state["research_output"]
        )

        assert (
            output.records[0]
            is not
            validated_state["research_output"].records[0]
        )

        return original(
            adapter_context,
            plan,
            output,
        )

    monkeypatch.setattr(
        writer, "writer_fixture", spy
    )

    update = writer.writer_node(
        validated_state, context
    )

    assert len(calls) == 1
    assert update["counters"].adapter_invocations == 3


def test_writer_rejects_insufficient_fixtures(
    context, monkeypatch
):
    state = _validated_state(
        context,
        incomplete=True,
    )

    assert evidence.route_after_evidence(
        state, context
    ) == "abstain"

    def forbidden(*args, **kwargs):
        pytest.fail("Writer must not run")

    monkeypatch.setattr(
        writer, "writer_fixture", forbidden
    )

    _assert_security_error(
        lambda: writer.writer_node(state, context)
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "researched"),
        ("stage", "written"),
        ("stage", None),
        ("plan", None),
        ("research_output", None),
        ("fixture_coverage", 0.75),
        ("fixture_coverage", 1),
        ("draft_report", {}),
        ("result", {}),
        ("repair_used", True),
        ("repair_used", 0),
        ("error_category", "execution_failed"),
        ("counters", ExecutionCounters()),
        (
            "counters",
            ExecutionCounters(adapter_invocations=3),
        ),
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("scope", {"changed": True}),
        ("evidence_ids", ("fabricated",)),
        ("coverage", 1.0),
    ],
)
def test_writer_rejects_invalid_initial_state(
    context, validated_state, monkeypatch, field, value
):
    validated_state[field] = value

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid state reached Writer adapter")

    monkeypatch.setattr(
        writer, "writer_fixture", forbidden
    )

    _assert_security_error(
        lambda: writer.writer_node(
            validated_state,
            context,
        )
    )


@pytest.mark.parametrize(
    "mutation",
    ["none", "mapping", "blank_title"],
)
def test_writer_rejects_malformed_output(
    context, validated_state, monkeypatch, mutation
):
    candidate = adapters.writer_fixture(
        context,
        validated_state["plan"],
        validated_state["research_output"],
    )

    if mutation == "none":
        bad = None
    elif mutation == "mapping":
        bad = candidate.model_dump()
    else:
        bad = candidate.model_copy(
            update={"title": ""}
        )

    monkeypatch.setattr(
        writer,
        "writer_fixture",
        lambda *args: bad,
    )

    _assert_safe_error(
        lambda: writer.writer_node(
            validated_state, context
        ),
        report.S05ReportError,
        "invalid_output",
    )


def _bad_reference_candidate(candidate, mutation):
    section = candidate.sections[0]
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
    }

    changed_reference = reference.model_copy(
        update=changes[mutation]
    )

    changed_section = section.model_copy(
        update={
            "fixture_references": (
                changed_reference,
            ) + section.fixture_references[1:]
        }
    )

    return candidate.model_copy(
        update={
            "sections": (
                changed_section,
            ) + candidate.sections[1:]
        }
    )


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "cross_task", "cross_attempt"],
)
def test_writer_rejects_unapproved_references(
    context, validated_state, monkeypatch, mutation
):
    candidate = adapters.writer_fixture(
        context,
        validated_state["plan"],
        validated_state["research_output"],
    )

    bad = _bad_reference_candidate(
        candidate, mutation
    )

    monkeypatch.setattr(
        writer,
        "writer_fixture",
        lambda *args: bad,
    )

    _assert_security_error(
        lambda: writer.writer_node(
            validated_state,
            context,
        )
    )


def test_writer_sanitizes_adapter_exception(
    context, validated_state, monkeypatch
):
    original = deepcopy(validated_state)
    calls = []

    def failing(*args):
        calls.append(True)
        raise RuntimeError("private synthetic marker")

    monkeypatch.setattr(
        writer, "writer_fixture", failing
    )

    _assert_safe_error(
        lambda: writer.writer_node(
            validated_state, context
        ),
        writer.S05WriterError,
        "execution_failed",
    )

    assert len(calls) == 1
    assert validated_state == original


@pytest.mark.parametrize(
    "mutation",
    ["context", "plan", "output", "state"],
)
@pytest.mark.parametrize(
    "raise_after_mutation",
    [False, True],
)
def test_writer_detects_adapter_boundary_mutation(
    context,
    validated_state,
    monkeypatch,
    mutation,
    raise_after_mutation,
):
    candidate = adapters.writer_fixture(
        context,
        validated_state["plan"],
        validated_state["research_output"],
    )

    def mutate(adapter_context, plan, output):
        if mutation == "context":
            object.__setattr__(
                adapter_context,
                "question",
                "Changed context",
            )

        elif mutation == "plan":
            object.__setattr__(
                plan.subquestions[0],
                "query",
                "fixture:unapproved",
            )

        elif mutation == "output":
            object.__setattr__(
                output.records[0],
                "content",
                "Changed record",
            )

        else:
            validated_state["stage"] = "written"

        if raise_after_mutation:
            raise RuntimeError("private marker")

        return candidate

    monkeypatch.setattr(
        writer, "writer_fixture", mutate
    )

    _assert_security_error(
        lambda: writer.writer_node(
            validated_state,
            context,
        )
    )


def test_report_validation_returns_only_owned_channels(
    context, written_state
):
    original = deepcopy(written_state)

    update = writer.report_validation_node(
        written_state, context
    )

    assert set(update) == {
        "draft_report",
        "stage",
    }

    assert update["stage"] == "report_validated"
    assert update["draft_report"] == original["draft_report"]

    assert (
        update["draft_report"]
        is not written_state["draft_report"]
    )

    assert written_state == original

    merged = {**written_state, **update}

    verify_protected_state(merged, context)

    assert merged["counters"].adapter_invocations == 3
    assert merged["evidence_ids"] == ()
    assert merged["coverage"] == 0.0
    assert merged["result"] is None


def test_report_validation_invokes_no_adapters(
    context, written_state, monkeypatch
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

    monkeypatch.setattr(
        writer, "writer_fixture", forbidden
    )

    assert writer.report_validation_node(
        written_state, context
    )["stage"] == "report_validated"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "evidence_validated"),
        ("stage", "report_validated"),
        ("stage", None),
        ("plan", None),
        ("research_output", None),
        ("fixture_coverage", 0.25),
        ("fixture_coverage", 1),
        ("result", {}),
        ("repair_used", True),
        ("repair_used", 0),
        ("error_category", "execution_failed"),
        (
            "counters",
            ExecutionCounters(adapter_invocations=2),
        ),
        (
            "counters",
            ExecutionCounters(adapter_invocations=4),
        ),
        ("task_id", str(UUID(int=999))),
        ("attempt_id", None),
        ("evidence_ids", ("fabricated",)),
        ("coverage", 1.0),
    ],
)
def test_report_validation_rejects_invalid_state(
    context, written_state, field, value
):
    written_state[field] = value

    _assert_security_error(
        lambda: writer.report_validation_node(
            written_state, context
        )
    )


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "cross_task", "cross_attempt"],
)
def test_report_validation_rejects_tampered_references(
    context, written_state, mutation
):
    written_state["draft_report"] = (
        _bad_reference_candidate(
            written_state["draft_report"],
            mutation,
        )
    )

    _assert_security_error(
        lambda: writer.report_validation_node(
            written_state, context
        )
    )


def test_report_validation_rejects_malformed_draft(
    context, written_state
):
    written_state["draft_report"] = (
        written_state["draft_report"].model_copy(
            update={"summary": ""}
        )
    )

    _assert_safe_error(
        lambda: writer.report_validation_node(
            written_state, context
        ),
        report.S05ReportError,
        "invalid_output",
    )


# WP04-02C: SEC05 shared validator boundary regression.


def _sec05_mixed_writer_candidate(candidate):
    assert type(candidate) is DraftReport

    section = candidate.sections[0]
    reference = section.fixture_references[0]

    forged = reference.model_copy(
        update={"task_id": UUID(int=999)}
    )

    changed = section.model_copy(
        update={"fixture_references": (forged,)}
    )

    return candidate.model_copy(
        update={
            "title": "",
            "sections": (
                changed,
            ) + candidate.sections[1:]
        }
    )


def test_sec05_writer_mixed_error_fails_closed(
    context,
    validated_state,
    monkeypatch,
):
    original = deepcopy(validated_state)

    candidate = adapters.writer_fixture(
        context,
        validated_state["plan"],
        validated_state["research_output"],
    )

    assert report.validate_draft_report(
        context,
        validated_state["plan"],
        validated_state["research_output"],
        candidate,
    ) == candidate

    bad = _sec05_mixed_writer_candidate(
        candidate
    )

    calls = []

    def mixed_writer(*args):
        calls.append(True)
        return bad

    monkeypatch.setattr(
        writer,
        "writer_fixture",
        mixed_writer,
    )

    _assert_security_error(
        lambda: writer.writer_node(
            validated_state,
            context,
        )
    )

    assert len(calls) == 1
    assert validated_state == original
    assert validated_state["draft_report"] is None
    assert validated_state["result"] is None
    assert validated_state["repair_used"] is False


def test_sec05_report_validation_mixed_error_fails_closed(
    context,
    written_state,
    monkeypatch,
):
    assert writer.report_validation_node(
        written_state,
        context,
    )["stage"] == "report_validated"

    written_state["draft_report"] = (
        _sec05_mixed_writer_candidate(
            written_state["draft_report"]
        )
    )

    original = deepcopy(written_state)
    calls = []

    def forbidden(*args):
        calls.append(True)
        pytest.fail("Unexpected Writer invocation")

    monkeypatch.setattr(
        writer,
        "writer_fixture",
        forbidden,
    )

    _assert_security_error(
        lambda: writer.report_validation_node(
            written_state,
            context,
        )
    )

    assert calls == []
    assert written_state == original
    assert written_state["result"] is None
    assert written_state["repair_used"] is False
