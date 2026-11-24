
-- AG-003.3B — Transactional DDL rollback
-- Disposable migration-test database ONLY.
-- Does not run Alembic downgrade.

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF current_database() <> 'agentops_migration_test'
       OR current_user <> 'agentops_migrator'
    THEN
        RAISE EXCEPTION 'Unauthorized database target';
    END IF;

    IF (
        SELECT pg_get_userbyid(nspowner)
        FROM pg_namespace
        WHERE nspname = 'app'
    ) IS DISTINCT FROM 'agentops_migrator'
    THEN
        RAISE EXCEPTION 'Unexpected schema ownership';
    END IF;

    IF to_regclass('app.users') IS NULL THEN
        RAISE EXCEPTION 'Required identity table missing';
    END IF;
END
$$;

BEGIN;

SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE app.users
ADD COLUMN ag0033b_rollback_probe boolean;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'app'
          AND table_name = 'users'
          AND column_name = 'ag0033b_rollback_probe'
    ) THEN
        RAISE EXCEPTION
            'FAIL: Transactional DDL not visible';
    END IF;

    RAISE NOTICE 'PASS: DDL visible inside transaction';
END
$$;

ROLLBACK;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'app'
          AND table_name = 'users'
          AND column_name = 'ag0033b_rollback_probe'
    ) THEN
        RAISE EXCEPTION
            'FAIL: DDL survived transaction rollback';
    END IF;

    IF to_regclass('app.users') IS NULL THEN
        RAISE EXCEPTION 'FAIL: Identity table disappeared';
    END IF;

    RAISE NOTICE 'PASS: Transactional DDL rollback verified';
END
$$;
