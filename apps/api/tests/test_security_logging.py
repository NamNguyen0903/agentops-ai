"""Application formatter boundary, not proof of deployed collector configuration."""
import io
import logging

import pytest

from agentops_api.core.security_logging import SecurityFormatter


@pytest.mark.parametrize('logger_name', ['authlib.integrations.base_client.sync_app', 'uvicorn.access', 'httpx', 'agentops.auth'])
def test_untrusted_log_payloads_and_exception_values_are_not_serialized(logger_name):
    sentinel = 'synthetic-secret-must-not-appear'
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SecurityFormatter())
    try:
        raise ValueError(sentinel)
    except ValueError:
        import sys
        record = logging.LogRecord(logger_name, logging.ERROR, __file__, 22,
            'code=%s code_verifier=%s client_secret=%s id_token=%s access_token=%s session=%s',
            (sentinel,)*6, sys.exc_info())
        record.authorization = sentinel
        handler.handle(record)
    output = stream.getvalue()
    assert sentinel not in output
    assert 'exception_raised' in output and 'frames' in output
    assert 'ERROR' in output
