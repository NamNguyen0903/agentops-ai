"""Review-only API; registered only when explicitly enabled."""
import asyncio
import time
from collections import deque

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from agentops_api.core.security_logging import log_failure
from agentops_api.services.auth import random_token, digest
from agentops_api.services.google_oidc import ISSUER


class RateLimit:
    """Bounded process-local abuse guard; distributed quota remains a release gate."""
    def __init__(self, limit=20, window=60):
        self.limit, self.window = limit, window
        self.entries = {}

    def allow(self, key):
        now = time.monotonic()
        for old in list(self.entries):
            if not self.entries[old] or self.entries[old][-1] <= now-self.window:
                del self.entries[old]
        if key not in self.entries and len(self.entries) >= 10000:
            return False
        queue = self.entries.setdefault(key, deque())
        while queue and queue[0] <= now-self.window:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(now)
        return True


def make_router(config, provider):
    router = APIRouter(prefix='/auth')
    limiter = RateLimit()

    def finish(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    def error(status=400):
        return finish(JSONResponse({'detail': 'Authentication request rejected'}, status_code=status))

    def cookie(response, name, value, age):
        response.set_cookie(name, value, max_age=age, secure=not config.development_http,
                            httponly=True, samesite='lax', path='/')

    def clear(response, name):
        response.delete_cookie(name, path='/', secure=not config.development_http,
                               httponly=True, samesite='lax')

    def service(request):
        return request.app.state.auth_service

    @router.get('/login/google')
    async def login(request: Request):
        if not limiter.allow(digest(request.client.host if request.client else 'unknown')):
            return error(429)
        try:
            async with asyncio.timeout(10):
                context = await provider.authorize()
                binding = random_token()
                await service(request).issue_state(context['state'], binding, context)
            response = RedirectResponse(context['url'], status_code=302)
            cookie(response, config.binding_cookie, binding, 300)
            return finish(response)
        except Exception as exc:
            log_failure('auth.login.failure', exc)
            return error(503)

    @router.get('/callback/google')
    async def callback(request: Request):
        if not limiter.allow(digest('callback:' + (request.client.host if request.client else 'unknown'))):
            return error(429)
        try:
            params = request.query_params
            if any(len(params.getlist(k)) > 1 for k in ('state','code','error','iss')):
                return error()
            state, binding = params.get('state'), request.cookies.get(config.binding_cookie)
            if not state or not binding or len(state) > 256 or len(binding) > 256:
                return error()
            async with asyncio.timeout(15):
                context = await service(request).consume(state, binding)
                if not context or params.get('error') or params.get('iss') not in (None, ISSUER):
                    return error()
                code = params.get('code')
                if not code or len(code) > 4096:
                    return error()
                issuer, subject = await provider.exchange(code, context)
                token = await service(request).login(issuer, subject, request.cookies.get(config.session_cookie))
            if token is None:
                return error(403)
            response = RedirectResponse(config.origin + '/', status_code=303)
            cookie(response, config.session_cookie, token, 43200)
            clear(response, config.binding_cookie)
            return finish(response)
        except Exception as exc:
            log_failure('auth.callback.failure', exc)
            return error()

    @router.get('/me')
    async def me(request: Request):
        try:
            result = await service(request).principal(request.cookies.get(config.session_cookie))
            return finish(JSONResponse({'id': result['id']})) if result else error(401)
        except Exception as exc:
            log_failure('auth.session.failure', exc)
            return error(503)

    @router.get('/csrf')
    async def csrf(request: Request):
        # Same-origin GETs may omit Origin; SOP applies (no CORS enabled).
        if (len(request.headers.getlist('origin')) > 1
                or request.headers.get('origin') not in (None, config.origin)
                or request.headers.get('sec-fetch-site') not in (None, 'same-origin', 'none')):
            return error(403)
        try:
            result = await service(request).principal(request.cookies.get(config.session_cookie), new_csrf=True)
            return finish(JSONResponse({'csrf_token': result['csrf_token']})) if result else error(401)
        except Exception as exc:
            log_failure('auth.csrf.failure', exc)
            return error(503)

    @router.post('/logout')
    async def logout(request: Request):
        if request.headers.getlist('origin') != [config.origin]:
            return error(403)
        try:
            await service(request).principal(request.cookies.get(config.session_cookie),
                csrf=request.headers.get('x-csrf-token'), logout=True)
            response = Response(status_code=204)
            clear(response, config.session_cookie)
            return finish(response)
        except ValueError:
            return error(403)
        except Exception as exc:
            log_failure('auth.logout.failure', exc)
            return error(503)

    return router
