from urllib.parse import parse_qs, urlsplit

from authlib_oidc_poc.oidc_client import authorize_url, pkce_s256


def test_p02_authorization_request_has_pkce_and_expected_params(config):
    url = authorize_url(config, "test-state", "test-nonce", "X" * 48)
    params = parse_qs(urlsplit(url).query)
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert params["client_id"] == [config.client_id]
    assert params["redirect_uri"] == [config.redirect_uri]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] == [pkce_s256("X" * 48)]
    assert "code_verifier" not in params


def test_p02_distinct_verifiers_have_distinct_challenges():
    assert pkce_s256("A" * 48) != pkce_s256("B" * 48)
