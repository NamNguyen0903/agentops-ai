"""Application-owned credential access.

Live authorization must succeed before secret lookup.
No real secret lookup is possible under the current
S06 authorization policy.
"""

import os
from dataclasses import dataclass, field

from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)

from .authorization import require_live_authorization


@dataclass(frozen=True, slots=True, repr=False)
class TavilyCredential:
    value: str = field(repr=False)

    def __repr__(self):
        return "TavilyCredential([REDACTED])"

    def __str__(self):
        return "[REDACTED]"


def read_tavily_credential():
    require_live_authorization()

    value = os.environ.get("TAVILY_API_KEY")

    if (
        type(value) is not str
        or not 1 <= len(value) <= 512
        or not value.isascii()
        or any(
            ord(char) <= 32 or ord(char) >= 127
            for char in value
        )
    ):
        raise AcquisitionError(
            ErrorCode.PROVIDER_FAILURE
        ) from None

    return TavilyCredential(value)


def authorization_header(credential):
    if type(credential) is not TavilyCredential:
        raise AcquisitionError(
            ErrorCode.INVALID_INPUT
        ) from None

    value = credential.value

    if (
        type(value) is not str
        or not 1 <= len(value) <= 512
        or not value.isascii()
        or any(
            ord(char) <= 32 or ord(char) >= 127
            for char in value
        )
    ):
        raise AcquisitionError(
            ErrorCode.PROVIDER_FAILURE
        ) from None

    return "Bearer " + value
