"""Application-owned resolver with bounded waiting.

A timed-out operating-system DNS call cannot be forcibly
cancelled through Python getaddrinfo. A single in-flight
lookup is allowed per process to prevent accumulating
unbounded abandoned resolver threads.

Live authorization is checked before starting DNS work.
"""

import queue
import socket
import threading

from agentops_api.agent.s06.errors import (
    AcquisitionError,
    ErrorCode,
)

from agentops_api.agent.s06.network_policy import public_ip

from .authorization import require_live_authorization


DNS_SLOT = threading.BoundedSemaphore(1)
MAX_DNS_ANSWERS = 16


def fail(code):
    raise AcquisitionError(code) from None


class DeadlineResolver:
    def __init__(
        self, budget, deadline, *,
        _smoke_kind=None, _smoke_ticket=None, _smoke_url=None,
    ):
        self.budget = budget
        self.deadline = deadline
        self._smoke_kind = _smoke_kind
        self._smoke_ticket = _smoke_ticket
        self._smoke_url = _smoke_url

    def resolve(self, host):
        if (
            self._smoke_kind is None
            and self._smoke_ticket is None
            and self._smoke_url is None
        ):
            require_live_authorization()
        else:
            from agentops_api.agent.s06.network_policy import validate_url
            from agentops_api.services.smoke_runtime import authorize_network

            destination = validate_url(self._smoke_url)

            if destination.host != host:
                fail(ErrorCode.UNSAFE_DESTINATION)

            self.deadline = min(
                self.deadline,
                authorize_network(
                    self._smoke_ticket,
                    self._smoke_kind,
                    destination.url,
                    "dns",
                ),
            )

        self.budget.check(self.deadline)

        if (
            type(host) is not str
            or not host
            or len(host) > 253
            or not host.isascii()
        ):
            fail(ErrorCode.INVALID_INPUT)

        result = queue.Queue(maxsize=1)

        if not DNS_SLOT.acquire(blocking=False):
            fail(ErrorCode.DNS_FAILURE)

        def lookup():
            try:
                answers = socket.getaddrinfo(
                    host,
                    None,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                )

                result.put_nowait(
                    (True, answers)
                )

            except Exception:
                result.put_nowait(
                    (False, None)
                )

            finally:
                DNS_SLOT.release()

        thread = threading.Thread(
            target=lookup,
            daemon=True,
            name="s06-bounded-dns",
        )

        try:
            thread.start()
        except Exception:
            DNS_SLOT.release()
            fail(ErrorCode.DNS_FAILURE)

        try:
            success, answers = result.get(
                timeout=self.budget.remaining(
                    self.deadline
                )
            )

        except queue.Empty:
            fail(ErrorCode.DEADLINE_EXCEEDED)

        self.budget.check(self.deadline)

        if (
            success is not True
            or type(answers) is not list
            or not 1 <= len(answers) <= MAX_DNS_ANSWERS
        ):
            fail(ErrorCode.DNS_FAILURE)

        addresses = []

        for answer in answers:
            try:
                family, kind, protocol, name, endpoint = answer

                if family not in {
                    socket.AF_INET,
                    socket.AF_INET6,
                }:
                    fail(ErrorCode.DNS_FAILURE)

                if kind != socket.SOCK_STREAM:
                    fail(ErrorCode.DNS_FAILURE)

                address = public_ip(endpoint[0])

            except AcquisitionError:
                raise

            except Exception:
                fail(ErrorCode.DNS_FAILURE)

            if address not in addresses:
                addresses.append(address)

        if not addresses:
            fail(ErrorCode.DNS_FAILURE)

        self.budget.check(self.deadline)

        return tuple(addresses)

    def __call__(self, host):
        return self.resolve(host)
