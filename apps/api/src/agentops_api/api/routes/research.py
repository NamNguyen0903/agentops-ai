"""Authenticated research task endpoints; no AI execution in S03."""

import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from agentops_api.core.config import Settings
from agentops_api.core.security_logging import log_failure
from agentops_api.repositories.research import (
    IdempotencyConflict,
    ResearchSubmission,
)
from agentops_api.schemas.research import (
    CreateResearchRequest,
    ResearchAcceptedResponse,
    ResearchHistoryResponse,
    ResearchTaskResponse,
)
from agentops_api.services.research import (
    QueueFull,
    QueueUnavailable,
    admit_task,
    detail,
    history,
)


ERRORS = {
    401: ("authentication_required", "Authentication required."),
    403: ("request_forbidden", "Request authorization failed."),
    404: ("task_not_found", "Research task not found."),
    409: ("idempotency_conflict", "Idempotency key is unavailable."),
    422: ("invalid_request", "Invalid research request."),
    429: ("queue_full", "Research queue is full. Try again later."),
    503: ("service_unavailable", "Research service is unavailable."),
    500: ("internal_error", "An unexpected error occurred."),
}


class ResearchRoute(APIRoute):
    """Route-scoped safe errors; do not change existing auth contracts."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request: Request):
            request_id = str(uuid4())
            fields = []

            try:
                response = await handler(request)
            except (RequestValidationError, ValidationError) as exc:
                status = 422

                allowed_fields = {
                    "question", "scope", "geography",
                    "competitors", "category", "time_scope",
                    "limit", "cursor", "task_id",
                    "idempotency-key",
                }

                for error in exc.errors():
                    safe = [
                        part for part in error.get("loc", ())
                        if isinstance(part, str) and part in allowed_fields
                    ]
                    fields.append({
                        "field": ".".join(safe) or "request",
                        "code": "invalid_value",
                    })

                fields = fields[:16]
            except HTTPException as exc:
                status = exc.status_code
            except IdempotencyConflict:
                status = 409
            except QueueFull:
                status = 429
            except QueueUnavailable:
                status = 503
            except SQLAlchemyError as exc:
                log_failure("research.database.failure", exc)
                status = 503
            except Exception as exc:
                log_failure("research.request.failure", exc)
                status = 500
            else:
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Request-ID"] = request_id
                return response

            if status not in ERRORS:
                status = 500

            code, message = ERRORS[status]
            payload = {
                "code": code,
                "message": message,
                "request_id": request_id,
            }

            if status == 422 and fields:
                payload["fields"] = fields

            headers = {
                "Cache-Control": "no-store",
                "X-Request-ID": request_id,
            }
            if status == 429:
                headers["Retry-After"] = "60"

            return JSONResponse(
                payload,
                status_code=status,
                headers=headers,
            )

        return guarded


def encode_cursor(task) -> str:
    value = json.dumps([
        task.created_at.isoformat(),
        str(task.id),
    ]).encode("utf-8")

    return base64.urlsafe_b64encode(value).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        value = json.loads(base64.b64decode(
            cursor.encode("ascii"),
            altchars=b"-_",
            validate=True,
        ))

        if not isinstance(value, list) or len(value) != 2:
            raise ValueError

        timestamp = datetime.fromisoformat(value[0])
        if timestamp.tzinfo is None:
            raise ValueError

        return timestamp.astimezone(timezone.utc), UUID(value[1])
    except (
        ValueError, TypeError, AttributeError,
        UnicodeError, binascii.Error, OverflowError,
    ):
        raise HTTPException(422) from None


def make_research_router(settings: Settings, auth_settings=None):
    router = APIRouter(
        prefix="/research/tasks",
        tags=["research"],
        route_class=ResearchRoute,
    )

    limits = {
        "question_limit": settings.research_question_limit,
        "scope_limit": settings.research_scope_limit,
    }

    def resources(request: Request):
        auth = getattr(request.app.state, "auth_service", None)
        db = getattr(request.app.state, "orm_database", None)

        if not settings.auth_review_enabled or auth_settings is None:
            raise HTTPException(503)

        if auth is None or db is None or db.session_factory is None:
            raise HTTPException(503)

        token = request.cookies.get(auth_settings.session_cookie)
        if not token or len(token) > 256:
            raise HTTPException(401)

        return auth, db.session_factory, token

    async def authenticate(
        auth, session, token, request: Request, *, mutation=False,
    ) -> UUID:
        csrf = None

        if mutation:
            if request.headers.getlist("origin") != [auth_settings.origin]:
                raise HTTPException(403)

            proofs = request.headers.getlist("x-csrf-token")
            if len(proofs) != 1 or not proofs[0] or len(proofs[0]) > 256:
                raise HTTPException(403)

            csrf = proofs[0]

        try:
            principal = await auth.principal_in_transaction(
                session,
                token,
                csrf=csrf,
                require_csrf=mutation,
            )
        except ValueError:
            raise HTTPException(403) from None

        if principal is None:
            raise HTTPException(401)

        return UUID(principal["id"])

    @router.post(
        "",
        status_code=202,
        response_model=ResearchAcceptedResponse,
    )
    async def create_task(
        request: Request,
        body: CreateResearchRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
        ),
    ):
        auth, factory, token = resources(request)

        if (
            len(request.headers.getlist("idempotency-key")) != 1
            or not idempotency_key.strip()
            or "\x00" in idempotency_key
        ):
            raise HTTPException(422)

        submission = ResearchSubmission.model_validate(
            body.model_dump(),
            context=limits,
        )

        async with factory() as session, session.begin():
            owner = await authenticate(
                auth, session, token, request, mutation=True,
            )

            result = await admit_task(
                session,
                owner_id=owner,
                idempotency_key=idempotency_key,
                submission=submission,
                capacity=settings.research_queue_capacity,
                validation_limits=limits,
            )

            response = ResearchAcceptedResponse(
                task_id=result.task.id,
                status=result.task.status,
                status_url=(
                    f"/api/v1/research/tasks/{result.task.id}"
                ),
            )

        # session.begin() has successfully committed here.
        return response

    @router.get("", response_model=ResearchHistoryResponse)
    async def task_history(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=256),
    ):
        auth, factory, token = resources(request)

        before = decode_cursor(cursor) if cursor is not None else None

        async with factory() as session, session.begin():
            owner = await authenticate(
                auth, session, token, request,
            )

            # Count one extra item while preserving repository limit <= 100.
            tasks = await history(
                session,
                owner_id=owner,
                limit=min(limit + 1, 100),
                before=before,
            )

            has_more = len(tasks) > limit
            if limit == 100 and len(tasks) == 100:
                extra = await history(
                    session,
                    owner_id=owner,
                    limit=1,
                    before=(tasks[-1].created_at, tasks[-1].id),
                )
                has_more = bool(extra)

            page = tasks[:limit]

            response = ResearchHistoryResponse(
                items=[
                    ResearchTaskResponse.model_validate(task)
                    for task in page
                ],
                next_cursor=(
                    encode_cursor(page[-1])
                    if has_more and page else None
                ),
            )

        return response

    @router.get("/{task_id}", response_model=ResearchTaskResponse)
    async def task_detail(request: Request, task_id: UUID):
        auth, factory, token = resources(request)

        async with factory() as session, session.begin():
            owner = await authenticate(
                auth, session, token, request,
            )
            task = await detail(
                session,
                owner_id=owner,
                task_id=task_id,
            )
            if task is None:
                raise HTTPException(404)

            response = ResearchTaskResponse.model_validate(task)

        return response

    return router
