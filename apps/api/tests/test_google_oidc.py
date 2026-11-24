"""Actual adapter and Authlib; fake provider transport, no external requests."""
import asyncio
import base64
import secrets
import time
from urllib.parse import parse_qs, urlsplit
import httpx2
import pytest
from joserfc import jwt
from joserfc.errors import InvalidClaimError, ExpiredTokenError, BadSignatureError, MissingClaimError
from joserfc.jwk import RSAKey
from agentops_api.core.auth_config import AuthSettings
from agentops_api.services import google_oidc as module

@pytest.mark.parametrize('mode', ['valid','nonce','missing_nonce','issuer','audience','expired','signature','missing_id_token','metadata'])
def test_real_adapter_offline(monkeypatch, mode):
    key = RSAKey.generate_key(2048, parameters={'kid':'offline'})
    wrong = RSAKey.generate_key(2048, parameters={'kid':'offline'})
    context = {}
    config = AuthSettings(client_id='offline-client', client_secret='offline-secret',
        context_key=base64.b64encode(secrets.token_bytes(32)).decode(), origin='https://app.example.test')
    async def handler(request):
        url = str(request.url)
        if url == module.DISCOVERY:
            return httpx2.Response(200,json={'issuer':module.ISSUER,
                'authorization_endpoint':module.AUTHORIZE,
                'token_endpoint':'http://127.0.0.1/token' if mode == 'metadata' else 'https://oauth2.googleapis.com/token',
                'jwks_uri':'https://www.googleapis.com/oauth2/v3/certs',
                'id_token_signing_alg_values_supported':['RS256'],
                'token_endpoint_auth_methods_supported':['client_secret_post']})
        if url == 'https://www.googleapis.com/oauth2/v3/certs':
            return httpx2.Response(200,json={'keys':[key.as_dict(private=False)]})
        if url != 'https://oauth2.googleapis.com/token':
            raise AssertionError('Unexpected offline destination')
        form = parse_qs(request.content.decode())
        if form.get('client_secret') != ['offline-secret']:
            raise AssertionError('Confidential-client authentication missing')
        if form.get('code_verifier') != [context['code_verifier']]:
            raise AssertionError('PKCE verifier missing')
        now = int(time.time())
        claims = {'iss':module.ISSUER,'sub':'offline-subject','aud':'offline-client',
                  'iat':now,'exp':now+300,'nonce':context['nonce']}
        if mode == 'nonce': claims['nonce'] = 'wrong'
        if mode == 'missing_nonce': claims.pop('nonce')
        if mode == 'issuer': claims['iss'] = 'https://wrong.test'
        if mode == 'audience': claims['aud'] = 'wrong'
        if mode == 'expired': claims['exp'] = now-120
        token = {'access_token':'inert-offline-token','token_type':'Bearer'}
        if mode != 'missing_id_token':
            token['id_token'] = jwt.encode({'alg':'RS256','kid':'offline'},claims,wrong if mode == 'signature' else key)
        return httpx2.Response(200,json=token)
    monkeypatch.setattr(module,'TrustedGoogleTransport',lambda: httpx2.MockTransport(handler))
    async def scenario():
        provider = module.GoogleOIDC(config)
        context.update(await provider.authorize())
        params = parse_qs(urlsplit(context['url']).query)
        assert params['code_challenge_method'] == ['S256']
        assert 'code_verifier' not in params
        return await provider.exchange('offline-code',context)
    if mode == 'valid':
        assert asyncio.run(scenario()) == (module.ISSUER,'offline-subject')
    else:
        expected = {"nonce": InvalidClaimError, "missing_nonce": MissingClaimError, "issuer": InvalidClaimError, "audience": InvalidClaimError,
                    "expired": ExpiredTokenError, "signature": BadSignatureError,
                    "missing_id_token": ValueError, "metadata": ValueError}[mode]
        with pytest.raises(expected):
            asyncio.run(scenario())

@pytest.mark.parametrize('mode', ['destination','redirect','oversize'])
def test_transport_rejects_unsafe_responses(mode):
    async def handler(request):
        if mode == 'redirect':
            return httpx2.Response(302, headers={'location':'http://127.0.0.1/'})
        if mode == 'oversize':
            class Body(httpx2.AsyncByteStream):
                async def __aiter__(self):
                    yield b'x'*(1024*1024+1)
            return httpx2.Response(200, stream=Body())
        raise AssertionError('Untrusted destination reached transport')
    transport = module.TrustedGoogleTransport()
    asyncio.run(transport.aclose())
    transport.transport = httpx2.MockTransport(handler)
    async def scenario():
        url = 'http://127.0.0.1/' if mode == 'destination' else module.DISCOVERY
        await transport.handle_async_request(httpx2.Request('GET',url))
    with pytest.raises(ValueError):
        asyncio.run(scenario())
def test_oidc_transport_not_reused_after_close(monkeypatch):
    """Metadata and OAuth operations must use independent transports."""

    transports = []

    class TrackingTransport(httpx2.AsyncBaseTransport):
        def __init__(self):
            self.closed = False
            self.requests = 0
            transports.append(self)

        async def handle_async_request(self, request):
            if self.closed:
                raise RuntimeError("HTTP transport reused after close")

            self.requests += 1
            url = str(request.url)

            if url == module.DISCOVERY:
                return httpx2.Response(
                    200,
                    json={
                        "issuer": module.ISSUER,
                        "authorization_endpoint": module.AUTHORIZE,
                        "token_endpoint": "https://oauth2.googleapis.com/token",
                        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                        "id_token_signing_alg_values_supported": ["RS256"],
                        "token_endpoint_auth_methods_supported": ["client_secret_post"],
                    },
                )

            if url == "https://oauth2.googleapis.com/token":
                return httpx2.Response(
                    200,
                    json={"status": "offline-ok"},
                )

            raise AssertionError("Unexpected HTTP destination")

        async def aclose(self):
            self.closed = True

    monkeypatch.setattr(
        module,
        "TrustedGoogleTransport",
        TrackingTransport,
    )

    config = AuthSettings(
        client_id="offline-client",
        client_secret="offline-secret",
        context_key=base64.b64encode(
            secrets.token_bytes(32)
        ).decode(),
        origin="https://app.example.test",
    )

    async def scenario():
        provider = module.GoogleOIDC(config)

        remote = await asyncio.wait_for(
            provider.trusted_remote(),
            timeout=3,
        )

        assert len(transports) == 1
        assert transports[0].closed is True

        async with remote._get_oauth_client(
            **remote.server_metadata
        ) as client:
            response = await client.request(
                "GET",
                "https://oauth2.googleapis.com/token",
                withhold_token=True,
            )

            assert response.status_code == 200
            assert response.json() == {
                "status": "offline-ok"
            }

        assert transports[1].closed is True

    asyncio.run(scenario())

    assert len(transports) == 2

    assert transports[0].requests == 1
    assert transports[1].requests == 1

    assert all(transport.closed for transport in transports)