"""Offline synthetic RS256 identity provider for tests only."""
from __future__ import annotations

import time

from authlib.jose import JsonWebToken
from cryptography.hazmat.primitives.asymmetric import rsa


class FakeOIDCProvider:
    def __init__(self, issuer="https://fake-idp.example.test"):
        self.issuer = issuer
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()

    def issue_id_token(
        self, *, audience: str, nonce: str, sub: str = "test-user-123",
        at_time: int | None = None, ttl: int = 300, **overrides,
    ) -> str:
        current = int(time.time()) if at_time is None else int(at_time)
        claims = {
            "iss": self.issuer,
            "aud": audience,
            "sub": sub,
            "iat": current,
            "exp": current + ttl,
            "nonce": nonce,
        }
        claims.update(overrides)
        return JsonWebToken(["RS256"]).encode({"alg": "RS256"}, claims, self.private_key).decode("ascii")
