"""S08 real-evidence contract and transaction-owned persistence.

Real evidence never enters the synthetic S06 repository.
No public insertion endpoint or report publication is exposed.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid5

from sqlalchemy import func, select

from agentops_api.agent.s06.contracts import (
    RetrievalRequest, validate_contract,
)
from agentops_api.agent.s06.evidence import (
    normalize_text, valid_uuid,
)
from agentops_api.agent.s06.network_policy import validate_url
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.models.execution_context import ResearchRealEvidence
from agentops_api.services.execution_budget import (
    BudgetRejected, ExecutionBudgetService, UNRESOLVED,
)

NAMESPACE = UUID("6b749428-3168-4d4f-ae17-50ac08989808")
LIMIT = 20


def reject():
    raise BudgetRejected("real_evidence_rejected") from None


def canonical_retrieval_url(request):
    request = validate_contract(RetrievalRequest, request)
    destination = validate_url(request.url)

    if (
        destination.scheme != "https"
        or destination.url != request.url
    ):
        reject()

    return destination.url


def retrieval_digest(request):
    return sha256(
        canonical_retrieval_url(request).encode("utf-8")
    ).digest()


@dataclass(frozen=True, slots=True)
class RealPageObservation:
    source_url: str
    retrieved_url: str
    content_type: str
    body: bytes


def validate_observation(request, page):
    try:
        url = canonical_retrieval_url(request)

        if (
            type(page) is not RealPageObservation
            or page.source_url != url
            or page.retrieved_url != url
            or page.content_type != "text/plain"
            or type(page.body) is not bytes
            or not 1 <= len(page.body) <= 1048576
        ):
            reject()

        text = normalize_text(
            page.body.decode("utf-8", errors="strict"),
            1048576,
        )

        excerpt = text[:4096].rstrip()

        if not excerpt:
            reject()

        return excerpt

    except Exception:
        reject()


def identity(owner, task, attempt, source_hash, content_hash):
    for value in (owner, task, attempt):
        valid_uuid(value)

    if (
        type(source_hash) is not bytes
        or len(source_hash) != 32
        or type(content_hash) is not bytes
        or len(content_hash) != 32
    ):
        reject()

    return uuid5(
        NAMESPACE,
        ":".join((
            str(owner), str(task), str(attempt),
            source_hash.hex(), content_hash.hex(),
        )),
    )


def build_values(handle, row, request, page, now):
    """Pure projection of an already verified observation.

    The caller must hold the existing ownership transaction
    and consume a trusted retrieval ticket before persistence.
    """
    try:
        url = canonical_retrieval_url(request)
        excerpt = validate_observation(request, page)

        if (
            row.owner_id != handle.owner_id
            or row.task_id != handle.task_id
            or row.attempt_id != handle.attempt_id
            or row.kind != "retrieval"
            or row.acquisition_origin != "live"
            or row.status != "succeeded"
            or row.smoke_grant_id is None
            or row.request_sha256 != retrieval_digest(request)
            or row.dispatched_at is None
            or row.resolved_at != now
            or type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
            or not row.dispatched_at <= now <= row.deadline_at
        ):
            reject()

        source_hash = sha256(url.encode()).digest()
        content_hash = sha256(excerpt.encode()).digest()

        return {
            "id": identity(
                handle.owner_id, handle.task_id,
                handle.attempt_id, source_hash, content_hash,
            ),
            "owner_id": handle.owner_id,
            "task_id": handle.task_id,
            "attempt_id": handle.attempt_id,
            "operation_ledger_id": valid_uuid(row.id),
            "acquisition_origin": "live",
            "operation_kind": "retrieval",
            "operation_status": "succeeded",
            "title": validate_url(url).host,
            "source_url": url,
            "retrieved_url": url,
            "source_identity_sha256": source_hash,
            "content_hash": content_hash,
            "excerpt": excerpt,
            "acquisition_method": "http_retrieval",
            "retrieved_at": now.astimezone(timezone.utc),
            "published_at": None,
        }

    except Exception:
        reject()


def validate_stored(handle, row, operation):
    try:
        url = canonical_retrieval_url(
            RetrievalRequest(url=row.source_url)
        )

        source_hash = sha256(url.encode()).digest()
        excerpt_hash = sha256(row.excerpt.encode()).digest()

        if (
            row.owner_id != handle.owner_id
            or row.task_id != handle.task_id
            or row.attempt_id != handle.attempt_id
            or row.operation_ledger_id != operation.id
            or operation.owner_id != handle.owner_id
            or operation.task_id != handle.task_id
            or operation.attempt_id != handle.attempt_id
            or operation.kind != "retrieval"
            or operation.acquisition_origin != "live"
            or operation.status != "succeeded"
            or operation.smoke_grant_id is None
            or operation.dispatched_at is None
            or operation.resolved_at != row.retrieved_at
            or not operation.dispatched_at <= row.retrieved_at <= operation.deadline_at
            or operation.request_sha256 != source_hash
            or row.acquisition_origin != "live"
            or row.operation_kind != "retrieval"
            or row.operation_status != "succeeded"
            or row.acquisition_method != "http_retrieval"
            or row.published_at is not None
            or row.source_url != row.retrieved_url
            or row.title != validate_url(url).host
            or normalize_text(row.excerpt, 4096) != row.excerpt
            or row.source_identity_sha256 != source_hash
            or row.content_hash != excerpt_hash
            or row.id != identity(
                handle.owner_id, handle.task_id,
                handle.attempt_id, source_hash, excerpt_hash,
            )
        ):
            reject()

        return row.id

    except Exception:
        reject()


async def _insert_settled(session, handle, row, request, page, now):
    """Private insertion within the owned settlement transaction."""
    from agentops_api.services.smoke_runtime import (
        require as require_live_authorization,
    )

    require_live_authorization()

    from agentops_api.services.smoke_runtime import check_row
    check_row(handle, row, "retrieval")

    if not session.in_transaction():
        reject()

    values = build_values(handle, row, request, page, now)

    existing = await session.scalar(
        select(ResearchRealEvidence).where(
            ResearchRealEvidence.id == values["id"],
            ResearchRealEvidence.owner_id == handle.owner_id,
            ResearchRealEvidence.task_id == handle.task_id,
            ResearchRealEvidence.attempt_id == handle.attempt_id,
        ).execution_options(populate_existing=True)
    )

    if existing is not None:
        validate_stored(handle, existing, row)
        return existing.id

    # Task-wide limit includes all attempts and both evidence stores.
    count = 0

    for model in (ResearchEvidence, ResearchRealEvidence):
        value = await session.scalar(
            select(func.count()).select_from(model).where(
                model.owner_id == handle.owner_id,
                model.task_id == handle.task_id,
            )
        )

        if type(value) is not int or value < 0:
            reject()

        count += value

    if count >= LIMIT:
        raise BudgetRejected("evidence_limit_exceeded")

    session.add(ResearchRealEvidence(**values))
    await session.flush()

    return values["id"]


async def resolve_real_citations(session, handle, evidence_ids):
    """Resolve only existing evidence under current durable ownership."""
    if (
        type(evidence_ids) is not tuple
        or not 1 <= len(evidence_ids) <= LIMIT
    ):
        reject()

    try:
        for value in evidence_ids:
            valid_uuid(value)
    except Exception:
        reject()

    if len(set(evidence_ids)) != len(evidence_ids):
        reject()

    if not session.in_transaction():
        reject()

    service = ExecutionBudgetService(
        session, isolated_test_scope=True,
    )

    _, _, _, operations, _ = await service._owned_context(handle)

    if any(item.status in UNRESOLVED for item in operations):
        reject()

    records = (
        await session.scalars(
            select(ResearchRealEvidence).where(
                ResearchRealEvidence.owner_id == handle.owner_id,
                ResearchRealEvidence.task_id == handle.task_id,
                ResearchRealEvidence.attempt_id == handle.attempt_id,
                ResearchRealEvidence.id.in_(evidence_ids),
            ).execution_options(populate_existing=True)
        )
    ).all()

    by_id = {item.id: item for item in records}
    by_operation = {item.id: item for item in operations}

    if set(by_id) != set(evidence_ids):
        reject()

    for evidence_id in evidence_ids:
        record = by_id[evidence_id]
        operation = by_operation.get(record.operation_ledger_id)

        if operation is None:
            reject()

        validate_stored(handle, record, operation)

    return tuple(by_id[item].id for item in evidence_ids)
