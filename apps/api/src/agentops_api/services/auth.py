"""Review-only services; all persistence uses the existing explicit sessions."""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, func, update

from agentops_api.models.identity import AuthIdentity, AuthSession, User, OIDCLoginTransaction
from agentops_api.services.oidc_state import consume_oidc_state


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


class ContextCipher:
    """Versioned AEAD; key supplied externally. Rotation invalidates pending logins."""
    def __init__(self, encoded_key):
        self.cipher = AESGCM(base64.b64decode(encoded_key, validate=True))

    def encrypt(self, context, state, binding):
        nonce = secrets.token_bytes(12)
        aad = b'agentops-oidc-v1' + digest(state) + digest(binding)
        return b'\x01' + nonce + self.cipher.encrypt(nonce, json.dumps(context).encode(), aad)

    def decrypt(self, data, state, binding):
        if data[:1] != b'\x01':
            raise ValueError('Invalid OIDC context')
        aad = b'agentops-oidc-v1' + digest(state) + digest(binding)
        return json.loads(self.cipher.decrypt(data[1:13], data[13:], aad))


class AuthService:
    def __init__(self, factory, cipher):
        self.factory = factory
        self.cipher = cipher

    async def issue_state(self, state, binding, context):
        async with self.factory() as session, session.begin():
            now = await session.scalar(select(func.clock_timestamp()))
            session.add(OIDCLoginTransaction(state_digest=digest(state), browser_binding_digest=digest(binding),
                encrypted_context=self.cipher.encrypt(context, state, binding), created_at=now,
                expires_at=now+timedelta(minutes=5)))

    async def consume(self, state, binding):
        async with self.factory() as session:
            data = await consume_oidc_state(session, state_digest=digest(state), browser_binding_digest=digest(binding))
        return self.cipher.decrypt(data, state, binding) if data else None

    async def login(self, issuer, subject, old_token):
        async with self.factory() as session, session.begin():
            user = await session.scalar(select(User).join(AuthIdentity).where(
                AuthIdentity.issuer == issuer, AuthIdentity.subject == subject).with_for_update(of=User))
            if user is None or not user.is_active:
                return None
            now = await session.scalar(select(func.clock_timestamp()))
            if old_token:
                await session.execute(
                        update(AuthSession)
                        .where(
                            AuthSession.token_digest == digest(old_token),
                            AuthSession.user_id == user.id,
                            AuthSession.revoked_at.is_(None),
                        )
                        .values(revoked_at=now)
                )
            token, csrf = random_token(), random_token()
            session.add(AuthSession(user_id=user.id, token_digest=digest(token), csrf_token_digest=digest(csrf),
                created_at=now, last_seen_at=now, idle_expires_at=now+timedelta(minutes=30),
                absolute_expires_at=now+timedelta(hours=12)))
        return token

    async def principal(self, token, *, csrf=None, logout=False, new_csrf=False):
        if not token or len(token) > 256:
            return None
        async with self.factory() as session, session.begin():
            # All account/session mutations lock User before AuthSession.
            # The initial lookup is advisory only; revalidate the session under lock.
            owner_id = await session.scalar(select(AuthSession.user_id).where(
                AuthSession.token_digest == digest(token)))
            if owner_id is None:
                return None
            user = await session.scalar(select(User).where(User.id == owner_id)
                .with_for_update().execution_options(populate_existing=True))
            if user is None or not user.is_active:
                return None
            record = await session.scalar(select(AuthSession).where(
                AuthSession.token_digest == digest(token), AuthSession.user_id == owner_id)
                .with_for_update().execution_options(populate_existing=True))
            if record is None:
                return None
            now = await session.scalar(select(func.clock_timestamp()))
            if (record.revoked_at or record.idle_expires_at <= now or record.absolute_expires_at <= now
                    or user is None or not user.is_active):
                return None
            if logout:
                if not csrf or not hmac.compare_digest(record.csrf_token_digest, digest(csrf)):
                    raise ValueError('Invalid CSRF proof')
                record.revoked_at = now
            else:
                record.last_seen_at = now
                record.idle_expires_at = min(now+timedelta(minutes=30), record.absolute_expires_at)
            proof = random_token() if new_csrf else None
            if proof:
                record.csrf_token_digest = digest(proof)
            result = {'id': str(user.id), 'csrf_token': proof}
        return result
    async def disable_user_and_revoke_sessions(self, user_id):
        async with self.factory() as session, session.begin():
            user = await session.scalar(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
            )

            if user is None:
                return False

            now = await session.scalar(
                select(func.clock_timestamp())
            )

            user.is_active = False
            user.updated_at = now

            await session.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )

        return True
