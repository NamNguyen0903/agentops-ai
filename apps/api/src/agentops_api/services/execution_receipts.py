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


def _issue(reservation, outcome, *, retryable=False):
    if outcome not in {"succeeded", "failed", "indeterminate"}:
        raise BudgetRejected("invalid_observed_outcome")
    if type(retryable) is not bool or (retryable and outcome != "failed"):
        raise BudgetRejected("invalid_observed_outcome")
    receipt = _Receipt()
    with _LOCK:
        _RECEIPTS[receipt] = (reservation, outcome, retryable)
    return receipt


def _consume(receipt, reservation):
    if type(receipt) is not _Receipt:
        raise BudgetRejected("untrusted_outcome_receipt")
    with _LOCK:
        value = _RECEIPTS.pop(receipt, None)
    if value is None or value[0] != reservation:
        raise BudgetRejected("untrusted_outcome_receipt")
    return value[1:]
