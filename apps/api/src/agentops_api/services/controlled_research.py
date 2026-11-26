"""S08 controlled research orchestration.

Private Development MVP smoke workflow. No API registration,
worker activation, model inference, or report publication.

A single retrieved source is insufficient for a market report.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from sqlalchemy import select

from agentops_api.agent.s06.contracts import (
    RetrievalRequest,
    SearchRequest,
    SearchHit,
    validate_contract,
)
from agentops_api.agent.s06.evidence import valid_uuid
from agentops_api.models.execution_context import (
    ResearchRealEvidence,
    ResearchSmokeGrant,
)
from agentops_api.services.durable_execution import DurableExecution
from agentops_api.services.execution_budget import (
    BudgetRejected,
    ExecutionBudgetService,
    UNRESOLVED,
    reservation_deadline,
)
from agentops_api.services.provider_accounting import (
    plan_smoke_search,
)
from agentops_api.services.real_evidence import (
    canonical_retrieval_url,
    retrieval_digest,
    resolve_real_citations,
)
from agentops_api.services.smoke_runtime import (
    require as require_live_authorization,
)
from agentops_api.services.s06_acquisition.tavily import (
    VerifiedSearchResponse,
)
from agentops_api.services.s06_workflow import (
    require_tracing_disabled,
)

from agentops_api.services.smoke_scope import prepare_scope

WORKFLOW_VERSION = "s08-controlled-v1"
RECURSION_LIMIT = 12
WORKFLOW_SECONDS = 30.0


def reject():
    raise BudgetRejected("controlled_research_rejected") from None


@dataclass(frozen=True, slots=True)
class VerifiedExcerpt:
    evidence_id: UUID
    source_url: str
    excerpt: str
    retrieved_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class ControlledOutcome:
    status: str
    workflow_version: str
    reason: str
    evidence: tuple[VerifiedExcerpt, ...]
    real_evidence_count: int
    synthetic_evidence_count: int
    publishable: bool


class ResearchState(TypedDict, total=False):
    matched: bool
    evidence_id: UUID | None


def _select_approved_source(result, retrieval_request, max_results):
    """Ignore snippet instructions and never expand the approved URL."""

    if (
        type(result) is not VerifiedSearchResponse
        or result.synthetic is not False
        or type(result.credits) is not int
        or result.credits != 1
        or type(result.hits) is not tuple
        or len(result.hits) > max_results
    ):
        reject()

    approved = canonical_retrieval_url(retrieval_request)
    matched = False

    for hit in result.hits:
        checked = validate_contract(SearchHit, hit, output=True)

        # The URL must match literally. No redirect, alternative
        # source, snippet content or model-selected URL is used.
        if checked.url == approved:
            matched = True

    return matched


async def _preflight(session_factory, handle, search, retrieval):
    """Validate both acquisition scopes before any dispatch."""

    require_live_authorization()

    async with session_factory() as session, session.begin():
        service = ExecutionBudgetService(
            session, isolated_test_scope=True,
        )

        task, attempt, context, rows, now = (
            await service._owned_context(handle)
        )

        if any(row.status in UNRESOLVED for row in rows):
            reject()

        if any(row.acquisition_origin == "live" for row in rows):
            reject()

        grant = await session.scalar(
            select(ResearchSmokeGrant)
            .where(
                ResearchSmokeGrant.owner_id == task.owner_id,
                ResearchSmokeGrant.task_id == task.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        from agentops_api.services.execution import _clock
        now = await _clock(session)

        if (
            grant is None
            or grant.max_search_requests != 1
            or grant.max_provider_credits != 1
            or grant.max_retrieval_requests != 1
            or grant.retrieval_url_sha256
            != retrieval_digest(retrieval)
        ):
            reject()

        plan_smoke_search(
            grant, task, rows, search, now,
            reservation_deadline(context, attempt, now, "search"),
        )

        from agentops_api.services.smoke_runtime import (
            check_operation, check_grant,
        )

        check_operation(handle, "search", search)
        check_operation(handle, "retrieval", retrieval)
        check_grant(
            handle, grant, "search", search, now,
            reservation_deadline(context, attempt, now, "search"),
        )

        scope = prepare_scope(
            handle, grant, search, retrieval, now
        )
        require_live_authorization()
        return scope


def _build_graph(durable, handle, search, retrieval, *, scope=None):
    """Fixed graph with application-owned acquisition operations.

    This private constructor is not an authorization boundary.
    The service entrypoint and individual operations enforce it.
    """

    async def search_node(state):
        if scope is not None:
            scope.check(handle, "search", search)
        result = await durable._search_smoke(handle, search)

        return {
            "matched": _select_approved_source(
                result, retrieval, search.max_results
            ),
        }

    def route(state):
        if state["matched"] is True:
            return "retrieve"
        return "insufficient"

    async def retrieve_node(state):
        if scope is not None:
            scope.check(handle, "retrieval", retrieval)
        evidence_id = await durable._retrieve_smoke(
            handle, retrieval
        )

        valid_uuid(evidence_id)

        return {"evidence_id": evidence_id}

    def insufficient_node(state):
        return {"evidence_id": None}

    graph = StateGraph(ResearchState)

    graph.add_node("search", search_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("insufficient", insufficient_node)

    graph.add_edge(START, "search")

    graph.add_conditional_edges(
        "search", route,
        {
            "retrieve": "retrieve",
            "insufficient": "insufficient",
        },
    )

    graph.add_edge("retrieve", END)
    graph.add_edge("insufficient", END)

    return graph.compile()


async def _run_graph(durable, handle, search, retrieval, *, scope=None):
    require_tracing_disabled()

    with tracing_context(enabled=False):
        state = await _build_graph(
            durable, handle, search, retrieval, scope=scope
        ).ainvoke(
            {},
            config={"recursion_limit": RECURSION_LIMIT},
        )

    matched = state.get("matched")
    evidence_id = state.get("evidence_id")

    if type(matched) is not bool:
        reject()

    if matched:
        valid_uuid(evidence_id)
    elif evidence_id is not None:
        reject()

    return evidence_id


async def _read_verified_excerpt(session_factory, handle, evidence_id):
    """Resolve and re-read under the current ownership transaction."""

    async with session_factory() as session, session.begin():
        resolved = await resolve_real_citations(
            session, handle, (evidence_id,)
        )

        if resolved != (evidence_id,):
            reject()

        row = await session.scalar(
            select(ResearchRealEvidence).where(
                ResearchRealEvidence.id == evidence_id,
                ResearchRealEvidence.owner_id == handle.owner_id,
                ResearchRealEvidence.task_id == handle.task_id,
                ResearchRealEvidence.attempt_id == handle.attempt_id,
            ).execution_options(populate_existing=True)
        )

        if row is None:
            reject()

        return VerifiedExcerpt(
            evidence_id=row.id,
            source_url=row.source_url,
            excerpt=row.excerpt,
            retrieved_at=row.retrieved_at,
            published_at=row.published_at,
        )


async def run_controlled_research(
    session_factory, handle, search_request, retrieval_request
):
    """Dormant entrypoint; existing G04 denial remains unconditional."""

    require_live_authorization()
    require_tracing_disabled()

    search = validate_contract(SearchRequest, search_request)
    retrieval = validate_contract(RetrievalRequest, retrieval_request)
    canonical_retrieval_url(retrieval)

    from agentops_api.services.smoke_runtime import check_operation

    check_operation(handle, "search", search)
    check_operation(handle, "retrieval", retrieval)

    try:
        async with asyncio.timeout(WORKFLOW_SECONDS):
            scope = await _preflight(
                session_factory, handle, search, retrieval
            )

            durable = DurableExecution(
                session_factory, isolated_test_scope=True
            )

            evidence_id = await _run_graph(
                durable, handle, search, retrieval, scope=scope
            )

            if evidence_id is None:
                snapshot = await durable._call("snapshot", handle)

                if snapshot.blocked:
                    reject()

                evidence = ()
                reason = "approved_source_not_found"

            else:
                evidence = (
                    await _read_verified_excerpt(
                        session_factory, handle, evidence_id
                    ),
                )
                reason = "single_source_insufficient"

            require_live_authorization()

            return ControlledOutcome(
                status="insufficient_evidence",
                workflow_version=WORKFLOW_VERSION,
                reason=reason,
                evidence=evidence,
                real_evidence_count=len(evidence),
                synthetic_evidence_count=0,
                publishable=False,
            )

    except asyncio.CancelledError:
        raise
    except Exception:
        reject()
