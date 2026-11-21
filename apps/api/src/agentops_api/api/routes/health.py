from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["agentops-api"] = "agentops-api"


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Report process liveness without checking external dependencies."""
    return HealthResponse()