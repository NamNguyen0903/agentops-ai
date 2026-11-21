
"""Deterministic tests for the AgentOps AI integration script."""

from __future__ import annotations

import io
import json
import time
import unittest

from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import test_integration as smoke


def health_response() -> smoke.Response:
    return smoke.Response(
        status=200,
        content_type="application/json",
        body=json.dumps(
            smoke.EXPECTED_HEALTH
        ).encode("utf-8"),
    )


def frontend_response() -> smoke.Response:
    return smoke.Response(
        status=200,
        content_type="text/html",
        body=(
            b"<!doctype html><html><body>"
            b'<div id="root"></div>'
            b"</body></html>"
        ),
    )


class SmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.opener_patch = patch.object(
            smoke,
            "build_opener",
        )

        self.build_opener = self.opener_patch.start()
        self.addCleanup(self.opener_patch.stop)

        self.opener = self.build_opener.return_value

        self.opener.open.side_effect = AssertionError(
            "Unexpected network request"
        )

    def configure_http_response(
        self,
        body: bytes,
        content_type: str = "application/json",
        status: int = 200,
    ) -> None:
        response = MagicMock()
        response.status = status
        response.headers = Message()
        response.headers["Content-Type"] = content_type
        response.read1.side_effect = [body, b""]

        self.opener.open.side_effect = None

        self.opener.open.return_value.__enter__.return_value = (
            response
        )

    def test_fetch_and_health_success(self) -> None:
        self.configure_http_response(
            json.dumps(
                smoke.EXPECTED_HEALTH
            ).encode("utf-8")
        )

        response = smoke.fetch(
            "http://127.0.0.1:8000/api/v1/health",
            request_timeout=1,
            deadline=time.monotonic() + 5,
        )

        smoke.validate_health(response)

        request = self.opener.open.call_args.args[0]

        self.assertEqual(
            request.get_method(),
            "GET",
        )

        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:8000/api/v1/health",
        )

    def test_health_rejects_wrong_http_status(self) -> None:
        response = smoke.Response(
            503,
            "application/json",
            b"{}",
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.validate_health(response)

        self.assertEqual(
            caught.exception.category,
            "HTTP",
        )

    def test_health_rejects_wrong_content_type(self) -> None:
        response = smoke.Response(
            200,
            "text/html",
            json.dumps(
                smoke.EXPECTED_HEALTH
            ).encode("utf-8"),
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.validate_health(response)

        self.assertEqual(
            caught.exception.category,
            "ASSERTION",
        )

        self.assertIn(
            "Content-Type",
            str(caught.exception),
        )

    def test_health_rejects_invalid_json(self) -> None:
        response = smoke.Response(
            200,
            "application/json",
            b"not-json",
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.validate_health(response)

        self.assertEqual(
            caught.exception.category,
            "INVALID_JSON",
        )

    def test_health_rejects_wrong_payload(self) -> None:
        payloads = [
            {
                "status": "error",
                "service": "agentops-api",
            },
            {
                **smoke.EXPECTED_HEALTH,
                "extra": True,
            },
            {
                "status": "ok",
            },
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                response = smoke.Response(
                    200,
                    "application/json",
                    json.dumps(payload).encode("utf-8"),
                )

                with self.assertRaises(
                    smoke.CheckFailure
                ) as caught:
                    smoke.validate_health(response)

                self.assertEqual(
                    caught.exception.category,
                    "ASSERTION",
                )

    def test_http_error_is_categorized(self) -> None:
        self.opener.open.side_effect = HTTPError(
            "http://example.test/health",
            503,
            "Unavailable",
            {},
            io.BytesIO(),
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.fetch(
                "http://example.test/health",
                request_timeout=1,
                deadline=time.monotonic() + 5,
            )

        self.assertEqual(
            caught.exception.category,
            "HTTP",
        )

    def test_connection_error_is_categorized(self) -> None:
        self.opener.open.side_effect = URLError(
            ConnectionRefusedError("refused")
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.fetch(
                "http://example.test/health",
                request_timeout=1,
                deadline=time.monotonic() + 5,
            )

        self.assertEqual(
            caught.exception.category,
            "CONNECTION",
        )

    def test_timeout_is_categorized(self) -> None:
        self.opener.open.side_effect = URLError(
            TimeoutError()
        )

        with self.assertRaises(
            smoke.CheckFailure
        ) as caught:
            smoke.fetch(
                "http://example.test/health",
                request_timeout=1,
                deadline=time.monotonic() + 5,
            )

        self.assertEqual(
            caught.exception.category,
            "TIMEOUT",
        )

    def test_frontend_accepts_valid_html(self) -> None:
        smoke.validate_frontend(frontend_response())

    def test_frontend_rejects_invalid_responses(self) -> None:
        invalid = [
            smoke.Response(
                503,
                "text/html",
                b'<div id="root"></div>',
            ),
            smoke.Response(
                200,
                "application/json",
                b'<div id="root"></div>',
            ),
            smoke.Response(
                200,
                "text/html",
                b"<html>Other application</html>",
            ),
            smoke.Response(
                200,
                "text/html",
                b"\xff",
            ),
        ]

        for response in invalid:
            with self.subTest(response=response):
                with self.assertRaises(
                    smoke.CheckFailure
                ):
                    smoke.validate_frontend(response)

    def test_retries_are_bounded(self) -> None:
        failure = smoke.CheckFailure(
            "CONNECTION",
            "unreachable",
        )

        with (
            patch.object(
                smoke,
                "fetch",
                side_effect=failure,
            ) as mocked_fetch,
            patch.object(
                smoke.time,
                "sleep",
            ) as mocked_sleep,
        ):
            result = smoke.run_check(
                "http://example.test/health",
                smoke.validate_health,
                retries=2,
                delay=0.1,
                request_timeout=1,
                deadline=time.monotonic() + 5,
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(mocked_fetch.call_count, 3)
        self.assertEqual(mocked_sleep.call_count, 2)
        self.assertEqual(len(result.failures), 3)

    def test_success_after_retry(self) -> None:
        with (
            patch.object(
                smoke,
                "fetch",
                side_effect=[
                    smoke.CheckFailure(
                        "CONNECTION",
                        "unreachable",
                    ),
                    health_response(),
                ],
            ),
            patch.object(
                smoke.time,
                "sleep",
            ),
        ):
            result = smoke.run_check(
                "http://example.test/health",
                smoke.validate_health,
                retries=2,
                delay=0,
                request_timeout=1,
                deadline=time.monotonic() + 5,
            )

        self.assertTrue(result.passed)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(result.failures), 1)

    def test_expired_deadline_prevents_requests(self) -> None:
        with patch.object(
            smoke,
            "fetch",
        ) as mocked_fetch:
            result = smoke.run_check(
                "http://example.test/health",
                smoke.validate_health,
                retries=2,
                delay=0,
                request_timeout=1,
                deadline=time.monotonic() - 1,
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.attempts, 0)
        mocked_fetch.assert_not_called()

    def test_url_join_preserves_prefix(self) -> None:
        self.assertEqual(
            smoke.endpoint_url(
                "http://example.test/",
                "/api/v1/health",
            ),
            "http://example.test/api/v1/health",
        )

        self.assertEqual(
            smoke.endpoint_url(
                "http://example.test/prefix/",
                "/api/v1/health",
            ),
            "http://example.test/prefix/api/v1/health",
        )

    def test_url_rejects_invalid_inputs(self) -> None:
        invalid_urls = [
            "",
            "ftp://example.test",
            "example.test",
            "http://example.test/?key=1",
            "http://example.test/#fragment",
            "http://user:secret@example.test",
            "http://example.test:99999",
            "http://example.test:invalid",
            "http://example test",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    smoke.endpoint_url(
                        url,
                        "/api/v1/health",
                    )

    def test_cli_rejects_invalid_timeout(self) -> None:
        invalid_args = [
            ["--total-timeout", "0"],
            ["--total-timeout", "-1"],
            ["--request-timeout", "nan"],
            ["--request-timeout", "inf"],
        ]

        for arguments in invalid_args:
            with self.subTest(arguments=arguments):
                with (
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as caught,
                ):
                    smoke.main(arguments)

                self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_invalid_retry_settings(self) -> None:
        invalid_args = [
            ["--retries", "11"],
            ["--retries", "-1"],
            ["--retry-delay", "-0.1"],
            ["--retry-delay", "3"],
        ]

        for arguments in invalid_args:
            with self.subTest(arguments=arguments):
                with (
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as caught,
                ):
                    smoke.main(arguments)

                self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_invalid_base_url(self) -> None:
        with (
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            smoke.main(
                [
                    "--api-base-url",
                    "ftp://example.test",
                ]
            )

        self.assertEqual(caught.exception.code, 2)

    def test_main_returns_zero_when_all_pass(self) -> None:
        output = io.StringIO()

        with (
            patch.object(
                smoke,
                "fetch",
                side_effect=[
                    health_response(),
                    frontend_response(),
                    health_response(),
                ],
            ),
            redirect_stdout(output),
        ):
            exit_code = smoke.main(
                ["--retries", "0"]
            )

        self.assertEqual(exit_code, 0)

        self.assertIn(
            "Summary: 3/3 checks passed.",
            output.getvalue(),
        )

    def test_main_returns_nonzero_on_failure(self) -> None:
        output = io.StringIO()

        with (
            patch.object(
                smoke,
                "fetch",
                side_effect=[
                    health_response(),
                    frontend_response(),
                    smoke.CheckFailure(
                        "HTTP",
                        "received HTTP 502",
                    ),
                ],
            ),
            redirect_stdout(output),
        ):
            exit_code = smoke.main(
                ["--retries", "0"]
            )

        self.assertEqual(exit_code, 1)

        self.assertIn(
            "FAIL proxied API health",
            output.getvalue(),
        )

        self.assertIn(
            "Summary: 2/3 checks passed.",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
