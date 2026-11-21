
#!/usr/bin/env bash
# Read-only verification, except rollback-only negative DDL tests.
set +x
set -Eeuo pipefail

: "${APP_DB_PASSWORD:?Missing application password}"

export PGPASSWORD="$APP_DB_PASSWORD"
export PGCONNECT_TIMEOUT=3
export PGOPTIONS="-c statement_timeout=3000"

PSQL=(
  psql
  -X
  -h 127.0.0.1
  -p 5432
  -U agentops_app
  -d agentops
  -v ON_ERROR_STOP=1
  -qAt
)

if [[ "$("${PSQL[@]}" -c "SELECT 1" 2>/dev/null)" != "1" ]]; then
  echo "FAIL: application credential connection" >&2
  exit 1
fi

echo "PASS: application role TCP authentication"

role_flags=$(
  "${PSQL[@]}" -c "
    SELECT
      rolsuper::int,
      rolcreatedb::int,
      rolcreaterole::int,
      rolreplication::int,
      rolbypassrls::int
    FROM pg_roles
    WHERE rolname = current_user;
  " 2>/dev/null
)

if [[ "$role_flags" != "0|0|0|0|0" ]]; then
  echo "FAIL: unexpected application role privileges" >&2
  exit 1
fi

echo "PASS: role privilege flags"

privileges=$(
  "${PSQL[@]}" -c "
    SELECT
      has_database_privilege(current_user, current_database(), 'CONNECT')::int,
      has_database_privilege(current_user, current_database(), 'CREATE')::int,
      has_schema_privilege(current_user, 'public', 'USAGE')::int,
      has_schema_privilege(current_user, 'public', 'CREATE')::int;
  " 2>/dev/null
)

if [[ "$privileges" != "1|0|1|0" ]]; then
  echo "FAIL: unexpected effective database/schema privileges" >&2
  exit 1
fi

echo "PASS: effective database/schema privileges"

# Both commands run in transactions. A successful CREATE is
# rolled back before the process returns; that success is a failure
# of the security test, not permission to keep the object.
if "${PSQL[@]}" -c "
  BEGIN;
  CREATE SCHEMA agentops_negative_schema;
  ROLLBACK;
" >/dev/null 2>&1; then
  echo "FAIL: application role can CREATE SCHEMA" >&2
  exit 1
fi

echo "PASS: CREATE SCHEMA denied"

if "${PSQL[@]}" -c "
  BEGIN;
  CREATE TABLE public.agentops_negative_table (id integer);
  ROLLBACK;
" >/dev/null 2>&1; then
  echo "FAIL: application role can CREATE TABLE" >&2
  exit 1
fi

echo "PASS: CREATE TABLE denied"

memberships=$(
  "${PSQL[@]}" -c "
    SELECT COUNT(*)
    FROM pg_auth_members
    WHERE member = (
      SELECT oid FROM pg_roles
      WHERE rolname = current_user
    );
  " 2>/dev/null
)

if [[ "$memberships" != "0" ]]; then
  echo "FAIL: application role has unexpected memberships" >&2
  exit 1
fi

echo "PASS: no inherited/granted role memberships"
echo "PASS: PostgreSQL application role verification"
