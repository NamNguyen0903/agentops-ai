"""Repository statement and transaction contract tests.

No PostgreSQL connection is created in this module.
SQL behavior under concurrency is verified in WP03-B.
"""

import asyncio
from dataclasses import fields, replace
from types import SimpleNamespace

import pytest

from sqlalchemy.dialects import postgresql

from agentops_api.agent.s06.evidence import (
    EvidenceRecord,
    EvidenceRejected,
    EvidenceUnavailable,
    EvidenceLimitExceeded,
)
from agentops_api.repositories.evidence import (
    get_evidence,
    list_evidence,
    store_evidence,
)

from test_s06_evidence_domain import scope, record


def run(coroutine):
    return asyncio.run(coroutine)


def row(value):
    return SimpleNamespace(**{
        field.name: getattr(value, field.name)
        for field in fields(EvidenceRecord)
    })


class ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, answers=(), *, transaction=True):
        self.answers = list(answers)
        self.transaction = transaction
        self.statements = []

    def in_transaction(self):
        return self.transaction

    async def scalar(self, statement):
        self.statements.append(statement)
        assert self.answers, "Unexpected scalar query"
        return self.answers.pop(0)

    async def scalars(self, statement):
        self.statements.append(statement)
        assert self.answers, "Unexpected scalars query"
        return ScalarRows(self.answers.pop(0))

    async def commit(self):
        raise AssertionError("Repository must not commit")

    async def rollback(self):
        raise AssertionError("Repository must not rollback")

    async def execute(self, *args):
        raise AssertionError("Unexpected execute operation")


def sql(statement):
    return str(
        statement.compile(
            dialect=postgresql.dialect()
        )
    )


def test_insert_evidence_under_task_lock():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        None,
        0,
        value.id,
        row(value),
    ))

    result = run(store_evidence(
        session, scope=context, record=value
    ))

    assert result.created is True
    assert result.record == value
    assert not session.answers

    assert "FOR UPDATE" in sql(session.statements[0])

    statement = sql(session.statements[4])

    assert "INSERT INTO app.research_evidence" in statement
    assert "ON CONFLICT" in statement
    assert "RETURNING" in statement


def test_duplicate_reuses_existing_record():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        row(value),
    ))

    result = run(store_evidence(
        session, scope=context, record=value
    ))

    assert result.created is False
    assert result.record == value
    assert len(session.statements) == 3


@pytest.mark.parametrize("count", [20, 21, 100])
def test_task_wide_limit(count):
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        None,
        count,
    ))

    with pytest.raises(EvidenceLimitExceeded):
        run(store_evidence(
            session,
            scope=context,
            record=value,
        ))

    query = sql(session.statements[3])

    assert "research_evidence.owner_id" in query
    assert "research_evidence.task_id" in query
    assert "research_evidence.execution_id" not in query
    assert len(session.statements) == 4


@pytest.mark.parametrize("count", [
    None, True, -1, "20",
])
def test_invalid_count_rejected(count):
    context = scope()

    session = FakeSession((
        context.task_id,
        False,
        None,
        count,
    ))

    with pytest.raises(EvidenceRejected):
        run(store_evidence(
            session,
            scope=context,
            record=record(context),
        ))


def test_unavailable_task_denied():
    context = scope()
    session = FakeSession((None,))

    with pytest.raises(EvidenceUnavailable):
        run(store_evidence(
            session,
            scope=context,
            record=record(context),
        ))

    query = sql(session.statements[0])

    assert "research_tasks.owner_id" in query
    assert "research_tasks.deleted_at IS NULL" in query
    assert len(session.statements) == 1


@pytest.mark.parametrize("operation", [
    "store", "get", "list",
])
def test_explicit_transaction_required(operation):
    context = scope()
    value = record(context)

    session = FakeSession(transaction=False)

    with pytest.raises(RuntimeError, match="explicit transaction"):
        if operation == "store":
            run(store_evidence(
                session, scope=context, record=value
            ))
        elif operation == "get":
            run(get_evidence(
                session, scope=context, evidence_id=value.id
            ))
        else:
            run(list_evidence(session, scope=context))

    assert not session.statements


def test_get_evidence_scoped_query():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        row(value),
    ))

    assert run(get_evidence(
        session,
        scope=context,
        evidence_id=value.id,
    )) == value

    query = sql(session.statements[2])

    for field in (
        "owner_id", "task_id", "execution_id", "id"
    ):
        assert f"research_evidence.{field}" in query

    parameters = session.statements[2].compile(
        dialect=postgresql.dialect()
    ).params

    for expected in (
        context.owner_id,
        context.task_id,
        context.execution_id,
        value.id,
    ):
        assert expected in parameters.values()


def test_missing_evidence_returns_none():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        None,
    ))

    assert run(get_evidence(
        session,
        scope=context,
        evidence_id=value.id,
    )) is None


def test_list_evidence_scope_and_order():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        [row(value)],
    ))

    assert run(list_evidence(
        session, scope=context
    )) == (value,)

    query = sql(session.statements[2])

    assert "research_evidence.execution_id" in query
    assert "ORDER BY" in query
    assert "LIMIT" in query


def test_list_excessive_rows_rejected():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        [row(value)] * 21,
    ))

    with pytest.raises(EvidenceRejected):
        run(list_evidence(
            session, scope=context
        ))


def test_list_duplicate_rows_rejected():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        [row(value), row(value)],
    ))

    with pytest.raises(EvidenceRejected):
        run(list_evidence(
            session, scope=context
        ))


def test_cross_scope_insert_rejected_before_queries():
    context = scope()
    other = scope()
    session = FakeSession()

    with pytest.raises(EvidenceRejected):
        run(store_evidence(
            session,
            scope=context,
            record=record(other),
        ))

    assert not session.statements


def test_conflict_without_scoped_record_rejected():
    context = scope()

    session = FakeSession((
        context.task_id,
        False,
        None,
        0,
        None,
        None,
    ))

    with pytest.raises(EvidenceUnavailable):
        run(store_evidence(
            session,
            scope=context,
            record=record(context),
        ))


def test_tampered_database_content_rejected():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        row(replace(value, excerpt="tampered")),
    ))

    with pytest.raises(EvidenceRejected):
        run(get_evidence(
            session,
            scope=context,
            evidence_id=value.id,
        ))


def test_cross_execution_row_rejected():
    context = scope()
    value = record(context)

    session = FakeSession((
        context.task_id,
        False,
        row(record(
            replace(context, execution_id=scope().execution_id)
        )),
    ))

    with pytest.raises(EvidenceRejected):
        run(get_evidence(
            session,
            scope=context,
            evidence_id=value.id,
        ))



def test_legacy_scope_cannot_bypass_worker_attempt():
    context = scope()
    session = FakeSession((context.task_id, True))

    with pytest.raises(EvidenceUnavailable):
        run(store_evidence(
            session, scope=context, record=record(context),
        ))

    assert len(session.statements) == 2
    assert "research_execution_attempts" in sql(
        session.statements[1]
    )
