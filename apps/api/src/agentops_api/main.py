
from fastapi import APIRouter, FastAPI

from agentops_api.api.routes.health import router as health_router
from agentops_api.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application without external dependencies."""
    if settings is None:
        settings = Settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(health_router)
    application.include_router(api_router)

    return application


app = create_app()
