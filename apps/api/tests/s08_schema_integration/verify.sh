#!/usr/bin/env bash
# Owner-operated, disposable S08 schema verification only.
set -Eeuo pipefail
umask 077
OUT="${1:?Exact evidence directory required}"
OUT="$(cd "$OUT" && pwd -P)"

SCHEMA_TEST_MODE="${2:-full}"
readonly SCHEMA_TEST_MODE
case "$SCHEMA_TEST_MODE" in
    full|regression-only|provider-accounting|smoke-wire|real-evidence|controlled-research|integrated-security|persistence-security|ci-successor|smoke-scope|smoke-runtime|owner-smoke-preflight) ;;
    *) echo 'Invalid S08 schema test mode'; exit 1 ;;
esac
echo "S08_SCHEMA_TEST_MODE=$SCHEMA_TEST_MODE"
API="$(cd "$(dirname "$0")/../.." && pwd -P)"
ID="s08-schema-$(date +%s)-$$"
NETWORK="$ID"
DB="$ID-db"
RUNNER="$ID-runner"
DEV_IMAGE="$ID-dev:local"
RUNTIME_IMAGE="$ID-runtime:local"
NETWORK_CREATED=0
DB_CREATED=0
RUNNER_CREATED=0
DEV_CREATED=0
RUNTIME_CREATED=0
cleanup() {
    local failed=0
    if [ "$RUNNER_CREATED" = 1 ]; then docker rm -f "$RUNNER" || failed=1; fi
    if [ "$DB_CREATED" = 1 ]; then docker rm -f "$DB" || failed=1; fi
    if [ "$NETWORK_CREATED" = 1 ]; then docker network rm "$NETWORK" || failed=1; fi
    if [ "$DEV_CREATED" = 1 ]; then docker image rm "$DEV_IMAGE" || failed=1; fi
    if [ "$RUNTIME_CREATED" = 1 ]; then docker image rm "$RUNTIME_IMAGE" || failed=1; fi
    [ "$failed" = 0 ]
}
finish() {
    local rc=$?
    trap - EXIT
    if cleanup > "$OUT/budget-cleanup.log" 2>&1; then
        echo 'DISPOSABLE_CLEANUP=PASS' >> "$OUT/budget-cleanup.log"
    else
        echo 'DISPOSABLE_CLEANUP=FAILED' >> "$OUT/budget-cleanup.log"
        rc=1
    fi
    cat "$OUT/budget-cleanup.log"
    exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker info >/dev/null
[ -z "${DOCKER_HOST:-}" ]
CONTEXT_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
case "$CONTEXT_HOST" in unix://*) ;; *) echo 'Local Docker daemon required'; exit 1 ;; esac
[ "$(docker info --format '{{.OSType}}')" = linux ]
case "$(docker info --format '{{.Architecture}}')" in
    aarch64|arm64) TARGET=py312-linux-aarch64 ;;
    x86_64|amd64) TARGET=py312-linux-x86_64 ;;
    *) echo 'Unsupported Docker architecture'; exit 1 ;;
esac
mkdir "$OUT/dependency-build"
cp "$API/requirements/$TARGET-dev.txt" "$OUT/dependency-build/dev.txt"
cp "$API/requirements/$TARGET-runtime.txt" "$OUT/dependency-build/runtime.txt"
cat > "$OUT/dependency-build/Dockerfile" <<'DOCKER'
FROM python:3.12-bookworm
ARG LOCK
COPY ${LOCK}.txt /tmp/requirements.txt
RUN python -m pip install --only-binary=:all: --require-hashes -r /tmp/requirements.txt && python -m pip check
DOCKER
for MODE in dev; do
    IMAGE="$ID-$MODE:local"
    docker build --build-arg "LOCK=$MODE" --tag "$IMAGE" "$OUT/dependency-build" > "$OUT/$MODE-image-build.log" 2>&1
    if [ "$MODE" = dev ]; then DEV_CREATED=1; else RUNTIME_CREATED=1; fi
    docker image inspect --format '{{.Id}}' "$IMAGE" > "$OUT/$MODE-image-id.txt"
