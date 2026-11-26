
"""Graph-only recovery of frozen synthetic evaluation.

Preserves prior acquisition observations. No live provider,
external inference, persistence or publication authority.
"""
import hashlib
import json
import sys

from pathlib import Path
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError
from langsmith import tracing_context

from agentops_api.agent.s05.contract import S05GraphInput
from agentops_api.agent.s05.workflow import run_specialized_workflow
from agentops_api.services.s06_workflow import require_tracing_disabled

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def validation_details(exc):
    return [
        {
            "loc": [str(part) for part in item["loc"]],
            "type": item["type"],
        }
        for item in exc.errors(
            include_input=False,
            include_context=False,
            include_url=False,
        )
    ]

def main():
    assert Path("/.dockerenv").is_file()
    import os
    import socket
    import fcntl
    import struct

    assert "TAVILY_API_KEY" not in os.environ

    flags_by_interface = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        for _, name in socket.if_nameindex():
            response = fcntl.ioctl(
                probe.fileno(),
                0x8913,
                struct.pack("256s", name.encode()),
            )
            flags = struct.unpack_from("H", response, 16)[0]
            flags_by_interface[name] = flags

    active = sorted(
        name for name, flags in flags_by_interface.items()
        if flags & 0x1
    )

    print("INTERFACE_FLAGS=" + repr(flags_by_interface), flush=True)
    print("ACTIVE_INTERFACES=" + repr(active), flush=True)

    assert active == ["lo"], "Unexpected active network interface"

    ipv4 = Path("/proc/net/route").read_text().splitlines()[1:]

    for line in ipv4:
        fields = line.split()
        assert fields[0] == "lo", "Non-loopback IPv4 route"

    ipv6 = Path("/proc/net/ipv6_route")

    if ipv6.exists():
        for line in ipv6.read_text().splitlines():
            fields = line.split()
            assert len(fields) == 10
            assert fields[-1] == "lo", "Non-loopback IPv6 route"

    print("NETWORK_NAMESPACE_ISOLATION=PASS", flush=True)

    require_tracing_disabled()

    envelope = json.load(sys.stdin)

    dataset_raw = envelope["dataset"].encode()
    previous_raw = envelope["previous"].encode()

    assert sha(dataset_raw) == (
        "6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894"
    )

    assert sha(previous_raw) == (
        "fbba7930468d177641a60ebb47431a38543ade9d653cc9f179151d720bc9df1b"
    )

    cases = json.loads(dataset_raw)["cases"]
    previous = json.loads(previous_raw)

    assert len(cases) == len(previous["results"]) == 40
    assert previous["verified_fixture_sources"] == 66
    assert previous["graph_errors"] == 40

    by_id = {
        row["case_id"]: row for row in previous["results"]
    }

    rows = []

    for case in cases:
        old = by_id[case["id"]]

        assert old["graph_error"] == "ValidationError"
        assert old["verified_source_count"] == len(case["sources"])
        assert not old["source_errors"]

        values = {
            "task_id": uuid5(
                NAMESPACE_URL, "s08-eval-task:" + case["id"]
            ),
            "attempt_id": uuid5(
                NAMESPACE_URL, "s08-eval-attempt:" + case["id"]
            ),
            "question": case["question"],
        }

        original_validation = []

        try:
            S05GraphInput(
                **values,
                scope="Frozen synthetic evaluation, offline only",
            )
        except ValidationError as exc:
            original_validation = validation_details(exc)

        row = {
            "case_id": case["id"],
            "category": case["category"],
            "split": case["split"],
            "original_input_validation": original_validation,
            "retained_verified_source_count": (
                old["verified_source_count"]
            ),
            "input_validated": False,
            "graph_returned": False,
            "graph_outcome": None,
            "graph_error": None,
            "validation_errors": [],
            "quality_score": None,
        }

        start = monotonic()

        try:
            # Use the structured task scope expected by the
            # existing application contract, not free-form text.
            graph_input = S05GraphInput(**values, scope={})
            row["input_validated"] = True

            with tracing_context(enabled=False):
                graph = run_specialized_workflow(
                    graph_input,
                    deadline_monotonic=monotonic() + 30,
                )

            row["graph_outcome"] = str(graph.outcome)

            if getattr(graph, "publishable", False) is True:
                raise AssertionError("Unexpected publication authority")

            row["graph_returned"] = True

        except ValidationError as exc:
            row["graph_error"] = "ValidationError"
            row["validation_errors"] = validation_details(exc)

        except Exception as exc:
            row["graph_error"] = type(exc).__name__

        row["graph_duration_ms"] = round(
            (monotonic() - start) * 1000, 3
        )

        rows.append(row)

    report = {
        "classification": "FROZEN_SYNTHETIC_GRAPH_RECOVERY",
        "dataset_sha256": sha(dataset_raw),
        "prior_report_sha256": sha(previous_raw),
        "cases_executed": len(rows),
        "retained_verified_fixture_sources": 66,
        "fixture_acquisition_rerun": False,
        "valid_inputs": sum(
            r["input_validated"] for r in rows
        ),
        "graphs_returned": sum(
            r["graph_returned"] for r in rows
        ),
        "candidate_ready": sum(
            r["graph_returned"]
            and r["graph_outcome"] == "candidate_ready"
            for r in rows
        ),
        "graph_errors": sum(
            r["graph_error"] is not None for r in rows
        ),
        "external_model_calls": 0,
        "live_provider_calls": 0,
        "publication_executed": False,
        "manual_analyst_arm": "NOT_EXECUTED",
        "single_model_arm": "NOT_EXECUTED",
        "agentops_live_report_arm": "NOT_EXECUTED",
        "report_quality_metrics": previous["report_quality_metrics"],
        "quality_acceptance": "NOT_MEASURED",
        "results": rows,
    }

    print("GRAPH_RECOVERY=" + json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
