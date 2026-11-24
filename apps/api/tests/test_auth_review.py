"""Offline route/control tests; fake storage is not PostgreSQL verification."""
import base64
import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agentops_api.core.auth_config import AuthSettings
from agentops_api.core.config import Settings
from agentops_api.main import create_app
from agentops_api.services.auth import ContextCipher
from agentops_api.api.routes.auth import RateLimit


@pytest.fixture
def config():
    return AuthSettings(client_id='offline', client_secret='synthetic',
        context_key=base64.b64encode(secrets.token_bytes(32)).decode(), origin='https://app.example.test')


@pytest.fixture
def client(config):
    provider = SimpleNamespace(authorize=AsyncMock(return_value={'state':'offline-state', 'nonce':'offline-nonce',
        'code_verifier':'offline-verifier', 'url':'https://accounts.google.com/o/oauth2/v2/auth'}),
        exchange=AsyncMock(return_value=('https://accounts.google.com','subject')))
    application = create_app(Settings(auth_review_enabled=True, database_enabled=True, database_password='unused'),
                             auth_settings=config, auth_provider=provider)
    with TestClient(application, base_url=config.origin) as browser:
        store = SimpleNamespace(issue_state=AsyncMock(), consume=AsyncMock(return_value={'nonce':'offline-nonce'}),
            login=AsyncMock(return_value='new-synthetic-session'), principal=AsyncMock(return_value=None))
        application.state.auth_service = store
        yield browser, store, provider


def test_disabled_by_default():
    with TestClient(create_app(Settings())) as client:
        assert client.get('/api/v1/auth/me').status_code == 404


def test_cookie_rotation_and_no_store(client, config):
    browser, store, provider = client
    response = browser.get('/api/v1/auth/login/google', follow_redirects=False)
    assert response.status_code == 302
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    browser.cookies.set(config.session_cookie, 'old-synthetic-session')
    response = browser.get('/api/v1/auth/callback/google?state=offline-state&code=offline-code', follow_redirects=False)
    assert response.status_code == 303
    assert 'new-synthetic-session' in response.headers['set-cookie']
    assert response.headers['cache-control'] == 'no-store'
    assert store.login.await_args.args[-1] == 'old-synthetic-session'
    assert provider.exchange.await_count == 1


@pytest.mark.parametrize('query', ['state=x&state=y&code=z', 'state=x&error=access_denied',
                                   'state=x&code=z&iss=https://evil.test', 'state=x'])
def test_callback_errors_do_not_exchange(client, config, query):
    browser, store, provider = client
    browser.cookies.set(config.binding_cookie, 'synthetic-binding')
    response = browser.get('/api/v1/auth/callback/google?'+query)
    assert response.status_code == 400
    provider.exchange.assert_not_awaited()


def test_anonymous_and_outage(client):
    browser, store, _ = client
    assert browser.get('/api/v1/auth/me').status_code == 401
    store.principal.side_effect = RuntimeError('synthetic-secret')
    response = browser.get('/api/v1/auth/me')
    assert response.status_code == 503 and 'synthetic-secret' not in response.text


def test_origin_csrf_and_repeated_logout(client, config):
    browser, store, _ = client
    assert browser.post('/api/v1/auth/logout').status_code == 403
    assert browser.get('/api/v1/auth/csrf', headers={'Origin':'https://evil.test'}).status_code == 403
    store.principal.side_effect = ValueError('invalid csrf')
    assert browser.post('/api/v1/auth/logout', headers={'Origin':config.origin}).status_code == 403
    store.principal.side_effect = None
    for _ in range(2):
        assert browser.post('/api/v1/auth/logout', headers={'Origin':config.origin}).status_code == 204


@pytest.mark.parametrize('change', ['tamper','binding','state','key','version'])
def test_context_authentication(config, change):
    cipher = ContextCipher(config.context_key.get_secret_value())
    encrypted = cipher.encrypt({'nonce':'synthetic'}, 'state', 'binding')
    assert cipher.decrypt(encrypted, 'state', 'binding') == {'nonce':'synthetic'}
    if change == 'tamper': encrypted = encrypted[:-1]+bytes([encrypted[-1]^1])
    if change == 'version': encrypted = b'\x02'+encrypted[1:]
    if change == 'key': cipher = ContextCipher(base64.b64encode(secrets.token_bytes(32)).decode())
    with pytest.raises(Exception):
        cipher.decrypt(encrypted, 'other' if change == 'state' else 'state',
                       'other' if change == 'binding' else 'binding')


def test_rate_limit_is_bounded():
    limiter = RateLimit(limit=2)
    assert limiter.allow('key') and limiter.allow('key')
    assert not limiter.allow('key')


def test_startup_protects_existing_handlers(config):
    import io
    import logging
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger('authlib.integrations.base_client.sync_app')
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    app = create_app(Settings(auth_review_enabled=True, database_enabled=True, database_password='unused'),
                     auth_settings=config, auth_provider=SimpleNamespace())
    try:
        with TestClient(app):
            try:
                raise ValueError('synthetic-token-secret')
            except ValueError:
                logger.exception('Using code_verifier: synthetic-verifier-secret')
        assert 'synthetic-token-secret' not in output.getvalue()
        assert 'synthetic-verifier-secret' not in output.getvalue()
        assert 'frames' in output.getvalue() and 'oidc_client_event' in output.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def test_same_site_foreign_csrf_request_cannot_rotate(client):
    browser, store, _ = client
    response = browser.get('/api/v1/auth/csrf', headers={'Sec-Fetch-Site':'same-site'})
    assert response.status_code == 403
    store.principal.assert_not_awaited()


def test_callback_denial_consumes_and_storage_failure_never_exchanges(client, config):
    browser, store, provider = client
    browser.cookies.set(config.binding_cookie,'synthetic-binding')
    assert browser.get('/api/v1/auth/callback/google?state=x&error=access_denied').status_code == 400
    store.consume.assert_awaited_once()
    store.consume.side_effect = RuntimeError('synthetic-uncertain-commit-secret')
    response = browser.get('/api/v1/auth/callback/google?state=x&code=y')
    assert response.status_code == 400
    assert 'synthetic-uncertain-commit-secret' not in response.text
    provider.exchange.assert_not_awaited()
    store.login.assert_not_awaited()


def test_startup_failure_restores_logging_and_disposes(config, monkeypatch):
    import logging
    from unittest.mock import AsyncMock
    from agentops_api.services import auth as services
    from agentops_api.core.orm import OrmDatabase
    dispose = AsyncMock()
    monkeypatch.setattr(OrmDatabase, 'dispose', dispose)
    def invalid_cipher(*args):
        raise ValueError('synthetic invalid cipher setup')
    monkeypatch.setattr(services, 'ContextCipher', invalid_cipher)
    logger = logging.getLogger('authlib.integrations.base_client.sync_app')
    previous_filters = list(logger.filters)
    app = create_app(Settings(auth_review_enabled=True, database_enabled=True, database_password='unused'),
                     auth_settings=config, auth_provider=SimpleNamespace())
    with pytest.raises(ValueError, match='invalid cipher setup'):
        with TestClient(app):
            pass
    dispose.assert_awaited_once()
    assert logger.filters == previous_filters


@pytest.mark.parametrize('origin', ['https://app.example.test:bad', 'https://app.example.test:99999',
                                   'https://app.example.test\n'])
def test_invalid_origin_rejected_at_configuration(config, origin):
    values = config.model_dump()
    values['origin'] = origin
    with pytest.raises(ValueError):
        AuthSettings(**values)
