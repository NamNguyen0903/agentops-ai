"""Conservative retry classification for retrieval I/O."""

import errno

from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)


class RetryableTransportFailure(AcquisitionError):
    def __init__(self):
        super().__init__(ErrorCode.TRANSPORT_FAILURE)


TRANSIENT_ERRNOS = frozenset({
    errno.ECONNRESET,
    errno.ECONNREFUSED,
    errno.ECONNABORTED,
    errno.EPIPE,
})


def transport_failure(exc):
    if isinstance(exc, TimeoutError):
        return AcquisitionError(
            ErrorCode.DEADLINE_EXCEEDED
        )

    if (
        isinstance(exc, OSError)
        and exc.errno in TRANSIENT_ERRNOS
    ):
        return RetryableTransportFailure()

    return AcquisitionError(
        ErrorCode.TRANSPORT_FAILURE
    )
