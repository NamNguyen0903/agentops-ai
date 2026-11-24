"""State service unit contracts; no database or provider requests."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agentops_api.services.oidc_state import consume_oidc_state


@pytest.mark.parametrize('case', ['valid', 'expired', 'mismatch', 'consumed', 'missing', 'commit_failure'])
def test_consumption_contract(case):
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(consumed_at=now if case == 'consumed' else None,
                          expires_at=now + timedelta(seconds=-1 if case == 'expired' else 300),
                          browser_binding_digest=b'b' * 32, encrypted_context=b'ciphertext')
    committed = []

    @asynccontextmanager
    async def begin():
        yield
        if case == 'commit_failure':
            raise RuntimeError('simulated uncertain commit')
        committed.append(True)

    session = SimpleNamespace(begin=begin,
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None if case == 'missing' else row)),
        scalar=AsyncMock(return_value=now))
    async def scenario():
        result = await consume_oidc_state(session, state_digest=b's'*32,
            browser_binding_digest=(b'x' if case == 'mismatch' else b'b')*32)
        assert committed
        assert result == (b'ciphertext' if case == 'valid' else None)
        if case not in ('missing', 'consumed'):
            assert row.encrypted_context == b''
            assert row.consumed_at == now
    if case == 'commit_failure':
        with pytest.raises(RuntimeError, match='uncertain commit'):
            asyncio.run(scenario())
    else:
        asyncio.run(scenario())


def test_invalid_digest_never_opens_transaction():
    asyncio.run(consume_oidc_state(None, state_digest=b'', browser_binding_digest=b'b'*32))


def test_database_error_is_sanitized():
    from sqlalchemy.exc import OperationalError
    from agentops_api.services.oidc_state import OIDCStateUnavailable
    @asynccontextmanager
    async def begin():
        raise OperationalError('secret SQL', {'secret': 'hidden'}, Exception('secret driver message'))
        yield
    with pytest.raises(OIDCStateUnavailable) as caught:
        asyncio.run(consume_oidc_state(SimpleNamespace(begin=begin), state_digest=b's'*32,
                                      browser_binding_digest=b'b'*32))
    assert 'secret' not in str(caught.value)
    assert caught.value.__suppress_context__
