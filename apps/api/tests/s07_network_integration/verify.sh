#!/usr/bin/env bash
# Dedicated isolated S07 integration verification.
# Never invoke with a shared Docker network or runtime secrets.

set -Eeuo pipefail
umask 077

OUT="${1:?Evidence directory required}"

[ -d "$OUT" ]

OUT="$(cd "$OUT" && pwd -P)"
API="$(cd "$(dirname "$0")/../.." && pwd -P)"

ID="s07-net-$(date +%s)-$$"

NETWORK="$ID"
IMAGE="$ID:local"

PRIMARY="$ID-primary"
SECONDARY="$ID-secondary"
RUNNER="$ID-runner"
CERTGEN="$ID-certgen"

CERTS="$OUT/private-certificates"
BUILD="$OUT/image-build"

NETWORK_CREATED=0
IMAGE_CREATED=0
CLEANUP_DONE=0

cleanup() {
    local failed=0
    local container

    if [ "$CLEANUP_DONE" -eq 1 ]; then
        return 0
    fi

    {
        echo "===== S07 RESOURCE CLEANUP ====="

        for container in \
            "$RUNNER" "$SECONDARY" "$PRIMARY" "$CERTGEN"
        do
            if docker container inspect \
                "$container" >/dev/null 2>&1
            then
                docker rm -f "$container" || failed=1
            fi
        done

        if [ "$NETWORK_CREATED" -eq 1 ]; then
            docker network rm "$NETWORK" || failed=1

            if docker network inspect \
                "$NETWORK" >/dev/null 2>&1
            then
                failed=1
            fi
        fi

        if [ "$IMAGE_CREATED" -eq 1 ]; then
            docker image rm "$IMAGE" || failed=1
        fi

        # Delete only this package's temporary certificates.
        if [ -d "$CERTS" ]; then
            rm -f -- \
                "$CERTS/ca.pem" \
                "$CERTS/server.pem" \
                "$CERTS/server.key" || failed=1

            rmdir "$CERTS" || failed=1
        fi

        if [ -e "$CERTS" ]; then
            failed=1
        fi

        if [ "$failed" -eq 0 ]; then
            echo "PRIVATE_CERTIFICATES_REMOVED=YES"
            echo "ISOLATED_RESOURCE_CLEANUP=PASS"
        else
            echo "ISOLATED_RESOURCE_CLEANUP=FAILED"
        fi

    } >> "$OUT/cleanup.log" 2>&1

    cat "$OUT/cleanup.log"

    if [ "$failed" -eq 0 ]; then
        CLEANUP_DONE=1
        return 0
    fi

    return 1
}

finish() {
    local rc=$?

    trap - EXIT

    cleanup || rc=1

    exit "$rc"
}

trap finish EXIT

echo "===== VERIFY DOCKER AVAILABILITY ====="

docker info >/dev/null

ARCH="$(docker info --format '{{.Architecture}}')"

case "$ARCH" in
    aarch64|arm64)
        LOCK="py312-linux-aarch64-dev.txt"
        ;;
    x86_64|amd64)
        LOCK="py312-linux-x86_64-dev.txt"
        ;;
    *)
        echo "Unsupported Docker architecture: $ARCH"
        exit 1
        ;;
esac

echo "LOCKED_REQUIREMENTS=$LOCK"

mkdir -p "$BUILD" "$CERTS"

cp "$API/requirements/$LOCK" \
    "$BUILD/requirements.txt"

# Dependency preparation is separated from connector tests.
# The build context contains no repository source or secrets.
cat > "$BUILD/Dockerfile" <<'DOCKER'
FROM python:3.12-bookworm
WORKDIR /workspace
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install \
    --only-binary=:all: \
    --require-hashes \
    -r /tmp/requirements.txt \
    && python -m pip check \
    && rm /tmp/requirements.txt
DOCKER

docker build \
    --tag "$IMAGE" \
    "$BUILD" \
    2>&1 | tee "$OUT/image-build.log"

IMAGE_CREATED=1

docker image inspect \
    "$IMAGE" \
    --format '{{.Id}}' \
    > "$OUT/test-image-id.txt"

echo "===== CREATE ISOLATED INTERNAL NETWORK ====="

# Fail closed on Docker versions that do not support
# isolated bridge gateway mode. Do not downgrade isolation.
docker network create \
    --driver bridge \
    --internal \
    --subnet 11.77.0.0/24 \
    --opt com.docker.network.bridge.gateway_mode_ipv4=isolated \
    "$NETWORK" \
    > "$OUT/network-id.txt"

NETWORK_CREATED=1

docker network inspect \
    "$NETWORK" \
    > "$OUT/network-initial.json"

python3 - "$OUT/network-initial.json" <<'PY'
import json
import sys

network = json.load(open(sys.argv[1]))[0]

assert network["Internal"] is True
assert network["Driver"] == "bridge"
assert network["EnableIPv6"] is False
assert not network["Containers"]

assert network["Options"][
    "com.docker.network.bridge.gateway_mode_ipv4"
] == "isolated"

