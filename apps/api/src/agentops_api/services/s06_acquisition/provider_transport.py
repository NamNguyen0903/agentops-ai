"""Fixed-origin, deadline-bounded Tavily HTTPX transport.

This transport is used only behind live authorization.
No generic HTTP proxy, redirect, retry or connection pool.
"""

import re

import httpx

from agentops_api.agent.s06.budgets import Budget
from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)
from agentops_api.agent.s06.network_policy import (
    bind_destination,
)
from agentops_api.agent.s06.retrieval import validated_headers
from agentops_api.agent.s06.transport import TransportResponse

from agentops_api.services.smoke_runtime import require as require_live_authorization
from . import smoke_wire
from .request_policy import (
    MAX_REQUEST_BYTES,
    validate_basic_wire_request,
)
from .resolver import DeadlineResolver
from . import bounded_http as wire
from . import pinned_transport as pinned
from .transport_failures import transport_failure


ENDPOINT = "https://api.tavily.com/search"


def fail(code):
    raise AcquisitionError(code) from None


class TavilyPinnedTransport(httpx.BaseTransport):
    def __init__(self, budget, deadline, *, _wire_ticket=None):
        if type(budget) is not Budget:
            fail(ErrorCode.INVALID_INPUT)

        self.budget = budget
        self.deadline = deadline
        self._used = False
        self._wire_ticket = _wire_ticket
        self._claimant = object()

    def handle_request(self, request):
        require_live_authorization()

        if (
            type(request) is not httpx.Request
            or request.method != "POST"
            or str(request.url) != ENDPOINT
        ):
            fail(ErrorCode.UNSAFE_DESTINATION)

        if self._used:
            fail(ErrorCode.BUDGET_EXHAUSTED)

        self._used = True

        budget = self.budget
        deadline = self.deadline

        budget.check(deadline)

        try:
            body = request.content
            credential = request.headers.get(
                "authorization", ""
            )

            if (
                type(body) is not bytes
                or not 1 <= len(body) <= MAX_REQUEST_BYTES
                or not re.fullmatch(
                    r"Bearer [!-~]{1,512}",
                    credential,
                )
            ):
                fail(ErrorCode.INVALID_INPUT)

            checked = validate_basic_wire_request(body)
            deadline = min(
                deadline,
                smoke_wire.claim(
                    self._wire_ticket, checked, self._claimant
                ),
            )
            self.deadline = deadline
            budget.check(deadline)

            target = bind_destination(
                ENDPOINT,
                DeadlineResolver(
                    budget, deadline,
                    _smoke_kind="search",
                    _smoke_ticket=self._wire_ticket,
                    _smoke_url=ENDPOINT,
                ),
            )

            budget.check(deadline)

            return self._exchange(
                target,
                body,
                credential,
            )

        except AcquisitionError:
            raise

        except OSError as exc:
            raise transport_failure(exc) from None

        except Exception:
            fail(ErrorCode.PROVIDER_FAILURE)

    def _exchange(self, target, body, credential):
        require_live_authorization()
        checked = validate_basic_wire_request(body)
        authority_deadline = smoke_wire.enter_exchange(
            self._wire_ticket, checked, self._claimant
        )

        budget = self.budget
        deadline = self.deadline

        deadline = min(deadline, authority_deadline)
        budget.check(deadline)

        destination, ip = pinned.validated_target(target)

        if destination.url != ENDPOINT:
            fail(ErrorCode.UNSAFE_DESTINATION)

        sock = None

        try:
            sock = pinned._connect_bound(
                target,
                budget,
                deadline,
                _smoke_kind="search",
                _smoke_ticket=self._wire_ticket,
            )

            pinned.verify_peer(sock, ip)

            budget.check(deadline)

            request = wire.CRLF.join([
                b"POST /search HTTP/1.1",
                b"Host: api.tavily.com",
                (
                    "Authorization: " + credential
                ).encode("ascii"),
                b"Content-Type: application/json",
                b"Accept: application/json",
                b"Accept-Encoding: identity",
                (
                    "Content-Length: " + str(len(body))
                ).encode("ascii"),
                b"Connection: close",
                b"",
                b"",
            ]) + body

            sock.settimeout(
                budget.remaining(deadline)
            )

            require_live_authorization()
            smoke_wire.check_exchange(
                self._wire_ticket, checked, self._claimant
            )
            budget.check(deadline)
            sock.sendall(request)

            budget.check(deadline)

            status, pairs, initial = wire.read_head(
                sock,
                budget,
                deadline,
            )

            metadata = TransportResponse(
                status=status,
                headers=pairs,
                chunks=(),
                peer_ip=ip,
                tls_verified=True,
                tls_hostname=destination.host,
            )

            headers = validated_headers(metadata)

            if status != 200:
                fail(ErrorCode.PROVIDER_FAILURE)

            payload = wire.bounded_body(
                sock,
                initial,
                headers,
                budget,
                deadline,
                accepted_types=frozenset({
                    "application/json",
                }),
            )

            budget.check(deadline)

            return httpx.Response(
                200,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(payload)),
                },
                content=payload,
            )

        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
