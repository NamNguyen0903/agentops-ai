"""S04-WP03 fail-closed error boundary tests."""

from uuid import uuid4

import pytest

from agentops_api.agent import workflow
from agentops_api.agent.contract import GraphInput


def make_request():
    return GraphInput(
        task_id=uuid4(),
        question="Offline safe-error test",
    )


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("SECRET_API_KEY=private-value"),
        ConnectionError("postgres://user:password@private-host/db"),
        TimeoutError("Sensitive internal service information"),
    ],
)
def test_internal_errors_are_sanitized(
    monkeypatch,
    exception,
):
    class FailingGraph:
        def invoke(self, initial, config=None):
            raise exception

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: FailingGraph(),
    )

    with pytest.raises(Exception) as caught:
        workflow.run_offline_graph(make_request())

    error = caught.value

    assert type(error).__name__ == "GraphExecutionError"
    assert getattr(error, "category", None) == "execution_failed"
    assert str(error) == "offline graph execution failed"

    exposed = str(error)
    for secret in (
        "SECRET_API_KEY",
        "private-value",
        "postgres://",
        "password",
        "Sensitive internal",
    ):
        assert secret not in exposed


def test_invalid_graph_output_has_safe_category(monkeypatch):
    class InvalidGraph:
        def invoke(self, initial, config=None):
            return {"result": "SECRET_INTERNAL_DATA"}

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: InvalidGraph(),
    )

    with pytest.raises(Exception) as caught:
        workflow.run_offline_graph(make_request())

    error = caught.value

    assert type(error).__name__ == "GraphExecutionError"
    assert getattr(error, "category", None) == "invalid_output"
    assert str(error) == "invalid offline graph output"
    assert "SECRET_INTERNAL_DATA" not in str(error)


def test_public_traceback_hides_internal_exception(monkeypatch):
    import traceback

    class FailingGraph:
        def invoke(self, initial, config=None):
            raise RuntimeError("PRIVATE_TOKEN_DO_NOT_EXPOSE")

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: FailingGraph(),
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(make_request())

    error = caught.value
    rendered = "".join(
        traceback.format_exception(error)
    )

    assert error.category == "execution_failed"
    assert "offline graph execution failed" in rendered
    assert "PRIVATE_TOKEN_DO_NOT_EXPOSE" not in rendered
    assert error.__suppress_context__ is True


def test_graph_build_failure_is_sanitized(monkeypatch):
    def failing_build():
        raise RuntimeError("INTERNAL_BUILD_SECRET")

    monkeypatch.setattr(
        workflow,
        "build_graph",
        failing_build,
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(make_request())

    assert caught.value.category == "execution_failed"
    assert str(caught.value) == "offline graph execution failed"


def test_invalid_output_public_traceback_is_sanitized(monkeypatch):
    import traceback

    class InvalidGraph:
        def invoke(self, initial, config=None):
            return {"result": "PRIVATE_OUTPUT_SECRET"}

    monkeypatch.setattr(
        workflow,
        "build_graph",
        lambda: InvalidGraph(),
    )

    with pytest.raises(workflow.GraphExecutionError) as caught:
        workflow.run_offline_graph(make_request())

    error = caught.value
    rendered = "".join(
        traceback.format_exception(error)
    )

    assert error.category == "invalid_output"
    assert "invalid offline graph output" in rendered
    assert "PRIVATE_OUTPUT_SECRET" not in rendered
    assert error.__suppress_context__ is True