done

# No published port, host network, mounted host DB or shared volume.
docker network create --driver bridge --internal --subnet 11.78.0.0/24 \
    --opt com.docker.network.bridge.gateway_mode_ipv4=isolated "$NETWORK" > "$OUT/budget-network-id.txt"
NETWORK_CREATED=1
docker network inspect "$NETWORK" > "$OUT/budget-network.json"
python3 - "$OUT/budget-network.json" <<'CHECK'
import json, sys
n = json.load(open(sys.argv[1]))[0]
assert n['Internal'] is True and n['Driver'] == 'bridge'
assert n['Options']['com.docker.network.bridge.gateway_mode_ipv4'] == 'isolated'
assert not n['Containers']
CHECK

docker create --name "$DB" --network "$NETWORK" --network-alias db --ip 11.78.0.10 \
    --read-only --security-opt no-new-privileges \
    --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev --tmpfs /var/run/postgresql:rw,nosuid,nodev --tmpfs /tmp:rw,nosuid,nodev \
    -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=isolated-test-only-postgres -e POSTGRES_DB=postgres \
    --mount "type=bind,source=$API/tests/migration_lifecycle/bootstrap.sql,target=/docker-entrypoint-initdb.d/01-bootstrap.sql,readonly" \
    postgres:17-bookworm > "$OUT/budget-db-id.txt"
DB_CREATED=1
docker start "$DB" >/dev/null
READY=0
for attempt in {1..60}; do
    if docker exec "$DB" pg_isready -h 127.0.0.1 -U postgres -d postgres >/dev/null 2>&1; then READY=1; break; fi
    sleep 1
done
[ "$READY" = 1 ]

docker create --name "$RUNNER" --network "$NETWORK" --ip 11.78.0.20 \
    --read-only --cap-drop ALL --security-opt no-new-privileges \
    --tmpfs /tmp:rw,nosuid,nodev --workdir /workspace \
    -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/workspace/src \
    -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -e AGENTOPS_RUN_DB_INTEGRATION=1 \
    -e "S08_SCHEMA_TEST_MODE=$SCHEMA_TEST_MODE" \
    -e AGENTOPS_MIGRATION_DATABASE_URL=postgresql+psycopg://agentops_migrator:isolated-test-only-migrator@db:5432/agentops_migration_test \
    --mount "type=bind,source=$API/src,target=/workspace/src,readonly" \
    --mount "type=bind,source=$API/tests,target=/workspace/tests,readonly" \
    --mount "type=bind,source=$API/alembic,target=/workspace/alembic,readonly" \
    --mount "type=bind,source=$API/alembic.ini,target=/workspace/alembic.ini,readonly" \
    --mount "type=bind,source=$API/pyproject.toml,target=/workspace/pyproject.toml,readonly" \
    "$DEV_IMAGE" sh -eu -c '
python - <<'"'"'CHECK'"'"'
from pathlib import Path
assert Path("/.dockerenv").is_file()
for line in Path("/proc/net/route").read_text().splitlines()[1:]:
    assert line.split()[1] != "00000000"
ipv6 = Path("/proc/net/ipv6_route")
if ipv6.exists():
    for line in ipv6.read_text().splitlines():
        fields = line.split()
        assert not (len(fields) >= 10 and fields[0] == "0" * 32 and fields[1] == "00" and fields[-1] != "lo")
print("ISOLATED_POSTGRES_RUNNER=PASS")
CHECK

echo "RUNNER_EFFECTIVE_TEST_MODE=$S08_SCHEMA_TEST_MODE"
case "$S08_SCHEMA_TEST_MODE" in
    full|regression-only|provider-accounting|smoke-wire|real-evidence|controlled-research|integrated-security|persistence-security|ci-successor|smoke-scope|smoke-runtime|owner-smoke-preflight) ;;
    *) echo "INVALID_RUNNER_TEST_MODE"; exit 1 ;;
