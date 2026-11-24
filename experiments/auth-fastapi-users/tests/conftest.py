"""Offline guards, sanitized diagnostics, and security result reporting."""

import os
import re
import socket
import subprocess
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import pytest

SENSITIVE_VALUES = tuple(character * 43 for character in "ABC") + (
    "unused-test-value",
)

# requirements, successful observation's conclusion, scope, expected case count
OBSERVATIONS = {
    "p01": (("AUTH-P01", "AUTH-P10"), "PASS", "imports, mapped initialization, offline metadata compilation", 1),
    "p02": (("AUTH-P02",), "PASS", "real strategy lifecycle with memory storage", 1),
    "p03": (("AUTH-P03",), "PASS", "digest-at-rest contract", 1),
    "p04": (("AUTH-P04",), "PASS", "per-token revocation versus cookie clearing", 1),
    "p05_absolute": (("AUTH-P05",), "PASS", "absolute cutoff with fake storage filtering", 1),
    "p05_idle": (("AUTH-P05",), "NOT_PROVIDED", "rolling idle expiration", 1),
    "p06": (("AUTH-P06",), "PASS", "active-user dependency enforcement", 1),
    "p07": (("AUTH-P07",), "PASS", "actual cookie response attributes", 1),
    "p08": (("AUTH-P08",), "NOT_PROVIDED", "server-side Origin and CSRF enforcement", 1),
    "p09_schema": (("AUTH-P09",), "FAIL", "stock schema differs from proposed split schema", 1),
    "p09_queries": (("AUTH-P09",), "PASS", "adapter query construction; no SQL execution", 1),
    "p09_mutations": (("AUTH-P09",), "FAIL", "adapter-owned commits observed through session mocks", 6),
    "p09_autobegin": (("AUTH-P09",), "FAIL", "unscoped create conflicts with autobegin=False", 1),
    "p09_dataclass": (("AUTH-P09",), "PASS", "dataclass is rejected as an ORM query model", 1),
    "p10_versions": (("AUTH-P10",), "PASS", "actual installed versions match experiment pins", 1),
    "p10_constraints": (("AUTH-P10",), "PASS", "selected declared requirements and Python constraints", 1),
}
EXTERNAL_GAPS = (
    ("AUTH-P10", "UNVERIFIED", "complete installed dependency consistency: separate pip check evidence"),
    ("AUTH-P10", "UNVERIFIED", "maintenance-mode risk acceptance: explicit architecture decision"),
    ("AUTH-P10", "UNVERIFIED", "security advisory review of the resolved dependency graph"),
)
_guard = pytest.MonkeyPatch()
_items: list[Any] = []
_reports: dict[str, dict[str, Any]] = {}
_collection_failed = False


def redact(text: str) -> str:
    """Sanitize fixture values and sensitive header representations."""
    for value in SENSITIVE_VALUES:
        text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)\bBearer\s+[^\s'\";,]+", "Bearer [REDACTED]", text)
    return re.sub(
        r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\b\s*[:=]\s*)[^\r\n]*",
        r"\1[REDACTED]",
        text,
    )


def aggregate(states: Sequence[str]) -> str:
    for state in ("FAIL", "BLOCKED", "UNVERIFIED", "NOT_PROVIDED"):
        if state in states:
            return state
    return "PASS" if states and all(s == "PASS" for s in states) else "UNVERIFIED"


def describe(states: Sequence[str]) -> str:
    observed = sorted(set(states) & {"PASS", "FAIL", "NOT_PROVIDED"})
    gaps = sorted(set(states) & {"BLOCKED", "UNVERIFIED"})
    return (
        f"{aggregate(states)}; observed={','.join(observed) or 'none'}; "
        f"evidence_gaps={','.join(gaps) or 'none'}"
    )


def sanitize_report(report: Any) -> None:
    if report.longrepr is not None:
        if isinstance(report.longrepr, tuple):
            report.longrepr = tuple(
                redact(value) if isinstance(value, str) else value
                for value in report.longrepr
            )
        else:
            report.longrepr = redact(str(report.longrepr))
    report.sections = [(name, redact(content)) for name, content in report.sections]
    if getattr(report, "wasxfail", None):
        report.wasxfail = redact(str(report.wasxfail))


