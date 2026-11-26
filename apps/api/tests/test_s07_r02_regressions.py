"""Regression for precise policy-error provenance and import boundaries."""
from pathlib import Path
import ast
import pytest
from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.contracts import RetrievalRequest
from agentops_api.agent.s06.errors import AcquisitionError, ErrorCode
from agentops_api.agent.s06.retrieval import retrieve_offline
from agentops_api.agent.s06.transport import FixtureResolver, FixtureTransport
from test_s06_acquisition import response


@pytest.mark.parametrize("code", [ErrorCode.BUDGET_EXHAUSTED, ErrorCode.DEADLINE_EXCEEDED])
def test_predispatch_policy_error_is_preserved_and_transport_is_not_called(monkeypatch, code):
    def reject(self, deadline):
        raise AcquisitionError(code)
    monkeypatch.setattr(Budget, "reserve_retrieval", reject)
    transport = FixtureTransport((response(),))
    with pytest.raises(AcquisitionError) as exc:
        retrieve_offline(
            RetrievalRequest(url="https://example.com/"), Budget(),
            resolver=FixtureResolver({"example.com": ("93.184.216.34",)}), transport=transport,
        )
    assert exc.value.code is code
    assert transport.requests == ()


@pytest.mark.parametrize("error", [RuntimeError("PRIVATE_TRANSPORT_DETAIL"), AcquisitionError(ErrorCode.BUDGET_EXHAUSTED)])
def test_transport_cannot_spoof_policy_error_or_leak_details(monkeypatch, error):
    def broken(*args, **kwargs):
        raise error
    monkeypatch.setattr(FixtureTransport, "send", broken)
    with pytest.raises(AcquisitionError) as exc:
        retrieve_offline(
            RetrievalRequest(url="https://example.com/"), Budget(),
            resolver=FixtureResolver({"example.com": ("93.184.216.34",)}), transport=FixtureTransport((response(),)),
        )
    assert exc.value.code is ErrorCode.TRANSPORT_FAILURE
    assert str(exc.value) == "transport_failure"


def test_original_s05_security_allowlists_remain_exact():
    # The implementation repair must not add a service/parent import to S05.
    from test_s05_security_boundaries import PACKAGE_ROOT, _source_violations
    assert _source_violations(PACKAGE_ROOT) == []
    assert not any(
        isinstance(n, ast.ImportFrom) and n.module == "agentops_api.agent.durable_hooks"
        for n in ast.walk(ast.parse((PACKAGE_ROOT / "controller.py").read_text()))
    )