esac
case "$S08_SCHEMA_TEST_MODE" in
    full)
        python -m alembic upgrade d8b3105f0804
        python -m alembic upgrade f9d3106b0802
        python -m alembic check
        python -m alembic downgrade d8b3105f0804
        python -m alembic upgrade f9d3106b0802
        python -m alembic check
        echo "S08_MIGRATION_LIFECYCLE=PASS"
        ;;
    ci-successor)
        sed -n '"'"'/^check_state() {/,/^echo "PASS: Alembic migration lifecycle"/p'"'"' \
            /workspace/tests/migration_lifecycle/run.sh \
            > /tmp/s08-successor-lifecycle.sh

        test -s /tmp/s08-successor-lifecycle.sh
        sh -eu /tmp/s08-successor-lifecycle.sh

        echo "S08_SUCCESSOR_LIFECYCLE=PASS"

        AGENTOPS_RUN_DB_INTEGRATION=0 \
            python -m pytest -p no:cacheprovider -q \
            --junitxml=/tmp/s08-optout.xml \
            tests/test_s08_schema_postgres.py

        python - <<'"'"'OPTOUT'"'"'
import xml.etree.ElementTree as ET
root = ET.parse("/tmp/s08-optout.xml")
cases = root.findall(".//testcase")
assert len(cases) == 44
assert all(case.find("skipped") is not None for case in cases)
assert not root.findall(".//failure")
assert not root.findall(".//error")
print("S08_SCHEMA_OPTOUT_44_SKIPPED=PASS")
OPTOUT
        ;;
    regression-only|provider-accounting|smoke-wire|real-evidence|controlled-research|integrated-security|persistence-security|smoke-scope|smoke-runtime|owner-smoke-preflight)
        python -m alembic upgrade f9d3106b0802
        python -m alembic check
        echo "S08_REGRESSION_DATABASE_READY=PASS"
        ;;
    *)
        exit 1
        ;;
esac
# Export JUnit before the runner exits: stopped-container tmpfs is ephemeral.
set +e
case "$S08_SCHEMA_TEST_MODE" in
    full)
        set -- tests/test_s08_schema_postgres.py tests/test_s07_budget_postgres.py tests/test_s08_provider_accounting_postgres.py tests/test_s08_smoke_wire.py tests/test_s08_provider_request_policy.py tests/test_s06_vendor_transport.py tests/test_s08_real_evidence.py tests/test_s08_controlled_research.py tests/test_s08_integrated_security.py tests/test_s08_persistence_security.py tests/test_identity_models.py tests/test_orm_infrastructure.py tests/test_s08_smoke_scope.py tests/test_s08_smoke_runtime.py tests/test_s08_owner_smoke.py tests/test_s08_retrieval_only.py
        ;;
    regression-only)
        set -- tests/test_s07_budget_postgres.py
        ;;
    provider-accounting)
        set -- tests/test_s07_budget_postgres.py tests/test_s08_provider_accounting_postgres.py
        ;;
    smoke-wire)
        set -- tests/test_s07_budget_postgres.py tests/test_s08_provider_accounting_postgres.py tests/test_s08_smoke_wire.py tests/test_s08_provider_request_policy.py tests/test_s06_vendor_transport.py
        ;;
    real-evidence)
        set -- tests/test_s07_budget_postgres.py tests/test_s08_provider_accounting_postgres.py tests/test_s08_smoke_wire.py tests/test_s08_real_evidence.py
        ;;
    controlled-research)
        set -- tests/test_s08_controlled_research.py
        ;;
    persistence-security)
        set -- tests/test_s08_persistence_security.py tests/test_identity_models.py tests/test_orm_infrastructure.py
        ;;
    ci-successor)
        set -- tests/test_s07_execution_postgres.py
        ;;
    smoke-scope)
        set -- tests/test_s08_smoke_scope.py tests/test_s08_controlled_research.py
        ;;
    smoke-runtime)
        set -- tests/test_s08_smoke_scope.py tests/test_s08_controlled_research.py tests/test_s08_provider_accounting_postgres.py tests/test_s08_smoke_wire.py tests/test_s08_real_evidence.py tests/test_s06_vendor_transport.py tests/test_s08_provider_request_policy.py tests/test_s07_budget_postgres.py tests/test_s08_integrated_security.py tests/test_s08_persistence_security.py tests/test_s08_smoke_runtime.py
        ;;
    owner-smoke-preflight)
        set -- tests/test_s08_owner_smoke.py tests/test_s08_smoke_runtime.py
        ;;
    integrated-security)
        set -- tests/test_s06_evidence_repository.py tests/test_s06_evidence_postgres.py tests/test_s06_evidence_security.py tests/test_s06_workflow_postgres.py tests/test_s06_workflow_service.py tests/test_s06_workflow_security.py tests/test_s08_real_evidence.py tests/test_s08_controlled_research.py tests/test_s08_integrated_security.py
        ;;
    *)
        exit 1
        ;;
