#!/usr/bin/env bash
# Owner-operated, disposable S07 WP04 runtime verification only.
set -Eeuo pipefail
umask 077
OUT="${1:?Exact evidence directory required}"
OUT="$(cd "$OUT" && pwd -P)"
API="$(cd "$(dirname "$0")/../.." && pwd -P)"
ID="s07-budget-$(date +%s)-$$"
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
for MODE in runtime dev; do
    IMAGE="$ID-$MODE:local"
    docker build --build-arg "LOCK=$MODE" --tag "$IMAGE" "$OUT/dependency-build" > "$OUT/$MODE-image-build.log" 2>&1
    if [ "$MODE" = dev ]; then DEV_CREATED=1; else RUNTIME_CREATED=1; fi
    docker image inspect --format '{{.Id}}' "$IMAGE" > "$OUT/$MODE-image-id.txt"
done

docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
    --tmpfs /tmp:rw,nosuid,nodev -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/workspace/src \
    --mount "type=bind,source=$API/src,target=/workspace/src,readonly" \
    "$RUNTIME_IMAGE" python -c '
import importlib, importlib.metadata as m, json
names = ["httpx", "httpx2", "sqlalchemy", "psycopg", "langgraph", "langsmith",
         "agentops_api.services.durable_execution", "agentops_api.services.s06_acquisition.tavily",
         "agentops_api.services.s06_acquisition.integrated_retrieval"]
for name in names: importlib.import_module(name)
print(json.dumps({p: m.version(p) for p in ["httpx", "httpx2", "SQLAlchemy", "psycopg", "langgraph", "langsmith"]}, sort_keys=True))
print("RUNTIME_IMPORT_COMPATIBILITY=PASS")
' > "$OUT/runtime-imports.log" 2>&1

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
python -m alembic upgrade c7a2104e0702
python -m alembic upgrade d8b3105f0804
python -m alembic check
python -m alembic downgrade c7a2104e0702
python -m alembic upgrade d8b3105f0804
python -m alembic check
# Export JUnit before the runner exits: stopped-container tmpfs is ephemeral.
set +e
python -m pytest -p no:cacheprovider -q --tb=short --junitxml=/tmp/s07-budget.xml tests/test_s07_worker_postgres.py tests/test_s07_execution_postgres.py tests/test_s06_evidence_repository.py tests/test_s06_evidence_postgres.py tests/test_s06_workflow_postgres.py tests/test_s06_workflow_service.py tests/test_s06_evidence_security.py tests/test_s06_workflow_security.py tests/test_s07_durable_integration.py tests/test_s07_budget_postgres.py tests/test_s07_execution_budget.py tests/test_s07_execution_runner.py
TEST_RC=$?
set -e
python - <<'"'"'CHECK'"'"'
import base64, hashlib, json
from pathlib import Path
import xml.etree.ElementTree as ET
raw = Path("/tmp/s07-budget.xml").read_bytes()
# Emit losslessly even when the following acceptance assertions fail.
print("S07_JUNIT_EXPORT=" + json.dumps({
    "name": "s07-budget.xml", "size": len(raw),
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
assert counts["test_s07_worker_postgres"] == 9
for suite in (
    "test_s07_execution_postgres",
    "test_s06_evidence_repository",
    "test_s06_evidence_postgres",
    "test_s06_workflow_postgres",
    "test_s06_workflow_service",
    "test_s06_evidence_security",
    "test_s06_workflow_security",
    "test_s07_durable_integration",
):
    assert counts[suite] > 0, suite
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
# Decode exactly one completed export after execution; never ignore a missing
# or corrupted artifact and never grant a writable host mount to the runner.
python3 - "$OUT" <<'EXPORT'
import base64, hashlib, json, sys
from pathlib import Path
import xml.etree.ElementTree as ET
out = Path(sys.argv[1])
prefix = "S07_JUNIT_EXPORT="
records = [line[len(prefix):] for line in (out / "budget-postgres.log").read_text().splitlines() if line.startswith(prefix)]
assert len(records) == 1, "Expected exactly one live-runner JUnit export"
record = json.loads(records[0])
assert record["name"] == "s07-budget.xml"
raw = base64.b64decode(record["base64"], validate=True)
assert len(raw) == record["size"]
assert hashlib.sha256(raw).hexdigest() == record["sha256"]
root = ET.fromstring(raw)
(out / "s07-budget.xml").write_bytes(raw)
review = {key: record[key] for key in ("name", "size", "sha256")}
review.update({"transport": "live_runner_stdout", "integrity": "PASS", "cases": len(root.findall(".//testcase"))})
(out / "junit-export-review.json").write_text(json.dumps(review, indent=2) + "\n")
print("JUNIT_LOSSLESS_EXPORT=PASS")
EXPORT
[ "$RUN_RC" = 0 ]
[ "$(docker inspect --format '{{.State.ExitCode}}' "$RUNNER")" = 0 ]
echo 'S07_WP05_INTEGRATED_POSTGRES=PASS'
