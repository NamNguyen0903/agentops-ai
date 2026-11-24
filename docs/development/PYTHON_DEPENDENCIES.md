# Python Dependency Baseline

## Status

- Date: 2026-11-24
- Sprint: S02
- Ticket: AG-003.6
- Work package: WP01.1
- Status: VERIFIED_LOCALLY
- Remote CI: PENDING
- Production approval: NOT APPROVED

## Dependency policy

Application dependencies are installed from platform-specific,
hash-checked requirements using binary wheels.

Install the local application package separately with
`--no-deps --no-build-isolation`, followed by `pip check`.

The seed file constrains the reviewed dependency baseline.
It is not an installation lockfile.

Unsupported platform profiles must not silently fall back
to unconstrained installation.

## Reviewed versions

| Package | Version |
|---|---|
| Authlib | 1.9.10 |
| FastAPI | 0.165.0 |
| Starlette | 1.10.0 |
| cryptography | 50.0.2 |
| joserfc | 1.8.0 |
| httpx2 | 2.16.2 |
| httpcore2 | 2.16.2 |
| SQLAlchemy | 2.0.58 |
| Psycopg | 3.3.9 |
| setuptools | 84.1.0 |

## Security remediation

The initial advisory audit reported setuptools findings
across all nine application profiles.

Reported advisory IDs:

- PYSEC-2026-3447
- GHSA-xmj3-9gf7-h52w

Setuptools was updated from 79.0.1 / 80.10.2 to 84.1.0.

The other application dependency pins were retained.

The nine final lockfiles were derived by a targeted,
verified wheel/hash replacement, not a new full resolution.

Patched wheel SHA256:

`5231689c6ac8156cd155cfb98c3fd6fb252c3e7e9bd3d78b64d3c55f132624c9`

## Verification results

| Target | Backend regression | Offline Authlib PoC |
|---|---|---|
| Python 3.12 macOS ARM64 | 100 passed, 8 skipped | 56 passed, 1 xfailed |
| Python 3.11 Linux AMD64 | 100 passed, 8 skipped | N/A |
| Python 3.12 Linux AMD64 | 100 passed, 8 skipped | 56 passed, 1 xfailed |
| Python 3.12 Linux ARM64 | 100 passed, 8 skipped | N/A |

Additional verification:

- Fresh installation: all nine required profiles passed.
- Generator replay and smoke compilation: four targets passed.
- Docker runtime builds: AMD64 and ARM64 passed.
- Runtime non-root checks: passed.
- Runtime pytest exclusion: passed.
- PostgreSQL migration lifecycle: passed.
- PostgreSQL integration: seven tests passed.
- Application lockfile audit using pip-audit 2.10.1:
  nine profiles passed with no known vulnerabilities reported.
- Git whitespace check: passed.

The eight backend skips include explicitly gated
PostgreSQL tests and the legacy shared-stack test.
The seven disposable PostgreSQL tests were run separately.

## Integration

Hash-checked installation is integrated into:

- apps/api/Dockerfile
- .github/workflows/backend-ci.yml
- apps/api/tests/migration_lifecycle/run.sh

## Remaining limitations

- Remote GitHub Actions verification is pending.
- Actionlint has not been executed.
- Stock Authlib PKCE DEBUG logging exposure remains
  a known security failure, preserved as strict XFAIL.
- The application-specific logging mitigation does not
  establish universal logging or deployment safety.
- Generator replay is verified, but the generator's initial
  bootstrap is not fully prelocked in the repository.
- The audit covers application lockfiles, not all OS,
  container, frontend, tooling or bundled native components.
- Base image tags and installer bootstrap are not fully pinned.
- Live Google OIDC and production acceptance remain outside
  this verification result.
- No production authorization or ADR acceptance is implied.

## Lockfile evidence

| Lockfile | Advisory audit | SHA256 |
|---|---|---|
| `apps/api/requirements/py311-linux-x86_64-dev.txt` | PASS | `cadd63d57c4c9bb6f2295cdd8438d24b0041bc55ac45fd12ef1ff8ef73f3623c` |
| `apps/api/requirements/py312-darwin-arm64-dev.txt` | PASS | `cadd63d57c4c9bb6f2295cdd8438d24b0041bc55ac45fd12ef1ff8ef73f3623c` |
| `apps/api/requirements/py312-darwin-arm64-runtime.txt` | PASS | `59cf481155cf35e916f4234460bcb59ac3a7754f46a7a57ce66ac102e908608f` |
| `apps/api/requirements/py312-linux-aarch64-dev.txt` | PASS | `cadd63d57c4c9bb6f2295cdd8438d24b0041bc55ac45fd12ef1ff8ef73f3623c` |
| `apps/api/requirements/py312-linux-aarch64-runtime.txt` | PASS | `59cf481155cf35e916f4234460bcb59ac3a7754f46a7a57ce66ac102e908608f` |
| `apps/api/requirements/py312-linux-x86_64-dev.txt` | PASS | `cadd63d57c4c9bb6f2295cdd8438d24b0041bc55ac45fd12ef1ff8ef73f3623c` |
| `apps/api/requirements/py312-linux-x86_64-runtime.txt` | PASS | `59cf481155cf35e916f4234460bcb59ac3a7754f46a7a57ce66ac102e908608f` |
| `experiments/auth-authlib-oidc/requirements/py312-darwin-arm64-poc-dev.txt` | PASS | `0a4ed6b82afd24d1c62663908be46e913f6dfb3f2632a6bbca1bae043903ff80` |
| `experiments/auth-authlib-oidc/requirements/py312-linux-x86_64-poc-dev.txt` | PASS | `4646caa93d9fde9032ee046091fb2365b7dfdb0b79fb5dfdddf03e3a4bd84dde` |

## S04 LangGraph dependency extension

- Date: 2026-11-24.
- Candidate direct dependency: `langgraph==1.2.24`.
- Seven platform-specific hash-checked application locks extended.
- Prior baseline pins preserved.
- Seven resolver and seven hash-checked dry-run profiles: PASS.
- Seven candidate audits with pip-audit 2.10.1: PASS.
- Fresh macOS ARM64 install and pip check: PASS.
- Single-agent offline tests: 7 PASS.
- Existing backend regression: 124 PASS, 49 SKIP.
- Linux container runtime and GitHub CI: PENDING.
- Prior S02 historical evidence remains unchanged.
- Security audit scope is Python lockfile advisories only;
  it does not establish complete container or runtime security.
