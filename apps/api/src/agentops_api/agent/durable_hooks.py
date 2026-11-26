"""Internal accounting binding; no worker or external authority on import.

Absent a binding, the established S05/S06 interfaces retain their behavior.
Only the application service binds the observer. This is not a Python sandbox.
"""
from functools import wraps

from agentops_api.agent.s05.controller import _DURABLE_OBSERVER as _OBSERVER


def acquisition_boundary(kind, *, hop=False):
    def decorate(operation):
        @wraps(operation)
        def invoke(*args, **kwargs):
            observer = _OBSERVER.get()
            if observer is None:
                return operation(*args, **kwargs)
            return observer.acquire(kind, operation, args, kwargs, hop=hop)
        return invoke
    return decorate


def invoke_adapter(name, repair, operation, args, kwargs):
    observer = _OBSERVER.get()
    if observer is None:
        return operation(*args, **kwargs)
    return observer.adapter(name, repair, operation, args, kwargs)
