"""Opt-in disposable PostgreSQL evidence, using actual service and independent sessions."""
import asyncio
import hashlib
import os
import secrets
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select, text, event
from sqlalchemy.exc import OperationalError
from agentops_api.services.oidc_state import OIDCStateUnavailable
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from agentops_api.models.identity import OIDCLoginTransaction
from agentops_api.services.oidc_state import consume_oidc_state


def test_postgres_state_consumption():
    if os.getenv('AGENTOPS_RUN_DB_INTEGRATION') != '1':
        pytest.skip('Explicit disposable PostgreSQL opt-in required')
    url = make_url(os.environ['AGENTOPS_MIGRATION_DATABASE_URL'])
    assert url.database == 'agentops_migration_test' and url.username == 'agentops_migrator'

    async def scenario():
        engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True,
            connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=5000 -c lock_timeout=2000'})
        factory = async_sessionmaker(engine, autobegin=False, expire_on_commit=False)
        digests = []
        binding = hashlib.sha256(secrets.token_bytes(32)).digest()
        async def issue(expired=False):
            state = hashlib.sha256(secrets.token_bytes(32)).digest()
            digests.append(state)
            async with factory() as session, session.begin():
                now = await session.scalar(select(func.clock_timestamp()))
                session.add(OIDCLoginTransaction(state_digest=state, browser_binding_digest=binding,
                    encrypted_context=b'synthetic-ciphertext', created_at=now-timedelta(seconds=10),
                    expires_at=now+timedelta(seconds=-1 if expired else 300)))
            return state
        async def consume(state, match=True):
            async with factory() as session:
                result = await consume_oidc_state(session, state_digest=state,
                    browser_binding_digest=binding if match else b'x'*32)
                assert not session.in_transaction()
                return result
        try:
            async with factory() as session, session.begin():
                assert (await session.execute(text('SELECT current_database(), current_user'))).one() == ('agentops_migration_test','agentops_migrator')
            state = await issue()
            results = await asyncio.gather(consume(state), consume(state))
            assert results.count(b'synthetic-ciphertext') == 1 and results.count(None) == 1
            await engine.dispose()  # fresh connections retain consumed state
            assert await consume(state) is None
            for expired, match in [(True, True), (False, False)]:
                state = await issue(expired)
                assert await consume(state, match) is None
                assert await consume(state) is None
                async with factory() as session, session.begin():
                    row = await session.scalar(select(OIDCLoginTransaction).where(OIDCLoginTransaction.state_digest == state))
                    assert row.consumed_at is not None and row.encrypted_context == b''
            # Verify a real row-lock wait, then expiry using time read after lock.
            state = await issue()
            async with factory() as holder:
                async with holder.begin():
                    row = await holder.scalar(select(OIDCLoginTransaction).where(
                        OIDCLoginTransaction.state_digest == state).with_for_update())
                    pending = asyncio.create_task(consume(state))
                    for _ in range(50):
                        async with factory() as observer, observer.begin():
                            waiting = await observer.scalar(text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND wait_event_type='Lock' AND query LIKE '%oidc_login_transactions%'"))
                        if waiting:
                            break
                        await asyncio.sleep(0.02)
                    else:
                        raise AssertionError('Expected PostgreSQL lock wait was not observed')
                    row.expires_at = await holder.scalar(select(func.clock_timestamp()))
                assert await asyncio.wait_for(pending, 3) is None
            # A rolled-back pre-commit mutation must not consume state.
            state = await issue()
            async with factory() as holder:
                transaction = await holder.begin()
                row = await holder.scalar(select(OIDCLoginTransaction).where(
                    OIDCLoginTransaction.state_digest == state).with_for_update())
                row.consumed_at = await holder.scalar(select(func.clock_timestamp()))
                row.encrypted_context = b''
                await holder.flush()
                await transaction.rollback()
            assert await consume(state) == b'synthetic-ciphertext'
            # Cancellation while blocked rolls back without returning context.
            state = await issue()
            async with factory() as holder, holder.begin():
                await holder.scalar(select(OIDCLoginTransaction).where(
                    OIDCLoginTransaction.state_digest == state).with_for_update())
                pending = asyncio.create_task(consume(state))
                for _ in range(50):
                    async with factory() as observer, observer.begin():
                        waiting = await observer.scalar(text(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                            "AND wait_event_type='Lock' AND query LIKE '%oidc_login_transactions%'"))
                    if waiting:
                        break
                    await asyncio.sleep(0.02)
                else:
                    raise AssertionError('Cancellation test never reached lock wait')
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            assert await consume(state) == b'synthetic-ciphertext'
            # Inject a lost acknowledgement AFTER an actual database commit.
            state = await issue()
            async with factory() as uncertain:
                def lost_ack(session):
                    raise OperationalError('synthetic commit acknowledgement', {}, Exception('synthetic'))
                event.listen(uncertain.sync_session, 'after_commit', lost_ack, once=True)
                with pytest.raises(OIDCStateUnavailable):
                    await consume_oidc_state(uncertain, state_digest=state, browser_binding_digest=binding)
            assert await consume(state) is None
            assert await consume(b'z'*32) is None
        finally:
            async with factory() as session, session.begin():
                await session.execute(delete(OIDCLoginTransaction).where(OIDCLoginTransaction.state_digest.in_(digests)))
            await engine.dispose()
    asyncio.run(scenario())
