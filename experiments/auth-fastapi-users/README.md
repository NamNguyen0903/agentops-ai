# FastAPI Users Compatibility PoC

**Ticket:** AG-003.1A

**Sprint:** S02

**Scope:** EXPERIMENT_ONLY

**Review state:** Tech Lead approved isolated execution (user instruction)

**Execution state:** VERIFIED for the narrow observations recorded below; security gaps remain

**ADR-0002:** PROPOSED — READY FOR DECISION

**Recommendation:** REJECT unmodified stock integration against the current proposal

## Purpose

Evaluate FastAPI Users 15.0.5 and SQLAlchemy adapter 7.0.0 without
implementing production authentication. Real library methods use isolated
storage boundaries. This does not approve identity schemas, migrations,
production authentication, or AG-003.4.

## Reinspection Baseline

The four experiment files were absent before this execution task. They are
new files. The user's latest instruction authorizes creation and execution
for this experiment despite the older manual-copy working agreement.

The backend retains async SQLAlchemy, Psycopg 3, `autobegin=False`,
application-owned transactions, and lifespan-managed engine disposal.
Alembic's versions directory contains only `.gitkeep`.
Historical backend results are not evidence that this experiment ran.

## Dependency Baseline

Python 3.12 is required. Use a dedicated virtual environment.

| Package | Pin | Basis |
|---|---|---|
| FastAPI Users | 15.0.5 | Tagged upstream APIs reviewed |
| SQLAlchemy adapter | 7.0.0 | Tagged upstream APIs reviewed |
| FastAPI | 0.165.0 | Inspected backend metadata |
| Starlette | 1.10.0 | Inspected backend metadata |
| Pydantic | 2.14.4 | Inspected backend metadata |
| SQLAlchemy | 2.0.58 | Inspected backend metadata |
| httpx | 0.28.1 | Inspected backend metadata |
| pytest | 9.2.0 | Inspected backend metadata |
| packaging | 26.3 | Inspected backend metadata |

FastAPI Users was not installed in the backend environment at inspection.
Pins do not prove resolver success. The build backend and transitive graph
are not fully locked; an inventory is not a hash-verified lockfile.
Preserve resolver errors rather than silently loosening pins or changing
production dependencies.

## Isolation

- No production application imports or environment-file reads.
- No PostgreSQL or SQLite connection, engine, SQL execution, DDL, migration,
  or `create_all`.
- Mapped classes exist only in isolated Python metadata.
- PostgreSQL-dialect metadata compilation does not execute SQL.
- Unbound sessions are used only for initialization and policy checks.
- Real adapter methods use mocked session I/O.
- Real DatabaseStrategy methods use memory storage.
- HTTP requests use in-process TestClient transport.
- Time and synthetic tokens are deterministic.
- Password authentication and hashing are not tested.

The fixture-cookie route bypasses credentials only for transport/dependency
tests. Never copy it into production.

Pre-collection Python guards block common socket, engine, and subprocess
entry points. These are guardrails, not an OS security sandbox against
malicious native code or arbitrary plugins. Disable pytest plugin autoload.
Installation may use the network; tests do not need it.

## Diagnostics and Confidentiality

Short tracebacks preserve file locations, exception types, and fixed
assertion messages. Local-variable dumps are disabled. Registered synthetic
token/password values and sensitive header representations are sanitized
in reports. Captured output is suppressed from failure reports.

Tests do not print bearer values, password values, request headers, SQL
parameters, or token-bearing mock calls. The sanitizer is scoped to the
known fixtures, not a general data-loss-prevention mechanism. Do not add
real credentials, unregistered secret fixtures, HTTP debug logging, or
external reporting plugins.

## Observation Boundaries

### Strategy and storage

Memory storage is a protocol fake. It does not establish PostgreSQL
persistence, constraints, isolation, concurrency, restart durability, or
revocation-race behavior. Fixed randomness does not assess entropy quality.

### ORM models and adapters

