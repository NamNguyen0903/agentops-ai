"""Application-owned, per-execution S05 accounting.

This controller owns invocation accounting only.
It has no provider, persistence, publication or
external tool authority.

Public workflow repair activation remains outside
the scope of this module.
"""

from contextvars import ContextVar
from time import monotonic
from math import isfinite

from agentops_api.agent.s05.contract import (
    MAX_ADAPTER_INVOCATIONS,
    MAX_REPAIR_ATTEMPTS,
    MAX_RUNTIME_SECONDS,
    ExecutionCounters,
)
from agentops_api.agent.s05.validation import (
    S05StateIntegrityError,
)


class S05BudgetError(ValueError):
    """Sanitized execution budget exhaustion."""

    category = "budget_exceeded"

    def __init__(self) -> None:
        super().__init__("S05 execution budget exhausted")


class S05DeadlineError(ValueError):
    """Sanitized soft deadline exhaustion."""

    category = "deadline_exceeded"

    def __init__(self) -> None:
        super().__init__("S05 execution deadline exceeded")


class _InvalidDeadlineError(ValueError):
    """Invalid caller-supplied deadline."""

    def __init__(self) -> None:
        super().__init__("invalid S05 deadline")


def _read_monotonic():
    value = monotonic()

    if type(value) is not float:
        raise S05StateIntegrityError()

    if not isfinite(value):
        raise S05StateIntegrityError()

    return value


class ExecutionController:
    """One bounded accounting ledger per synchronous execution.

    Only application-owned invocation boundaries may use
    this controller. It is not a Python execution sandbox
    or a concurrent execution primitive.

    Repair reservation is private and is not an eligibility
    decision. Trusted eligibility and deadline checks must
    precede any future repair activation.
    """

    __slots__ = (
        "_ledger",
        "_active",
        "_failed",
        "_deadline",
        "_last_clock",
        "_expired",
        "_clock_failed",
    )

    def __init__(
        self,
        *,
        deadline_monotonic=None,
    ) -> None:
        started = _read_monotonic()
        maximum = started + MAX_RUNTIME_SECONDS

        if deadline_monotonic is not None:
            if type(deadline_monotonic) not in (
                int, float
            ):
                raise _InvalidDeadlineError()

            if type(deadline_monotonic) is float:
                if not isfinite(deadline_monotonic):
                    raise _InvalidDeadlineError()

            maximum = min(
                maximum, deadline_monotonic
            )

        self._deadline = maximum
        self._last_clock = started
        self._expired = started >= maximum
        self._clock_failed = False

        self._ledger = ()
        self._active = False
        self._failed = False

    def _observe_deadline(self):
        """Record expiry without masking security checks."""

        try:
            now = _read_monotonic()

            if now < self._last_clock:
                self._clock_failed = True
                return

            self._last_clock = now

            if now >= self._deadline:
                self._expired = True

        except Exception:
            self._clock_failed = True

    def check_deadline(self):
        """Reject expired or untrustworthy execution clocks."""

        self._observe_deadline()

        if self._clock_failed:
            raise S05StateIntegrityError()

        if self._expired:
            raise S05DeadlineError()

    @property
    def invocation_history(self):
        """Return immutable reservation history."""

        return self._ledger

    def snapshot(self) -> ExecutionCounters:
        """Return an independent typed counter snapshot."""

        return ExecutionCounters(
            adapter_invocations=len(self._ledger),
            repair_attempts=sum(
                1
                for _, repair in self._ledger
                if repair
            ),
        )

    @property
    def repair_used(self) -> bool:
        return self.snapshot().repair_attempts != 0

    def _reserve(self, adapter, repair=False) -> None:
        """Consume an allowance before adapter execution."""

        if (
            type(adapter) is not str
            or adapter not in (
                "planner",
                "research",
                "writer",
            )
            or type(repair) is not bool
        ):
            raise S05StateIntegrityError()

        if self._active:
            raise S05StateIntegrityError()

        current = self.snapshot()

        if (
            current.adapter_invocations
            >= MAX_ADAPTER_INVOCATIONS
        ):
            raise S05BudgetError()

        if repair and (
            current.repair_attempts
            >= MAX_REPAIR_ATTEMPTS
        ):
            raise S05BudgetError()

        if self._failed:
            raise S05StateIntegrityError()

        if repair:
            if adapter not in (
                "planner", "writer"
            ):
                raise S05StateIntegrityError()

            if not self._ledger:
                raise S05StateIntegrityError()

            if self._ledger[-1] != (
                adapter, False
            ):
                raise S05StateIntegrityError()

        else:
            normal_history = tuple(
                name
                for name, is_repair in self._ledger
                if not is_repair
            )

            order = (
                "planner",
                "research",
                "writer",
            )

            index = len(normal_history)

            if index >= len(order):
                raise S05StateIntegrityError()

            if normal_history != order[:index]:
                raise S05StateIntegrityError()

            if adapter != order[index]:
                raise S05StateIntegrityError()

        self.check_deadline()

        self._ledger = (
            *self._ledger,
            (adapter, repair),
        )

    def invoke(self, adapter, operation, *args, **kwargs):
        """Execute one normal application-owned invocation."""

        return self._invoke(
            adapter,
            operation,
            args,
            kwargs,
            repair=False,
        )

    def _invoke_repair(
        self, adapter, operation, *args, **kwargs
    ):
        """Internal repair accounting primitive.

        Not connected to the public workflow.
        This method does not determine repair eligibility.
        """

        return self._invoke(
            adapter,
            operation,
            args,
            kwargs,
            repair=True,
        )

    def _invoke(
        self,
        adapter,
        operation,
        args,
        kwargs,
        *,
        repair,
    ):
        if not callable(operation):
            raise S05StateIntegrityError()

        self._reserve(adapter, repair)

        try:
            result = self._execute_reserved(
                operation, args, kwargs
            )

        except Exception:
            self.check_deadline()
            raise

        self.check_deadline()

        return result

    def _execute_reserved(
        self, operation, args, kwargs
    ):
        self._active = True
        completed = False

        try:
            result = operation(*args, **kwargs)
            completed = True
            return result

        finally:
            self._active = False

            # Reservations are never rolled back.
            # Unexpected adapter failure closes this
            # controller against further invocations.
            if not completed:
                self._failed = True

            self._observe_deadline()



