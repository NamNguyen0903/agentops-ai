"""Create identity foundation.

Revision ID: 0291ce4556fe
Revises:
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0291ce4556fe"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "app"


def upgrade() -> None:
    # Schema must already exist and be owned by agentops_migrator.
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        schema=SCHEMA,
    )

    op.create_table(
        "auth_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_identities"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.users.id"],
            name="fk_auth_identities_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "issuer", "subject",
            name="uq_auth_identities_issuer",
        ),
        sa.CheckConstraint(
            "length(issuer) > 0",
            name="ck_auth_identities_issuer_nonempty",
        ),
        sa.CheckConstraint(
            "length(subject) > 0",
            name="ck_auth_identities_subject_nonempty",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_auth_identities_user_id",
        "auth_identities",
        ["user_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "idle_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "absolute_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "token_digest",
            name="uq_auth_sessions_token_digest",
        ),
        sa.CheckConstraint(
            "octet_length(token_digest) = 32",
            name="ck_auth_sessions_token_digest_length",
        ),
        sa.CheckConstraint(
            "octet_length(csrf_token_digest) = 32",
            name="ck_auth_sessions_csrf_digest_length",
        ),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_auth_sessions_idle_before_absolute",
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name="ck_auth_sessions_valid_absolute_expiry",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_auth_sessions_user_id",
        "auth_sessions",
        ["user_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "oidc_login_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "browser_binding_digest",
            sa.LargeBinary(length=32),
            nullable=False,
        ),
        sa.Column("encrypted_context", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_oidc_login_transactions",
        ),
        sa.UniqueConstraint(
            "state_digest",
            name="uq_oidc_login_transactions_state_digest",
        ),
        sa.CheckConstraint(
            "octet_length(state_digest) = 32",
            name="ck_oidc_login_transactions_state_digest_length",
        ),
        sa.CheckConstraint(
            "octet_length(browser_binding_digest) = 32",
            name="ck_oidc_login_transactions_browser_binding_digest_length",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_oidc_login_transactions_valid_expiry",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_oidc_login_transactions_expires_at",
        "oidc_login_transactions",
        ["expires_at"],
        schema=SCHEMA,
    )

    # AG-003.3B: Explicit runtime privilege policy.
    # The migration role owns schema objects.
    # The application role receives only approved DML.

    identity_tables = (
        "users",
        "auth_identities",
        "auth_sessions",
        "oidc_login_transactions",
    )

    for table_name in identity_tables:
        op.execute(
            f"REVOKE ALL PRIVILEGES "
            f"ON TABLE app.{table_name} "
            f"FROM agentops_app"
        )

        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON TABLE app.{table_name} "
            f"TO agentops_app"
        )

    # Runtime code must never modify Alembic history.
    op.execute(
        "REVOKE ALL PRIVILEGES "
        "ON TABLE app.alembic_version "
        "FROM agentops_app"
    )

    # Prevent schema-specific automatic DML grants
    # on future tables created by the migration role.
    op.execute(
        "ALTER DEFAULT PRIVILEGES "
        "FOR ROLE agentops_migrator "
        "IN SCHEMA app "
        "REVOKE SELECT, INSERT, UPDATE, DELETE "
        "ON TABLES FROM agentops_app"
    )



def downgrade() -> None:
    # Destructive: only permitted in a disposable test database.
    op.drop_index(
        "ix_oidc_login_transactions_expires_at",
        table_name="oidc_login_transactions",
        schema=SCHEMA,
    )
    op.drop_table("oidc_login_transactions", schema=SCHEMA)

    op.drop_index(
        "ix_auth_sessions_user_id",
        table_name="auth_sessions",
        schema=SCHEMA,
    )
    op.drop_table("auth_sessions", schema=SCHEMA)

    op.drop_index(
        "ix_auth_identities_user_id",
        table_name="auth_identities",
        schema=SCHEMA,
    )
    op.drop_table("auth_identities", schema=SCHEMA)

    op.drop_table("users", schema=SCHEMA)
