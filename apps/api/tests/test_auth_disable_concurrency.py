"""Independent PostgreSQL transactions prove the account-disable ordering barrier."""
import asyncio
import base64
import os
import secrets

import pytest
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agentops_api.models.identity import User, AuthIdentity
from agentops_api.services.auth import AuthService, ContextCipher


@pytest.mark.parametrize('operation', ['read', 'csrf', 'logout'])
def test_disable_serializes_principal(operation):
    if os.getenv('AGENTOPS_RUN_DB_INTEGRATION') != '1':
        pytest.skip('Explicit disposable PostgreSQL opt-in required')
    url = make_url(os.environ['AGENTOPS_MIGRATION_DATABASE_URL'])
    assert url.database == 'agentops_migration_test' and url.username == 'agentops_migrator'

    async def scenario():
        engine = create_async_engine(url, hide_parameters=True, pool_size=4, max_overflow=0,
            connect_args={'connect_timeout':3, 'options':'-c statement_timeout=5000 -c lock_timeout=3000'})
        locked, proceed = asyncio.Event(), asyncio.Event()
        class PausingSession(AsyncSession):
            async def execute(self, statement, *args, **kwargs):
                if getattr(statement, 'is_update', False) and statement.table.name == 'auth_sessions':
                    # disable_user has already locked User; pause before session revocation.
                    locked.set()
                    await asyncio.wait_for(proceed.wait(), 3)
                return await super().execute(statement, *args, **kwargs)
        factory = async_sessionmaker(engine, class_=PausingSession, autobegin=False, expire_on_commit=False)
        service = AuthService(factory, ContextCipher(base64.b64encode(secrets.token_bytes(32)).decode()))
        subject = secrets.token_hex(16)
        user_id = None
        tasks = []
        try:
            async with factory() as session, session.begin():
                assert (await session.execute(text('SELECT current_database(), current_user'))).one() == (
                    'agentops_migration_test','agentops_migrator')
                user = User()
                session.add(user)
                await session.flush()
                user_id = user.id
                session.add(AuthIdentity(user_id=user_id, issuer='https://accounts.google.com', subject=subject))
            token = await service.login('https://accounts.google.com', subject, None)
            proof = (await service.principal(token, new_csrf=True))['csrf_token']
            disabling = asyncio.create_task(service.disable_user_and_revoke_sessions(user_id))
            tasks.append(disabling)
            await asyncio.wait_for(locked.wait(), 2)
            kwargs = {'new_csrf':True} if operation == 'csrf' else {'logout':True,'csrf':proof} if operation == 'logout' else {}
            checking = asyncio.create_task(service.principal(token, **kwargs))
            tasks.append(checking)
            # Require an observed database lock wait, not a scheduling assumption.
            for _ in range(100):
                assert not checking.done(), 'Principal passed an account-disable barrier'
                async with factory() as observer, observer.begin():
                    waiting = await observer.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event_type='Lock' AND query LIKE '%app.users%'"))
                if waiting:
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError('Principal did not wait on the account row lock')
            proceed.set()
            assert await asyncio.wait_for(disabling, 2) is True
            assert await asyncio.wait_for(checking, 2) is None
            assert await service.principal(token) is None
        finally:
            proceed.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if user_id:
                async with factory() as session, session.begin():
                    await session.execute(delete(User).where(User.id == user_id))
            await engine.dispose()
    asyncio.run(scenario())
