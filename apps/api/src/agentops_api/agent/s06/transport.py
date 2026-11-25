"""Controlled offline transport; no socket connector."""

from dataclasses import dataclass
from typing import Protocol

from .network_policy import BoundDestination


class TransientTransportError(Exception):
    """Eligible simulated transient failure."""


@dataclass(frozen=True, slots=True)
class TransportResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    chunks: tuple[bytes, ...]
    peer_ip: str
    tls_verified: bool
    tls_hostname: str | None


class Transport(Protocol):
    def send(
        self,
        target: BoundDestination,
        *,
        timeout: float,
    ) -> TransportResponse: ...


class FixtureTransport:
    def __init__(self, responses):
        if type(responses) is not tuple or len(responses) > 12:
            raise ValueError("invalid fixture sequence")

        self._responses = responses
        self._position = 0
        self._requests = []

    @property
    def requests(self):
        return tuple(self._requests)

    def send(self, target, *, timeout):
        if self._position >= len(self._responses):
            raise RuntimeError("fixture exhausted")

        self._requests.append(target)
        value = self._responses[self._position]
        self._position += 1

        if type(value) is TransientTransportError:
            raise value

        return value


class FixtureResolver:
    def __init__(self, answers):
        self._answers = dict(answers)

    def __call__(self, host):
        return self._answers[host]
