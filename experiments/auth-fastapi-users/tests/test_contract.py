"""AG-003.1A: isolated library observations, not production authentication."""

import asyncio
import socket
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from importlib.metadata import metadata, version
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import AccessTokenDatabase, DatabaseStrategy
from fastapi_users.authentication.strategy.db import strategy as strategy_module
from fastapi_users.db import BaseUserDatabase
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
    SQLAlchemyBaseAccessTokenTableUUID,
)
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ArgumentError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, configure_mappers
from sqlalchemy.schema import CreateTable

INITIAL_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
USER_ID = UUID("00000000-0000-0000-0000-000000000001")
COOKIE_NAME = "__Host-agentops-poc"
EXPECTED_VERSIONS = {
    "fastapi-users": "15.0.5",
    "fastapi-users-db-sqlalchemy": "7.0.0",
    "fastapi": "0.165.0",
    "starlette": "1.10.0",
    "pydantic": "2.14.4",
    "SQLAlchemy": "2.0.58",
    "httpx": "0.28.1",
    "pytest": "9.2.0",
    "packaging": "26.3",
}


def require(condition: bool, message: str) -> None:
    """Use fixed diagnostics instead of rendering sensitive operands."""
    if not condition:
        raise AssertionError(message)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


@dataclass(repr=False)
class Clock:
    now: datetime = INITIAL_TIME

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass(repr=False)
class MemoryUser:
    id: UUID = USER_ID
    email: str = "fixture@example.invalid"
    hashed_password: str = field(default="unused-test-value", repr=False)
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False


@dataclass(repr=False)
class MemoryToken:
    token: str
    user_id: UUID
    created_at: datetime


class MemoryUsers(BaseUserDatabase[MemoryUser, UUID]):
    """Implements only the lookup exercised by this experiment."""
    def __init__(self, user: MemoryUser) -> None:
        self.user = user

    async def get(self, id: UUID) -> MemoryUser | None:
        return self.user if id == self.user.id else None


class MemoryTokens(AccessTokenDatabase[MemoryToken]):
    """Protocol storage fake; not a database or persistence simulation."""
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.rows: dict[str, MemoryToken] = {}
        self.created_values: list[dict[str, Any]] = []
        self.cutoffs: list[datetime | None] = []
        self.update_count = 0

    async def get_by_token(self, token: str, max_age: datetime | None = None) -> MemoryToken | None:
        self.cutoffs.append(max_age)
        record = self.rows.get(token)
        if record is None:
            return None
        if max_age is not None and record.created_at < max_age:
            return None
        return record

    async def create(self, create_dict: dict[str, Any]) -> MemoryToken:
        self.created_values.append(dict(create_dict))
        record = MemoryToken(
            token=create_dict["token"], user_id=create_dict["user_id"], created_at=self.clock.now,
        )
        self.rows[record.token] = record
        return record

    async def update(self, access_token: MemoryToken, update_dict: dict[str, Any]) -> MemoryToken:
        self.update_count += 1
        for name, value in update_dict.items():
            setattr(access_token, name, value)
        return access_token

    async def delete(self, access_token: MemoryToken) -> None:
        self.rows.pop(access_token.token, None)


class UserManager(UUIDIDMixin, BaseUserManager[MemoryUser, UUID]):
    pass


@dataclass(repr=False)
class Harness:
    clock: Clock
    user: MemoryUser
    store: MemoryTokens
    manager: UserManager
    strategy: DatabaseStrategy


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    clock = Clock()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return clock.now.replace(tzinfo=None)
            return clock.now.astimezone(tz)

    generated = iter(character * 43 for character in "ABC")
    monkeypatch.setattr(strategy_module, "datetime", FrozenDateTime)
    monkeypatch.setattr(strategy_module.secrets, "token_urlsafe", lambda *args, **kwargs: next(generated))
    user = MemoryUser()
    store = MemoryTokens(clock)
    manager = UserManager(MemoryUsers(user))
    strategy = DatabaseStrategy(store, lifetime_seconds=60)
    return Harness(clock, user, store, manager, strategy)


