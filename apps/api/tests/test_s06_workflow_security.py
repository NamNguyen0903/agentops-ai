"""Adversarial offline graph boundaries."""

import ast
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from agentops_api.agent.s06 import workflow
from agentops_api.agent.s06.workflow_contracts import (
    WorkflowRejected,
)
from agentops_api.agent.s06.workflow import run_offline

from test_s06_evidence_domain import scope
from test_s06_workflow import request


def test_tampered_evidence_aborts_before_writer(monkeypatch):
    context = scope()
    value = request(context)

    forged = replace(
        value.evidence[0],
        content_hash=b"x" * 32,
    )

    value = replace(
        value,
        evidence=(forged, value.evidence[1]),
    )

    calls = []

    def forbidden_writer(*args, **kwargs):
        calls.append(True)
        raise AssertionError("writer must not execute")

    monkeypatch.setattr(
        workflow,
        "write_candidate",
        forbidden_writer,
    )

    with pytest.raises(WorkflowRejected):
        run_offline(value)

    assert calls == []


def test_insufficient_evidence_never_calls_writer(monkeypatch):
    calls = []

    def forbidden_writer(*args, **kwargs):
        calls.append(True)
        raise AssertionError("writer must not execute")

    monkeypatch.setattr(
        workflow,
        "write_candidate",
        forbidden_writer,
    )

    result = run_offline(
        request(scope(), 1)
    )

    assert result.candidate is None
    assert calls == []


def test_writer_forgery_cannot_escape_validation(monkeypatch):
    original = workflow.write_candidate

    def forged(*args, **kwargs):
        candidate = original(*args, **kwargs)

        return replace(
            candidate,
            publishable=True,
        )

    monkeypatch.setattr(
        workflow,
        "write_candidate",
        forged,
    )

    with pytest.raises(WorkflowRejected):
        run_offline(request(scope()))


def test_runtime_error_sanitized(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError(
            "private-provider-secret-and-raw-payload"
        )

    monkeypatch.setattr(
        workflow,
        "write_candidate",
        broken,
    )

    with pytest.raises(WorkflowRejected) as exc:
        run_offline(request(scope()))

    assert str(exc.value) == "invalid_workflow_input"


def test_no_external_socket_connection(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError(
            "external connection forbidden"
        )

    # Do not forbid socketpair(): asyncio may need
    # an internal wakeup descriptor.
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        forbidden,
    )

    monkeypatch.setattr(
        socket,
        "create_connection",
        forbidden,
    )

    monkeypatch.setattr(
        socket.socket,
        "connect",
        forbidden,
    )

    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        forbidden,
    )

    result = run_offline(
        request(scope())
    )

    assert result.publishable is False
    assert calls == []


def test_graph_has_no_persistence_or_tools():
    graph = workflow._build_graph()

    assert graph.checkpointer is None

    nodes = set(
        graph.get_graph().nodes
    )

    assert nodes == {
        "__start__",
        "__end__",
        "assess",
        "write",
        "citations",
        "insufficient",
    }


def test_graph_recursion_limit_fixed():
    assert workflow.RECURSION_LIMIT == 12


def test_no_caller_graph_config():
    with pytest.raises(TypeError):
        run_offline(
            request(scope()),
            config={"recursion_limit": 1000},
        )


def test_new_runtime_modules_import_boundaries():
    root = Path(workflow.__file__).parent

    allowed = {
        "dataclasses",
        "typing",
        "uuid",
        "langgraph.graph",
    }

    modules = (
        "workflow.py",
        "workflow_contracts.py",
        "evidence_validation.py",
        "citations.py",
    )

    for name in modules:
        tree = ast.parse(
            (root / name).read_text()
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed

            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module in allowed

                else:
                    assert node.level == 1
                    assert node.module in {
                        "evidence",
                        "evidence_validation",
                        "workflow_contracts",
                        "citations",
                    }


def test_no_lifecycle_or_publication_calls():
    root = Path(workflow.__file__).parent

    forbidden = {
        "commit",
        "rollback",
        "publish",
        "publish_report",
        "create_engine",
        "create_async_engine",
        "getaddrinfo",
        "connect",
        "eval",
        "exec",
        "open",
    }

    for name in (
        "workflow.py",
        "workflow_contracts.py",
        "evidence_validation.py",
        "citations.py",
    ):
        tree = ast.parse(
            (root / name).read_text()
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func

                if isinstance(target, ast.Attribute):
                    assert target.attr not in forbidden

                elif isinstance(target, ast.Name):
                    assert target.id not in forbidden