# Execution-local binding. The default contains no
# mutable controller and grants no execution authority.

# Application-owned observer binding. The pure S05 layer imports no service,
# network or persistence module; the application binds it for isolated runs.
_DURABLE_OBSERVER = ContextVar("s07_durable_observer", default=None)


_ACTIVE_CONTROLLER = ContextVar(
    "s05_execution_controller",
    default=None,
)


_REQUIRED_CONTROLLER = ContextVar(
    "s05_required_execution_controller",
    default=None,
)


class _AdapterExecutionFailure(ValueError):
    """Sanitized adapter-body failure."""

    def __init__(self):
        super().__init__("S05 adapter execution failed")


class _InvocationBoundaryError(ValueError):
    """Internal sanitized controller-boundary failure."""

    __slots__ = ("_category",)

    def __init__(self, category):
        self._category = category
        super().__init__("S05 invocation boundary rejected")


def _current_controller():
    controller = _ACTIVE_CONTROLLER.get()
    required = _REQUIRED_CONTROLLER.get()

    if required is not None:
        if (
            type(required) is not ExecutionController
            or controller is not required
        ):
            raise S05StateIntegrityError()

    elif controller is not None:
        raise S05StateIntegrityError()

    return controller


def _invoke_fixture(adapter, operation, *args, **kwargs):
    return _invoke_fixture_mode(
        adapter, operation, args, kwargs, repair=False
    )


def _invoke_fixture_mode(
    adapter, operation, args, kwargs, *, repair
):
    """Enforce execution authority before adapter entry."""

    boundary_category = None
    controller = None

    try:
        controller = _current_controller()

    except Exception:
        boundary_category = "security_violation"

    if boundary_category is not None:
        raise _InvocationBoundaryError(
            boundary_category
        )

    if not callable(operation):
        raise _InvocationBoundaryError(
            "security_violation"
        )

    # A direct node invocation outside a public
    # execution retains isolated compatibility.
    # Public executions require both bindings.

    if repair and controller is None:
        raise _InvocationBoundaryError("security_violation")

    if controller is not None:
        try:
            controller._reserve(adapter, repair)

        except Exception as error:
            if type(error) is S05BudgetError:
                boundary_category = "budget_exceeded"
            elif type(error) is S05DeadlineError:
                boundary_category = "deadline_exceeded"
            else:
                boundary_category = "security_violation"

    if boundary_category is not None:
        raise _InvocationBoundaryError(
            boundary_category
        )

    original_operation = operation

    def accounted_operation(*values, **options):
        observer = _DURABLE_OBSERVER.get()
        if observer is None:
            return original_operation(*values, **options)
        return observer.adapter(
            adapter, repair, original_operation, values, options
        )

    operation = accounted_operation
    failed = False
    result = None

    # No exception originating in the adapter body
    # may be interpreted as a reservation error.

    try:
        if controller is None:
            result = operation(*args, **kwargs)

        else:
            result = controller._execute_reserved(
                operation, args, kwargs
            )

    except Exception:
        failed = True

    if failed:
        raise _AdapterExecutionFailure()

    return result


def _invocation_counters(expected_count):
    """Return accounting authority for normal node output."""

    controller = _current_controller()

    if controller is None:
        return ExecutionCounters(
            adapter_invocations=expected_count
        )

    counters = controller.snapshot()

    if (
        counters.adapter_invocations != expected_count
        or counters.repair_attempts != 0
    ):
        raise S05StateIntegrityError()

    return counters