Mapped classes use actual library mixins. Tests resolve the token foreign
key and compile CreateTable objects without execution. Real create/update/
delete methods operate on session mocks. Call counts establish ownership
of commit calls, not commit success, rollback, isolation, or atomicity.
Production `autobegin=False` remains unchanged.

### Expiration

The real strategy computes a creation-time cutoff; the memory fake filters
against it. Separate adapter tests examine actual query construction.
Absolute-expiry tests use a 60-second fixture lifetime. The stock boundary
is inclusive; rejection occurs immediately afterward. Idle tests use the
proposed 12-hour absolute lifetime and more than 30 minutes of inactivity.

### Browser behavior

Cookie tests inspect actual Set-Cookie responses. TestClient does not prove
browser SameSite, CORS, TLS, or cookie-prefix enforcement. Foreign-Origin
POST acceptance demonstrates missing server-side protection in this
composition, not a complete browser exploit.

## Reporting Semantics

| Label | Meaning |
|---|---|
| PASS | Narrow observation succeeded |
| FAIL | Observed behavior violates the proposed contract |
| NOT_PROVIDED | Stock component lacks the control |
| BLOCKED | Unexpected failure prevents a reliable conclusion |
| UNVERIFIED | Required evidence is absent |

Reports show individual observations and AUTH-P01–AUTH-P10 aggregates.
Precedence: `FAIL > BLOCKED > UNVERIFIED > NOT_PROVIDED > PASS`.
Observed conclusions and evidence gaps also appear separately. Missing,
deselected, skipped, or interrupted cases cannot become PASS.

## Strict XFAIL

Only digest-at-rest uses `strict=True, raises=DigestAtRestViolation`.
The exception contains no token data. Other failures are unexpected;
unexpected compliance produces strict XPASS and requires review.
The expected violation aggregates to AUTH-P03 FAIL, including under
`--runxfail`. A green diagnostic run is not authentication acceptance.

## Dependency Assessment

AUTH-P10 separates imports/initialization, exact installed versions,
selected declared constraints, complete dependency consistency via a
separate `pip check`, maintenance-risk acceptance, and independent security
advisory review. Metadata never establishes absence of vulnerabilities.

FastAPI Users is in maintenance mode: security/dependency maintenance,
without new features promised. Acceptance requires an explicit decision.
The automated report leaves externally assessed items UNVERIFIED; record
their evidence separately instead of inferring it from pytest.

## Compatibility Matrix

Runtime conclusions require actual execution evidence.

| ID | Narrow observation | Source finding / limitation |
|---|---|---|
| AUTH-P01 | Imports, mapping and offline FK compilation | No database execution |
| AUTH-P02 | Strategy lifecycle with memory storage | No persistence claim |
| AUTH-P03 | Captured storage value versus issued token | Stock raw-token behavior FAIL |
| AUTH-P04 | Per-token deletion versus cookie clearing | Not account-wide revocation |
| AUTH-P05 | Absolute cutoff and separate idle observation | Idle expiry NOT_PROVIDED |
| AUTH-P06 | current_user(active=True) | Dependency behavior only |
| AUTH-P07 | Actual cookie attributes | No browser enforcement claim |
| AUTH-P08 | Foreign-Origin POST without CSRF proof | Protection NOT_PROVIDED |
| AUTH-P09 | Schema, queries, mutation ownership, autobegin | Stock integration FAIL |
| AUTH-P10 | Imports, versions, constraints, external reviews | Overall UNVERIFIED |

Stock user mappings combine email and password hash; the proposal splits
users, identities, credentials, and sessions. Tokens remain raw and stock
adapters commit internally. No custom replacement is implemented here.

## Static Test Inventory

19 functions expand to 31 cases: AUTH-P01 1; network guard 1; redaction 1;
aggregation 8; AUTH-P02 1; AUTH-P03 1; AUTH-P04 1; AUTH-P05 2; AUTH-P06 1;
AUTH-P07 1; AUTH-P08 1; AUTH-P09 10; AUTH-P10 2.
Expected, until executed: 30 passed and 1 xfailed, with security gaps retained.