assert len(network["IPAM"]["Config"]) == 1

assert network["IPAM"]["Config"][0][
    "Subnet"
] == "11.77.0.0/24"

print("NETWORK_INTERNAL=PASS")
print("ISOLATED_GATEWAY_MODE=PASS")
print("IPV6_DISABLED=PASS")
PY

# Override resolver configuration directly.
# Do not depend on Docker's external DNS forwarding.
cat > "$OUT/resolv.conf" <<'DNS'
nameserver 11.77.0.10
options ndots:1 timeout:1 attempts:1
DNS

echo "===== GENERATE TEMPORARY CERTIFICATES OFFLINE ====="

docker run \
    --rm \
    --name "$CERTGEN" \
    --network none \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev \
    -e AGENTOPS_S07_NETWORK_FIXTURE=1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    --mount "type=bind,source=$API/tests/s07_network_integration,target=/fixture,readonly" \
    --mount "type=bind,source=$CERTS,target=/certificates" \
    "$IMAGE" \
    python /fixture/fixture_server.py \
        certificates \
        --directory /certificates \
    | tee "$OUT/certificate-generation.log"

[ -f "$CERTS/ca.pem" ]
[ -f "$CERTS/server.pem" ]
[ -f "$CERTS/server.key" ]

echo "===== START CONTROLLED FIXTURES ====="

common=(
    --network "$NETWORK"
    --cap-drop ALL
    --cap-add NET_BIND_SERVICE
    --security-opt no-new-privileges
    --read-only
    --tmpfs /tmp:rw,nosuid,nodev
    -e AGENTOPS_S07_NETWORK_FIXTURE=1
    -e PYTHONDONTWRITEBYTECODE=1
    --mount "type=bind,source=$API/tests/s07_network_integration,target=/fixture,readonly"
    --mount "type=bind,source=$CERTS,target=/certificates,readonly"
    --mount "type=bind,source=$OUT/resolv.conf,target=/etc/resolv.conf,readonly"
)

docker run -d \
    --name "$PRIMARY" \
    --ip 11.77.0.10 \
    "${common[@]}" \
    "$IMAGE" \
    python /fixture/fixture_server.py \
        serve \
        --directory /certificates \
        --address 11.77.0.10 \
        --dns

docker run -d \
    --name "$SECONDARY" \
    --ip 11.77.0.11 \
    "${common[@]}" \
    "$IMAGE" \
    python /fixture/fixture_server.py \
        serve \
        --directory /certificates \
        --address 11.77.0.11

ready() {
    local container="$1"
    local address="$2"
    local attempt

    for attempt in $(seq 1 40); do
        if docker logs "$container" 2>&1 |
            grep -Fq "fixture_ready:$address"
        then
            return 0
        fi

        sleep 0.25
    done

    docker logs "$container" >&2 || true

    return 1
}

ready "$PRIMARY" "11.77.0.10"
ready "$SECONDARY" "11.77.0.11"

echo "FIXTURE_READINESS=PASS"

echo "===== CREATE INTEGRATION RUNNER ====="

docker create \
    --name "$RUNNER" \
    --network "$NETWORK" \
    --ip 11.77.0.20 \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev \
    --workdir /workspace \
    -e AGENTOPS_S07_NETWORK_FIXTURE=1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e PYTHONPATH=/workspace/src \
    --mount "type=bind,source=$API/src,target=/workspace/src,readonly" \
    --mount "type=bind,source=$API/tests,target=/workspace/tests,readonly" \
    --mount "type=bind,source=$API/pyproject.toml,target=/workspace/pyproject.toml,readonly" \
    --mount "type=bind,source=$CERTS/ca.pem,target=/s07-ca.pem,readonly" \
    --mount "type=bind,source=$OUT/resolv.conf,target=/etc/resolv.conf,readonly" \
    "$IMAGE" \
    sh -ec '
        sh tests/s07_network_integration/run.sh preflight

        python - <<'"'"'PY'"'"'
from pathlib import Path
import socket

servers = [
    line.split()[1]
    for line in Path("/etc/resolv.conf").read_text().splitlines()
    if line.startswith("nameserver ")
]

assert servers == ["11.77.0.10"]

# A kernel routing query using UDP connect sends no
# application payload. No external HTTP or DNS probe.
probe = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM,
)

try:
    try:
        probe.connect(("192.0.2.1", 9))
    except OSError:
        pass
    else:
        raise AssertionError(
            "Unexpected route outside fixture subnet"
        )
finally:
    probe.close()

print("FIXTURE_DNS_ONLY=PASS")
print("OUTSIDE_SUBNET_ROUTE_DENIED=PASS")
PY

        sh tests/s07_network_integration/run.sh verify
    '

echo "===== VERIFY CONTAINER AND NETWORK CONFINEMENT ====="

docker inspect \
    "$PRIMARY" \
    "$SECONDARY" \
    "$RUNNER" \
    > "$OUT/container-inspection.private.json"

