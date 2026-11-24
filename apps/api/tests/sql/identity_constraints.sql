
-- AG-003.3B: PostgreSQL negative constraint tests
-- Target: agentops_migration_test ONLY
-- Execute via psql with ON_ERROR_STOP=1.
-- No permanent data changes.

BEGIN;

DO $$
DECLARE
    target_db text := current_database();
    current_role_name text := current_user;
BEGIN
    IF target_db <> 'agentops_migration_test'
       OR current_role_name <> 'agentops_migrator'
    THEN
        RAISE EXCEPTION 'Unauthorized test database or role';
    END IF;
END
$$;

-- Verify critical constraints exist.
DO $$
DECLARE
    count_constraints integer;
BEGIN
    SELECT COUNT(*)
    INTO count_constraints
    FROM pg_constraint
    WHERE connamespace = 'app'::regnamespace;

    IF count_constraints < 19 THEN
        RAISE EXCEPTION
            'Expected at least 19 app constraints, found %',
            count_constraints;
    END IF;
END
$$;

-- Negative test: duplicate external identity must fail.
-- All changes remain inside the outer transaction.

DO $$
DECLARE
    test_user_id uuid :=
        '11111111-1111-4111-8111-111111111111';

    first_identity_id uuid :=
        '22222222-2222-4222-8222-222222222221';

    duplicate_identity_id uuid :=
        '22222222-2222-4222-8222-222222222222';

    constraint_caught boolean := false;
BEGIN
    INSERT INTO app.users (id)
    VALUES (test_user_id);

    INSERT INTO app.auth_identities (
        id,
        user_id,
        issuer,
        subject
    )
    VALUES (
        first_identity_id,
        test_user_id,
        'https://test.example.com',
        'test-subject-001'
    );

    BEGIN
        INSERT INTO app.auth_identities (
            id,
            user_id,
            issuer,
            subject
        )
        VALUES (
            duplicate_identity_id,
            test_user_id,
            'https://test.example.com',
            'test-subject-001'
        );

    EXCEPTION
        WHEN unique_violation THEN
            constraint_caught := true;
    END;

    IF NOT constraint_caught THEN
        RAISE EXCEPTION
            'FAILED: Duplicate issuer/subject was accepted';
    END IF;

    RAISE NOTICE
        'PASS: Duplicate issuer/subject rejected';
END
$$;

-- Negative test: identity cannot reference a nonexistent user.

DO $$
DECLARE
    constraint_caught boolean := false;
BEGIN
    BEGIN
        INSERT INTO app.auth_identities (
            id,
            user_id,
            issuer,
            subject
        )
        VALUES (
            '33333333-3333-4333-8333-333333333333',
            '99999999-9999-4999-8999-999999999999',
            'https://fk-test.example.com',
            'missing-user-test'
        );

    EXCEPTION
        WHEN foreign_key_violation THEN
            constraint_caught := true;
    END;

    IF NOT constraint_caught THEN
        RAISE EXCEPTION
            'FAILED: Invalid user_id was accepted';
    END IF;

    RAISE NOTICE
        'PASS: Foreign key rejected nonexistent user';
END
$$;

-- AG-003.3B: Additional negative constraint tests.
-- Execute only inside the existing outer transaction.

DO $$
DECLARE
    caught boolean;
