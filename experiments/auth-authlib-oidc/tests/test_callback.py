import pytest

from authlib_oidc_poc.oidc_client import InvalidIDToken, verify_id_token


def checked(provider, config, token, *, nonce="expected", now=1000):
    return verify_id_token(token, provider.public_key, issuer=config.issuer,
                           audience=config.client_id, nonce=nonce, now=now)


def test_p05_valid_signed_id_token(provider, config):
    token = provider.issue_id_token(audience=config.client_id, nonce="expected", at_time=1000)
    assert checked(provider, config, token)["sub"] == "test-user-123"


@pytest.mark.parametrize("overrides", [
    {"iss": "https://bad-issuer.test"},
    {"aud": "different-client"},
    {"nonce": "bad-nonce"},
    {"exp": 999},
    {"sub": ""},
    {"aud": ["agentops-poc-client", "another-client"], "azp": "another-client"},
])
def test_p05_rejects_bad_claims(provider, config, overrides):
    claims = {
    "audience": config.client_id,
    "nonce": "expected",
    "at_time": 1000,
    }

    claims.update(overrides)

    token = provider.issue_id_token(**claims)
    with pytest.raises(InvalidIDToken):
            checked(provider, config, token)


def test_p05_rejects_wrong_signing_key(provider, config):
    from authlib_oidc_poc.fake_provider import FakeOIDCProvider
    other = FakeOIDCProvider()
    token = other.issue_id_token(audience=config.client_id, nonce="expected", at_time=1000)
    with pytest.raises(InvalidIDToken):
        checked(provider, config, token)
