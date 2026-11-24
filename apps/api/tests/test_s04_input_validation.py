"""S04-WP03 input boundary regression tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentops_api.agent.contract import GraphInput


def test_reject_whitespace_only_question():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="   \t   ",
        )


def test_reject_non_json_scope_object():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            scope={"unsafe": object()},
        )


def test_reject_scope_over_size_limit():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            scope={"payload": "x" * 8192},
        )


def test_accept_scope_within_size_limit():
    request = GraphInput(
        task_id=uuid4(),
        question="Offline research",
        scope={"payload": "x" * 100},
    )
    assert request.scope["payload"] == "x" * 100


def test_reject_excessive_scope_depth():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            scope={"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}},
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_reject_nonfinite_scope_number(value):
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            scope={"number": value},
        )


def test_reject_non_string_scope_key():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            scope={1: "invalid"},
        )


def test_accept_valid_nested_scope():
    request = GraphInput(
        task_id=uuid4(),
        question="  Compare two markets.  ",
        scope={
            "geography": ["VN", "SG"],
            "filters": {"active": True, "minimum": 0.5},
        },
    )

    assert request.question == "  Compare two markets.  "
    assert request.scope["filters"]["active"] is True


@pytest.mark.parametrize(
    "mutated_value",
    [
        object(),
        "x" * 9000,
    ],
)
def test_reject_mutated_scope_at_execution(mutated_value):
    from uuid import uuid4

    from agentops_api.agent import workflow
    from agentops_api.agent.contract import GraphInput

    request = GraphInput(
        task_id=uuid4(),
        question="Offline input integrity test",
        scope={"payload": "approved"},
    )

    request.scope["payload"] = mutated_value

    with pytest.raises(ValueError):
        workflow.run_offline_graph(request)


def test_reject_valid_scope_mutation_after_validation():
    from uuid import uuid4

    from agentops_api.agent import workflow
    from agentops_api.agent.contract import GraphInput

    request = GraphInput(
        task_id=uuid4(),
        question="Offline semantic integrity test",
        scope={"filters": {"region": "VN"}},
    )

    # The new value is valid JSON and satisfies scope limits,
    # but differs from the originally validated request.
    request.scope["filters"]["region"] = "UNAPPROVED"

    with pytest.raises(
        ValueError,
        match="scope changed after validation",
    ):
        workflow.run_offline_graph(request)


def test_external_scope_reference_cannot_change_execution():
    from uuid import uuid4

    from agentops_api.agent import workflow
    from agentops_api.agent.contract import GraphInput

    external_scope = {"filters": {"region": "VN"}}

    request = GraphInput(
        task_id=uuid4(),
        question="External reference integrity",
        scope=external_scope,
    )

    external_scope["filters"]["region"] = "UNAPPROVED"

    # Either the model has an independent copy or its
    # execution boundary must reject the mutated scope.
    if request.scope["filters"]["region"] != "VN":
        with pytest.raises(
            ValueError,
            match="scope changed after validation",
        ):
            workflow.run_offline_graph(request)
    else:
        result = workflow.run_offline_graph(request)
        assert result.publishable is False


def test_model_copy_update_cannot_bypass_scope_snapshot():
    from uuid import uuid4

    from agentops_api.agent import workflow
    from agentops_api.agent.contract import GraphInput

    request = GraphInput(
        task_id=uuid4(),
        question="Model copy integrity",
        scope={"filters": {"region": "VN"}},
    )

    modified = request.model_copy(
        update={"scope": {"filters": {"region": "UNAPPROVED"}}}
    )

    with pytest.raises(
        ValueError,
        match="scope changed after validation",
    ):
        workflow.run_offline_graph(modified)


def test_deep_copied_valid_request_still_executes():
    from uuid import uuid4

    from agentops_api.agent import workflow
    from agentops_api.agent.contract import GraphInput

    request = GraphInput(
        task_id=uuid4(),
        question="Deep copy integrity",
        scope={"filters": {"region": "VN"}},
    )

    copied = request.model_copy(deep=True)
    result = workflow.run_offline_graph(copied)

    assert result.outcome == "insufficient_evidence"
    assert result.publishable is False
    assert result.evidence_ids == []
