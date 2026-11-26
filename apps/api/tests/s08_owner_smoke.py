"""Owner-operated S08 disposable smoke runner.

Not a public API, worker entrypoint or production capability.
No raw provider response, credential or exception is exported.

Offline fixtures may exercise this runner only in an isolated
database and with controlled fake HTTP wire responses.
"""

import asyncio
import json
import logging
import os
import sys

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select

from agentops_api.models.execution_context import (
    ResearchExecutionContext,
    ResearchOperationReservation,
    ResearchRealEvidence,
    ResearchSmokeGrant,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.services import smoke_runtime as runtime
from agentops_api.services.controlled_research import (
    run_controlled_research,
)
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.provider_accounting import query_digest
from agentops_api.services.real_evidence import (
    retrieval_digest, validate_stored,
)
from agentops_api.services.smoke_scope import (
    prepare_scope, proposed_requests,
)
from agentops_api.services.s06_acquisition.credentials import (
    TavilyCredential, authorization_header,
)
from agentops_api.services.s06_workflow import (
    require_tracing_disabled,
)
from tests.test_s07_budget_postgres import database, ledger


APPROVAL = "79be6005b3bfe87f303992acf82775f63b38d177c1d7f9a9f2bb7ce91894b95c"


def guard():
    if (
        not Path("/.dockerenv").is_file()
        or os.environ.get("AGENTOPS_RUN_DB_INTEGRATION") != "1"
        or os.environ.get("AGENTOPS_MIGRATION_DATABASE_URL") != (
            "postgresql+psycopg://agentops_migrator:"
            "isolated-test-only-migrator@db:5432/"
            "agentops_migration_test"
        )
    ):
        raise BudgetRejected("disposable_owner_runner_required")

    require_tracing_disabled()


async def execute_once(*, observer=None, verify_replay=False):
    guard()
    search, retrieval = proposed_requests()

    async with database() as (admin, app, handle, engine):
        grant_id = uuid4()

        try:
            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                assert await session.scalar(
                    select(func.count()).select_from(ResearchSmokeGrant)
                ) == 0

                grant = ResearchSmokeGrant(
                    id=grant_id,
                    owner_id=handle.owner_id,
                    task_id=handle.task_id,
                    provider_name="tavily",
                    endpoint="https://api.tavily.com/search",
                    query_sha256=query_digest(search),
                    retrieval_url_sha256=retrieval_digest(retrieval),
                    issued_at=now,
                    expires_at=now + timedelta(seconds=30),
                    max_search_requests=1,
                    max_provider_credits=1,
                    max_retrieval_requests=1,
                    lock_marker=0,
                )

                scope = prepare_scope(
                    handle, grant, search, retrieval, now
                )

                session.add(grant)
                await session.flush()

            if observer is not None:
                observer(admin, handle)

            outcome = None
            replay_denied = None

            permit = runtime._OwnerPermit(scope)

            with runtime._activate(scope, _owner_permit=permit):
                try:
                    outcome = await run_controlled_research(
                        app, handle, search, retrieval
                    )
                except Exception:
                    # Never propagate raw provider exceptions.
                    outcome = None

                if verify_replay and outcome is not None:
                    try:
                        await run_controlled_research(
                            app, handle, search, retrieval
                        )
                    except BudgetRejected:
                        replay_denied = True
                    else:
                        replay_denied = False

            rows = await ledger(admin, handle)

            async with admin() as session, session.begin():
                context = await session.get(
                    ResearchExecutionContext, handle.task_id
                )

                records = (
                    await session.scalars(
                        select(ResearchRealEvidence).where(
                            ResearchRealEvidence.owner_id == handle.owner_id,
                            ResearchRealEvidence.task_id == handle.task_id,
                            ResearchRealEvidence.attempt_id == handle.attempt_id,
                        )
                    )
                ).all()

                synthetic_count = await session.scalar(
                    select(func.count())
                    .select_from(ResearchEvidence)
                    .where(ResearchEvidence.task_id == handle.task_id)
                )

                assert len(rows) <= 2
                assert sum(row.kind == "search" for row in rows) <= 1
                assert sum(row.kind == "retrieval" for row in rows) <= 1

                assert all(
                    row.smoke_grant_id == grant_id
                    and row.acquisition_origin == "live"
                    and row.retry_ordinal == 0
                    and row.retry_eligible is False
                    for row in rows
                )

                assert synthetic_count == 0
                assert len(records) <= 1

                by_id = {row.id: row for row in rows}
                evidence = []

                for record in records:
                    operation = by_id[record.operation_ledger_id]

                    validate_stored(handle, record, operation)

                    evidence.append({
                        "evidence_id": str(record.id),
                        "source_url": record.source_url,
                        "source_identity_sha256": (
                            record.source_identity_sha256.hex()
                        ),
                        "content_sha256": record.content_hash.hex(),
                        "excerpt_length": len(record.excerpt),
                        "retrieved_at": record.retrieved_at.isoformat(),
                        "published_at": None,
                        "operation_ledger_id": str(operation.id),
                    })

                citation_verified = False

                if outcome is not None:
                    assert outcome.publishable is False
                    assert outcome.synthetic_evidence_count == 0
                    assert outcome.real_evidence_count == len(records)

                    if records:
                        assert len(outcome.evidence) == 1
                        assert outcome.evidence[0].evidence_id == records[0].id
                        assert outcome.evidence[0].excerpt == records[0].excerpt
                        citation_verified = True

                result = {
                    "owner_id": str(handle.owner_id),
                    "task_id": str(handle.task_id),
                    "attempt_id": str(handle.attempt_id),
                    "grant_id": str(grant_id),
                    "generation": handle.generation,
                    "workflow_status": (
                        outcome.status if outcome else "failed_closed"
                    ),
                    "reason": (
                        outcome.reason if outcome else "workflow_failed"
                    ),
                    "publishable": False,
                    "citation_verified": citation_verified,
                    "replay_denied": replay_denied,
                    "context_blocked": context.blocked_at is not None,
                    "search_calls": context.search_calls,
                    "retrieval_calls": context.retrieval_calls,
                    "model_calls": context.model_calls,
                    "operations": [
                        {
                            "id": str(row.id),
                            "kind": row.kind,
                            "status": row.status,
                            "reserved_credits": row.reserved_provider_credits,
                            "observed_credits": row.observed_provider_credits,
                            "request_sha256": row.request_sha256.hex(),
                            "retry_ordinal": row.retry_ordinal,
                            "reserved_at": row.reserved_at.isoformat(),
                            "dispatched_at": (
                                row.dispatched_at.isoformat()
                                if row.dispatched_at else None
                            ),
                            "resolved_at": (
                                row.resolved_at.isoformat()
                                if row.resolved_at else None
                            ),
                        }
                        for row in rows
                    ],
                    "evidence": evidence,
                }

                assert result["model_calls"] == 0

                return result

        finally:
            # Delete only this disposable task's smoke rows,
            # in dependency order, after exporting observations.
            async with admin() as session, session.begin():
                for model in (
                    ResearchRealEvidence,
                    ResearchOperationReservation,
                    ResearchSmokeGrant,
                ):
                    await session.execute(
                        delete(model).where(
                            model.owner_id == handle.owner_id,
                            model.task_id == handle.task_id,
                        )
                    )


def main():
    logging.disable(logging.CRITICAL)
    guard()

    receipt = Path("/tmp/s08-g04-preflight.json")
    xml = Path("/tmp/s08-g04-preflight.xml")

    proof = json.loads(receipt.read_text())

    if (
        proof.get("approval") != APPROVAL
        or proof.get("passed") != 20
        or proof.get("junit_sha256") != sha256(xml.read_bytes()).hexdigest()
    ):
        raise BudgetRejected("preflight_receipt_invalid")

    # One execution per disposable runner.
    with Path("/tmp/s08-g04-live.used").open("x") as stream:
        stream.write(APPROVAL)

    # Key arrives over stdin, not arguments or Docker configuration.
    raw = sys.stdin.buffer.read(514)

    if not raw.endswith(bytes((10,))) or len(raw) > 513:
        raise BudgetRejected("credential_input_invalid")

    key = raw[:-1].decode("ascii")

    authorization_header(TavilyCredential(key))

    if "TAVILY_API_KEY" in os.environ:
        raise BudgetRejected("ambient_credential_forbidden")

    os.environ["TAVILY_API_KEY"] = key

    try:
        result = asyncio.run(execute_once())
        print(
            "G04_RESULT=" + json.dumps(result, sort_keys=True),
            flush=True,
        )
    finally:
        os.environ.pop("TAVILY_API_KEY", None)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Do not print traceback, HTTP bodies or secret-bearing locals.
        print("G04_RUNNER_FAILED_CLOSED", flush=True)
        raise SystemExit(1)
