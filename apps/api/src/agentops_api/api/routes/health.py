
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Dependency-independent liveness check."""
    return {
        "status": "ok",
        "service": "agentops-api",
    }
