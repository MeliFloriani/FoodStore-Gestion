"""
FastAPI exception handlers with RFC 7807 Problem Details responses.

Design decisions:
- D-08: All error responses use Content-Type: application/problem+json.
- D-08: validation_error_handler returns ONE response with errors: [...] extension,
  not one response per field (P-03).
- unhandled_error_handler logs full traceback but hides internal details from client.
- register_error_handlers() is the single call-site for wiring handlers to the app.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.schemas.base import ProblemDetail

_PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError and its subclasses with RFC 7807 responses."""
    problem = ProblemDetail(
        type="about:blank",
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
        code=exc.code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type=_PROBLEM_JSON_MEDIA_TYPE,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic RequestValidationError with a single RFC 7807 response.

    Decision D-08: returns ONE ProblemDetail with an errors=[...] extension
    containing all field errors. Does NOT return one response per error.
    """
    errors = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    problem = ProblemDetail(
        type="about:blank",
        title="Validation Error",
        status=422,
        detail="One or more fields failed validation",
        instance=str(request.url.path),
        errors=errors,
    )
    return JSONResponse(
        status_code=422,
        content=problem.model_dump(exclude_none=True),
        media_type=_PROBLEM_JSON_MEDIA_TYPE,
    )


async def unhandled_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Logs the full traceback (structured, with request_id) but returns a generic
    message to the client to avoid leaking internal implementation details.
    """
    logger = get_logger(__name__)
    logger.exception("unhandled_exception", exc_info=exc)
    problem = ProblemDetail(
        type="about:blank",
        title="Internal Server Error",
        status=500,
        detail="An unexpected error occurred",
        instance=str(request.url.path),
    )
    return JSONResponse(
        status_code=500,
        content=problem.model_dump(exclude_none=True),
        media_type=_PROBLEM_JSON_MEDIA_TYPE,
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Handle slowapi RateLimitExceeded with RFC 7807 response."""
    problem = ProblemDetail(
        type="about:blank",
        title="Too Many Requests",
        status=429,
        detail=str(exc.detail),
        instance=str(request.url.path),
    )
    return JSONResponse(
        status_code=429,
        content=problem.model_dump(exclude_none=True),
        media_type=_PROBLEM_JSON_MEDIA_TYPE,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application.

    Order matters: the catch-all Exception handler must be last.
    """
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type]
