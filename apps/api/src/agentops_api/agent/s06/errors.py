"""Sanitized acquisition failures."""

from enum import Enum


class ErrorCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EXTERNAL_DISABLED = "external_disabled"
    UNSAFE_DESTINATION = "unsafe_destination"
    DNS_FAILURE = "dns_failure"
    TRANSPORT_FAILURE = "transport_failure"
    TRANSPORT_INTEGRITY = "transport_integrity"
    TLS_FAILURE = "tls_failure"
    REDIRECT_LIMIT = "redirect_limit"
    RESPONSE_TOO_LARGE = "response_too_large"
    UNSUPPORTED_CONTENT = "unsupported_content"
    INVALID_RESPONSE = "invalid_response"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    PROVIDER_FAILURE = "provider_failure"


class AcquisitionError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)
