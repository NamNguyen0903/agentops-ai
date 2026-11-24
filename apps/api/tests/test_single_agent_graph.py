"""Focused S04 single-agent baseline tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentops_api.agent.contract import GraphInput, GraphResult
from agentops_api.agent.workflow import build_graph, run_offline_graph


def make_request() -> GraphInput:
    return GraphInput(
        task_id=uuid4(),
        question="Compare two example markets.",
        scope={"geography": "offline-test"},
    )


def test_single_node_graph_compiles():
    assert build_graph() is not None


def test_deterministic_outcome():
    request = make_request()
    first = run_offline_graph(request)
    second = run_offline_graph(request)
    assert first == second
    assert first.outcome == "insufficient_evidence"


def test_no_publication_or_fabricated_evidence():
    result = run_offline_graph(make_request())
    assert result.publishable is False
    assert result.evidence_ids == []
    assert result.coverage == 0.0
    assert result.stage == "fixture_complete"


def test_invalid_question_rejected():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="",
        )


def test_unknown_request_field_rejected():
    with pytest.raises(ValidationError):
        GraphInput(
            task_id=uuid4(),
            question="Offline research",
            unsafe_tool="external_network",
        )


def test_result_cannot_be_declared_publishable():
    valid = run_offline_graph(make_request())
    payload = valid.model_dump()
    payload["publishable"] = True

    with pytest.raises(ValidationError):
        GraphResult.model_validate(payload)


def test_version_metadata_present():
    result = run_offline_graph(make_request())
    assert result.versions.graph == "s04-single-agent-v1"
    assert result.versions.prompt == "none"
    assert result.versions.model == "none"
