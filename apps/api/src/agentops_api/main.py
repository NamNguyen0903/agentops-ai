
from fastapi import APIRouter, FastAPI

from agentops_api.api.routes.health import (
    router as health_router,
)
from agentops_api.api.routes.readiness import (
    router as readiness_router,
)
from agentops_api.core.config import Settings
from agentops_api.core.database import DatabaseProbe


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API without network access."""
    if settings is None:
        settings = Settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    application.state.database_probe = DatabaseProbe(settings)

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(health_router)
    api_router.include_router(readiness_router)

    application.include_router(api_router)
    return application


app = create_app()
