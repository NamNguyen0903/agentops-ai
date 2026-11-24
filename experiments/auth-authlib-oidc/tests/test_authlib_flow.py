"""Real Authlib redirect/callback; fake HTTP provider and memory persistence."""
import asyncio
import copy
import json
import logging
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import integration
from joserfc._rfc7519 import claims as claim_clock
from joserfc.jwk import RSAKey
from starlette.requests import Request

from authlib_oidc_poc.offline_flow import (
    BROWSER_COOKIE, CALLBACK, CLIENT_ID, ISSUER, Clock, Flow,
)
from authlib_oidc_poc.oidc_client import pkce_s256


@pytest.fixture(scope="session")
def keys():
    # Ephemeral synthetic keys; never serialized to disk or printed.
    return (RSAKey.generate_key(2048, parameters={"kid": "offline-key"}),
            RSAKey.generate_key(2048, parameters={"kid": "offline-key"}))


@pytest.fixture
def flow_factory(monkeypatch, keys):
    clock = Clock()
    monkeypatch.setattr(claim_clock, "_generate_now", lambda: clock.now)
    monkeypatch.setattr(integration, "time", SimpleNamespace(time=lambda: clock.now))
    return lambda **kwargs: Flow(clock, *keys, **kwargs)


def run(coroutine):
    return asyncio.run(coroutine)


def state_of(callback):
    return parse_qs(urlsplit(callback).query)["state"][0]