def deny_external_io(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("External I/O is forbidden in this experiment")


def pytest_configure(config: pytest.Config) -> None:
    """Install guards before test-module collection."""
    global _collection_failed
    from sqlalchemy.engine import Engine

    _items.clear()
    _reports.clear()
    _collection_failed = False
    for name in ("create_connection", "getaddrinfo"):
        _guard.setattr(socket, name, deny_external_io)
    for name in ("connect", "connect_ex", "sendto"):
        _guard.setattr(socket.socket, name, deny_external_io)
    _guard.setattr(subprocess, "Popen", deny_external_io)
    _guard.setattr(os, "system", deny_external_io)
    _guard.setattr(Engine, "connect", deny_external_io)
    _guard.setattr(Engine, "raw_connection", deny_external_io)
    config.option.showlocals = False
    config.option.tbstyle = "short"
    config.option.showcapture = "no"


def pytest_unconfigure(config: pytest.Config) -> None:
    _guard.undo()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[Any]) -> None:
    _items[:] = items
    for item in items:
        marker = item.get_closest_marker("contract")
        if marker is not None:
            if len(marker.args) != 1 or marker.args[0] not in OBSERVATIONS:
                raise pytest.UsageError("Unknown compatibility observation marker")


@pytest.hookimpl(tryfirst=True)
def pytest_collectreport(report: Any) -> None:
    global _collection_failed
    if report.failed:
        _collection_failed = True
    sanitize_report(report)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: Any, call: Any):
    outcome = yield
    report = outcome.get_result()
    marker = item.get_closest_marker("contract")
    xfail = item.get_closest_marker("xfail")
    expected_exception = xfail.kwargs.get("raises") if xfail else None
    report.poc_known_failure = bool(
        report.when == "call"
        and marker is not None
        and marker.args[0] == "p03"
        and expected_exception is not None
        and call.excinfo is not None
        and call.excinfo.errisinstance(expected_exception)
    )
    sanitize_report(report)
    _reports.setdefault(item.nodeid, {})[report.when] = report


def observation_states(item: Any, success_state: str) -> list[str]:
    reports = _reports.get(item.nodeid, {})
    call = reports.get("call")
    states: list[str] = []
    known_failure = bool(call and getattr(call, "poc_known_failure", False))
    if known_failure:
        states.append("FAIL")
    elif call is not None and call.passed:
        states.append(success_state)
    for phase in ("setup", "call", "teardown"):
        report = reports.get(phase)
        if report is None:
            states.append("UNVERIFIED")
        elif report.failed and not (phase == "call" and known_failure):
            states.append("BLOCKED")
        elif report.skipped and not (phase == "call" and known_failure):
            states.append("UNVERIFIED")
    return states or ["UNVERIFIED"]


@pytest.fixture
def reporting_tools() -> dict[str, Any]:
    return {"aggregate": aggregate, "redact": redact}


def pytest_terminal_summary(terminalreporter: Any) -> None:
    terminalreporter.section("Individual security observations")
    requirement_states: dict[str, list[str]] = defaultdict(list)
    for key, (requirements, success_state, scope, expected_count) in OBSERVATIONS.items():
        matching = [
            item for item in _items
            if item.get_closest_marker("contract") is not None
            and item.get_closest_marker("contract").args[0] == key
        ]
        for item in matching:
            states = observation_states(item, success_state)
            terminalreporter.write_line(f"{key}/{item.name}: {describe(states)} — {scope}")
            for requirement in requirements:
                requirement_states[requirement].extend(states)
        missing = max(0, expected_count - len(matching))
        if missing:
            state = "BLOCKED" if _collection_failed else "UNVERIFIED"
            terminalreporter.write_line(f"{key}: {state} — {missing} expected case(s) not collected")
            for requirement in requirements:
                requirement_states[requirement].append(state)
        if len(matching) > expected_count:
            terminalreporter.write_line(f"{key}: BLOCKED — observation inventory requires review")
            for requirement in requirements:
                requirement_states[requirement].append("BLOCKED")
    for requirement, state, scope in EXTERNAL_GAPS:
        terminalreporter.write_line(f"{requirement}: {state} — {scope}")
        requirement_states[requirement].append(state)
    terminalreporter.section("Aggregated requirements — diagnostic, not adoption")
    for number in range(1, 11):
        requirement = f"AUTH-P{number:02d}"
        terminalreporter.write_line(f"{requirement}: {describe(requirement_states[requirement])}")
    terminalreporter.write_line("PASS applies only to the listed observation scope.")
    terminalreporter.write_line("Known security FAIL remains FAIL even if pytest exits zero.")
    terminalreporter.write_line("Mocks do not verify PostgreSQL persistence, rollback, or isolation.")
    terminalreporter.write_line("Authentication adoption is NOT approved by this diagnostic run.")
