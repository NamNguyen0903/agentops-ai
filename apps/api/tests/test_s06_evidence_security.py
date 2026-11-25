"""Adversarial evidence integrity and persistence boundaries."""

import ast
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from agentops_api.agent.s06.contracts import RetrievedPage
from agentops_api.agent.s06.evidence import (
    EvidenceRejected,
    EvidenceScope,
    deduplicate,
    validate_record,
    content_digest,
)
from agentops_api.models.evidence import ResearchEvidence

from test_s06_evidence_domain import (
    NOW,
    scope,
    record,
    page,
)


@pytest.mark.parametrize("field,value", [
    ("id", uuid4()),
    ("owner_id", uuid4()),
    ("task_id", uuid4()),
    ("execution_id", uuid4()),
    ("content_hash", b"x" * 32),
    ("content_hash", b"x"),
    ("content_hash", "invalid"),
    ("excerpt", "tampered content"),
    ("title", "   "),
    ("source_url", "http://127.0.0.1/"),
    ("retrieved_url", "https://example.org/changed"),
    ("acquisition_method", "live_search"),
    ("synthetic", False),
    ("synthetic", 1),
    ("published_at", NOW),
    ("retrieved_at", None),
])
def test_tampered_record(field, value):
    context = scope()
    candidate = replace(
        record(context),
        **{field: value},
    )

    with pytest.raises(EvidenceRejected) as exc:
        validate_record(candidate, context)

    assert str(exc.value) == "invalid_evidence"


@pytest.mark.parametrize("field", [
    "owner_id", "task_id", "execution_id",
])
def test_forged_scope_fields(field):
    context = scope()

    object.__setattr__(
        context, field, str(uuid4())
    )

    with pytest.raises(EvidenceRejected):
        record(context)


def test_nil_uuid_rejected():
    with pytest.raises(EvidenceRejected):
        EvidenceScope(
            owner_id=UUID(int=0),
            task_id=uuid4(),
            execution_id=uuid4(),
        )


def test_mapping_is_not_trusted_scope():
    with pytest.raises(EvidenceRejected):
        record({
            "owner_id": uuid4(),
            "task_id": uuid4(),
            "execution_id": uuid4(),
        })


def test_forged_live_page_rejected():
    forged = RetrievedPage.model_construct(
        source_url="https://example.com/",
        retrieved_url="https://example.com/",
        content_type="text/plain",
        body=b"fixture",
        synthetic=False,
    )

    with pytest.raises(EvidenceRejected):
        record(scope(), page=forged)


@pytest.mark.parametrize("url", [
    "http://localhost/",
    "http://127.0.0.1/",
    "http://169.254.169.254/",
    "file:///etc/passwd",
    "https://user:secret@example.com/",
    "http://[::1]/",
])
def test_unsafe_source_url(url):
    with pytest.raises(EvidenceRejected):
        record(scope(), page=page(source_url=url))


def test_https_downgrade_rejected():
    with pytest.raises(EvidenceRejected):
        record(
            scope(),
            page=page(
                retrieved_url="http://example.com/source"
            ),
        )


def test_forged_hash_alone_cannot_reuse_id():
    context = scope()
    value = record(context)

    changed = replace(
        value,
        excerpt="changed",
        content_hash=content_digest("changed"),
    )

    with pytest.raises(EvidenceRejected):
        validate_record(changed, context)


def test_dedup_does_not_silently_ignore_tampering():
    context = scope()
    value = record(context)

    invalid = replace(
        value, content_hash=b"x" * 32
    )

    with pytest.raises(EvidenceRejected):
        deduplicate((value, invalid), context)


def test_dedup_input_bounded():
    context = scope()
    value = record(context)

    with pytest.raises(EvidenceRejected):
        deduplicate((value,) * 21, context)


def test_composite_foreign_key_definition():
    table = ResearchEvidence.__table__

    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(
            constraint, ForeignKeyConstraint
        )
    ]

    assert len(constraints) == 1

    foreign_key = constraints[0]

    assert [
        column.name for column in foreign_key.columns
    ] == ["owner_id", "task_id"]

    assert [
        element.target_fullname
        for element in foreign_key.elements
    ] == [
        "app.research_tasks.owner_id",
        "app.research_tasks.id",
    ]

    assert foreign_key.ondelete == "RESTRICT"


def test_database_check_constraints_declared():
    constraints = [
        str(item.sqltext)
        for item in ResearchEvidence.__table__.constraints
        if isinstance(item, CheckConstraint)
    ]

    assert len(constraints) == 7
    assert "synthetic IS TRUE" in constraints
    assert "published_at IS NULL" in constraints
    assert "octet_length(content_hash) = 32" in constraints


def test_postgresql_ddl_compiles():
    ddl = str(
        CreateTable(
            ResearchEvidence.__table__
        ).compile(
            dialect=postgresql.dialect()
        )
    )

    assert "CREATE TABLE app.research_evidence" in ddl
    assert "FOREIGN KEY(owner_id, task_id)" in ddl
    assert "ON DELETE RESTRICT" in ddl


def test_evidence_domain_has_no_io_imports():
    from agentops_api.agent.s06 import evidence

    tree = ast.parse(
        Path(evidence.__file__).read_text()
    )

    permitted = {
        "dataclasses",
        "datetime",
        "hashlib",
        "json",
        "re",
        "uuid",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in permitted

        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                assert node.module in permitted


def test_repository_no_lifecycle_or_commit_calls():
    from agentops_api.repositories import evidence

    tree = ast.parse(
        Path(evidence.__file__).read_text()
    )

    forbidden = {
        "commit",
        "rollback",
        "delete",
        "update",
        "create_engine",
        "create_async_engine",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func

            if isinstance(target, ast.Attribute):
                assert target.attr not in forbidden

            elif isinstance(target, ast.Name):
                assert target.id not in forbidden


def test_direct_record_https_downgrade_rejected():
    from agentops_api.agent.s06.evidence import stable_id

    context = scope()
    original = record(context)
    destination = "http://example.com/source"

    candidate = replace(
        original,
        retrieved_url=destination,
        id=stable_id(
            context,
            source_url=original.source_url,
            retrieved_url=destination,
            content_hash=original.content_hash,
        ),
    )

    with pytest.raises(EvidenceRejected):
        validate_record(candidate, context)
