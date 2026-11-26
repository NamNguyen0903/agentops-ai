"""Dedicated G04-B retrieval-only disposable runner."""
import asyncio
import hashlib
import json
import logging
import os
import sys
import threading
import xml.etree.ElementTree as ET

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select
from agentops_api.agent.s06.contracts import RetrievalRequest
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.models.execution_context import (
    ResearchExecutionContext, ResearchOperationReservation,
    ResearchRealEvidence, ResearchSmokeGrant,
)
from agentops_api.models.evidence import ResearchEvidence
from agentops_api.services import smoke_runtime as runtime
from agentops_api.services.execution_budget import BudgetRejected
from agentops_api.services.real_evidence import (
    retrieval_digest, resolve_real_citations, validate_stored,
)
from agentops_api.services.retrieval_only import prepare_retrieval_scope
from agentops_api.services.smoke_scope import URL, proposed_requests
from tests.s08_owner_smoke import guard
from tests.test_s07_budget_postgres import database, ledger

APPROVAL = "2e317b20571ed9cbb6ba62e3c1052e6a11c06c590b61adc7eb0c35702af549cd"



class _RetrievalDiagnostics:
    """Bounded disposable-runner diagnostics.

    Record only trusted module/function identifiers and enum codes.
    Never record exception messages, response bodies, locals,
    headers, credentials or provider-supplied strings.
    """

    MODULES = {
        "agentops_api.services.s06_acquisition.resolver",
        "agentops_api.services.s06_acquisition.pinned_transport",
        "agentops_api.services.s06_acquisition.bounded_http",
        "agentops_api.services.s06_acquisition.controlled_retrieval",
        "agentops_api.services.real_evidence",
        "agentops_api.services.execution_budget",
    }

    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def trace(self, frame, event, arg):
        module = frame.f_globals.get("__name__")

        if module not in self.MODULES:
            return None

        frame.f_trace_lines = False
        frame.f_trace_opcodes = False

        if event == "exception":
            _, exc, _ = arg

            if (
                isinstance(exc, AcquisitionError)
                and type(exc.code) is ErrorCode
            ):
                code = exc.code.name
            elif isinstance(exc, OSError):
                code = "OS_ERROR"
            elif isinstance(exc, BudgetRejected):
                code = "BUDGET_REJECTED"
            else:
                return self.trace

            entry = {
                "module": module.rsplit(".", 1)[-1],
                "function": frame.f_code.co_name,
                "code": code,
            }

            with self.lock:
                if (
                    len(self.events) < 24
                    and entry not in self.events
                ):
                    self.events.append(entry)

        return self.trace

    def __enter__(self):
        self.previous = sys.gettrace()
        self.previous_thread = threading.gettrace()

        if self.previous is not None:
            raise BudgetRejected("diagnostic_trace_conflict")

        threading.settrace(self.trace)
        sys.settrace(self.trace)

        return self

    def __exit__(self, *args):
        sys.settrace(self.previous)
        threading.settrace(self.previous_thread)


def grant_values(handle, now):
    request = RetrievalRequest(url=URL)

    return dict(
        id=uuid4(),
        owner_id=handle.owner_id,
        task_id=handle.task_id,
        grant_kind="retrieval_only",
        provider_name="rfc_editor",
        endpoint=URL,
        query_sha256=None,
        retrieval_url_sha256=retrieval_digest(request),
        issued_at=now,
        expires_at=now + timedelta(seconds=30),
        max_search_requests=0,
        max_provider_credits=0,
        max_retrieval_requests=1,
        lock_marker=0,
    )