esac
python -m pytest -p no:cacheprovider -q --tb=short --junitxml=/tmp/s08-schema.xml "$@"
TEST_RC=$?
set -e
python - <<'"'"'CHECK'"'"'
import base64, hashlib, json, os
from pathlib import Path
import xml.etree.ElementTree as ET
raw = Path("/tmp/s08-schema.xml").read_bytes()
# Emit losslessly even when the following acceptance assertions fail.
print("S08_SCHEMA_JUNIT_EXPORT=" + json.dumps({
    "name": "s08-schema.xml", "size": len(raw),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "base64": base64.b64encode(raw).decode(),
}, sort_keys=True), flush=True)
root = ET.fromstring(raw)
cases = root.findall(".//testcase")
from collections import Counter
counts = Counter(
    case.attrib.get("classname", "").rsplit(".", 1)[-1]
    for case in cases
)
mode = os.environ["S08_SCHEMA_TEST_MODE"]
if mode == "full":
    assert counts == {
        "test_s08_retrieval_only": 31,
        "test_s08_owner_smoke": 5,
        "test_s08_smoke_runtime": 15,
        "test_s08_smoke_scope": 17,
        "test_s08_persistence_security": 7,
        "test_identity_models": 7,
        "test_orm_infrastructure": 9,
        "test_s08_controlled_research": 14,
        "test_s08_integrated_security": 9,
        "test_s08_real_evidence": 24,
        "test_s08_schema_postgres": 44,
        "test_s07_budget_postgres": 22,
        "test_s08_provider_accounting_postgres": 29,
        "test_s08_smoke_wire": 15,
        "test_s08_provider_request_policy": 39,
        "test_s06_vendor_transport": 41,
    }, counts
elif mode == "regression-only":
    assert counts == {"test_s07_budget_postgres": 22}, counts
elif mode == "provider-accounting":
    assert counts == {
        "test_s07_budget_postgres": 22,
        "test_s08_provider_accounting_postgres": 29,
    }, counts
elif mode == "smoke-wire":
    assert counts == {
        "test_s07_budget_postgres": 22,
        "test_s08_provider_accounting_postgres": 29,
        "test_s08_smoke_wire": 15,
        "test_s08_provider_request_policy": 39,
        "test_s06_vendor_transport": 41,
    }, counts
elif mode == "real-evidence":
    assert counts == {
        "test_s07_budget_postgres": 22,
        "test_s08_provider_accounting_postgres": 29,
        "test_s08_smoke_wire": 15,
        "test_s08_real_evidence": 24,
    }, counts
elif mode == "controlled-research":
    assert counts == {"test_s08_controlled_research": 14}, counts
elif mode == "integrated-security":
    assert counts == {"test_s06_evidence_postgres": 17, "test_s06_evidence_repository": 23, "test_s06_evidence_security": 38, "test_s06_workflow_postgres": 9, "test_s06_workflow_security": 10, "test_s06_workflow_service": 32, "test_s08_controlled_research": 14, "test_s08_integrated_security": 9, "test_s08_real_evidence": 24}, counts
    assert counts["test_s08_integrated_security"] == 9, counts
    assert counts["test_s08_real_evidence"] == 24, counts
    assert counts["test_s08_controlled_research"] == 14, counts
    assert all(value > 0 for value in counts.values()), counts