## Execution Commands

From this directory:

```bash
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m pip check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest --collect-only -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -v
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest --runxfail -k p03 -v
```

The last command should fail for the known security violation. Preserve that
failure rather than weakening the contract. Backend regressions use the
existing backend environment, never this environment.

## Required Evidence

Record installation and resolver failures, Python/package versions,
`pip check`, collection count, pytest outcomes/exit codes, individual and
aggregate security reports, backend regressions, remaining architecture
decisions, and actual Git checkpoint. Never fabricate missing outcomes.

## Primary Sources

- [Strategy 15.0.5](https://raw.githubusercontent.com/fastapi-users/fastapi-users/v15.0.5/fastapi_users/authentication/strategy/db/strategy.py)
- [Cookie transport 15.0.5](https://raw.githubusercontent.com/fastapi-users/fastapi-users/v15.0.5/fastapi_users/authentication/transport/cookie.py)
- [Authenticator 15.0.5](https://raw.githubusercontent.com/fastapi-users/fastapi-users/v15.0.5/fastapi_users/authentication/authenticator.py)
- [Token adapter 7.0.0](https://raw.githubusercontent.com/fastapi-users/fastapi-users-db-sqlalchemy/v7.0.0/fastapi_users_db_sqlalchemy/access_token.py)
- [User adapter 7.0.0](https://raw.githubusercontent.com/fastapi-users/fastapi-users-db-sqlalchemy/v7.0.0/fastapi_users_db_sqlalchemy/__init__.py)
- [Maintenance policy](https://github.com/fastapi-users/fastapi-users)
- [pytest XFAIL semantics](https://docs.pytest.org/en/stable/how-to/skipping.html)

## Next Action

Tech Lead reviews the execution evidence below and resolves the stock
integration rejection/fallback decision. Remain on AG-003.1A; keep ADR-0002
PROPOSED and dependent authentication implementation blocked.

## Observed Execution Evidence

**Recorded:** 2026-11-22T01:44:59Z.

Evidence source: actual assistant tool execution authorized by the user's
latest instruction. No commits, pushes, application changes, schema changes,
or ADR approval were performed.

Repository checkpoint: `feat/ag-003-3-sqlalchemy-alembic`, HEAD
`cfab6154b10299c5f4640afea81e4b88cd452e90`. The pre-existing modified sprint
report and untracked ADR-0002 were preserved. The handoff/index still record
the older AG-003.3A resume point; they were not edited in this experiment.

### Commands and results

Commands in this table ran from the experiment directory unless indicated.

| Actual command | Exit | Observed output/result |
|---|---:|---|
| `python3.12 --version` (repository root) | 0 | Python 3.12.9 |
| `python3.12 -m venv .venv && .venv/bin/python -m pip install .` | 1 | Venv created; build dependency installation failed on package-index DNS access; `setuptools>=68` could not be resolved in the restricted environment |
| `.venv/bin/python -m pip install .` (network-enabled retry) | 0 | Successfully built and installed agentops-auth-fastapi-users-poc 0.1.0 and its pinned dependencies |
| `.venv/bin/python -m pip check` | 0 | No broken requirements found. |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest --collect-only -q` | 0 | 31 tests collected in 1.08s |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -v` | 0 | 30 passed, 1 xfailed, 1 warning in 0.39s |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest --runxfail -k p03 -v` | 1 | 1 failed, 30 deselected, 1 warning in 0.29s; DigestAtRestViolation, as intended |
| `.venv/bin/python --version` (backend directory) | 0 | Python 3.12.2 |
| `.venv/bin/python -m pip check` (backend directory) | 0 | No broken requirements found. |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` (backend directory) | 0 | 31 passed, 1 warning in 6.66s |
| `git diff --check` (repository root) | 0 | No output |
| `git diff -- apps/api compose.yaml docker/postgres` (repository root) | 0 | No output |
| `git diff --cached --stat` (repository root) | 0 | No output |
| `git check-ignore experiments/auth-fastapi-users/.venv/pyvenv.cfg` (repository root) | 0 | Virtual environment is ignored |

The initial inventory command exited 2 because the experiment directory
did not exist; its preceding Git inspection succeeded. Installation's
restricted-network failure was resolved without changing any dependency
pin. No unexpected test failures occurred and no corrective test changes
were required. Files retain the approved behavior with condensed formatting.

A final no-index whitespace check initially reported Markdown hard-break
spaces in this README (exit 3). They were replaced with blank lines. Each
new file then produced no diagnostics and Git exit 1 (normal no-index
differences from /dev/null); the verification wrapper exited 0. No
executable code changed after the test runs.

The warning in both environments is StarletteDeprecationWarning: httpx
TestClient support is deprecated in favor of httpx2. No production dependency
was changed in response. Pip also warned that its cache was unavailable in
the restricted environment; dependency checks still returned zero.

### Full-run aggregate security report

```text
AUTH-P01: PASS; observed=PASS; evidence_gaps=none
AUTH-P02: PASS; observed=PASS; evidence_gaps=none
AUTH-P03: FAIL; observed=FAIL; evidence_gaps=none
AUTH-P04: PASS; observed=PASS; evidence_gaps=none
AUTH-P05: NOT_PROVIDED; observed=NOT_PROVIDED,PASS; evidence_gaps=none
AUTH-P06: PASS; observed=PASS; evidence_gaps=none
AUTH-P07: PASS; observed=PASS; evidence_gaps=none
AUTH-P08: NOT_PROVIDED; observed=NOT_PROVIDED; evidence_gaps=none
AUTH-P09: FAIL; observed=FAIL,PASS; evidence_gaps=none
AUTH-P10: UNVERIFIED; observed=PASS; evidence_gaps=UNVERIFIED
```

The standalone pip check is now separately verified. The automated report
does not ingest that external output and conservatively retains its note.
Maintenance-risk acceptance and advisory review remain UNVERIFIED, so
AUTH-P10's aggregate does not change. The filtered p03 run correctly marks
other unexecuted requirements UNVERIFIED and p03 FAIL; it does not supersede
the full-run evidence.

### Installed version inventory

Observed using Python importlib.metadata, without dumping environment values:

```text
Python: 3.12.9
agentops-auth-fastapi-users-poc==0.1.0
annotated-doc==0.0.7
annotated-types==0.8.0
anyio==4.16.0
argon2-cffi==25.1.0
argon2-cffi-bindings==26.2.0
bcrypt==5.0.0
certifi==2026.11.20
cffi==2.1.1
cryptography==50.0.2
dnspython==2.9.2
email-validator==2.3.0
fastapi==0.165.0
fastapi-users==15.0.5
fastapi-users-db-sqlalchemy==7.0.0
greenlet==3.5.6
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
iniconfig==2.3.1
makefun==1.16.0
opentelemetry-api==1.45.2
packaging==26.3
pip==25.0
pluggy==1.7.0
pwdlib==0.3.0
pycparser==3.12
pydantic==2.14.4
pydantic_core==2.50.5
Pygments==2.21.0
PyJWT==2.15.1
pytest==9.2.0
python-multipart==0.0.34
SQLAlchemy==2.0.58
starlette==1.10.0
typing-inspection==0.4.5
typing_extensions==4.16.0
```

### Remaining blockers

- Raw-token storage and stock schema/transaction mismatches remain FAIL.
- Idle expiry and CSRF/Origin protection remain NOT_PROVIDED.
- Maintenance acceptance and independent advisory review remain pending.
- Mocks and TestClient do not establish production database/browser security.
- ADR-0002 remains PROPOSED. No subsequent ticket is started.
