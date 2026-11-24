
#!/usr/bin/env bash
# First initialization of the local PostgreSQL volume only.
set +x
set -Eeuo pipefail

if [[ "${POSTGRES_USER:-}" != "agentops_bootstrap" ]] ||
   [[ "${POSTGRES_DB:-}" != "agentops" ]]; then
  echo "Invalid PostgreSQL bootstrap configuration." >&2
  exit 1
fi

if [[ ! "${POSTGRES_PASSWORD:-}" =~ ^[[:xdigit:]]{32,}$ ]] ||
   [[ ! "${APP_DB_PASSWORD:-}" =~ ^[[:xdigit:]]{32,}$ ]]; then
  echo "Generated hexadecimal passwords are required." >&2
  exit 1
fi

if [[ "$POSTGRES_PASSWORD" == "$APP_DB_PASSWORD" ]]; then
  echo "Bootstrap and application passwords must differ." >&2
  exit 1
fi

# The official image starts a temporary server during initialization.
# Connect over its Unix socket, not the TCP host.
# Errors are suppressed because SQL errors can contain secret literals.
if ! PGOPTIONS="-c log_statement=none -c log_min_error_statement=panic" \
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --no-psqlrc \
    --set=ON_ERROR_STOP=1 \
    --quiet \
    >/dev/null 2>&1 <<'SQL'
\getenv app_password APP_DB_PASSWORD

BEGIN;

CREATE ROLE agentops_app
  LOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOREPLICATION
  NOBYPASSRLS
  CONNECTION LIMIT 10
  PASSWORD :'app_password';

REVOKE ALL ON DATABASE agentops FROM PUBLIC;
GRANT CONNECT ON DATABASE agentops TO agentops_app;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO agentops_app;

ALTER ROLE agentops_app IN DATABASE agentops
  SET statement_timeout = '5s';

ALTER ROLE agentops_app IN DATABASE agentops
  SET lock_timeout = '2s';

COMMIT;
SQL
then
  echo "Application role bootstrap failed; preserve the volume." >&2
  exit 1
fi

unset APP_DB_PASSWORD
echo "Application database role initialized."
