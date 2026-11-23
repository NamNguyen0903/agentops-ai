"""Fixed-provider OIDC boundary; HTTP destinations cannot come from a caller."""
import httpx2
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.starlette_client.apps import StarletteOAuth2App

ISSUER = 'https://accounts.google.com'
DISCOVERY = ISSUER + '/.well-known/openid-configuration'
AUTHORIZE = ISSUER + '/o/oauth2/v2/auth'
ALLOWED = {DISCOVERY, 'https://oauth2.googleapis.com/token', 'https://www.googleapis.com/oauth2/v3/certs'}


class TrustedGoogleTransport(httpx2.AsyncBaseTransport):
    def __init__(self):
        self.transport = httpx2.AsyncHTTPTransport(verify=True, retries=0)

    async def handle_async_request(self, request):
        if str(request.url) not in ALLOWED:
            raise ValueError('Untrusted OIDC destination')
        response = await self.transport.handle_async_request(request)
        if 300 <= response.status_code < 400:
            await response.aclose()
            raise ValueError('OIDC redirects forbidden')
        content = bytearray()
        try:
            async for chunk in response.aiter_raw():
                content.extend(chunk)
                if len(content) > 1024 * 1024:
                    raise ValueError('OIDC response too large')
        finally:
            await response.aclose()
        if response.headers.get('content-encoding', 'identity') != 'identity':
            raise ValueError('Compressed OIDC responses are not permitted')
        return httpx2.Response(response.status_code, headers=response.headers, content=bytes(content))

    async def aclose(self):
        await self.transport.aclose()

from authlib.integrations.httpx_client import AsyncOAuth2Client


class TrustedGoogleOAuthClient(AsyncOAuth2Client):
    """Give each Authlib OAuth client its own trusted transport."""

    def __init__(self, *args, **kwargs):
        kwargs.pop("transport", None)
        kwargs["transport"] = TrustedGoogleTransport()
        super().__init__(*args, **kwargs)

class TrustedGoogleOAuthApp(StarletteOAuth2App):
    """Use an isolated trusted transport for each HTTP client."""

    client_cls = TrustedGoogleOAuthClient

class GoogleOIDC:
    def __init__(self, config):
        self.config = config

    def remote(self):
        # Authlib closes each client's transport; construct one per operation.
        return OAuth().register(name='google', client_cls=TrustedGoogleOAuthApp, client_id=self.config.client_id,
            client_secret=self.config.client_secret.get_secret_value(), server_metadata_url=DISCOVERY,
            client_kwargs={'scope': 'openid email profile', 'code_challenge_method': 'S256',
                           'token_endpoint_auth_method': 'client_secret_post',
                           'follow_redirects': False, 'timeout': 5, 'headers': {'Accept-Encoding': 'identity'}})

    async def trusted_remote(self):
        remote = self.remote()
        metadata = await remote.load_server_metadata()
        if (metadata.get('issuer') != ISSUER or metadata.get('authorization_endpoint') != AUTHORIZE
                or metadata.get('token_endpoint') != 'https://oauth2.googleapis.com/token'
                or metadata.get('jwks_uri') != 'https://www.googleapis.com/oauth2/v3/certs'
                or 'RS256' not in metadata.get('id_token_signing_alg_values_supported', [])
                or 'client_secret_post' not in metadata.get('token_endpoint_auth_methods_supported', [])):
            raise ValueError('Untrusted provider metadata')
        remote.server_metadata['id_token_signing_alg_values_supported'] = ['RS256']
        return remote

    async def authorize(self):
        remote = await self.trusted_remote()
        result = await remote.create_authorization_url(self.config.callback_url)
        from urllib.parse import urlsplit
        url = urlsplit(result['url'])
        if f'{url.scheme}://{url.netloc}{url.path}' != AUTHORIZE:
            raise ValueError('Unexpected authorization endpoint')
        return result

    async def exchange(self, code, context):
        # Reject corrupt/incomplete persisted context before spending the one-use code.
        if not isinstance(context, dict) or any(
            not isinstance(context.get(name), str) or not context[name]
            for name in ('nonce', 'code_verifier')
        ):
            raise ValueError('Valid OIDC context required')
        remote = await self.trusted_remote()
        token = await remote.fetch_access_token(code=code, code_verifier=context['code_verifier'],
                                               redirect_uri=self.config.callback_url)
        if not token.get('id_token') or not context.get('nonce'):
            raise ValueError('Verified identity required')
        identity = await remote.parse_id_token(token, nonce=context['nonce'], leeway=30,
            claims_options={'iss': {'essential': True, 'value': ISSUER},
                            'aud': {'essential': True, 'value': self.config.client_id},
                            'exp': {'essential': True}, 'sub': {'essential': True}})
        if not isinstance(identity.get('sub'), str) or not identity['sub']:
            raise ValueError('Verified subject required')
        return identity['iss'], identity['sub']