python3 - \
    "$OUT/container-inspection.private.json" \
    "$NETWORK" \
    "$OUT/confinement.json" <<'PY'
import json
import sys

path, network_name, output = sys.argv[1:]

containers = json.load(open(path))

assert len(containers) == 3

expected = [
    "11.77.0.10",
    "11.77.0.11",
    "11.77.0.20",
]

evidence = []

for container, ip in zip(
    containers, expected
):
    host = container["HostConfig"]

    assert host["Privileged"] is False
    assert host["ReadonlyRootfs"] is True

    assert not host.get("PortBindings")
    assert host["NetworkMode"] == network_name

    def normalize_capabilities(values):
        assert values is None or isinstance(values, list), (
            "Invalid Docker capability representation"
        )

        result = set()

        for value in values or []:
            assert isinstance(value, str)

            # Docker may serialize capabilities with CAP_.
            # Normalize representation only, not privileges.
            result.add(value.upper().removeprefix("CAP_"))

        return result

    dropped = normalize_capabilities(
        host.get("CapDrop")
    )

    added = normalize_capabilities(
        host.get("CapAdd")
    )

    assert dropped == {"ALL"}, (
        container["Name"],
        "All default capabilities must be dropped",
        sorted(dropped),
    )

    expected_added = (
        {"NET_BIND_SERVICE"}
        if ip in {"11.77.0.10", "11.77.0.11"}
        else set()
    )

    assert added == expected_added, (
        container["Name"],
        "Unexpected added capabilities",
        sorted(added),
        sorted(expected_added),
    )

    print(
        "CAPABILITY_POLICY_PASS="
        + container["Name"]
    )

    assert any(
        "no-new-privileges" in value
        for value in host.get("SecurityOpt", [])
    )

    networks = container[
        "NetworkSettings"
    ]["Networks"]

    assert set(networks) == {network_name}

    assigned = networks[network_name]

    configured = (
        assigned.get("IPAddress")
        or assigned.get(
            "IPAMConfig", {}
        ).get("IPv4Address")
    )

    assert configured == ip, (
        container["Name"],
        "Unexpected fixture address",
        configured,
        ip,
    )

    assert not assigned.get("Gateway"), (
        container["Name"],
        "Unexpected IPv4 gateway",
    )

    assert not assigned.get("IPv6Gateway"), (
        container["Name"],
        "Unexpected IPv6 gateway",
    )

    mounts = container["Mounts"]

    for mount in mounts:
        if mount["Type"] == "bind":
            assert mount["RW"] is False

        assert mount["Destination"] not in {
            "/var/run/docker.sock",
            "/run/docker.sock",
        }

    environment_names = {
        item.split("=", 1)[0]
        for item in container["Config"]["Env"]
    }

    forbidden = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "TAVILY_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "AGENTOPS_DATABASE_URL",
    }

    assert not (
        environment_names & forbidden
    )

    evidence.append({
        "name": container["Name"],
        "configured_ipv4": configured,
        "network": network_name,
        "privileged": False,
        "published_ports": False,
        "read_only_root": True,
        "bind_mounts_read_only": True,
        "credential_environment_names_present": False,
        "normalized_capabilities_dropped": sorted(dropped),
        "normalized_capabilities_added": sorted(added),
        "ipv4_gateway": assigned.get("Gateway"),
        "ipv6_gateway": assigned.get("IPv6Gateway"),
    })

with open(output, "w") as handle:
    json.dump(
        evidence,
        handle,
        indent=2,
    )
    handle.write("\n")

print("CONTAINER_CONFINEMENT=PASS")
PY

# Do not export raw docker inspect data.
rm -f "$OUT/container-inspection.private.json"

docker network inspect \
    "$NETWORK" \
    > "$OUT/network-before-tests.json"

python3 - \
    "$OUT/network-before-tests.json" \
    "$PRIMARY" "$SECONDARY" "$RUNNER" <<'PY'
import json
import sys

network = json.load(
    open(sys.argv[1])
)[0]

assert network["Internal"] is True

members = {
    item["Name"]
    for item in network["Containers"].values()
}

assert {
    sys.argv[2], sys.argv[3]
} <= members

assert members <= set(sys.argv[2:])

print("NETWORK_MEMBERSHIP=PASS")
PY

echo "===== EXECUTE ACTUAL CONNECTOR TESTS ====="

set +e

docker start -a "$RUNNER" \
    2>&1 | tee "$OUT/connector-tests.log"

TEST_RC="${PIPESTATUS[0]}"

set -e

docker logs "$PRIMARY" \
    > "$OUT/primary-fixture.log" 2>&1

docker logs "$SECONDARY" \
    > "$OUT/secondary-fixture.log" 2>&1

[ "$TEST_RC" -eq 0 ]

[ "$(docker inspect \
    --format '{{.State.ExitCode}}' "$RUNNER")" = "0" ]

echo "ACTUAL_CONNECTOR_TEST_RUN=PASS"

cleanup

trap - EXIT