async def execute_once(*, observer=None, verify_denials=False):
    guard()

    if "TAVILY_API_KEY" in os.environ:
        raise BudgetRejected("credential_forbidden")

    search, request = proposed_requests()

    async with database() as (admin, app, handle, engine):
        try:
            async with admin() as session, session.begin():
                now = await session.scalar(
                    select(func.clock_timestamp())
                )

                assert await session.scalar(
                    select(func.count()).select_from(ResearchSmokeGrant)
                ) == 0

                grant = ResearchSmokeGrant(**grant_values(handle, now))
                session.add(grant)
                await session.flush()

                scope = prepare_retrieval_scope(
                    handle, grant, request, now
                )
                grant_id = grant.id

            if observer is not None:
                observer(admin, handle)

            evidence_id = None
            citation = False
            denials = []
            diagnostic = _RetrievalDiagnostics()
            failure_kind = None

            with runtime._activate(
                scope,
                _owner_permit=runtime._OwnerPermit(scope),
            ):
                if verify_denials:
                    for name, method, value in (
                        ("search", "_reserve_smoke_search", search),
                        (
                            "alternate_url",
                            "_reserve_smoke_retrieval",
                            RetrievalRequest(url="https://example.org/"),
                        ),
                    ):
                        try:
                            await engine._call(method, handle, value)
                        except (BudgetRejected, AcquisitionError):
                            denials.append(name)
                        else:
                            raise AssertionError("Unexpected authority")

                    try:
                        runtime.read_credential(object(), search)
                    except AcquisitionError:
                        denials.append("credential")
                    else:
                        raise AssertionError("Credential read accepted")

                    assert not await ledger(admin, handle)

                try:
                    with diagnostic:
                        evidence_id = await engine._retrieve_smoke(
                            handle, request
                        )
                except Exception:
                    evidence_id = None
                    failure_kind = (
                        "CLASSIFIED_FAILURE"
                        if diagnostic.events
                        else "UNCLASSIFIED_FAILURE"
                    )

                if evidence_id is not None:
                    async with app() as session, session.begin():
                        resolved = await resolve_real_citations(
                            session, handle, (evidence_id,)
                        )
                        citation = resolved == (evidence_id,)

                    if verify_denials:
                        try:
                            await engine._call(
                                "_reserve_smoke_retrieval",
                                handle, request,
                            )
                        except BudgetRejected:
                            denials.append("replay")
                        else:
                            raise AssertionError("Replay accepted")

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

                assert context.search_calls == 0
                assert context.model_calls == 0
                assert len(rows) <= 1
                assert len(records) <= 1

                assert await session.scalar(
                    select(func.count()).select_from(ResearchEvidence)
                    .where(ResearchEvidence.task_id == handle.task_id)
                ) == 0

                operations = []

                for row in rows:
                    assert row.kind == "retrieval"
                    assert row.acquisition_origin == "live"
                    assert row.smoke_grant_id == grant_id
                    assert row.request_sha256 == retrieval_digest(request)
                    assert row.retry_ordinal == 0
                    assert row.retry_eligible is False
                    assert row.provider_name is None
                    assert row.reserved_provider_credits is None
                    assert row.observed_provider_credits is None

                    operations.append({
                        "id": str(row.id),
                        "kind": row.kind,
                        "status": row.status,
                        "request_sha256": row.request_sha256.hex(),
                        "reserved_at": row.reserved_at.isoformat(),
                        "dispatched_at": (
                            row.dispatched_at.isoformat()
                            if row.dispatched_at else None
                        ),
                        "resolved_at": (
                            row.resolved_at.isoformat()
                            if row.resolved_at else None
                        ),
                        "retry_ordinal": row.retry_ordinal,
                        "reserved_credits": None,
                        "observed_credits": None,
                    })

                evidence = []

                for item in records:
                    assert len(rows) == 1
                    validate_stored(handle, item, rows[0])

                    assert item.source_url == URL
                    assert item.retrieved_url == URL
                    assert item.published_at is None

                    evidence.append({
                        "id": str(item.id),
                        "source_url": item.source_url,
                        "retrieved_url": item.retrieved_url,
                        "source_identity_sha256": (
                            item.source_identity_sha256.hex()
                        ),
                        "content_sha256": item.content_hash.hex(),
                        "retrieved_at": item.retrieved_at.isoformat(),
                        "published_at": None,
                        "excerpt_length": len(item.excerpt),
                        "operation_ledger_id": str(item.operation_ledger_id),
                    })

                return {
                    "owner_id": str(handle.owner_id),
                    "task_id": str(handle.task_id),
                    "attempt_id": str(handle.attempt_id),
                    "grant_id": str(grant_id),
                    "grant_kind": "retrieval_only",
                    "generation": handle.generation,
                    "search_calls": context.search_calls,
                    "retrieval_calls": context.retrieval_calls,
                    "model_calls": context.model_calls,
                    "citation_verified": citation,
                    "publishable": False,
                    "operations": operations,
                    "evidence": evidence,
                    "denials": denials,
                    "failure_kind": failure_kind,
                    "diagnostics": diagnostic.events,
                }

        finally:
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

    raw = Path("/tmp/s08-g04b-preflight.xml").read_bytes()
    proof = json.loads(
        Path("/tmp/s08-g04b-preflight.json").read_text()
    )

    if (
        proof.get("approval") != APPROVAL
        or proof.get("sha256") != hashlib.sha256(raw).hexdigest()
    ):
        raise BudgetRejected("preflight_receipt_invalid")

    cases = ET.fromstring(raw).findall(".//testcase")

    if (
        len(cases) != proof["cases"]
        or any(
            c.find(tag) is not None
            for c in cases
            for tag in ("failure", "error", "skipped")
        )
    ):
        raise BudgetRejected("preflight_receipt_invalid")

    with Path("/tmp/s08-g04b-live.used").open("x") as stream:
        stream.write(APPROVAL)

    result = asyncio.run(execute_once())

    print(
        "G04B_RESULT=" + json.dumps(result, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print("G04B_RUNNER_FAILED_CLOSED", flush=True)
        raise SystemExit(1)
