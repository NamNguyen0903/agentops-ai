"""Sequential application-owned acquisition limits."""

from dataclasses import dataclass
from time import monotonic
from math import isfinite
from typing import Callable

from .errors import AcquisitionError, ErrorCode


MAX_SEARCH_CALLS = 6
MAX_RETRIEVAL_CALLS = 12
MAX_OPERATION_SECONDS = 15.0
MAX_EXECUTION_SECONDS = 180.0
MAX_RETRIES = 1
MAX_REDIRECTS = 3
MAX_BODY_BYTES = 1048576


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    searches: int
    retrievals: int


class Budget:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._clock = clock
        self._last_time = None
        self._deadline = self._now() + MAX_EXECUTION_SECONDS
        self._searches = 0
        self._retrievals = 0

    def _now(self) -> float:
        try:
            value = self._clock()
        except Exception:
            raise AcquisitionError(
                ErrorCode.INVALID_INPUT
            ) from None

        if (
            type(value) not in {int, float}
            or not isfinite(value)
            or (
                self._last_time is not None
                and value < self._last_time
            )
        ):
            raise AcquisitionError(
                ErrorCode.INVALID_INPUT
            )

        self._last_time = value
        return float(value)

    def snapshot(self) -> UsageSnapshot:
        return UsageSnapshot(
            self._searches,
            self._retrievals,
        )

    def check(self, deadline=None) -> None:
        limit = self._deadline

        if deadline is not None:
            limit = min(limit, deadline)

        if self._now() >= limit:
            raise AcquisitionError(
                ErrorCode.DEADLINE_EXCEEDED
            )

    def operation_deadline(self) -> float:
        self.check()
        return min(
            self._deadline,
            self._now() + MAX_OPERATION_SECONDS,
        )

    def remaining(self, deadline: float) -> float:
        value = min(
            deadline, self._deadline
        ) - self._now()

        if value <= 0:
            raise AcquisitionError(
                ErrorCode.DEADLINE_EXCEEDED
            )

        return value

    def reserve_search(self, deadline: float) -> None:
        self.check(deadline)

        if self._searches >= MAX_SEARCH_CALLS:
            raise AcquisitionError(
                ErrorCode.BUDGET_EXHAUSTED
            )

        self._searches += 1

    def reserve_retrieval(self, deadline: float) -> None:
        self.check(deadline)

        if self._retrievals >= MAX_RETRIEVAL_CALLS:
            raise AcquisitionError(
                ErrorCode.BUDGET_EXHAUSTED
            )

        self._retrievals += 1
