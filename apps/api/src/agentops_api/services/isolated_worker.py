
"""S07 deterministic isolated worker harness.

No background scheduler, startup hook, external provider,
report persistence or publication. One explicitly invoked
worker operation uses short durable transactions and fixed
application-owned acquisition fixtures.
"""
import asyncio
from datetime import datetime, timezone

from langsmith import tracing_context

from agentops_api.agent.s06.contracts import (
    SearchRequest,
    RetrievalRequest,
)
from agentops_api.agent.s06.evidence import (
    EvidenceScope,
    from_retrieved_page,
    normalize_text,
)
from agentops_api.agent.s06.transport import (
    FixtureResolver,
    FixtureTransport,
    TransportResponse,
)
from agentops_api.agent.s06.workflow import run_offline
from agentops_api.agent.s06.workflow_contracts import WorkflowInput
from agentops_api.repositories.evidence import store_evidence

from agentops_api.services.durable_execution import DurableExecution
from agentops_api.services.execution import (
    ExecutionService,
    ExecutionRejected,
    _end_attempt,
    _terminal,
)
from agentops_api.services.execution_budget import (
    ExecutionBudgetService,
    BudgetRejected,
)
from agentops_api.services.s06_workflow import (
    require_tracing_disabled,
    revalidate_outcome,
)


class IsolatedWorker:
    def __init__(
        self, session_factory, *, isolated_test_scope=False,
    ):
        if isolated_test_scope is not True:
            raise ExecutionRejected("worker_activation_disabled")

        self._factory = session_factory
        self._execution = DurableExecution(
            session_factory, isolated_test_scope=True,
        )

    async def _lifecycle(self, method, *args):
        async with self._factory() as session:
            service = ExecutionService(
                session, isolated_test_scope=True,
            )
            return await getattr(service, method)(*args)

    async def run_one(self, worker_id):
        require_tracing_disabled()

        handle = await self._lifecycle(
            "claim", worker_id,
        )

        if handle is None:
            return None

        return await self.run_claimed(handle)

    async def _prepare(self, handle):
        require_tracing_disabled()

        graph_input, _, _ = await self._execution._call(
            "_actual_input", handle,
        )

        question = normalize_text(
            graph_input.question, 4000,
        )

        scope = EvidenceScope(
            handle.owner_id,
            handle.task_id,
            handle.attempt_id,
        )

        s05 = await self._execution.run_s05(handle)

        if s05.outcome != "candidate_ready":
            raise ExecutionRejected(
                "deterministic_workflow_rejected"
            )

        records = []

        for suffix in ("overview", "comparison"):
            await self._lifecycle("heartbeat", handle)

            search = await self._execution.search_offline(
                handle,
                SearchRequest(
                    query=(question[:980] + " " + suffix).strip(),
                    max_results=1,
                ),
            )

            if (
                search.synthetic is not True
                or len(search.hits) != 1
                or search.hits[0].url !=
                "https://example.com/fixture"
            ):
                raise ExecutionRejected(
                    "fixture_source_rejected"
                )

            hit = search.hits[0]

            # The S06 fixture provider returns the same URL
            # for both queries. Use distinct, application-owned
            # fixture paths so durable logical operation IDs
            # cannot collide across separate retrievals.
            initial = hit.url + "-" + suffix
            destination = "https://example.com/s07-" + suffix
            body = (
                "Synthetic fixture document: " + suffix
            ).encode("utf-8")

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

            page = await self._execution.retrieve_offline(
                handle,
                RetrievalRequest(url=initial),
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

        records = tuple(records)

        # Pure deterministic graph; no DB transaction,
        # provider or caller-controlled graph configuration.
        require_tracing_disabled()

        with tracing_context(enabled=False):
            outcome = run_offline(
                WorkflowInput(
                    scope=scope,
                    question=question,
                    evidence=records,
                )
            )

        return records, outcome

    async def _accept(self, handle, records, outcome):
        scope = EvidenceScope(
            handle.owner_id,
            handle.task_id,
            handle.attempt_id,
        )

        async with self._factory() as session, session.begin():
            authority = ExecutionBudgetService(
                session, isolated_test_scope=True,
            )

            task, _, _, rows, _ = (
                await authority._owned_context(handle)
            )

            current = [
                row for row in rows
                if row.attempt_id == handle.attempt_id
            ]

            # Require completed actual deterministic acquisition
            # and S05 adapter accounting under this generation.
            counts = {
                kind: sum(
                    row.kind == kind for row in current
                )
                for kind in ("adapter", "search", "retrieval")
            }

            if (
                counts != {
                    "adapter": 3,
                    "search": 2,
                    "retrieval": 4,
                }
                or len(current) != 9
                or any(
                    row.status != "succeeded"
                    for row in current
                )
                or type(records) is not tuple
                or len(records) != 2
            ):
                raise BudgetRejected(
                    "worker_accounting_incomplete"
                )

            for record in records:
                await store_evidence(
                    session,
                    scope=scope,
                    record=record,
                    execution_handle=handle,
                )

            validated = await revalidate_outcome(
                session,
                scope=scope,
                question=task.question,
                outcome=outcome,
                execution_handle=handle,
            )

            if (
                validated.publishable is not False
                or validated.real_evidence_count != 0
            ):
                raise ExecutionRejected(
                    "publication_disabled"
                )

            # Recheck ownership and deadlines immediately
            # before the authoritative terminal mutation.
            task, attempt, _, _, now = (
                await authority._owned_context(handle)
            )

            # Synthetic candidates are test artifacts only.
            # They cannot authorize a real completed report.
            _end_attempt(
                attempt, now, "insufficient_evidence",
            )

            _terminal(
                task,
                "insufficient_evidence",
                now,
                "insufficient_evidence",
            )

            await session.flush()

        # Return only after successful transaction commit.
        return validated

    async def run_claimed(self, handle):
        try:
            records, outcome = await self._prepare(handle)

            return await self._accept(
                handle, records, outcome,
            )

        except asyncio.CancelledError:
            # DurableExecution retains its cleanup authority.
            # An interrupted attempt is subject to recovery,
            # never an assumed successful terminal transition.
            raise

        except Exception:
            try:
                await self._lifecycle(
                    "finish", handle, "failed",
                )
            except (ExecutionRejected, BudgetRejected):
                # Ownership may already have been revoked.
                # Do not mutate the replacement generation.
                pass

            raise ExecutionRejected(
                "isolated_worker_failed"
            ) from None