elif mode == "persistence-security":
    assert counts == {"test_identity_models": 7, "test_orm_infrastructure": 9, "test_s08_persistence_security": 7}, counts
elif mode == "ci-successor":
    assert counts == {"test_s07_execution_postgres": 14}, counts
elif mode == "smoke-scope":
    assert counts == {"test_s08_controlled_research": 14, "test_s08_smoke_scope": 17}, counts
elif mode == "smoke-runtime":
    assert counts == {"test_s06_vendor_transport": 41, "test_s07_budget_postgres": 22, "test_s08_controlled_research": 14, "test_s08_integrated_security": 9, "test_s08_persistence_security": 7, "test_s08_provider_accounting_postgres": 29, "test_s08_provider_request_policy": 39, "test_s08_real_evidence": 24, "test_s08_smoke_runtime": 15, "test_s08_smoke_scope": 17, "test_s08_smoke_wire": 15}, counts
elif mode == "owner-smoke-preflight":
    assert counts == {"test_s08_owner_smoke": 5, "test_s08_smoke_runtime": 15}, counts
else:
    raise AssertionError("Unknown verification mode")
assert len({
    (case.attrib.get("classname"), case.attrib.get("name"))
    for case in cases
}) == len(cases)
assert not root.findall(".//skipped")
assert not root.findall(".//failure") and not root.findall(".//error")
print("POSTGRES_ZERO_SKIPS=PASS")
CHECK
exit "$TEST_RC"
' > "$OUT/budget-runner-id.txt"
RUNNER_CREATED=1
set +e
docker start -a "$RUNNER" > "$OUT/budget-postgres.log" 2>&1
RUN_RC=$?
set -e
docker logs "$DB" > "$OUT/budget-db.log" 2>&1
cat "$OUT/budget-postgres.log"

# Preserve the primary migration/runner failure if execution
# stopped before pytest could produce JUnit.
if ! grep -q '^S08_SCHEMA_JUNIT_EXPORT=' "$OUT/budget-postgres.log"; then
    echo 'JUNIT_EXPORT_MISSING=YES'
    echo "PRIMARY_RUNNER_EXIT=$RUN_RC"
    if [ "$RUN_RC" != 0 ]; then
        exit "$RUN_RC"
    fi
    exit 1
fi

# Decode exactly one completed export after execution; never ignore a missing
# or corrupted artifact and never grant a writable host mount to the runner.
python3 - "$OUT" <<'EXPORT'
import base64, hashlib, json, sys
from pathlib import Path
import xml.etree.ElementTree as ET
out = Path(sys.argv[1])
prefix = "S08_SCHEMA_JUNIT_EXPORT="
records = [line[len(prefix):] for line in (out / "budget-postgres.log").read_text().splitlines() if line.startswith(prefix)]
assert len(records) == 1, "Expected exactly one live-runner JUnit export"
record = json.loads(records[0])
assert record["name"] == "s08-schema.xml"
raw = base64.b64decode(record["base64"], validate=True)
assert len(raw) == record["size"]
assert hashlib.sha256(raw).hexdigest() == record["sha256"]
root = ET.fromstring(raw)
(out / "s08-schema.xml").write_bytes(raw)
review = {key: record[key] for key in ("name", "size", "sha256")}
review.update({"transport": "live_runner_stdout", "integrity": "PASS", "cases": len(root.findall(".//testcase"))})
(out / "junit-export-review.json").write_text(json.dumps(review, indent=2) + "\n")
print("JUNIT_LOSSLESS_EXPORT=PASS")
EXPORT
[ "$RUN_RC" = 0 ]
[ "$(docker inspect --format '{{.State.ExitCode}}' "$RUNNER")" = 0 ]
echo 'S08_SCHEMA_TARGETED_POSTGRES=PASS'
