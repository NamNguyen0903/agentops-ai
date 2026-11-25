"""Pure evidence contracts for the S06 development MVP.

Only synthetic acquisition is supported at this stage.
No database, network or worker operations occur here.
"""

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID, uuid5

from .contracts import RetrievedPage, validate_contract
from .errors import AcquisitionError
from .network_policy import validate_url


MAX_EVIDENCE_PER_TASK = 20
MAX_TITLE_CHARS = 512
MAX_EXCERPT_CHARS = 4096

EVIDENCE_NAMESPACE = UUID(
    "80aa52df-cfb4-44a1-a1c0-11a75b55a606"
)

METHOD = "fixture_retrieval"


class EvidenceRejected(ValueError):
    """Sanitized rejection without source content."""

    def __init__(self):
        super().__init__("invalid_evidence")


class EvidenceUnavailable(ValueError):
    def __init__(self):
        super().__init__("evidence_unavailable")


class EvidenceLimitExceeded(ValueError):
    def __init__(self):
        super().__init__("evidence_limit_exceeded")


def reject():
    raise EvidenceRejected() from None


def valid_uuid(value):
    if type(value) is not UUID or value.int == 0:
        reject()

    return value


def utc_time(value):
    if type(value) is not datetime:
        reject()

    if value.tzinfo is not timezone.utc:
        reject()

    return value


def normalize_text(value, limit):
    if type(value) is not str:
        reject()

    if len(value) > 1048576:
        reject()

    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        reject()

    for char in value:
        if (
            ord(char) < 32
            and char not in (
                chr(9), chr(10), chr(13)
            )
        ) or 127 <= ord(char) <= 159:
            reject()

    result = re.sub(r"\s+", " ", value).strip()

    if not result or len(result) > limit:
        reject()

    return result


def canonical_url(value):
    try:
        return validate_url(value).url
    except AcquisitionError:
        reject()


@dataclass(frozen=True, slots=True)
class EvidenceScope:
    """Trusted application scope, not a model-issued permission."""

    owner_id: UUID
    task_id: UUID
    execution_id: UUID

    def __post_init__(self):
        valid_uuid(self.owner_id)
        valid_uuid(self.task_id)
        valid_uuid(self.execution_id)


def validate_scope(scope):
    if type(scope) is not EvidenceScope:
        reject()

    return EvidenceScope(
        owner_id=valid_uuid(scope.owner_id),
        task_id=valid_uuid(scope.task_id),
        execution_id=valid_uuid(scope.execution_id),
    )


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    id: UUID
    owner_id: UUID
    task_id: UUID
    execution_id: UUID
    title: str
    source_url: str
    retrieved_url: str
    excerpt: str
    acquisition_method: str
    retrieved_at: datetime
    published_at: datetime | None
    content_hash: bytes
    synthetic: bool


def content_digest(excerpt):
    return sha256(excerpt.encode("utf-8")).digest()


def stable_id(
    scope,
    *,
    source_url,
    retrieved_url,
    content_hash,
):
    scope = validate_scope(scope)

    if (
        type(content_hash) is not bytes
        or len(content_hash) != 32
    ):
        reject()

    payload = json.dumps(
        {
            "version": 1,
            "owner_id": str(scope.owner_id),
            "task_id": str(scope.task_id),
            "execution_id": str(scope.execution_id),
            "source_url": canonical_url(source_url),
            "retrieved_url": canonical_url(retrieved_url),
            "content_hash": content_hash.hex(),
            "acquisition_method": METHOD,
            "synthetic": True,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return uuid5(EVIDENCE_NAMESPACE, payload)


def validate_record(record, scope):
    scope = validate_scope(scope)

    if type(record) is not EvidenceRecord:
        reject()

    try:
        valid_uuid(record.id)

        for name in (
            "owner_id", "task_id", "execution_id"
        ):
            if (
                valid_uuid(getattr(record, name))
                != getattr(scope, name)
            ):
                reject()

        if (
            type(record.acquisition_method) is not str
            or record.acquisition_method != METHOD
            or record.synthetic is not True
        ):
            reject()

        if record.published_at is not None:
            # Fixture acquisition cannot establish a
            # genuine publication timestamp.
            reject()

        utc_time(record.retrieved_at)

        if (
            normalize_text(record.title, MAX_TITLE_CHARS)
            != record.title
        ):
            reject()

        if (
            normalize_text(record.excerpt, MAX_EXCERPT_CHARS)
            != record.excerpt
        ):
            reject()

        if (
            canonical_url(record.source_url)
            != record.source_url
            or canonical_url(record.retrieved_url)
            != record.retrieved_url
        ):
            reject()

        if (
            type(record.content_hash) is not bytes
            or record.content_hash
            != content_digest(record.excerpt)
        ):
            reject()

        if (
            record.source_url.startswith("https://")
            and not record.retrieved_url.startswith("https://")
        ):
            reject()

        expected_id = stable_id(
            scope,
            source_url=record.source_url,
            retrieved_url=record.retrieved_url,
            content_hash=record.content_hash,
        )

        if record.id != expected_id:
            reject()

        return EvidenceRecord(**{
            field.name: getattr(record, field.name)
            for field in fields(EvidenceRecord)
        })

    except EvidenceRejected:
        raise
    except Exception:
        reject()


def from_retrieved_page(
    scope,
    *,
    title,
    page,
    retrieved_at,
):
    """Build fixture evidence from a trusted acquisition result.

    Retrieved_at is supplied by the application clock.
    The title is source metadata supplied by the application.
    Only plain text is supported until a safe extraction
    boundary is implemented.
    """

    scope = validate_scope(scope)

    try:
        page = validate_contract(
            RetrievedPage,
            page,
            output=True,
        )
    except AcquisitionError:
        reject()

    if page.synthetic is not True:
        reject()

    if page.content_type != "text/plain":
        reject()

    title = normalize_text(title, MAX_TITLE_CHARS)

    try:
        text = page.body.decode(
            "utf-8", errors="strict"
        )
    except UnicodeError:
        reject()

    # Normalize the bounded page before taking an excerpt.
    normalized = normalize_text(text, 1048576)

    excerpt = normalized[:MAX_EXCERPT_CHARS].rstrip()

    source_url = canonical_url(page.source_url)
    retrieved_url = canonical_url(page.retrieved_url)

    if (
        source_url.startswith("https://")
        and not retrieved_url.startswith("https://")
    ):
        reject()

    digest = content_digest(excerpt)

    record = EvidenceRecord(
        id=stable_id(
            scope,
            source_url=source_url,
            retrieved_url=retrieved_url,
            content_hash=digest,
        ),
        owner_id=scope.owner_id,
        task_id=scope.task_id,
        execution_id=scope.execution_id,
        title=title,
        source_url=source_url,
        retrieved_url=retrieved_url,
        excerpt=excerpt,
        acquisition_method=METHOD,
        retrieved_at=utc_time(retrieved_at),
        published_at=None,
        content_hash=digest,
        synthetic=True,
    )

    return validate_record(record, scope)


def deduplicate(records, scope):
    scope = validate_scope(scope)

    if (
        type(records) is not tuple
        or len(records) > MAX_EVIDENCE_PER_TASK
    ):
        reject()

    accepted = {}

    for candidate in records:
        candidate = validate_record(candidate, scope)

        # First valid record wins for the same evidence identity.
        accepted.setdefault(candidate.id, candidate)

    return tuple(accepted.values())