def replace_query(callback, **changes):
    values = {k: v[0] for k, v in parse_qs(urlsplit(callback).query).items()}
    values.update(changes)
    return CALLBACK + "?" + urlencode(values)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_p02_p03_real_redirect_exchange_and_pkce(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            location, callback = await flow.begin(browser)
            params = parse_qs(urlsplit(location).query)
            check(params["code_challenge_method"] == ["S256"], "PKCE method mismatch")
            check("code_verifier" not in params, "Verifier exposed in redirect")
            check(params["redirect_uri"] == [CALLBACK], "Redirect URI mismatch")
            check(params["client_id"] == [CLIENT_ID], "Client mismatch")
            check(params["scope"] == ["openid email profile"], "Scope mismatch")
            check(bool(params["state"][0]) and bool(params["nonce"][0]), "Binding fields missing")
            response = await browser.get(callback)
            check(response.status_code == 200, "Callback failed")
            check(response.json() == {"issuer": ISSUER, "subject": "offline-subject"}, "Identity mismatch")
            check(pkce_s256(flow.provider.last_form["code_verifier"]) == params["code_challenge"][0], "PKCE round trip failed")
            check(set(flow.provider.paths) == {"/.well-known/openid-configuration", "/authorize", "/token", "/jwks"}, "HTTP path coverage incomplete")
            check(not flow.cache.records, "State retained after callback")
    run(scenario())


@pytest.mark.parametrize("mode,expected", [
    ("nonce", "InvalidClaimError"), ("missing_nonce", "MissingClaimError"),
    ("signature", "BadSignatureError"), ("issuer", "InvalidClaimError"),
    ("audience", "InvalidClaimError"), ("expiry", "ExpiredTokenError"),
    ("future_iat", "InvalidClaimError"), ("azp", "InvalidClaimError"),
])
def test_p05_real_callback_rejects_invalid_id_token(flow_factory, mode, expected):
    async def scenario():
        flow = flow_factory()
        flow.provider.mode = mode
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            response = await browser.get(callback)
            check(response.status_code == 400, "Invalid ID token accepted")
            check(flow.errors == [expected], f"Unexpected failure category for {mode}: {flow.errors}")
            check(flow.provider.exchanges == 1, "Token validation path not reached")
            check((await browser.get(callback)).status_code == 400, "Failed callback replay accepted")
            check(flow.provider.exchanges == 1, "Failed transaction was reusable")
    run(scenario())


def test_p04_invalid_state_never_reaches_token_endpoint(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            response = await browser.get(replace_query(callback, state="unknown"))
            check(response.status_code == 400, "Unknown state accepted")
            check(flow.provider.exchanges == 0, "Unknown state reached exchange")
            check((await browser.get(callback)).status_code == 200, "Unrelated invalid state destroyed valid transaction")
    run(scenario())


def test_p06_atomic_state_expiry_boundary(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            flow.clock.now += 300
            check((await browser.get(callback)).status_code == 400, "Expired state accepted")
            check(flow.provider.exchanges == 0, "Expired state reached token endpoint")
    run(scenario())


def test_p06_stock_session_expiry_is_not_enforced_on_read(flow_factory):
    async def scenario():
        flow = flow_factory(atomic=False, cache=False)
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            flow.clock.now += 301
            # Demonstrates a stock gap, not compliant expiration.
            check((await browser.get(callback)).status_code == 200, "Stock expiry behavior changed; reassess gap")
    run(scenario())


def test_p07_replay_is_rejected_before_second_exchange(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            check((await browser.get(callback)).status_code == 200, "Initial callback failed")
            check((await browser.get(callback)).status_code == 400, "Replay accepted")
            check(flow.provider.exchanges == 1, "Replay reached token endpoint")
    run(scenario())


@pytest.mark.parametrize("atomic", [True, False])
def test_p08_concurrent_callback_atomicity_vs_stock_get_delete(flow_factory, atomic):
    async def scenario():
        flow = flow_factory(atomic=atomic)
        async with flow.client() as browser:
            location, first = await flow.begin(browser)
            # Two valid codes for the same authorization state prevent provider
            # code one-use enforcement from masking the client's state race.
            import httpx2
            async with httpx2.AsyncClient(transport=flow.provider.transport, trust_env=False) as provider_browser:
                second = (await provider_browser.get(location)).headers["location"]
            if not atomic:
                flow.cache.race_barrier = asyncio.Barrier(2)
            responses = await asyncio.wait_for(asyncio.gather(
                browser.get(first), browser.get(second),
            ), timeout=3)
            successes = sum(response.status_code == 200 for response in responses)
            check(successes == (1 if atomic else 2), "Unexpected concurrent state outcome")
            check(flow.provider.exchanges == (1 if atomic else 2), "Unexpected exchange count")
    run(scenario())


def test_p09_wrong_browser_cannot_use_callback(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser, flow.client() as other:
            _, callback = await flow.begin(browser)
            check((await other.get(callback)).status_code == 400, "Wrong browser accepted")
            check(flow.provider.exchanges == 0, "Wrong browser reached token endpoint")
            check((await browser.get(callback)).status_code == 200, "Correct browser rejected")
    run(scenario())


def test_p09_atomic_binding_checked_even_with_copied_marker(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser, flow.client() as other:
            _, callback = await flow.begin(browser)
            await other.get("/experiment/login")
            source = flow.sessions[browser.cookies.get(BROWSER_COOKIE)]
            target = flow.sessions[other.cookies.get(BROWSER_COOKIE)]
            marker = f"_state_offline_{state_of(callback)}"
            target[marker] = copy.deepcopy(source[marker])
            check((await other.get(callback)).status_code == 400, "Copied marker bypassed binding")
            check(flow.provider.exchanges == 0, "Binding mismatch reached exchange")
            # Deliberate fail-closed consume burns the transaction on mismatch.
            check((await browser.get(callback)).status_code == 400, "Consumed mismatch reusable")
    run(scenario())


def test_p02_pkce_mismatch_rejected_by_fake_provider(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            cache_key = flow.cache.digest(f"_state_offline_{state_of(callback)}")
            raw, expiry = flow.cache.records[cache_key]
            saved = json.loads(raw)
            saved["data"]["code_verifier"] = "incorrect-verifier"
            flow.cache.records[cache_key] = (json.dumps(saved), expiry)
            check((await browser.get(callback)).status_code == 400, "Wrong PKCE verifier accepted")
            check(flow.provider.exchanges == 1, "Provider PKCE validation not reached")
    run(scenario())


@pytest.mark.parametrize("mode", ["token_error", "timeout", "missing_id_token"])
def test_p05_callback_failure_is_sanitized_and_consumed(flow_factory, mode):
    async def scenario():
        flow = flow_factory()
        flow.provider.mode = mode
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            response = await browser.get(callback)
            check(response.status_code == 400, "Invalid exchange accepted")
            check(response.json() == {"error": "invalid_oidc_callback"}, "Unsafe callback error response")
            if mode == "missing_id_token":
                check(flow.raw_missing_identity, "Missing identity did not reach application check")
            check((await browser.get(callback)).status_code == 400, "Error callback replay accepted")
            check(flow.provider.exchanges == 1, "Failed callback reused state")
    run(scenario())


@pytest.mark.parametrize("mode", ["duplicate", "wrong_issuer"])
def test_p04_application_rejects_ambiguous_or_mixup_callback(flow_factory, mode):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            bad = callback + "&state=duplicate" if mode == "duplicate" else replace_query(callback, iss="https://wrong.example.test")
            check((await browser.get(bad)).status_code == 400, "Invalid callback accepted")
            check(flow.provider.exchanges == 0, "Rejected callback reached exchange")
    run(scenario())


def test_p07_stock_provider_error_skips_state_consumption(flow_factory):
    async def scenario():
        flow = flow_factory(atomic=False)
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            state = state_of(callback)
            request = Request({"type": "http", "method": "GET", "path": "/",
                "headers": [], "query_string": urlencode({"state": state, "error": "access_denied"}).encode(),
                "session": copy.deepcopy(flow.sessions[browser.cookies.get(BROWSER_COOKIE)])})
            with pytest.raises(OAuthError):
                await flow.remote.authorize_access_token(request)
            check(bool(flow.cache.records), "Stock error handling changed; reassess cleanup")
    run(scenario())


def test_p07_application_consumes_provider_denial(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            check((await browser.get(replace_query(callback, error="access_denied"))).status_code == 400, "Denial accepted")
            check((await browser.get(callback)).status_code == 400, "Denied transaction reusable")
            check(flow.provider.exchanges == 0, "Denied callback reached exchange")
    run(scenario())


def test_p10_stock_debug_logging_contains_pkce_verifier(flow_factory, caplog):
    async def scenario():
        flow = flow_factory()
        caplog.set_level(logging.DEBUG, logger="authlib.integrations.base_client.sync_app")
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            key = flow.cache.digest(f"_state_offline_{state_of(callback)}")
            verifier = json.loads(flow.cache.records[key][0])["data"]["code_verifier"]
            observed = any(verifier in record.getMessage() for record in caplog.records)
            caplog.clear()
            check(observed, "Debug logging changed; reassess logging control")
    run(scenario())


def test_p03_real_flows_have_distinct_state_nonce_and_challenge(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            first, _ = await flow.begin(browser)
            second, _ = await flow.begin(browser)
            a, b = parse_qs(urlsplit(first).query), parse_qs(urlsplit(second).query)
            for name in ("state", "nonce", "code_challenge"):
                check(a[name] != b[name], "Real authorization flow reused binding material")
    run(scenario())


def test_p05_missing_stored_nonce_cannot_establish_identity(flow_factory):
    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            key = flow.cache.digest(f"_state_offline_{state_of(callback)}")
            raw, expiry = flow.cache.records[key]
            stored = json.loads(raw)
            stored["data"].pop("nonce")
            flow.cache.records[key] = (json.dumps(stored), expiry)
            check((await browser.get(callback)).status_code == 400, "Identity accepted without stored nonce")
            check(flow.raw_missing_identity, "Application identity gate was not exercised")
    run(scenario())


class PKCELogExposure(AssertionError):
    """Fixed diagnostic, never include the verifier in exception text."""


@pytest.mark.xfail(strict=True, raises=PKCELogExposure,
                   reason="Stock DEBUG verifier disclosure remains security FAIL")
def test_p10_stock_debug_must_not_disclose_verifier(flow_factory, caplog):
    async def scenario():
        flow = flow_factory()
        caplog.set_level(logging.DEBUG, logger="authlib.integrations.base_client.sync_app")
        async with flow.client() as browser:
            _, callback = await flow.begin(browser)
            key = flow.cache.digest(f"_state_offline_{state_of(callback)}")
            verifier = json.loads(flow.cache.records[key][0])["data"]["code_verifier"]
            leaked = any(verifier in record.getMessage() for record in caplog.records)
            caplog.clear()
            if leaked:
                raise PKCELogExposure("Stock Authlib emitted PKCE secret at DEBUG")
    run(scenario())


def test_p10_filter_redacts_real_event_preserving_diagnostics(flow_factory, caplog):
    from authlib_oidc_poc.logging_controls import PKCEVerifierFilter
    logger = logging.getLogger("authlib.integrations.base_client.sync_app")
    control = PKCEVerifierFilter()
    logger.addFilter(control)
    caplog.set_level(logging.DEBUG, logger=logger.name)
    try:
        async def scenario():
            flow = flow_factory()
            async with flow.client() as browser:
                _, callback = await flow.begin(browser)
                key = flow.cache.digest(f"_state_offline_{state_of(callback)}")
                verifier = json.loads(flow.cache.records[key][0])["data"]["code_verifier"]
                logger.debug("Safe diagnostic: %s", "authorization started")
                records = [r for r in caplog.records if r.name == logger.name]
                check(not any(verifier in r.getMessage() for r in records), "Verifier redaction failed")
                redacted = [r for r in records if r.getMessage() == "Using code_verifier: [REDACTED]"]
                check(len(redacted) == 1, "Real redacted event missing")
                check(redacted[0].levelno == logging.DEBUG and redacted[0].lineno > 0,
                      "Diagnostic metadata lost")
                check(any(r.getMessage() == "Safe diagnostic: authorization started" for r in records),
                      "Unrelated diagnostic suppressed")
                check((await browser.get(callback)).status_code == 200, "Filter disrupted callback")
        run(scenario())
    finally:
        logger.removeFilter(control)
        caplog.clear()


def test_real_authlib_methods_are_delegated_to(flow_factory, monkeypatch):
    from authlib.integrations.starlette_client.apps import StarletteOAuth2App
    counts = {"redirect": 0, "callback": 0}
    original_redirect = StarletteOAuth2App.authorize_redirect
    original_callback = StarletteOAuth2App.authorize_access_token

    async def redirect(self, *args, **kwargs):
        counts["redirect"] += 1
        return await original_redirect(self, *args, **kwargs)

    async def callback(self, *args, **kwargs):
        counts["callback"] += 1
        return await original_callback(self, *args, **kwargs)

    monkeypatch.setattr(StarletteOAuth2App, "authorize_redirect", redirect)
    monkeypatch.setattr(StarletteOAuth2App, "authorize_access_token", callback)

    async def scenario():
        flow = flow_factory()
        async with flow.client() as browser:
            _, url = await flow.begin(browser)
            check((await browser.get(url)).status_code == 200, "Delegated callback failed")
        check(counts == {"redirect": 1, "callback": 1}, "Actual Authlib entry points not exercised")
        check(flow.provider.exchanges == 1, "Actual code exchange not exercised")
    run(scenario())
