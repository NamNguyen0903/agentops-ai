
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from agentops_api.core.database import DatabaseProbe

router = APIRouter(tags=["health"])


def get_database_probe(request: Request) -> DatabaseProbe:
    return request.app.state.database_probe


@router.get("/ready")
async def get_readiness(
    probe: Annotated[
        DatabaseProbe,
        Depends(get_database_probe),
    ],
) -> JSONResponse:
    """Check PostgreSQL connectivity."""
    request_id = str(uuid4())

    headers = {
        "Cache-Control": "no-store",
        "X-Request-ID": request_id,
    }

    if await probe.is_ready():
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "checks": {"database": "ok"},
            },
            headers=headers,
        )

    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "checks": {"database": "unavailable"},
            "error": {
                "code": "database_not_ready",
                "message": "Database readiness check failed.",
                "request_id": request_id,
            },
        },
        headers=headers,
    )