class ExperimentBase(DeclarativeBase):
    """Isolated Python metadata; never bound to an engine."""


class MappedUser(SQLAlchemyBaseUserTableUUID, ExperimentBase):
    pass


class MappedToken(SQLAlchemyBaseAccessTokenTableUUID, ExperimentBase):
    pass


def session_double() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


def make_app(h: Harness) -> FastAPI:
    """In-process fixture app; never imported by production."""
    transport = CookieTransport(
        cookie_name=COOKIE_NAME, cookie_secure=True, cookie_httponly=True,
        cookie_samesite="lax", cookie_path="/", cookie_domain=None,
    )

    async def get_manager():
        yield h.manager

    def get_strategy():
        return h.strategy

    backend = AuthenticationBackend(name="experiment", transport=transport, get_strategy=get_strategy)
    users = FastAPIUsers[MemoryUser, UUID](get_manager, [backend])
    active_user = users.current_user(active=True)
    app = FastAPI()

    @app.post("/fixture-cookie")
    async def fixture_cookie() -> Response:
        token = await h.strategy.write_token(h.user)
        return await transport.get_login_response(token)

    @app.post("/clear-cookie")
    async def clear_cookie() -> Response:
        return await transport.get_logout_response()

    @app.get("/probe")
    async def probe(user=Depends(active_user)) -> dict[str, bool]:
        return {"authenticated": True}

    @app.post("/probe")
    async def mutation_probe(user=Depends(active_user)) -> dict[str, bool]:
        return {"authenticated": True}

    return app


@pytest.mark.contract("p01")
def test_p01_imports_initialization_and_metadata() -> None:
    require(sys.version_info[:2] == (3, 12), "Python 3.12 is required")
    configure_mappers()
    require(inspect(MappedUser).is_mapper, "User mapping failed")
    require(inspect(MappedToken).is_mapper, "Token mapping failed")
    foreign_keys = tuple(MappedToken.__table__.foreign_keys)
    require(len(foreign_keys) == 1, "Unexpected token foreign-key count")
    require(foreign_keys[0].column is MappedUser.__table__.c.id, "Token foreign key does not resolve to the mapped user")
    dialect = postgresql.dialect()
    for table in ExperimentBase.metadata.sorted_tables:
        compiled = str(CreateTable(table).compile(dialect=dialect))
        require(bool(compiled.strip()), "Offline metadata compilation failed")

    async def scenario() -> None:
        async with AsyncSession(autobegin=False) as session:
            users = SQLAlchemyUserDatabase(session, MappedUser)
            tokens = SQLAlchemyAccessTokenDatabase(session, MappedToken)
            require(users.session is session, "User adapter initialization failed")
            require(tokens.session is session, "Token adapter initialization failed")

    run(scenario())


def test_network_guard() -> None:
    with pytest.raises(RuntimeError, match="External I/O is forbidden"):
        socket.create_connection(("example.invalid", 443))


def test_diagnostic_redaction(reporting_tools: dict[str, Any]) -> None:
    token = "A" * 43
    message = (
        f"RuntimeError: marker {token}\n"
        f"Authorization: Bearer {token}\n"
        f"Set-Cookie: fixture={token}\n"
        "password=unused-test-value\n"
    )
    cleaned = reporting_tools["redact"](message)
    require(token not in cleaned, "Fixture token escaped redaction")
    require("unused-test-value" not in cleaned, "Password fixture escaped redaction")
    require("RuntimeError" in cleaned, "Exception type was lost")
    require("marker" in cleaned, "Non-sensitive diagnostic context was lost")


@pytest.mark.parametrize("states,expected", [
    ([], "UNVERIFIED"), (["PASS"], "PASS"),
    (["PASS", "NOT_PROVIDED"], "NOT_PROVIDED"), (["PASS", "FAIL"], "FAIL"),
    (["NOT_PROVIDED", "FAIL"], "FAIL"), (["PASS", "BLOCKED"], "BLOCKED"),
    (["PASS", "UNVERIFIED"], "UNVERIFIED"), (["FAIL", "BLOCKED"], "FAIL"),
])
def test_requirement_aggregation(reporting_tools: dict[str, Any], states: list[str], expected: str) -> None:
    require(reporting_tools["aggregate"](states) == expected, "Requirement aggregation precedence is incorrect")


