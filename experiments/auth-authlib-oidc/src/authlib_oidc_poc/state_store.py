"""Test-only in-memory OIDC transaction store; NOT multi-process durable storage.

Atomic consume is guarded by an asyncio lock. Runtime PostgreSQL implementation
and browser-cookie handling are deliberately not implemented here.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Callable


class InvalidOIDCState(Exception):
    """Non-specific error: no secret material in the exception message."""


@dataclass(frozen=True)
class OIDCTransaction:
    nonce: str
    code_verifier: str
    browser_digest: str
    expires_at: float


class InMemoryOIDCStateStore:
    def __init__(self, ttl_seconds: int = 300, clock: Callable[[], float] = time.time):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = asyncio.Lock()
        self._records: dict[str, OIDCTransaction] = {}

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def issue(self, browser_secret: str) -> tuple[str, OIDCTransaction]:
        if len(browser_secret) < 32:
            raise ValueError("browser binding is too short")
        state = secrets.token_urlsafe(32)
        record = OIDCTransaction(
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(48),
            browser_digest=self._digest(browser_secret),
            expires_at=self._clock() + self._ttl_seconds,
        )
        async with self._lock:
            self._records[self._digest(state)] = record
        return state, record

    async def consume(self, state: str, browser_secret: str) -> OIDCTransaction:
        if not state or not browser_secret:
            raise InvalidOIDCState("Invalid or expired OIDC transaction")
        key = self._digest(state)
        async with self._lock:
            record = self._records.pop(key, None)
        if record is None or self._clock() >= record.expires_at:
            raise InvalidOIDCState("Invalid or expired OIDC transaction")
        if not hmac.compare_digest(record.browser_digest, self._digest(browser_secret)):
            raise InvalidOIDCState("Invalid or expired OIDC transaction")
        return record

    async def pending_count(self) -> int:
        async with self._lock:
            return len(self._records)
