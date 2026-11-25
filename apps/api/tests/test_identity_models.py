"""Schema metadata tests; these tests do not modify PostgreSQL."""

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint

from agentops_api.core.orm import Base
from agentops_api.models.identity import (
    AuthIdentity,
    AuthSession,
    OIDCLoginTransaction,
    User,
)


def test_identity_tables_registered():
    assert set(Base.metadata.tables) >= {
        "app.users",
        "app.auth_identities",
        "app.auth_sessions",
        "app.oidc_login_transactions",
    }


def test_all_identity_tables_use_app_schema():
    for model in (
        User,
        AuthIdentity,
        AuthSession,
        OIDCLoginTransaction,
    ):
        assert model.__table__.schema == "app"


def test_external_identity_is_unique_by_issuer_and_subject():
    constraints = [
        c for c in AuthIdentity.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    assert any(
        {column.name for column in c.columns}
        == {"issuer", "subject"}
        for c in constraints
    )


def test_authentication_digests_are_unique():
    for model, column_name in (
        (AuthSession, "token_digest"),
        (OIDCLoginTransaction, "state_digest"),
    ):
        assert any(
            isinstance(c, UniqueConstraint)
            and {column.name for column in c.columns}
            == {column_name}
            for c in model.__table__.constraints
        )


def test_identity_foreign_keys_reference_users():
    for model in (AuthIdentity, AuthSession):
        foreign_keys = [
            fk
            for c in model.__table__.columns
            for fk in c.foreign_keys
            if isinstance(fk, ForeignKey)
        ]
        assert any(
            fk.target_fullname == "app.users.id"
            for fk in foreign_keys
        )


def test_security_check_constraints_exist():
    for model in (AuthSession, OIDCLoginTransaction):
        checks = [
            constraint
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        assert checks


def test_model_import_registers_only_expected_tables():
    from agentops_api.models import research, queue  # noqa: F401

    assert set(Base.metadata.tables) == {
        "app.users", "app.auth_identities", "app.auth_sessions",
        "app.oidc_login_transactions", "app.research_tasks",
        "app.queue_control",
        "app.research_evidence",
    }
