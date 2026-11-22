import asyncio

import pytest

from authlib_oidc_poc.state_store import InMemoryOIDCStateStore, InvalidOIDCState


BROWSER = "browser-binding-secret-" + "z" * 40


def run(coro):
    return asyncio.run(coro)


def test_p03_state_nonce_verifier_unique():
    async def scenario():
        store = InMemoryOIDCStateStore()
        first, a = await store.issue(BROWSER)
        second, b = await store.issue(BROWSER)
        assert first != second and a.nonce != b.nonce and a.code_verifier != b.code_verifier
    run(scenario())


def test_p04_wrong_state_rejected():
    async def scenario():
        store = InMemoryOIDCStateStore()
        await store.issue(BROWSER)
        with pytest.raises(InvalidOIDCState):
            await store.consume("invalid-state", BROWSER)
    run(scenario())


def test_p06_expired_state_rejected():
    async def scenario():
        now = [100.0]
        store = InMemoryOIDCStateStore(ttl_seconds=5, clock=lambda: now[0])
        state, _ = await store.issue(BROWSER)
        now[0] += 5
        with pytest.raises(InvalidOIDCState):
            await store.consume(state, BROWSER)
    run(scenario())


def test_p07_replay_rejected():
    async def scenario():
        store = InMemoryOIDCStateStore()
        state, record = await store.issue(BROWSER)
        assert await store.consume(state, BROWSER) == record
        with pytest.raises(InvalidOIDCState):
            await store.consume(state, BROWSER)
    run(scenario())


def test_p08_concurrent_consumes_only_one_succeeds():
    async def scenario():
        store = InMemoryOIDCStateStore()
        state, _ = await store.issue(BROWSER)
        results = await asyncio.gather(
            *[store.consume(state, BROWSER) for _ in range(16)], return_exceptions=True)
        assert sum(not isinstance(r, Exception) for r in results) == 1
        assert sum(isinstance(r, InvalidOIDCState) for r in results) == 15
    run(scenario())


def test_p09_binding_mismatch_rejected_and_consumed():
    async def scenario():
        store = InMemoryOIDCStateStore()
        state, _ = await store.issue(BROWSER)
        with pytest.raises(InvalidOIDCState):
            await store.consume(state, "another-browser-" + "x" * 40)
        with pytest.raises(InvalidOIDCState):
            await store.consume(state, BROWSER)
    run(scenario())