def _raise_boundary_error(error):
    """Raise only recognized application-boundary errors."""

    if type(error) is not _InvocationBoundaryError:
        return

    category = object.__getattribute__(
        error, "_category"
    )

    if (
        type(category) is str
        and category == "budget_exceeded"
    ):
        raise S05BudgetError()

    if (
        type(category) is str
        and category == "deadline_exceeded"
    ):
        raise S05DeadlineError()

    raise S05StateIntegrityError()



# Repair-aware accounting authority.
# These helpers do not activate public repair.


def _approved_history(normal_count, repair_at=None):
    """Construct one permitted invocation history."""

    if (
        type(normal_count) is not int
        or not 0 <= normal_count <= 3
    ):
        raise S05StateIntegrityError()

    if repair_at is not None:
        if type(repair_at) is not str:
            raise S05StateIntegrityError()

        if repair_at not in ("planner", "writer"):
            raise S05StateIntegrityError()

    names = ("planner", "research", "writer")
    normal = names[:normal_count]

    if repair_at is not None and repair_at not in normal:
        raise S05StateIntegrityError()

    history = ()

    for name in normal:
        history = (*history, (name, False))

        if name == repair_at:
            history = (*history, (name, True))

    return history


def _strict_history_equal(actual, expected):
    """Compare bounded ledger entries without coercion."""

    if type(actual) is not tuple:
        return False

    if len(actual) != len(expected):
        return False

    for left, right in zip(actual, expected):
        if type(left) is not tuple or len(left) != 2:
            return False

        if type(left[0]) is not str:
            return False

        if type(left[1]) is not bool:
            return False

        if left[0] != right[0]:
            return False

        if left[1] is not right[1]:
            return False

    return True


def _verified_stage_counters(normal_count):
    """Reconstruct counters from approved controller history.

    Without a bound controller, only the historical normal
    path is authorized. Repaired counters never originate
    from graph state or adapter output.
    """

    expected = _approved_history(normal_count)
    active = _current_controller()

    if active is None:
        return ExecutionCounters(
            adapter_invocations=normal_count
        )

    history = active.invocation_history

    permitted = [expected]

    if normal_count >= 1:
        permitted.append(
            _approved_history(normal_count, "planner")
        )

    if normal_count == 3:
        permitted.append(
            _approved_history(normal_count, "writer")
        )

    matched = None

    for candidate in permitted:
        if _strict_history_equal(history, candidate):
            matched = candidate
            break

    if matched is None:
        raise S05StateIntegrityError()

    if active._active is not False:
        raise S05StateIntegrityError()

    if active._failed is not False:
        raise S05StateIntegrityError()

    return ExecutionCounters(
        adapter_invocations=len(matched),
        repair_attempts=sum(
            1 for _, repair in matched if repair
        ),
    )


def _verify_stage_accounting(state, normal_count):
    """Verify graph accounting against execution authority."""

    expected = _verified_stage_counters(normal_count)
    actual = state["counters"]

    from agentops_api.agent.s05.validation import (
        _strict_equal,
        _verify_exact_model_shape,
    )

    valid = False

    try:
        _verify_exact_model_shape(
            actual, ExecutionCounters
        )

        valid = (
            actual.__pydantic_private__ is None
            and _strict_equal(
                actual.__dict__, expected.__dict__
            )
            and state["repair_used"] is (
                expected.repair_attempts == 1
            )
        )

    except Exception:
        pass

    if not valid:
        raise S05StateIntegrityError()

    return expected



def _repair_available():
    """Only a bound application controller can authorize repair."""
    active = _current_controller()

    if active is None:
        return False

    if active._active is not False:
        raise S05StateIntegrityError()

    if active._failed is not False:
        raise S05StateIntegrityError()

    active.check_deadline()

    return not active.repair_used


def _invoke_authorized_repair(adapter, operation, *args):
    """Reserve one repair through the sanitized adapter boundary."""
    if _current_controller() is None:
        raise S05StateIntegrityError()

    return _invoke_fixture_mode(
        adapter, operation, args, {}, repair=True
    )


def _verify_incoming_accounting(state, expected):
    """Check the preserved accounting of an incoming node state."""
    from agentops_api.agent.s05.validation import (
        _strict_equal,
        _verify_exact_model_shape,
    )

    actual = state["counters"]

    try:
        _verify_exact_model_shape(actual, ExecutionCounters)

        valid = (
            actual.__pydantic_private__ is None
            and _strict_equal(
                actual.__dict__, expected.__dict__
            )
            and state["repair_used"] is (
                expected.repair_attempts == 1
            )
        )

    except Exception:
        valid = False

    if not valid:
        raise S05StateIntegrityError()


def _require_invocation_progress(
    active, previous, adapter, *, repair
):
    """Reconcile exact ledger transitions after adapter return."""
    if _current_controller() is not active:
        raise S05StateIntegrityError()

    if active is None:
        if repair:
            raise S05StateIntegrityError()
        return

    if not _strict_history_equal(
        active.invocation_history,
        (*previous, (adapter, repair)),
    ):
        raise S05StateIntegrityError()

    if active._active is not False:
        raise S05StateIntegrityError()
