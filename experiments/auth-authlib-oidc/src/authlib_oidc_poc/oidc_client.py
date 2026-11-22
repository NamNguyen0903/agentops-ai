"""Isolated OIDC primitives plus an Authlib client registration smoke helper.

No real identity provider, persistent sessions or production routes are installed.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebToken

from .config import OIDCConfig


class InvalidIDToken(Exception):
    pass


def pkce_s256(code_verifier: str) -> str:
    raw = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def authorize_url(config: OIDCConfig, state: str, nonce: str, verifier: str) -> str:
    """Protocol-level redirect builder for independently testable PKCE contract."""
    if not state or not nonce or not verifier:
        raise ValueError("Missing OIDC transaction fields")
    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": config.redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": pkce_s256(verifier),
        "code_challenge_method": "S256",
    }
    return config.issuer + "/authorize?" + urlencode(params)


def register_authlib_client(config: OIDCConfig):
    """Verify Authlib Starlette client registration, not a callback integration."""
    oauth = OAuth()
    return oauth.register(
        name="google",
        client_id=config.client_id,
        client_secret="INERT_TEST_ONLY_NOT_REAL_SECRET",
        server_metadata_url=config.issuer + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )


def verify_id_token(
    token: str,
    public_key,
    *,
    issuer: str,
    audience: str,
    nonce: str,
    now: int,
) -> dict:
    """Local JOSE verification test; not proof of discovery/JWKS rotation.

    Enforce RS256 only. Real OIDC clients must also verify signing key provenance,
    metadata, response/code binding and clock-skew policy.
    """
    try:
        claims = JsonWebToken(["RS256"]).decode(
            token,
            public_key,
            claims_options={
                "iss": {"essential": True, "value": issuer},
                "aud": {"essential": True, "value": audience},
                "exp": {"essential": True},
                "iat": {"essential": True},
                "sub": {"essential": True},
                "nonce": {"essential": True, "value": nonce},
            },
        )
        claims.validate(now=now, leeway=0)
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise ValueError("Missing subject")
        if isinstance(claims.get("aud"), list) and len(claims["aud"]) > 1:
            if claims.get("azp") != audience:
                raise ValueError("Invalid authorized party")
        return dict(claims)
    except Exception as exc:
        raise InvalidIDToken("Invalid OIDC identity token") from exc
