
"""AgentOps AI FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from agentops_api.api.routes.health import (
    router as health_router,
)
from agentops_api.api.routes.readiness import (
    router as readiness_router,
)
from agentops_api.core.config import Settings
from agentops_api.core.database import DatabaseProbe
from agentops_api.core.orm import OrmDatabase
from agentops_api.core.security_logging import (
    acquire_logging_protection,
    release_logging_protection,
)

def create_app(settings: Settings | None = None, *, auth_settings=None, auth_provider=None) -> FastAPI:
    """Construct the application without database network I/O."""

    if settings is None:
        settings = Settings()

    if settings.auth_review_enabled:
        from agentops_api.core.auth_config import AuthSettings
        from agentops_api.services.auth import AuthService, ContextCipher
        from agentops_api.services.google_oidc import GoogleOIDC
        from agentops_api.api.routes.auth import make_router
        auth_settings = auth_settings or AuthSettings()
        auth_provider = auth_provider or GoogleOIDC(auth_settings)
        if not settings.database_enabled:
            raise ValueError("Review authentication requires database configuration")

    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ) -> AsyncIterator[None]:
        database = OrmDatabase(settings)
        application.state.orm_database = database

        previous_formatters = []
        pkce_logger = None
        pkce_filter = None
        logging_acquired = False

        try:
            if settings.auth_review_enabled:
                acquire_logging_protection()
                logging_acquired = True

                application.state.auth_service = AuthService(
                    database.session_factory,
                    ContextCipher(
                        auth_settings.context_key.get_secret_value()
                    ),
                )
                application.state.auth_session_cookie_name = (
                    auth_settings.session_cookie
                )

            yield
        finally:
            try:
                await database.dispose()
            finally:
                if logging_acquired:
                    release_logging_protection()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Existing AG-003.2 readiness infrastructure.
    application.state.database_probe = DatabaseProbe(
        settings
    )

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(health_router)
    api_router.include_router(readiness_router)

    if settings.auth_review_enabled:
        api_router.include_router(make_router(auth_settings, auth_provider))

    application.include_router(api_router)

    return application


app = create_app()