@pytest.mark.contract("p02")
def test_p02_strategy_lifecycle(harness: Harness) -> None:
    async def scenario() -> None:
        h = harness
        token = await h.strategy.write_token(h.user)
        require(len(h.store.created_values) == 1, "Storage create not observed")
        require(set(h.store.created_values[0]) == {"token", "user_id"}, "Unexpected storage payload shape")
        require(h.store.created_values[0]["user_id"] == h.user.id, "Storage owner mismatch")
        require(await h.strategy.read_token(token, h.manager) is h.user, "Issued token did not resolve")
        require(await h.strategy.read_token(None, h.manager) is None, "Missing token was accepted")
        require(await h.strategy.read_token("invalid", h.manager) is None, "Unknown token was accepted")
        await h.strategy.destroy_token(token, h.user)
        require(await h.strategy.read_token(token, h.manager) is None, "Revoked token still resolved")
    run(scenario())


class DigestAtRestViolation(Exception):
    """Known security-contract violation with no sensitive details."""


@pytest.mark.contract("p03")
@pytest.mark.xfail(strict=True, raises=DigestAtRestViolation, reason="AUTH-P03 FAIL: stock storage retains the bearer token")
def test_p03_digest_at_rest_contract(harness: Harness) -> None:
    async def scenario() -> None:
        h = harness
        token = await h.strategy.write_token(h.user)
        require(len(h.store.created_values) == 1, "Storage observation missing")
        stored = h.store.created_values[0]
        require("token" in stored, "Storage contract unexpectedly changed")
        if stored["token"] == token:
            raise DigestAtRestViolation("AUTH-P03 FAIL: reusable bearer token retained at storage boundary")
    run(scenario())


@pytest.mark.contract("p04")
def test_p04_revocation_and_cookie_deletion(harness: Harness) -> None:
    h = harness
    first = run(h.strategy.write_token(h.user))
    second = run(h.strategy.write_token(h.user))
    with TestClient(make_app(h), base_url="https://poc.invalid") as client:
        client.cookies.set(COOKIE_NAME, first)
        require(client.get("/probe").status_code == 200, "Initial access failed")
        response = client.post("/clear-cookie")
        require(response.status_code == 204, "Cookie clearing failed")
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        require(cookie[COOKIE_NAME]["max-age"] == "0", "Cookie not expired")
    require(run(h.strategy.read_token(first, h.manager)) is h.user, "Cookie-only operation unexpectedly revoked storage")
    run(h.strategy.destroy_token(first, h.user))
    run(h.strategy.destroy_token(first, h.user))
    require(run(h.strategy.read_token(first, h.manager)) is None, "First token remained usable")
    require(run(h.strategy.read_token(second, h.manager)) is h.user, "Per-token deletion affected another token")


@pytest.mark.contract("p05_absolute")
def test_p05_absolute_expiry(harness: Harness) -> None:
    async def scenario() -> None:
        h = harness
        token = await h.strategy.write_token(h.user)
        h.clock.advance(30)
        require(await h.strategy.read_token(token, h.manager) is h.user, "Token expired early")
        require(h.store.cutoffs[-1] == h.clock.now - timedelta(seconds=60), "Strategy supplied an incorrect cutoff")
        h.clock.advance(30)
        require(await h.strategy.read_token(token, h.manager) is h.user, "Inclusive creation-time boundary changed")
        h.clock.advance(0.001)
        require(await h.strategy.read_token(token, h.manager) is None, "Expired token remained usable")
        require(h.store.rows[token].created_at == INITIAL_TIME, "Activity changed creation time")
        require(h.store.update_count == 0, "Unexpected storage update")
    run(scenario())