BEGIN
    -- 1. Empty issuer must be rejected.
    caught := false;

    BEGIN
        INSERT INTO app.auth_identities (
            id, user_id, issuer, subject
        )
        VALUES (
            '44444444-4444-4444-8444-444444444441',
            '11111111-1111-4111-8111-111111111111',
            '',
            'empty-issuer'
        );
    EXCEPTION
        WHEN check_violation THEN
            caught := true;
    END;

    IF NOT caught THEN
        RAISE EXCEPTION 'FAILED: Empty issuer accepted';
    END IF;

    RAISE NOTICE 'PASS: Empty issuer rejected';

    -- 2. NULL subject must be rejected.
    caught := false;

    BEGIN
        INSERT INTO app.auth_identities (
            id, user_id, issuer, subject
        )
        VALUES (
            '44444444-4444-4444-8444-444444444442',
            '11111111-1111-4111-8111-111111111111',
            'https://example.com',
            NULL
        );
    EXCEPTION
        WHEN not_null_violation THEN
            caught := true;
    END;

    IF NOT caught THEN
        RAISE EXCEPTION 'FAILED: NULL subject accepted';
    END IF;

    RAISE NOTICE 'PASS: NULL subject rejected';

    -- 3. Invalid session token digest length.
    caught := false;

    BEGIN
        INSERT INTO app.auth_sessions (
            id,
            user_id,
            token_digest,
            csrf_token_digest,
            idle_expires_at,
            absolute_expires_at
        )
        VALUES (
            '44444444-4444-4444-8444-444444444443',
            '11111111-1111-4111-8111-111111111111',
            decode('abcd', 'hex'),
            decode(repeat('ab', 32), 'hex'),
            now() + interval '10 minutes',
            now() + interval '1 hour'
        );
    EXCEPTION
        WHEN check_violation THEN
            caught := true;
    END;

    IF NOT caught THEN
        RAISE EXCEPTION
            'FAILED: Invalid session digest accepted';
    END IF;

    RAISE NOTICE 'PASS: Invalid session digest rejected';

    -- 4. Idle expiry cannot exceed absolute expiry.
    caught := false;

    BEGIN
        INSERT INTO app.auth_sessions (
            id,
            user_id,
            token_digest,
            csrf_token_digest,
            idle_expires_at,
            absolute_expires_at
        )
        VALUES (
            '44444444-4444-4444-8444-444444444444',
            '11111111-1111-4111-8111-111111111111',
            decode(repeat('cd', 32), 'hex'),
            decode(repeat('ef', 32), 'hex'),
            now() + interval '2 hours',
            now() + interval '1 hour'
        );
    EXCEPTION
        WHEN check_violation THEN
            caught := true;
    END;

    IF NOT caught THEN
        RAISE EXCEPTION
            'FAILED: Invalid session expiry accepted';
    END IF;

    RAISE NOTICE 'PASS: Invalid session expiry rejected';

    -- 5. Invalid OIDC state digest length.
    caught := false;

    BEGIN
        INSERT INTO app.oidc_login_transactions (
            id,
            state_digest,
            browser_binding_digest,
            encrypted_context,
            expires_at
        )
        VALUES (
            '44444444-4444-4444-8444-444444444445',
            decode('1234', 'hex'),
            decode(repeat('ab', 32), 'hex'),
            decode('abcd', 'hex'),
            now() + interval '5 minutes'
        );
    EXCEPTION
        WHEN check_violation THEN
            caught := true;
    END;

    IF NOT caught THEN
        RAISE EXCEPTION
            'FAILED: Invalid OIDC state digest accepted';
    END IF;

    RAISE NOTICE 'PASS: Invalid OIDC state digest rejected';
END
$$;

-- Verify least-privilege configuration.
-- No DDL or permission changes.

DO $$
DECLARE
    table_name text;
    privilege_name text;
    has_permission boolean;
BEGIN
    -- The application must not create schema objects.
    IF has_schema_privilege(
        'agentops_app', 'app', 'CREATE'
    ) THEN
        RAISE EXCEPTION
            'FAIL: Application role has schema CREATE';
    END IF;

    -- Migration history must be inaccessible to runtime DML.
    FOREACH privilege_name IN ARRAY
        ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']
    LOOP
        IF has_table_privilege(
            'agentops_app',
            'app.alembic_version',
            privilege_name
        ) THEN
            RAISE EXCEPTION
                'FAIL: Application role has % on alembic_version',
                privilege_name;
        END IF;
    END LOOP;

    -- Verify runtime role does not own identity tables.
    FOR table_name IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'app'
          AND c.relkind IN ('r', 'p')
    LOOP
        IF EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'app'
              AND c.relname = table_name
              AND pg_get_userbyid(c.relowner) <> 'agentops_migrator'
        ) THEN
            RAISE EXCEPTION
                'FAIL: Unexpected owner for %', table_name;
        END IF;
    END LOOP;

    RAISE NOTICE 'PASS: Runtime permissions and ownership';
END
$$;

ROLLBACK;
