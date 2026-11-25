"""Fail-closed external execution policy."""

from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)


def require_live_authorization():
    # S06 owner approval covers implementation and isolated
    # verification only. No runtime switch can activate egress.
    raise AcquisitionError(ErrorCode.EXTERNAL_DISABLED)
