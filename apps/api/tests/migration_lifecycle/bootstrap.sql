
-- Isolated migration lifecycle database setup.
-- Runs only during initialization of the temporary container.

CREATE ROLE agentops_migrator
    LOGIN
    PASSWORD 'isolated-test-only-migrator';

-- Synthetic runtime login for this disposable database only.
CREATE ROLE agentops_app
    LOGIN
    PASSWORD 'isolated-test-only-runtime'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

CREATE DATABASE agentops_migration_test
    OWNER agentops_migrator;

\connect agentops_migration_test

CREATE SCHEMA app
    AUTHORIZATION agentops_migrator;

GRANT USAGE ON SCHEMA app
    TO agentops_app;
