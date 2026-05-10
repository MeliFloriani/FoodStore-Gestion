"""
Domain exception hierarchy.

All application-level errors inherit from AppError, which carries enough
information for the error handler (app/api/errors.py) to build a valid
RFC 7807 ProblemDetail response without needing to catch multiple types.

Note: AppValidationError is prefixed with App* to avoid name collision with
pydantic.ValidationError, which is a different concept (schema validation).
"""

from __future__ import annotations


class AppError(Exception):
    """Root exception for all domain and application errors.

    Args:
        detail: Human-readable explanation of this specific occurrence.
        code: Optional machine-readable error code (e.g. "product.not_found").
        status_code: HTTP status code for the response (default 500).
        title: Short summary of the problem type (default "Internal Server Error").
    """

    status_code: int = 500
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str,
        code: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        if status_code is not None:
            self.status_code = status_code
        if title is not None:
            self.title = title


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    title = "Not Found"


class ConflictError(AppError):
    """Raised when an operation conflicts with the current state of a resource."""

    status_code = 409
    title = "Conflict"


class AppValidationError(AppError):
    """Raised for domain-level validation failures.

    Named AppValidationError (not ValidationError) to avoid collision
    with pydantic.ValidationError.
    """

    status_code = 422
    title = "Validation Error"


class UnauthorizedError(AppError):
    """Raised when authentication is required but missing or invalid."""

    status_code = 401
    title = "Unauthorized"


class ForbiddenError(AppError):
    """Raised when the authenticated user lacks permission for the action."""

    status_code = 403
    title = "Forbidden"
