#!/bin/sh
# S07 test-only runner. The host orchestration layer must
# establish the dedicated internal network before invocation.

set -eu

export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export AGENTOPS_RUN_DB_INTEGRATION=0
export AGENTOPS_RUN_LEGACY_COMPOSE_TESTS=0

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
unset http_proxy https_proxy all_proxy
unset SSL_CERT_FILE SSL_CERT_DIR
unset REQUESTS_CA_BUNDLE CURL_CA_BUNDLE
unset TAVILY_API_KEY
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
unset OPENAI_API_KEY ANTHROPIC_API_KEY
unset LANGCHAIN_API_KEY LANGSMITH_API_KEY

if [ "${AGENTOPS_S07_NETWORK_FIXTURE:-}" != "1" ]; then
    echo "BLOCKER: isolated fixture scope required"
    exit 1
fi

python - <<'PY'
import os
from pathlib import Path

assert Path("/.dockerenv").is_file()

assert os.environ.get(
    "AGENTOPS_S07_NETWORK_FIXTURE"
) == "1"

routes = Path(
    "/proc/net/route"
).read_text().splitlines()

for line in routes[1:]:
    fields = line.split()

    assert fields[1] != "00000000", (
        "Default IPv4 route forbidden"
    )

ipv6 = Path("/proc/net/ipv6_route")

if ipv6.exists():
    for line in ipv6.read_text().splitlines():
        fields = line.split()

        if len(fields) >= 10:
            assert not (
                fields[0] == "0" * 32
                and fields[1] == "00"
                and fields[-1] != "lo"
            ), "Default IPv6 route forbidden"

print("CONTAINER_SCOPE=PASS")
print("DEFAULT_NETWORK_ROUTES=NONE")
PY

case "${1:-}" in
    preflight)
        echo "S07_ISOLATED_RUNNER_PREFLIGHT=PASS"
        ;;

    verify)
        # This suite is added by WP03-B.
        test -f tests/test_s07_secure_connector.py

        python -m pytest \
            -p no:cacheprovider \
            -v \
            --tb=short \
            tests/test_s07_secure_connector.py
        ;;

    *)
        echo "BLOCKER: expected preflight or verify"
        exit 2
        ;;
esac
