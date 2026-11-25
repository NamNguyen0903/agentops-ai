"""Application orchestration and security unit tests."""

import asyncio
import ast
import socket
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.workflow import run_offline
from agentops_api.agent.s06.workflow_contracts import (
    WorkflowInput,
)
from agentops_api.services import s06_workflow as service

from test_s06_evidence_domain import scope
from test_s06_workflow import QUESTION, snapshot


def execute(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture(autouse=True)
def disable_tracing(monkeypatch):
    for flag in service.TRACING_FLAGS:
        monkeypatch.setenv(flag, "false")


def test_fixture_acquisition_uses_shared_budget():
    budget = Budget()

    records = service.fixture_acquire(
        scope(),
        QUESTION,
        budget,
    )

    assert len(records) == 2
    assert all(item.synthetic is True for item in records)

    assert len({
        item.retrieved_url for item in records
    }) == 2

    usage = budget.snapshot()

    assert usage.searches == 2
    assert usage.retrievals == 4


def test_fixture_acquisition_has_no_network(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    records = service.fixture_acquire(
        scope(),
        QUESTION,
        Budget(),
    )

    assert len(records) == 2
    assert calls == []


def test_application_pipeline(monkeypatch):
    context = scope()
    records = snapshot(context)
    session = object()

    require_task = AsyncMock(
        return_value=None
    )

    store = AsyncMock(
        return_value=None
    )

    load = AsyncMock(
        side_effect=[records, records]
    )

    monkeypatch.setattr(
        service,
        "require_transaction",
        lambda session: None,
    )

    monkeypatch.setattr(
        service,
        "require_task",
        require_task,
    )

    monkeypatch.setattr(
        service,
        "fixture_acquire",
        lambda *args: records,
    )

    monkeypatch.setattr(
        service,
        "store_evidence",
        store,
    )

    monkeypatch.setattr(
        service,
        "list_evidence",
        load,
    )

    outcome = execute(
        service.run_fixture_workflow(
            session,
            scope=context,
            question=QUESTION,
        )
    )

    assert outcome.status == "synthetic_candidate"
    assert outcome.publishable is False
    assert outcome.real_evidence_count == 0

    assert store.await_count == 2
    assert load.await_count == 2
    require_task.assert_awaited_once_with(
        session, context
    )


@pytest.mark.parametrize("flag", service.TRACING_FLAGS)
@pytest.mark.parametrize("value", ["true", "1", "unexpected"])
def test_tracing_denied_before_database(
    monkeypatch,
    flag,
    value,
):
    monkeypatch.setenv(flag, value)

    lock = AsyncMock()

    monkeypatch.setattr(
        service,
        "require_transaction",
        lambda session: None,
    )

    monkeypatch.setattr(
        service,
        "require_task",
        lock,
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        execute(
            service.run_fixture_workflow(
                object(),
                scope=scope(),
                question=QUESTION,
            )
        )

    lock.assert_not_awaited()


def test_unauthorized_task_denied_before_acquisition(monkeypatch):
    calls = []

    def acquire(*args):
        calls.append(True)
        raise AssertionError("unexpected acquisition")

    monkeypatch.setattr(
        service,
        "require_transaction",
        lambda session: None,
    )

    monkeypatch.setattr(
        service,
        "require_task",
        AsyncMock(
            side_effect=ValueError("private task details")
        ),
    )

    monkeypatch.setattr(
        service,
        "fixture_acquire",
        acquire,
    )

    with pytest.raises(
        service.OfflineWorkflowRejected
    ) as exc:
        execute(
            service.run_fixture_workflow(
                object(),
                scope=scope(),
                question=QUESTION,
            )
        )

    assert str(exc.value) == "offline_workflow_rejected"
    assert calls == []


def test_no_transaction_denied():
    session = SimpleNamespace(
        in_transaction=lambda: False
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        execute(
            service.run_fixture_workflow(
                session,
                scope=scope(),
                question=QUESTION,
            )
        )


def test_deadline_denied(monkeypatch):
    times = iter([0.0, 31.0])

    monkeypatch.setattr(
        service,
        "monotonic",
        lambda: next(times),
    )

    monkeypatch.setattr(
        service,
        "require_transaction",
        lambda session: None,
    )

    monkeypatch.setattr(
        service,
        "require_task",
        AsyncMock(),
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        execute(
            service.run_fixture_workflow(
                object(),
                scope=scope(),
                question=QUESTION,
            )
        )


def verify_with_snapshot(
    monkeypatch,
    context,
    records,
    outcome,
):
    monkeypatch.setattr(
        service,
        "require_transaction",
        lambda session: None,
    )

    monkeypatch.setattr(
        service,
        "list_evidence",
        AsyncMock(return_value=records),
    )

    return execute(
        service.revalidate_outcome(
            object(),
            scope=context,
            question=QUESTION,
            outcome=outcome,
        )
    )


def test_repository_revalidation_positive(monkeypatch):
    context = scope()
    records = snapshot(context)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    assert verify_with_snapshot(
        monkeypatch,
        context,
        records,
        outcome,
    ) == outcome


def test_missing_evidence_denied(monkeypatch):
    context = scope()
    records = snapshot(context, 3)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        verify_with_snapshot(
            monkeypatch,
            context,
            records[1:],
            outcome,
        )


def test_changed_evidence_denied(monkeypatch):
    context = scope()
    records = snapshot(context)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    changed = replace(
        records[0],
        content_hash=b"x" * 32,
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        verify_with_snapshot(
            monkeypatch,
            context,
            (changed, records[1]),
            outcome,
        )


def test_cross_scope_repository_data_denied(monkeypatch):
    context = scope()
    records = snapshot(context)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        verify_with_snapshot(
            monkeypatch,
            context,
            snapshot(scope()),
            outcome,
        )


@pytest.mark.parametrize("field,value", [
    ("publishable", True),
    ("real_evidence_count", 1),
    ("real_evidence_count", False),
    ("synthetic_evidence_count", True),
    ("synthetic_evidence_count", 999),
    ("workflow_version", "unapproved"),
    ("status", "published"),
    ("reason", "unexpected"),
])
def test_forged_outcome_denied(
    monkeypatch,
    field,
    value,
):
    context = scope()
    records = snapshot(context)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    with pytest.raises(service.OfflineWorkflowRejected):
        verify_with_snapshot(
            monkeypatch,
            context,
            records,
            replace(outcome, **{field: value}),
        )


def test_insufficient_outcome_revalidated(monkeypatch):
    context = scope()
    records = snapshot(context, 1)

    outcome = run_offline(
        WorkflowInput(
            scope=context,
            question=QUESTION,
            evidence=records,
        )
    )

    result = verify_with_snapshot(
        monkeypatch,
        context,
        records,
        outcome,
    )

    assert result.candidate is None
    assert result.status == "insufficient_evidence"
    assert result.publishable is False


def test_no_transaction_or_lifecycle_mutation_calls():
    tree = ast.parse(
        Path(service.__file__).read_text()
    )

    forbidden = {
        "commit",
        "rollback",
        "delete",
        "update",
        "publish",
        "publish_report",
        "search_live",
        "retrieve_live",
        "create_engine",
        "create_async_engine",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func

            if isinstance(target, ast.Name):
                assert target.id not in forbidden

            elif isinstance(target, ast.Attribute):
                assert target.attr not in forbidden
