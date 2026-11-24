"""Boundary tests are intentionally modest; they do not certify production security."""
import inspect

from authlib_oidc_poc import oidc_client, state_store


def test_p10_errors_do_not_echo_state_or_browser_secret():
    import asyncio
    async def scenario():
        store = state_store.InMemoryOIDCStateStore()
        state, _ = await store.issue("s" * 64)
        try:
            await store.consume(state, "w" * 64)
        except state_store.InvalidOIDCState as error:
            assert state not in str(error)
            assert "s" * 64 not in str(error)
            assert "w" * 64 not in str(error)
        else:
            raise AssertionError("Expected invalid browser binding")
    asyncio.run(scenario())


def test_p11_isolated_components_do_not_import_sqlalchemy():
    for module in (oidc_client, state_store):
        source = inspect.getsource(module)
        assert "from sqlalchemy" not in source
        assert "import sqlalchemy" not in source
        assert ".commit(" not in source


def test_p12_no_production_routes_installed():
    # This only checks isolation in the sample, NOT backend regression.
    assert not hasattr(oidc_client, "app")
