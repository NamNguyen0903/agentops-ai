"""Offline persistence contracts; no PostgreSQL verification is inferred here."""

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from agentops_api.models.research import ResearchTask
from agentops_api.repositories.research import ResearchScope, ResearchSubmission, submit_task


@pytest.mark.parametrize("question", ["", "   ", "x\x00y", "x" * 4001])
def test_reject_invalid_question(question):
    with pytest.raises(ValidationError):
        ResearchSubmission(question=question)


@pytest.mark.parametrize("scope", [
    {"unknown": "value"}, {"geography": 123},
    {"category": "x" * 2001}, {"time_scope": "x\x00y"},
])
def test_reject_invalid_scope(scope):
    with pytest.raises(ValidationError):
        ResearchSubmission.model_validate({"question": "Compare products", "scope": scope})


def test_canonical_fingerprint_and_validated_scope():
    first = ResearchSubmission(question="Compare products", scope=ResearchScope(competitors=("A", "B")))
    second = ResearchSubmission.model_validate(first.model_dump())
    assert first.fingerprint() == second.fingerprint()
    assert len(first.fingerprint()) == 32
    assert first.fingerprint() != ResearchSubmission(question="Different question").fingerprint()
    assert first.scope.model_dump(mode="json")["competitors"] == ["A", "B"]


def test_limits_can_be_configured_without_changing_database_schema():
    data = {"question": "x" * 4001}
    result = ResearchSubmission.model_validate(data, context={"question_limit": 5000})
    assert result.question == data["question"]


def test_scope_accepts_json_array_without_string_coercion():
    scope = ResearchScope.model_validate({"competitors": ["A", "B"]})
    assert scope.competitors == ("A", "B")
    with pytest.raises(ValidationError):
        ResearchScope.model_validate({"competitors": [123]})


def test_model_compiles_owner_and_retry_foreign_keys():
    ddl = str(CreateTable(ResearchTask.__table__).compile(dialect=postgresql.dialect()))
    assert "REFERENCES app.users (id) ON DELETE RESTRICT" in ddl
    assert "FOREIGN KEY(owner_id, retry_parent_id)" in ddl
    assert "UNIQUE (owner_id, idempotency_key)" in ddl
    assert "insufficient_evidence" in ddl
    assert {index.name for index in ResearchTask.__table__.indexes} == {
        "ix_research_tasks_owner_history", "ix_research_tasks_queue",
    }


def test_submission_requires_explicit_transaction():
    session = MagicMock()
    session.in_transaction.return_value = False
    with pytest.raises(RuntimeError, match="explicit transaction"):
        asyncio.run(submit_task(session, owner_id=uuid4(), idempotency_key="k",
                                submission=ResearchSubmission(question="Compare products")))
    session.commit.assert_not_called()


@pytest.mark.parametrize("key", ["", "  ", "x" * 129, "x\x00y"])
def test_invalid_idempotency_key_rejected_before_sql(key):
    session = MagicMock()
    session.in_transaction.return_value = True
    with pytest.raises(ValueError, match="idempotency key"):
        asyncio.run(submit_task(session, owner_id=uuid4(), idempotency_key=key,
                                submission=ResearchSubmission(question="Compare products")))
    session.scalar.assert_not_called()
