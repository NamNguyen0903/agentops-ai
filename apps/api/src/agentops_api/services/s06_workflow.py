"""S06 internal offline application orchestration.

Not registered with API routes, workers, or live providers.
Caller owns authentication, execution context and transaction.

All evidence is synthetic. No report is persisted or published.
"""

import os
from datetime import datetime, timezone
from time import monotonic

from langsmith import tracing_context

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import (
    RetrievalRequest,
    SearchRequest,
)
from agentops_api.agent.s06.evidence import (
    EvidenceScope,
    from_retrieved_page,
    normalize_text,
    validate_scope,
)
from agentops_api.agent.s06.providers import (
    FixtureSearchProvider,
    search_offline,
)
from agentops_api.agent.s06.retrieval import (
    retrieve_offline,
)
from agentops_api.agent.s06.transport import (
    FixtureResolver,
    FixtureTransport,
    TransportResponse,
)
from agentops_api.agent.s06.evidence_validation import (
    assess_evidence,
)
from agentops_api.agent.s06.citations import (
    validate_candidate,
)
from agentops_api.agent.s06.workflow import run_offline
from agentops_api.agent.s06.workflow_contracts import (
    MAX_QUESTION_CHARS,
    WORKFLOW_VERSION,
    WorkflowInput,
    WorkflowOutcome,
)
from agentops_api.repositories.evidence import (
    list_evidence,
    store_evidence,
    require_transaction,
    require_task,
)


MAX_WORKFLOW_SECONDS = 30.0

TRACING_FLAGS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
)


class OfflineWorkflowRejected(ValueError):
    def __init__(self):
        super().__init__("offline_workflow_rejected")


def reject():
    raise OfflineWorkflowRejected() from None


def require_tracing_disabled():
    for flag in TRACING_FLAGS:
        value = os.environ.get(flag, "")

        if value.strip().lower() not in {
            "", "false", "0", "no", "off",
        }:
            reject()


def check_deadline(deadline):
    if monotonic() >= deadline:
        reject()


def fixture_acquire(scope, question, budget):
    """Run actual S06 fixture search and retrieval boundaries.

    Fixture response bytes are application-owned constants.
    No caller-provided URL, response, credential or adapter.
    """

    scope = validate_scope(scope)

    question = normalize_text(
        question,
        MAX_QUESTION_CHARS,
    )

    # The fixture provider returns a single source.
    # Use two fixed fixture queries and deterministic
    # retrieval snapshots to exercise acquisition.
    records = []

    for suffix in ("overview", "comparison"):
        query = (question[:980] + " " + suffix).strip()

        result = search_offline(
            SearchRequest(
                query=query,
                max_results=1,
            ),
            budget,
            provider=FixtureSearchProvider(),
        )

        if result.synthetic is not True:
            reject()

        for hit in result.hits:
            # These are synthetic fixture documents,
            # not copies of external source content.
            body = (
                "Synthetic fixture document: " + suffix
            ).encode("utf-8")

            destination = (
                "https://example.com/s06-" + suffix
            )

            # Exercise redirect validation and rebinding
            # through the existing retrieval implementation.
            responses = (
                TransportResponse(
                    status=302,
                    headers=(("Location", destination),),
                    chunks=(),
                    peer_ip="93.184.216.34",
                    tls_verified=True,
                    tls_hostname="example.com",
                ),
                TransportResponse(
                    status=200,
                    headers=(
                        ("Content-Type", "text/plain"),
                        ("Content-Length", str(len(body))),
                    ),
                    chunks=(body,),
                    peer_ip="93.184.216.34",
                    tls_verified=True,
                    tls_hostname="example.com",
                ),
            )

            page = retrieve_offline(
                RetrievalRequest(url=hit.url),
                budget,
                resolver=FixtureResolver({
                    "example.com": ("93.184.216.34",),
                }),
                transport=FixtureTransport(responses),
            )

            records.append(
                from_retrieved_page(
                    scope,
                    title=hit.title,
                    page=page,
                    retrieved_at=datetime.now(timezone.utc),
                )
            )

    return tuple(records)


