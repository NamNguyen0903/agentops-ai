"""Evidence normalization and provenance tests."""

from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from agentops_api.agent.s06.contracts import RetrievedPage
from agentops_api.agent.s06.evidence import (
    EvidenceRejected,
    EvidenceScope,
    content_digest,
    deduplicate,
    from_retrieved_page,
    validate_record,
)


NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def scope():
    return EvidenceScope(
        owner_id=uuid4(),
        task_id=uuid4(),
        execution_id=uuid4(),
    )


def page(**changes):
    values = {
        "source_url": "https://EXAMPLE.com/source#fragment",
        "retrieved_url": "https://example.com/source",
        "content_type": "text/plain",
        "body": b"Public synthetic research content.",
        "synthetic": True,
    }

    values.update(changes)

    return RetrievedPage(**values)


def record(context, **changes):
    arguments = {
        "title": "  Synthetic   research  ",
        "page": page(),
        "retrieved_at": NOW,
    }

    arguments.update(changes)

    return from_retrieved_page(context, **arguments)


def test_normalization():
    context = scope()

    result = record(
        context,
        page=page(
            body=b"  Market" + bytes((10, 9)) + b" research  "
        ),
    )

    assert result.title == "Synthetic research"
    assert result.excerpt == "Market research"
    assert result.source_url == "https://example.com/source"
    assert result.synthetic is True
    assert result.published_at is None
    assert result.acquisition_method == "fixture_retrieval"


def test_stable_id_for_same_content():
    context = scope()

    assert record(context).id == record(context).id


def test_normalized_content_has_same_id():
    context = scope()

    first = record(context, page=page(body=b"Market research"))

    second = record(
        context,
        page=page(body=b"  Market   research "),
    )

    assert first.id == second.id
    assert first.content_hash == second.content_hash


def test_content_changes_id():
    context = scope()

    assert record(context).id != record(
        context,
        page=page(body=b"Different evidence"),
    ).id


@pytest.mark.parametrize("field", [
    "owner_id",
    "task_id",
    "execution_id",
])
def test_scope_changes_id(field):
    context = scope()
    other = replace(context, **{field: uuid4()})

    assert record(context).id != record(other).id


def test_different_retrieved_url_changes_id():
    context = scope()

    assert record(context).id != record(
        context,
        page=page(
            retrieved_url="https://example.org/source"
        ),
    ).id


def test_retrieval_time_does_not_reset_identity():
    context = scope()

    first = record(context)
    second = record(
        context,
        retrieved_at=NOW + timedelta(seconds=1),
    )

    assert first.id == second.id
    assert first.retrieved_at != second.retrieved_at


def test_hash_matches_retained_excerpt():
    result = record(scope())

    assert len(result.content_hash) == 32
    assert result.content_hash == content_digest(
        result.excerpt
    )


def test_deduplication_first_record_wins():
    context = scope()

    first = record(context)
    second = record(
        context,
        title="Alternative source title",
    )

    assert deduplicate(
        (first, second), context
    ) == (first,)


def test_excerpt_is_bounded():
    result = record(
        scope(),
        page=page(body=b"x" * 5000),
    )

    assert len(result.excerpt) == 4096


def test_unicode_excerpt():
    result = record(
        scope(),
        page=page(
            body="Du lieu nghien cuu Việt Nam".encode("utf-8")
        ),
    )

    assert "Việt Nam" in result.excerpt


@pytest.mark.parametrize("value", [
    "",
    " ",
    "x" * 513,
    "x" + chr(0),
    123,
    True,
])
def test_invalid_title(value):
    with pytest.raises(EvidenceRejected):
        record(scope(), title=value)


@pytest.mark.parametrize("body", [
    b"",
    b"   ",
    bytes((255, 254)),
    b"abc" + bytes((0,)),
])
def test_invalid_body(body):
    with pytest.raises(EvidenceRejected):
        record(scope(), page=page(body=body))


@pytest.mark.parametrize("content_type", [
    "text/html",
    "application/xhtml+xml",
    "application/json",
])
def test_non_plain_text_rejected(content_type):
    with pytest.raises(EvidenceRejected):
        record(
            scope(),
            page=page(content_type=content_type),
        )


@pytest.mark.parametrize("value", [
    datetime(2026, 11, 25),
    datetime(
        2026, 11, 25,
        tzinfo=timezone(timedelta(hours=7)),
    ),
    "2026-11-25",
    None,
])
def test_invalid_retrieval_time(value):
    with pytest.raises(EvidenceRejected):
        record(scope(), retrieved_at=value)


def test_validate_record_returns_immutable_copy():
    context = scope()
    original = record(context)

    validated = validate_record(original, context)

    assert validated == original
    assert validated is not original
