"""Atomic consumption of a stored OIDC login transaction."""

import hmac

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from agentops_api.models.identity import OIDCLoginTransaction


async def _consume_oidc_state(
    session: AsyncSession,
    *,
    state_digest: bytes,
    browser_binding_digest: bytes,
) -> bytes | None:
    """Consume state once; return encrypted context on success.

    Caller must use a fresh login after a failed or uncertain
    consumption attempt. No provider I/O occurs here.

    The transaction must commit before this function returns
    the encrypted context to the caller.
    """
    if len(state_digest) != 32:
        return None

    if len(browser_binding_digest) != 32:
        return None

    async with session.begin():
        statement = (
            select(OIDCLoginTransaction)
            .where(
                OIDCLoginTransaction.state_digest
                == state_digest
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        result = await session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None or record.consumed_at is not None:
            return None

        # Read database time AFTER acquiring the row lock.
        now = await session.scalar(
            select(func.clock_timestamp())
        )

        if now is None:
            raise RuntimeError("Database clock unavailable")

        valid_time = record.expires_at > now

        valid_binding = hmac.compare_digest(
            record.browser_binding_digest,
            browser_binding_digest,
        )

        encrypted_context = (
            record.encrypted_context
            if valid_time and valid_binding
            else None
        )

        # Burn the transaction even when expired or binding
        # mismatched, as specified by the security contract.
        record.consumed_at = now
        record.encrypted_context = b""

    # Reaching here means the transaction committed.
    # The caller may now proceed to token exchange.
    return encrypted_context


class OIDCStateUnavailable(RuntimeError):
    """Safe boundary error; callers must not retry a potentially consumed state."""


async def consume_oidc_state(
    session: AsyncSession, *, state_digest: bytes, browser_binding_digest: bytes,
) -> bytes | None:
    """Return context only after confirmed commit; never expose driver details."""
    try:
        return await _consume_oidc_state(
            session, state_digest=state_digest,
            browser_binding_digest=browser_binding_digest,
        )
    except SQLAlchemyError:
        raise OIDCStateUnavailable("OIDC state storage unavailable; start a new login") from None
