"""One-use, process-local receipts issued at application dispatch boundaries.

A receipt certifies a locally observed boundary result, never remote
cancellation, provider billing, publication or semantic grounding.
"""
from threading import Lock
from weakref import WeakKeyDictionary

from agentops_api.services.execution_budget import BudgetRejected

_RECEIPTS = WeakKeyDictionary()
_LOCK = Lock()


class _Receipt:
    pass


def _issue(reservation, outcome, *, retryable=False, provider_credits=None):
    if outcome not in {"succeeded", "failed", "indeterminate"}:
        raise BudgetRejected("invalid_observed_outcome")
    if type(retryable) is not bool or (retryable and outcome != "failed"):
        raise BudgetRejected("invalid_observed_outcome")
    if provider_credits is not None and (
        type(provider_credits) is not int
        or provider_credits != 1
        or outcome != "succeeded"
        or retryable
    ):
        raise BudgetRejected("invalid_provider_usage")
    receipt = _Receipt()
    with _LOCK:
        _RECEIPTS[receipt] = (reservation, outcome, retryable, provider_credits)
    return receipt


def _consume(receipt, reservation, *, include_provider=False):
    if type(receipt) is not _Receipt:
        raise BudgetRejected("untrusted_outcome_receipt")
    with _LOCK:
        value = _RECEIPTS.pop(receipt, None)
    if value is None or value[0] != reservation:
        raise BudgetRejected("untrusted_outcome_receipt")
    if include_provider is True:
        return value[1:]
    if value[3] is not None:
        raise BudgetRejected("provider_receipt_required")
    return value[1:3]
