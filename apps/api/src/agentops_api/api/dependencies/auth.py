"""Reusable authentication dependency for protected API routes."""

from fastapi import HTTPException, Request, status

from agentops_api.core.security_logging import log_failure


async def require_principal(request: Request) -> str:
    """Return the authenticated internal user ID or fail closed."""

    service = getattr(request.app.state, "auth_service", None)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication unavailable",
        )

    cookie_name = getattr(
        request.app.state,
        "auth_session_cookie_name",
        None,
    )

    if not cookie_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication unavailable",
        )

    token = request.cookies.get(cookie_name)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        principal = await service.principal(token)
    except Exception as exc:
        log_failure("auth.session.failure", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication unavailable",
        ) from None

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return principal["id"]