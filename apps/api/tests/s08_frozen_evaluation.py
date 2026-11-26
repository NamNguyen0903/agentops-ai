"""Frozen synthetic evaluation preflight.

Run the existing deterministic S05 graph and actual offline S06
fixture acquisition for each frozen case. These are separate
component exercises, not a three-arm report quality benchmark.
No external model, live acquisition or publication.
"""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

from langsmith import tracing_context
from agentops_api.agent.s05.contract import S05GraphInput
from agentops_api.agent.s05.workflow import run_specialized_workflow
from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import (
    SearchRequest, RetrievalRequest,
)
from agentops_api.agent.s06.retrieval import retrieve_offline
from agentops_api.agent.s06.transport import (
    FixtureResolver, FixtureTransport, TransportResponse,
)
from agentops_api.services.s06_workflow import require_tracing_disabled

EXPECTED = "6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    assert Path("/.dockerenv").is_file()
    assert os.environ.get("AGENTOPS_RUN_DB_INTEGRATION") == "1"
    assert "TAVILY_API_KEY" not in os.environ
    require_tracing_disabled()

    raw = sys.stdin.buffer.read()
    assert sha(raw) == EXPECTED

    data = json.loads(raw)
    cases = data["cases"]

    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40

    assert Counter(case["split"] for case in cases) == {
        "development": 30,
        "held_out": 10,
    }

    categories = Counter(case["category"] for case in cases)
    assert len(categories) == 10
    assert set(categories.values()) == {4}

    results = []

    for case in cases:
        start = monotonic()
        question = case["question"]
        SearchRequest(query=question)

        result = {
            "case_id": case["id"],
            "category": case["category"],
            "split": case["split"],
            "origin": "synthetic_fixture",
            "fixture_source_count": len(case["sources"]),
            "verified_source_count": 0,
            "source_ids": [],
            "source_errors": [],
            "graph_outcome": None,
            "graph_error": None,
            "graph_publishable": None,
            "quality_score": None,
        }

        budget = Budget()
        sources = case["sources"]

        assert len({
            item["source_id"] for item in sources
        }) == len(sources)

        for index, source in enumerate(sources):
            body = source["text"].encode()

            assert sha(body) == source["content_sha256"]
            assert source["origin"].startswith("synthetic")

            url = f"https://example.com/s08-fixture/{index}"

            response = TransportResponse(
                status=200,
                headers=(
                    ("Content-Type", "text/plain"),
                    ("Content-Length", str(len(body))),
                ),
                chunks=(body,),
                peer_ip="93.184.216.34",
                tls_verified=True,
                tls_hostname="example.com",
            )

            try:
                page = retrieve_offline(
                    RetrievalRequest(url=url),
                    budget,
                    resolver=FixtureResolver({
                        "example.com": ("93.184.216.34",),
                    }),
                    transport=FixtureTransport((response,)),
                )

                assert page.synthetic is True
                assert sha(page.body) == source["content_sha256"]

                result["verified_source_count"] += 1
                result["source_ids"].append(source["source_id"])

            except Exception as exc:
                result["source_errors"].append({
                    "source_id": source["source_id"],
                    "error_type": type(exc).__name__,
                })

        graph_start = monotonic()

        try:
            graph_input = S05GraphInput(
                task_id=uuid5(
                    NAMESPACE_URL, "s08-eval-task:" + case["id"]
                ),
                attempt_id=uuid5(
                    NAMESPACE_URL, "s08-eval-attempt:" + case["id"]
                ),
                question=question,
                scope="Frozen synthetic evaluation, offline only",
            )

            with tracing_context(enabled=False):
                graph = run_specialized_workflow(graph_input)

            result["graph_outcome"] = str(graph.outcome)
            result["graph_publishable"] = getattr(
                graph, "publishable", None
            )

            if result["graph_publishable"] is True:
                raise AssertionError("Publishable fixture")

        except Exception as exc:
            result["graph_error"] = type(exc).__name__

        result["graph_duration_ms"] = round(
            (monotonic() - graph_start) * 1000, 3
        )

        result["component_duration_ms"] = round(
            (monotonic() - start) * 1000, 3
        )

        results.append(result)

    report = {
        "dataset_sha256": EXPECTED,
        "classification": "FROZEN_SYNTHETIC_COMPONENT_EVALUATION",
        "cases_executed": len(results),
        "splits": dict(Counter(r["split"] for r in results)),
        "fixture_sources": sum(
            r["fixture_source_count"] for r in results
        ),
        "verified_fixture_sources": sum(
            r["verified_source_count"] for r in results
        ),
        "graph_completed": sum(
            r["graph_error"] is None for r in results
        ),
        "graph_errors": sum(
            r["graph_error"] is not None for r in results
        ),
        "external_model_calls": 0,
        "live_provider_calls": 0,
        "external_provider_cost_usd": 0,
        "report_quality_metrics": {
            "structural_report_citation_validity": None,
            "citation_coverage": None,
            "human_groundedness": None,
            "report_completion_rate": None,
            "human_usefulness": None,
            "end_to_end_report_p95_seconds": None,
            "mean_report_variable_cost_usd": None,
            "paired_analyst_time_savings": None,
        },
        "manual_analyst_arm": "NOT_EXECUTED",
        "single_model_arm": "NOT_EXECUTED",
        "agentops_live_report_arm": "NOT_EXECUTED",
        "quality_acceptance": "NOT_MEASURED",
        "results": results,
    }

    print(
        "EVAL_RESULT=" + json.dumps(report, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    main()
