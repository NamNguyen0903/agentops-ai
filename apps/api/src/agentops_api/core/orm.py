
"""SQLAlchemy infrastructure for AgentOps AI.

No connections, tables, or migrations are created on import.
"""

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy import MetaData
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from agentops_api.core.config import Settings


APP_SCHEMA = "app"

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base for future approved application models."""

    metadata = MetaData(
        schema=APP_SCHEMA,
        naming_convention=NAMING_CONVENTION,
    )


def database_url(settings: Settings) -> URL:
    """Build a structured URL without manual password escaping."""

    if not settings.database_enabled:
        raise ValueError("Database is disabled")

    password = settings.database_password

    if password is None:
        raise ValueError("Database credentials are not configured")

    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.database_user,
        password=password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
    )


class OrmDatabase:
    """Application-owned async engine and session factory."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine | None = None
        self.session_factory: (
            async_sessionmaker[AsyncSession] | None
        ) = None

        if not settings.database_enabled:
            return

        self.engine = create_async_engine(
            database_url(settings),
            pool_size=2,
            max_overflow=0,
            pool_timeout=2,
            pool_recycle=300,
            pool_pre_ping=True,
            echo=False,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 2,
                "application_name": "agentops-api",
                "options": (
                    "-c statement_timeout=5000 "
                    "-c lock_timeout=2000 "
                    "-c idle_in_transaction_session_timeout=10000"
                ),
            },
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
            autobegin=False,
        )

    async def dispose(self) -> None:
        """Release pooled connections on application shutdown."""

        if self.engine is not None:
            await self.engine.dispose()


async def get_session(
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Provide one session, with no implicit commit.

    Future services explicitly open transactions:

        async with session.begin():
            ...

    Database/domain errors are not silently rewritten here.
    """

    database: OrmDatabase | None = getattr(
        request.app.state,
        "orm_database",
        None,
    )

    if database is None or database.session_factory is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": "Database access is unavailable.",
            },
        )

    async with database.session_factory() as session:
        yield session
