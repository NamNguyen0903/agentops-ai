"""Round 2 regressions, offline only; no production security equivalence claim."""
import asyncio
import io
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentops_api.core.security_logging import SecurityFormatter, PKCELogFilter, log_failure
from agentops_api.services.google_oidc import GoogleOIDC


@pytest.mark.parametrize('context', [{}, {'code_verifier':'synthetic'}, {'nonce':'synthetic'},
                                      {'nonce':None,'code_verifier':'synthetic'}, []])
def test_malformed_context_fails_before_provider_io(context):
    provider = GoogleOIDC(SimpleNamespace())
    provider.trusted_remote = AsyncMock()
    with pytest.raises(ValueError, match='context'):
        asyncio.run(provider.exchange('synthetic-code',context))
    provider.trusted_remote.assert_not_awaited()


def test_raw_dictionary_log_payload_is_safe():
    record = logging.LogRecord('agentops.auth',logging.ERROR,__file__,1,
                               {'token':'synthetic-secret'},(),None)
    result = SecurityFormatter().format(record)
    assert 'synthetic-secret' not in result


def test_safe_failure_event_retains_diagnostic_without_raw_exception():
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(SecurityFormatter())
    logger = logging.getLogger('agentops.auth')
    logger.addHandler(handler)
    try:
        try:
            raise ValueError('synthetic-code-token-key')
        except ValueError as exc:
            log_failure('auth.callback.failure', exc)
        text = output.getvalue()
        assert 'auth.callback.failure' in text and 'ValueError' in text and 'frames' in text
        assert 'synthetic-code-token-key' not in text
    finally:
        logger.removeHandler(handler)


def test_real_pinned_authlib_pkce_log_filtered_before_late_handler():
    # Use actual pinned Authlib URL builder with static trusted metadata; no HTTP.
    from authlib.integrations.starlette_client import OAuth
    logger = logging.getLogger('authlib.integrations.base_client.sync_app')
    control = PKCELogFilter()
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addFilter(control)
    output = io.StringIO()
    late_handler = logging.StreamHandler(output)  # intentionally ordinary formatter
    logger.addHandler(late_handler)
    try:
        remote = OAuth().register(name='offline',client_id='offline',
            authorize_url='https://idp.example.test/authorize',
            client_kwargs={'scope':'openid','code_challenge_method':'S256'})
        result = asyncio.run(remote.create_authorization_url('https://app.example.test/callback'))
        leaked = result['code_verifier'] in output.getvalue()
        assert not leaked, 'PKCE secret emitted'
        assert '[REDACTED]' in output.getvalue()
    finally:
        logger.removeHandler(late_handler)
        logger.removeFilter(control)
        logger.setLevel(previous_level)



def test_overlapping_lifespans_preserve_logging_protection():
    """Closing app A must not remove protection while app B runs."""
    import base64
    import io
    import logging
    import secrets
    from contextlib import ExitStack
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from agentops_api.core.auth_config import AuthSettings
    from agentops_api.core.config import Settings
    from agentops_api.main import create_app

    config = AuthSettings(
        client_id="offline",
        client_secret="synthetic",
        context_key=base64.b64encode(
            secrets.token_bytes(32)
        ).decode(),
        origin="https://app.example.test",
    )

    settings = Settings(
        auth_review_enabled=True,
        database_enabled=True,
        database_password="unused",
    )

    logger = logging.getLogger(
        "authlib.integrations.base_client.sync_app"
    )

    output = io.StringIO()
    handler = logging.StreamHandler(output)
    original_formatter = logging.Formatter("%(message)s")
    handler.setFormatter(original_formatter)
    logger.addHandler(handler)

    app_a = create_app(
        settings,
        auth_settings=config,
        auth_provider=SimpleNamespace(),
    )
    app_b = create_app(
        settings,
        auth_settings=config,
        auth_provider=SimpleNamespace(),
    )

    try:
        with ExitStack() as a_stack:
            a_stack.enter_context(TestClient(app_a))

            with TestClient(app_b):
                # A shuts down while B is still running.
                a_stack.close()

                # Use a generic sensitive message, not the
                # specific PKCE signature already filtered.
                logger.warning(
                    "synthetic-private-value-for-regression"
                )

                assert (
                    "synthetic-private-value-for-regression"
                    not in output.getvalue()
                ), (
                    "SEC-LOG-04: A removed logging protection "
                    "while B remained active"
                )
    finally:
        logger.removeHandler(handler)

    assert handler.formatter is original_formatter, (
        "SEC-LOG-05: Original formatter was not restored "
        "after all application lifespans stopped"
    )
