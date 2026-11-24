# Operator Account Provisioning Runbook

## Status and authorization

- Date: 2026-11-24.
- Sprint: S02.
- Policy: operator-managed account provisioning.
- Owner policy approval: APPROVED.
- Scope: Development MVP and synthetic identities only.
- Production deployment: NOT APPROVED.
- Real-user activation: NOT APPROVED.
- Authentication remains disabled by default.

## Preconditions

Verify the intended database, migration revision, environment
and operator authorization before making any changes.

Development verification uses disposable PostgreSQL:

- Database: agentops_migration_test.
- Test role: agentops_migrator.
- Schema: app.
- Migration revision: 0291ce4556fe.

The test migration role is not an approved production
operator role.

Never execute this procedure against a normal development
or production database without separate authorization.

## Identity policy

Accounts are identified by the verified issuer and subject.

Google issuer: https://accounts.google.com.

The subject must come from trusted identity verification.

Never use an email address as the identity key.
Never trust an arbitrary user-submitted subject.
Never automatically link or transfer identity ownership.

Use unique synthetic subjects during offline development.

## Account creation

The following ORM procedure uses the transactional pattern
covered by existing disposable PostgreSQL integration tests.

The caller must supply an explicitly authorized session
factory connected to the intended database.

```python
from agentops_api.models.identity import User, AuthIdentity

async def provision_account(factory, verified_subject):
    if not isinstance(verified_subject, str):
        raise ValueError("Invalid subject")

    if not verified_subject.strip() or len(verified_subject) > 255:
        raise ValueError("Invalid subject")

    async with factory() as session, session.begin():
        user = User()
        session.add(user)
        await session.flush()

        user_id = user.id

        session.add(
            AuthIdentity(
                user_id=user_id,
                issuer="https://accounts.google.com",
                subject=verified_subject,
            )
        )

        await session.flush()

    return user_id
```

The user ID is returned only after transaction commit.

User and identity creation must remain atomic.
A duplicate issuer/subject mapping must fail and roll back.

Do not implement an upsert that reassigns identity ownership.

If the commit result is uncertain, inspect the original
issuer/subject mapping before retrying.

## Access verification

In the isolated offline environment:

1. Verify the identity maps to the expected user ID.
2. Use the existing synthetic-provider login contract.
3. Confirm the server-derived principal matches the user.
4. Confirm unprovisioned identities are rejected.
5. Confirm inactive accounts are rejected.

Do not print raw session tokens, CSRF proofs or credentials.

## Disable and revoke

Use the existing AuthService method:

```python
result = await service.disable_user_and_revoke_sessions(user_id)
assert result is True
```

The service locks User before AuthSession and performs
account disable and session revocation in one transaction.

Do not merely set is_active to false without revoking
existing sessions.

After the transaction commits, previous sessions and new
login attempts must be rejected.

This operation does not cancel business actions that
were authorized before the disable transaction committed.

## Reactivation

Require explicit operator authorization.

Reactivation must not restore revoked sessions.
A fresh authentication flow is required.

## Existing verification evidence

The previously executed disposable PostgreSQL suite
recorded seven passing tests.

Relevant coverage includes:

- Transactional user and identity creation.
- Provisioned login and server-derived principal.
- Unprovisioned and inactive account rejection.
- Identity uniqueness.
- Account-wide session revocation.
- Reactivation without session resurrection.
- Cross-user session isolation.
- Concurrent account-disable serialization.

Source references:

- apps/api/tests/test_auth_postgres.py
- apps/api/tests/test_auth_disable_concurrency.py
- apps/api/tests/test_identity_unique_postgres.py
- apps/api/src/agentops_api/services/auth.py
- apps/api/src/agentops_api/models/identity.py
- docs/development/PYTHON_DEPENDENCIES.md

Existing tests verify the underlying ORM and service
operations.

The illustrative runbook function was not independently
executed as a standalone operator command.

No new application tests were executed during this
documentation checkpoint.

## Release gates

Before real-user exposure:

- Establish trusted live Google subject enrollment.
- Establish dedicated operator access controls.
- Establish operator authorization and audit trails.
- Verify deployed provisioning and disable procedures.

No real-user account activation is authorized.
