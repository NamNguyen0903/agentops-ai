"""Proposed S02 identity persistence models.

No database operations occur at import time.
Application transactions are explicitly managed by services.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from agentops_api.core.orm import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuthIdentity(Base):
    __tablename__ = "auth_identities"

    __table_args__ = (
        UniqueConstraint("issuer", "subject"),
        CheckConstraint(
            "length(issuer) > 0",
            name="issuer_nonempty",
        ),
        CheckConstraint(
            "length(subject) > 0",
            name="subject_nonempty",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issuer: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    __table_args__ = (
        UniqueConstraint("token_digest"),
        CheckConstraint(
            "octet_length(token_digest) = 32",
            name="token_digest_length",
        ),
        CheckConstraint(
            "octet_length(csrf_token_digest) = 32",
            name="csrf_digest_length",
        ),
        CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="idle_before_absolute",
        ),
        CheckConstraint(
            "absolute_expires_at > created_at",
            name="valid_absolute_expiry",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32),
        nullable=False,
    )

    csrf_token_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class OIDCLoginTransaction(Base):
    __tablename__ = "oidc_login_transactions"

    __table_args__ = (
        UniqueConstraint("state_digest"),
        CheckConstraint(
            "octet_length(state_digest) = 32",
            name="state_digest_length",
        ),
        CheckConstraint(
            "octet_length(browser_binding_digest) = 32",
            name="browser_binding_digest_length",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="valid_expiry",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    state_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32),
        nullable=False,
    )

    browser_binding_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32),
        nullable=False,
    )

    # Encrypted OIDC transaction context, including nonce and PKCE verifier.
    # Encryption/key management must be approved before production use.
    encrypted_context: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
