"""Experiment-only ASGI/Authlib integration. Never import into production.

The provider, session repository and cache are in-memory test doubles. Authlib's
redirect, code exchange, JWKS decoding and claim validation remain real.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx2
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth, StarletteIntegration
from fastapi import FastAPI, Request
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
from starlette.responses import JSONResponse

from .oidc_client import pkce_s256

ISSUER = "https://idp.example.test"
CLIENT_ID = "offline-client"
CALLBACK = "https://app.example.test/experiment/callback"
BROWSER_COOKIE = "__Host-poc-browser"


@dataclass
class Clock:
    now: int = 1_800_000_000


class StateCache:
    """Bounded-lifetime memory fake. consume is atomic only in this process."""

    def __init__(self, clock: Clock):
        self.clock = clock
        self.records = {}
        self.lock = asyncio.Lock()
        self.race_barrier = None

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    async def set(self, key, value, expires):
        self.records[self.digest(key)] = (value, self.clock.now + expires)

    async def get(self, key):
        record = self.records.get(self.digest(key))
        value = record[0] if record and self.clock.now < record[1] else None
        # Forces the stock get/delete race without timing-dependent sleeps.
        if self.race_barrier is not None:
            await self.race_barrier.wait()
        return value

    async def delete(self, key):
        self.records.pop(self.digest(key), None)

    async def consume(self, key, binding):
        async with self.lock:
            record = self.records.pop(self.digest(key), None)
            if not record or self.clock.now >= record[1]:
                return None
            value = json.loads(record[0])
            if not hmac.compare_digest(value["binding"], self.digest(binding)):
                return None
            return value["data"]


class AtomicIntegration(StarletteIntegration):
    """Proof of extension compatibility, NOT a production persistence adapter.

    Authlib reads then clears. This adapter atomically consumes at read; clear
    removes only the request's marker. Binding is checked inside the consume.
    """

    async def set_state_data(self, session, state, data):
        key = f"_state_{self.name}_{state}"
        value = {"data": data, "binding": self.cache.digest(session["_binding"])}
        await self.cache.set(key, json.dumps(value), self.expires_in)
        session[key] = {"exp": self.cache.clock.now + self.expires_in}

    async def get_state_data(self, session, state):
        key = f"_state_{self.name}_{state}"
        if not state or not session or key not in session:
            return None
        return await self.cache.consume(key, session["_binding"])

    async def clear_state_data(self, session, state):
        session.pop(f"_state_{self.name}_{state}", None)


class AtomicOAuth(OAuth):
    framework_integration_cls = AtomicIntegration


class Provider:
    """Offline discovery/authorization/token/JWKS transport with one-use codes."""

    def __init__(self, clock, signing_key, wrong_key):
        self.clock = clock
        self.key = signing_key
        self.wrong_key = wrong_key
        self.mode = "valid"
        self.codes = {}
        self.paths = []
        self.exchanges = 0
        self.last_form = None
        self.transport = httpx2.MockTransport(self.handle)

    async def handle(self, request):
        url = urlsplit(str(request.url))
        if f"{url.scheme}://{url.netloc}" != ISSUER:
            raise RuntimeError("Unapproved offline provider destination")
        self.paths.append(url.path)
        if url.path == "/.well-known/openid-configuration":
            return httpx2.Response(200, json={
                "issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize",
                "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/jwks",
                "response_types_supported": ["code"], "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
            })
        if url.path == "/jwks":
            return httpx2.Response(200, json={"keys": [self.key.as_dict(private=False)]})
        if url.path == "/authorize":
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            if (params.get("client_id") != CLIENT_ID or params.get("redirect_uri") != CALLBACK
                    or params.get("response_type") != "code" or params.get("code_challenge_method") != "S256"):
                return httpx2.Response(400, json={"error": "invalid_request"})
            code = secrets.token_urlsafe(32)
            self.codes[code] = params
            return httpx2.Response(302, headers={"location": CALLBACK + "?" + urlencode({
                "code": code, "state": params["state"], "iss": ISSUER,
            })})
        if url.path != "/token" or request.method != "POST":
            raise RuntimeError("Unexpected offline provider request")
        self.exchanges += 1
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.last_form = form
        if self.mode == "token_error":
            return httpx2.Response(400, json={"error": "invalid_grant"})
        if self.mode == "timeout":
            raise httpx2.ReadTimeout("Offline timeout fixture")
        saved = self.codes.pop(form.get("code"), None)
        if (not saved or form.get("grant_type") != "authorization_code"
                or form.get("client_id") != CLIENT_ID or form.get("redirect_uri") != CALLBACK
                or pkce_s256(form.get("code_verifier", "")) != saved["code_challenge"]):
            return httpx2.Response(400, json={"error": "invalid_grant"})
        claims = {
            "iss": ISSUER, "sub": "offline-subject", "aud": CLIENT_ID,
            "iat": self.clock.now, "exp": self.clock.now + 300, "nonce": saved["nonce"],
        }
        changes = {
            "nonce": {"nonce": "incorrect"}, "issuer": {"iss": "https://wrong.example.test"},
            "audience": {"aud": "other-client", "azp": CLIENT_ID},
            "expiry": {"exp": self.clock.now - 1}, "future_iat": {"iat": self.clock.now + 60},
            "azp": {"aud": [CLIENT_ID, "other"], "azp": "other"},
        }
        claims.update(changes.get(self.mode, {}))
        if self.mode == "missing_nonce":
            claims.pop("nonce")
        token = {"access_token": "inert-offline-access", "token_type": "Bearer"}
        if self.mode != "missing_id_token":
            key = self.wrong_key if self.mode == "signature" else self.key
            token["id_token"] = jwt.encode({"alg": "RS256", "kid": "offline-key"}, claims, key)
        return httpx2.Response(200, json=token)


class Flow:
    """Fixture-only server-side session repository and callback boundary."""

    def __init__(self, clock, key, wrong_key, *, atomic=True, cache=True):
        self.clock = clock
        self.provider = Provider(clock, key, wrong_key)
        self.cache = StateCache(clock) if cache else None
        self.sessions = {}
        self.errors = []
        self.raw_missing_identity = False
        oauth = (AtomicOAuth if atomic else OAuth)(cache=self.cache)
        self.remote = oauth.register(
            name="offline", client_id=CLIENT_ID,
            server_metadata_url=ISSUER + "/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile", "code_challenge_method": "S256",
                "token_endpoint_auth_method": "none", "transport": self.provider.transport,
                "trust_env": False, "timeout": 2,
            },
        )
        self.remote.framework.expires_in = 300
        self.app = FastAPI()

        @self.app.middleware("http")
        async def fixture_session(request: Request, call_next):
            browser = request.cookies.get(BROWSER_COOKIE)
            if browser not in self.sessions:
                browser = secrets.token_urlsafe(32)
                self.sessions[browser] = {"_binding": secrets.token_urlsafe(32)}
            request.scope["session"] = copy.deepcopy(self.sessions[browser])
            response = await call_next(request)
            self.sessions[browser] = request.scope["session"]
            response.set_cookie(BROWSER_COOKIE, browser, secure=True, httponly=True, samesite="lax")
            return response

        @self.app.get("/experiment/login")
        async def login(request: Request):
            return await self.remote.authorize_redirect(request, CALLBACK)

        @self.app.get("/experiment/callback")
        async def callback(request: Request):
            try:
                # These checks are application controls, not supplied by Authlib.
                for name in ("state", "code", "iss", "error"):
                    if len(request.query_params.getlist(name)) > 1:
                        raise ValueError("ambiguous_callback")
                if request.query_params.get("iss") not in (None, ISSUER):
                    raise ValueError("issuer_response_mismatch")
                if request.query_params.get("error"):
                    state = request.query_params.get("state")
                    await self.remote.framework.get_state_data(request.session, state)
                    await self.remote.framework.clear_state_data(request.session, state)
                    raise ValueError("provider_denied")
                if not request.query_params.get("code") or not request.query_params.get("state"):
                    raise ValueError("missing_callback_parameter")
                token = await self.remote.authorize_access_token(
                    request, leeway=0,
                    claims_options={"iss": {"essential": True, "value": ISSUER},
                                    "aud": {"essential": True, "value": CLIENT_ID}},
                )
                self.raw_missing_identity = "userinfo" not in token
                if self.raw_missing_identity or not token["userinfo"].get("sub"):
                    raise ValueError("missing_verified_identity")
                return JSONResponse({"issuer": token["userinfo"]["iss"], "subject": token["userinfo"]["sub"]})
            except (OAuthError, JoseError, httpx2.HTTPError, ValueError) as error:
                self.errors.append(type(error).__name__)
                return JSONResponse({"error": "invalid_oidc_callback"}, status_code=400)

    def client(self):
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=self.app),
                                 base_url="https://app.example.test", trust_env=False)

    async def begin(self, client):
        response = await client.get("/experiment/login")
        if response.status_code != 302:
            raise AssertionError("Authorization redirect failed")
        location = response.headers["location"]
        async with httpx2.AsyncClient(transport=self.provider.transport, trust_env=False) as browser:
            authorization = await browser.get(location)
        if authorization.status_code != 302:
            raise AssertionError("Offline provider rejected authorization request")
        return location, authorization.headers["location"]