async def revalidate_outcome(
    session,
    *,
    scope,
    question,
    outcome,
):
    """Re-read current scoped records and validate output.

    The caller must retain its transaction through this
    operation. No authorization survives transaction exit.
    """

    try:
        require_transaction(session)
        scope = validate_scope(scope)

        question = normalize_text(
            question,
            MAX_QUESTION_CHARS,
        )

        current = await list_evidence(
            session,
            scope=scope,
        )

        assessment = assess_evidence(
            scope,
            current,
        )

        if (
            type(outcome) is not WorkflowOutcome
            or type(outcome.status) is not str
            or type(outcome.workflow_version) is not str
            or outcome.workflow_version != WORKFLOW_VERSION
            or outcome.publishable is not False
            or type(outcome.real_evidence_count) is not int
            or outcome.real_evidence_count != 0
            or type(outcome.synthetic_evidence_count) is not int
            or outcome.synthetic_evidence_count
            != assessment.synthetic_evidence_count
        ):
            reject()

        if outcome.status == "insufficient_evidence":
            if (
                outcome.candidate is not None
                or assessment.sufficient_for_fixture
                or outcome.reason != "insufficient_fixture_sources"
            ):
                reject()

            return WorkflowOutcome(
                status="insufficient_evidence",
                workflow_version=WORKFLOW_VERSION,
                candidate=None,
                reason="insufficient_fixture_sources",
                real_evidence_count=0,
                synthetic_evidence_count=(
                    assessment.synthetic_evidence_count
                ),
                publishable=False,
            )

        if (
            outcome.status != "synthetic_candidate"
            or outcome.reason is not None
        ):
            reject()

        candidate = validate_candidate(
            outcome.candidate,
            assessment=assessment,
            scope=scope,
            question=question,
        )

        return WorkflowOutcome(
            status="synthetic_candidate",
            workflow_version=WORKFLOW_VERSION,
            candidate=candidate,
            reason=None,
            real_evidence_count=0,
            synthetic_evidence_count=(
                assessment.synthetic_evidence_count
            ),
            publishable=False,
        )

    except Exception:
        reject()


async def run_fixture_workflow(
    session,
    *,
    scope,
    question,
):
    """Internal Development MVP entry point.

    Requires a trusted application-issued scope and an
    explicit transaction. On failure the caller must
    roll back. Never catch a failure and commit partial
    acquisition as if the complete operation succeeded.
    """

    try:
        require_transaction(session)
        require_tracing_disabled()

        scope = validate_scope(scope)

        question = normalize_text(
            question,
            MAX_QUESTION_CHARS,
        )

        deadline = (
            monotonic() + MAX_WORKFLOW_SECONDS
        )

        budget = Budget()

        # Do not acquire evidence for unauthorized
        # or deleted tasks.
        await require_task(session, scope)
        check_deadline(deadline)

        records = fixture_acquire(
            scope,
            question,
            budget,
        )

        check_deadline(deadline)

        for record in records:
            check_deadline(deadline)

            await store_evidence(
                session,
                scope=scope,
                record=record,
            )

            check_deadline(deadline)

        snapshot = await list_evidence(
            session,
            scope=scope,
        )

        check_deadline(deadline)
        require_tracing_disabled()

        # Explicitly suppress LangSmith tracing for
        # this internal graph invocation.
        with tracing_context(enabled=False):
            outcome = run_offline(
                WorkflowInput(
                    scope=scope,
                    question=question,
                    evidence=snapshot,
                )
            )

        check_deadline(deadline)

        validated = await revalidate_outcome(
            session,
            scope=scope,
            question=question,
            outcome=outcome,
        )

        check_deadline(deadline)

        return validated

    except Exception:
        reject()
