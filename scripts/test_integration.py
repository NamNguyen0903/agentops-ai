
"""Read-only smoke tests for AgentOps AI local integration."""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import time

from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

EXPECTED_HEALTH = {
    "status": "ok",
    "service": "agentops-api",
}

MAX_BODY_BYTES = 128 * 1024


class CheckFailure(Exception):
    """Failure with a stable category for reporting."""

    def __init__(
        self,
        category: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class Result:
    passed: bool
    attempts: int
    failures: tuple[str, ...]


class NoRedirects(HTTPRedirectHandler):
    """Reject HTTP redirects during smoke checks."""

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        return None


class RootParser(HTMLParser):
    """Find the Vite application root element."""

    def __init__(self) -> None:
        super().__init__()
        self.found_root = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag == "div" and ("id", "root") in attrs:
            self.found_root = True


def positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be a number"
        ) from exc

    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError(
            "must be finite and greater than zero"
        )

    return number


def retry_count(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an integer"
        ) from exc

    if not 0 <= number <= 10:
        raise argparse.ArgumentTypeError(
            "must be between 0 and 10"
        )

    return number


def retry_delay(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be a number"
        ) from exc

    if not math.isfinite(number) or not 0 <= number <= 2:
        raise argparse.ArgumentTypeError(
            "must be between 0 and 2 seconds"
        )

    return number


def endpoint_url(base: str, endpoint: str) -> str:
    """Safely append a path to an HTTP(S) base URL."""

    base = base.strip()

    if not base or any(char.isspace() for char in base):
        raise ValueError(
            "base URL must not be empty or contain whitespace"
        )

    parts = urlsplit(base)

    if parts.scheme not in {"http", "https"}:
        raise ValueError(
            "base URL must use http or https"
        )

    if not parts.hostname:
        raise ValueError(
            "base URL must include a hostname"
        )

    if parts.username is not None or parts.password is not None:
        raise ValueError(
            "base URL must not contain credentials"
        )

    if parts.query or parts.fragment or "?" in base or "#" in base:
        raise ValueError(
            "base URL must not include query or fragment"
        )

    # Accessing the port validates its format and range.
    _ = parts.port

    path = (
        f"{parts.path.rstrip('/')}/"
        f"{endpoint.lstrip('/')}"
    )

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            path,
            "",
            "",
        )
    )


def remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()

    if remaining <= 0:
        raise CheckFailure(
            "TIMEOUT",
            "total execution deadline exhausted",
        )

    return remaining