@pytest.mark.contract("p05_idle")
def test_p05_idle_expiry_not_provided(harness: Harness) -> None:
    async def scenario() -> None:
        h = harness
        h.strategy.lifetime_seconds = 12 * 60 * 60
        token = await h.strategy.write_token(h.user)
        h.clock.advance(30 * 60 + 1)
        require(await h.strategy.read_token(token, h.manager) is h.user, "Idle behavior changed; review the conclusion")
        require(h.store.update_count == 0, "Unexpected idle-state update")
    run(scenario())


@pytest.mark.contract("p06")
def test_p06_disabled_user_rejection(harness: Harness) -> None:
    with TestClient(make_app(harness), base_url="https://poc.invalid") as client:
        require(client.get("/probe").status_code == 401, "Anonymous access allowed")
        require(client.post("/fixture-cookie").status_code == 204, "Fixture cookie issuance failed")
        require(client.get("/probe").status_code == 200, "Active user rejected")
        harness.user.is_active = False
        require(client.get("/probe").status_code == 401, "Disabled user accepted")


@pytest.mark.contract("p07")
def test_p07_cookie_headers(harness: Harness) -> None:
    with TestClient(make_app(harness), base_url="https://poc.invalid") as client:
        response = client.post("/fixture-cookie")
        require(response.status_code == 204, "Fixture cookie issuance failed")
        headers = response.headers.get_list("set-cookie")
        require(len(headers) == 1, "Unexpected cookie count")
        parsed = SimpleCookie()
        parsed.load(headers[0])
        require(COOKIE_NAME in parsed, "Expected cookie missing")
        cookie = parsed[COOKIE_NAME]
        require(bool(cookie["httponly"]), "HttpOnly missing")
        require(bool(cookie["secure"]), "Secure missing")
        require(cookie["samesite"].lower() == "lax", "SameSite is not Lax")
        require(cookie["path"] == "/", "Cookie path is not root")
        require(cookie["domain"] == "", "Cookie unexpectedly sets Domain")


@pytest.mark.contract("p08")
def test_p08_origin_and_csrf_not_provided(harness: Harness) -> None:
    with TestClient(make_app(harness), base_url="https://poc.invalid") as client:
        require(client.post("/fixture-cookie").status_code == 204, "Fixture cookie issuance failed")
        response = client.post("/probe", headers={"Origin": "https://foreign.invalid"})
        require(response.status_code == 200, "Origin behavior changed; review the conclusion")


@pytest.mark.contract("p09_schema")
def test_p09_stock_schema_shape() -> None:
    user_columns = set(MappedUser.__table__.columns.keys())
    token_columns = set(MappedToken.__table__.columns.keys())
    require({"email", "hashed_password"} <= user_columns, "Combined credential mapping changed")
    require("token" in token_columns, "Stock token column changed")
    require("token_digest" not in token_columns, "Digest column now exists")
    require("idle_expires_at" not in token_columns, "Idle column now exists")
    require(any(fk.target_fullname == "user.id" for fk in MappedToken.__table__.foreign_keys), "Stock user foreign key changed")


@pytest.mark.contract("p09_queries")
def test_p09_mapped_adapter_queries() -> None:
    async def scenario() -> None:
        session = session_double()
        token = MappedToken(token="A" * 43, user_id=USER_ID, created_at=INITIAL_TIME)
        result = MagicMock()
        result.scalar_one_or_none.return_value = token
        session.execute.return_value = result
        adapter = SQLAlchemyAccessTokenDatabase(session, MappedToken)
        require(await adapter.get_by_token(token.token, INITIAL_TIME) is token, "Token adapter result mismatch")
        statement = session.execute.call_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        require(token.token in compiled.params.values(), "Token equality parameter missing")
        require(INITIAL_TIME in compiled.params.values(), "Creation-time cutoff parameter missing")
        require("created_at >=" in str(compiled), "Inclusive creation-time predicate missing")
        user = MappedUser(id=USER_ID)
        result.unique.return_value.scalar_one_or_none.return_value = user
        users = SQLAlchemyUserDatabase(session, MappedUser)
        require(await users.get(USER_ID) is user, "User adapter result mismatch")
    run(scenario())


