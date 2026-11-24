"""S04-WP03-04 offline security boundary verification."""

import socket

import pytest
from uuid import uuid4

from agentops_api.agent.contract import GraphInput
from agentops_api.agent.workflow import run_offline_graph


def make_request():
    return GraphInput(
        task_id=uuid4(),
        question="Offline security verification",
    )


def test_offline_graph_attempts_no_socket_connections(monkeypatch):
    attempts = []

    def forbidden_connect(*args, **kwargs):
        attempts.append("socket connection attempted")
        raise AssertionError("Network access is forbidden in S04")

    monkeypatch.setattr(
        socket.socket,
        "connect",
        forbidden_connect,
    )
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        forbidden_connect,
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        forbidden_connect,
    )

    result = run_offline_graph(make_request())

    assert attempts == []
    assert result.outcome == "insufficient_evidence"
    assert result.publishable is False


def test_offline_graph_needs_no_dns_resolution(monkeypatch):
    attempts = []

    def forbidden_dns(*args, **kwargs):
        attempts.append("DNS lookup attempted")
        raise AssertionError("DNS resolution is forbidden in S04")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        forbidden_dns,
    )
    monkeypatch.setattr(
        socket,
        "gethostbyname",
        forbidden_dns,
    )

    result = run_offline_graph(make_request())

    assert attempts == []
    assert result.evidence_ids == []
    assert result.publishable is False


def test_offline_graph_attempts_no_database_operations(monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.engine import Connection

    attempts = []

    def forbidden_operation(name):
        def blocked(*args, **kwargs):
            attempts.append(name)
            raise AssertionError(
                "Database operation forbidden in S04"
            )
        return blocked

    for method in ("execute", "commit", "flush", "delete", "add"):
        monkeypatch.setattr(
            AsyncSession,
            method,
            forbidden_operation("AsyncSession." + method),
        )

    for method in ("execute", "commit"):
        monkeypatch.setattr(
            Connection,
            method,
            forbidden_operation("Connection." + method),
        )

    result = run_offline_graph(make_request())

    assert attempts == []
    assert result.outcome == "insufficient_evidence"
    assert result.publishable is False


def test_agent_modules_do_not_import_db_or_publication_layers():
    import ast
    from pathlib import Path

    agent_dir = Path(__file__).resolve().parents[1] / (
        "src/agentops_api/agent"
    )

    forbidden = (
        "agentops_api.core.database",
        "agentops_api.core.orm",
        "agentops_api.repositories",
        "agentops_api.services",
        "agentops_api.api",
        "agentops_api.models",
        "sqlalchemy",
    )

    violations = []

    for path in sorted(agent_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    violations.append(
                        f"{path.name}: relative import requires review"
                    )
                    continue
                names = [node.module or ""]
            else:
                continue

            for name in names:
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in forbidden
                ):
                    violations.append(f"{path.name}: {name}")

    assert violations == []


def test_offline_graph_does_not_call_research_layers(monkeypatch):
    import inspect

    from agentops_api.repositories import research as repository
    from agentops_api.services import research as service

    attempts = []

    def forbidden_call(name):
        def blocked(*args, **kwargs):
            attempts.append(name)
            raise AssertionError(
                f"Research layer call forbidden: {name}"
            )
        return blocked

    for layer in (repository, service):
        for name, obj in vars(layer).items():
            if name.startswith("_"):
                continue

            if not (
                inspect.isfunction(obj)
                or inspect.iscoroutinefunction(obj)
            ):
                continue

            # Patch only functions defined in this module,
            # not imported library or standard functions.
            if getattr(obj, "__module__", None) != layer.__name__:
                continue

            monkeypatch.setattr(
                layer,
                name,
                forbidden_call(layer.__name__ + "." + name),
            )

    result = run_offline_graph(make_request())

    assert attempts == []
    assert result.outcome == "insufficient_evidence"
    assert result.publishable is False


def test_candidate_cannot_claim_publication_or_evidence():
    result = run_offline_graph(make_request())

    assert result.outcome == "insufficient_evidence"
    assert result.stage == "fixture_complete"
    assert result.publishable is False
    assert result.coverage == 0.0
    assert result.evidence_ids == []
    assert result.error_category is None

    # The typed result forbids arbitrary publication metadata.
    from pydantic import ValidationError

    payload = result.model_dump()
    payload["published_report_id"] = "fabricated-report"

    with pytest.raises(ValidationError):
        type(result).model_validate(payload)