def fetch(
    url: str,
    *,
    request_timeout: float,
    deadline: float,
) -> Response:
    """Fetch HTTP data with bounded reads and no redirects."""

    timeout = min(
        request_timeout,
        remaining_seconds(deadline),
    )

    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json, text/html",
            "User-Agent": "agentops-integration-check/1",
        },
    )

    # Ignore ambient HTTP_PROXY for local checks.
    opener = build_opener(
        ProxyHandler({}),
        NoRedirects(),
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status

            if status != 200:
                raise CheckFailure(
                    "HTTP",
                    f"expected HTTP 200, received {status}",
                )

            chunks: list[bytes] = []
            size = 0

            while True:
                remaining_seconds(deadline)

                chunk = response.read1(
                    min(
                        4096,
                        MAX_BODY_BYTES - size + 1,
                    )
                )

                remaining_seconds(deadline)

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_BODY_BYTES:
                    raise CheckFailure(
                        "ASSERTION",
                        f"response exceeds {MAX_BODY_BYTES} bytes",
                    )

                chunks.append(chunk)

            return Response(
                status=status,
                content_type=response.headers.get_content_type(),
                body=b"".join(chunks),
            )

    except HTTPError as exc:
        status = exc.code
        exc.close()

        raise CheckFailure(
            "HTTP",
            f"received HTTP {status}",
        ) from exc

    except URLError as exc:
        if isinstance(
            exc.reason,
            (TimeoutError, socket.timeout),
        ):
            raise CheckFailure(
                "TIMEOUT",
                "request timed out",
            ) from exc

        raise CheckFailure(
            "CONNECTION",
            "could not reach service",
        ) from exc

    except (TimeoutError, socket.timeout) as exc:
        raise CheckFailure(
            "TIMEOUT",
            "request timed out",
        ) from exc

    except OSError as exc:
        raise CheckFailure(
            "CONNECTION",
            "connection failed while reading response",
        ) from exc


def validate_health(response: Response) -> None:
    """Verify the exact FastAPI health contract."""

    if response.status != 200:
        raise CheckFailure(
            "HTTP",
            f"expected HTTP 200, received {response.status}",
        )

    if response.content_type.lower() != "application/json":
        raise CheckFailure(
            "ASSERTION",
            "health Content-Type is not application/json",
        )

    try:
        payload = json.loads(response.body)
    except (ValueError, UnicodeError) as exc:
        raise CheckFailure(
            "INVALID_JSON",
            "response is not valid JSON",
        ) from exc

    if payload != EXPECTED_HEALTH:
        raise CheckFailure(
            "ASSERTION",
            "health JSON does not match the expected object",
        )


def validate_frontend(response: Response) -> None:
    """Verify HTML delivery, not browser rendering."""

    if response.status != 200:
        raise CheckFailure(
            "HTTP",
            f"expected HTTP 200, received {response.status}",
        )

    if response.content_type.lower() != "text/html":
        raise CheckFailure(
            "ASSERTION",
            "frontend Content-Type is not text/html",
        )

    try:
        html = response.body.decode("utf-8")
    except UnicodeError as exc:
        raise CheckFailure(
            "ASSERTION",
            "frontend HTML is not valid UTF-8",
        ) from exc

    parser = RootParser()
    parser.feed(html)
    parser.close()

    if not parser.found_root:
        raise CheckFailure(
            "ASSERTION",
            'frontend HTML has no <div id="root">',
        )


def run_check(
    url: str,
    validator: Callable[[Response], None],
    *,
    retries: int,
    delay: float,
    request_timeout: float,
    deadline: float,
) -> Result:
    """Run one check with a bounded retry budget."""

    failures: list[str] = []
    attempts = 0

    for attempt_index in range(retries + 1):
        try:
            remaining_seconds(deadline)
        except CheckFailure as exc:
            failures.append(
                f"{exc.category}: {exc}"
            )
            break

        attempts += 1

        try:
            response = fetch(
                url,
                request_timeout=request_timeout,
                deadline=deadline,
            )

            validator(response)
            remaining_seconds(deadline)

            return Result(
                passed=True,
                attempts=attempts,
                failures=tuple(failures),
            )

        except CheckFailure as exc:
            failures.append(
                f"{exc.category}: {exc}"
            )

        if attempt_index < retries:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                break

            time.sleep(min(delay, remaining))

    return Result(
        passed=False,
        attempts=attempts,
        failures=tuple(failures),
    )


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only integration smoke checks for "
            "AgentOps AI. Services must already be running."
        )
    )

    parser.add_argument(
        "--api-base-url",
        default=os.environ.get(
            "AGENTOPS_TEST_API_BASE_URL",
            "http://127.0.0.1:8000",
        ),
        help="API origin or prefix",
    )

    parser.add_argument(
        "--web-base-url",
        default=os.environ.get(
            "AGENTOPS_TEST_WEB_BASE_URL",
            "http://127.0.0.1:5173",
        ),
        help="Frontend origin or prefix",
    )

    parser.add_argument(
        "--request-timeout",
        type=positive_float,
        default=2.0,
        help="Per-request socket timeout in seconds",
    )

    parser.add_argument(
        "--total-timeout",
        type=positive_float,
        default=20.0,
        help="Shared deadline in seconds",
    )

    parser.add_argument(
        "--retries",
        type=retry_count,
        default=2,
        help="Additional attempts per check (0-10)",
    )

    parser.add_argument(
        "--retry-delay",
        type=retry_delay,
        default=0.25,
        help="Delay between attempts (0-2 seconds)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)

    try:
        checks = [
            (
                "direct API health",
                endpoint_url(
                    args.api_base_url,
                    "/api/v1/health",
                ),
                validate_health,
            ),
            (
                "frontend HTML",
                endpoint_url(
                    args.web_base_url,
                    "/",
                ),
                validate_frontend,
            ),
            (
                "proxied API health",
                endpoint_url(
                    args.web_base_url,
                    "/api/v1/health",
                ),
                validate_health,
            ),
        ]
    except ValueError as exc:
        parser.error(str(exc))

    deadline = (
        time.monotonic() + args.total_timeout
    )

    passed = 0

    for name, url, validator in checks:
        result = run_check(
            url,
            validator,
            retries=args.retries,
            delay=args.retry_delay,
            request_timeout=args.request_timeout,
            deadline=deadline,
        )

        label = "PASS" if result.passed else "FAIL"

        print(
            f"{label} {name} "
            f"(attempts={result.attempts})"
        )

        for failure in result.failures:
            print(f"  {failure}")

        if result.passed:
            passed += 1

    print(
        f"Summary: {passed}/{len(checks)} "
        "checks passed."
    )

    print(
        "Frontend HTML delivery was checked; "
        "React browser rendering was not."
    )

    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(
            "FAIL interrupted by user",
            file=sys.stderr,
        )
        sys.exit(130)