@pytest.mark.parametrize("kind", ["user", "token"])
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.contract("p09_mutations")
def test_p09_mutation_commit_ownership(kind: str, operation: str) -> None:
    async def scenario() -> None:
        session = session_double()
        if kind == "user":
            adapter = SQLAlchemyUserDatabase(session, MappedUser)
            values = {"id": USER_ID, "email": "fixture@example.invalid", "hashed_password": "unused-test-value", "is_active": True}
            record = MappedUser(**values)
            changes = {"is_active": False}
        else:
            adapter = SQLAlchemyAccessTokenDatabase(session, MappedToken)
            values = {"token": "A" * 43, "user_id": USER_ID, "created_at": INITIAL_TIME}
            record = MappedToken(**values)
            changes = {"created_at": INITIAL_TIME + timedelta(seconds=1)}
        if operation == "create":
            created = await adapter.create(values)
            require(isinstance(created, type(record)), "Unexpected adapter model type")
            if kind == "token":
                require(created.token == values["token"], "Token storage behavior changed")
        elif operation == "update":
            await adapter.update(record, changes)
            require(all(getattr(record, name) == value for name, value in changes.items()), "Adapter did not apply the requested field changes")
        else:
            await adapter.delete(record)
        require(session.commit.await_count == 1, "Commit ownership changed")
        if operation == "delete":
            require(session.delete.await_count == 1, "Delete not awaited")
            require(session.refresh.await_count == 0, "Unexpected delete refresh")
        else:
            require(session.add.call_count == 1, "Model not added")
            require(session.refresh.await_count == 1, "Refresh not awaited")
    run(scenario())


@pytest.mark.contract("p09_autobegin")
def test_p09_autobegin_false_rejects_unscoped_create() -> None:
    async def scenario() -> None:
        async with AsyncSession(autobegin=False) as session:
            adapter = SQLAlchemyAccessTokenDatabase(session, MappedToken)
            with pytest.raises(InvalidRequestError, match="Autobegin is disabled"):
                await adapter.create({"token": "A" * 43, "user_id": USER_ID, "created_at": INITIAL_TIME})
    run(scenario())


@pytest.mark.contract("p09_dataclass")
def test_p09_dataclass_is_not_an_orm_model() -> None:
    async def scenario() -> None:
        adapter = SQLAlchemyAccessTokenDatabase(session_double(), MemoryToken)
        with pytest.raises(ArgumentError):
            await adapter.get_by_token("A" * 43)
    run(scenario())


@pytest.mark.contract("p10_versions")
def test_p10_installed_versions() -> None:
    for name, expected in EXPECTED_VERSIONS.items():
        require(version(name) == expected, f"Version mismatch: {name}")


@pytest.mark.contract("p10_constraints")
def test_p10_selected_declared_constraints() -> None:
    manifest = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with manifest.open("rb") as stream:
        configuration = tomllib.load(stream)
    python_version = ".".join(str(value) for value in sys.version_info[:3])
    require(SpecifierSet(configuration["project"]["requires-python"]).contains(python_version), "Experiment Python constraint is not satisfied")
    for text in configuration["project"]["dependencies"]:
        requirement = Requirement(text)
        require(requirement.specifier.contains(version(requirement.name)), f"Experiment dependency mismatch: {requirement.name}")
    for name in ("fastapi-users", "fastapi-users-db-sqlalchemy"):
        package_metadata = metadata(name)
        requires_python = package_metadata.get("Requires-Python")
        require(bool(requires_python), f"Python constraint missing: {name}")
        require(SpecifierSet(requires_python).contains(python_version), f"Unsupported Python metadata: {name}")
        requirements = package_metadata.get_all("Requires-Dist") or []
        require(bool(requirements), f"Dependency metadata missing: {name}")
        for text in requirements:
            requirement = Requirement(text)
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            require(requirement.specifier.contains(version(requirement.name)), f"Selected dependency constraint mismatch: {requirement.name}")
