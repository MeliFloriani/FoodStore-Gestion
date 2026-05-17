"""
Domain exception hierarchy.

All application-level errors inherit from AppError, which carries enough
information for the error handler (app/api/errors.py) to build a valid
RFC 7807 ProblemDetail response without needing to catch multiple types.

Note: AppValidationError is prefixed with App* to avoid name collision with
pydantic.ValidationError, which is a different concept (schema validation).

TokenReplayError is intentionally NOT a subclass of AppError or HTTPException.
It is a plain Python Exception used as an internal signal within the auth
refresh flow (D-07-C). It MUST NOT be registered with a global exception_handler
because the router's explicit except block must be the sole catch point — the
second-UoW revoke_family call must complete before the 401 is returned.
"""

from __future__ import annotations

import uuid


class TokenReplayError(Exception):
    """Raised by AuthService.rotate_refresh when a replay attack is detected.

    This exception signals that a previously-rotated (already revoked) refresh
    token was presented again. It is caught exclusively by the /auth/refresh
    router endpoint which then opens a SECOND independent UnitOfWork to call
    revoke_family(family_id) before re-raising as UnauthorizedError.

    CRITICAL INHERITANCE RULE: This class inherits directly from Exception, NOT
    from AppError, HTTPException, or any subclass thereof. If it inherited from
    AppError, the global AppError exception_handler would intercept it before
    the router's explicit except block — bypassing the second-UoW commit and
    leaving the token family active (a security defect, D-07-C B-1 fix).

    Do NOT register a global @app.exception_handler(TokenReplayError).

    Args:
        family_id: The UUID of the compromised token family to revoke.
        user_id: The UUID of the user who owns the compromised family.
    """

    def __init__(self, family_id: uuid.UUID, user_id: uuid.UUID) -> None:
        super().__init__(
            f"Replay attack detected: family_id={family_id}, user_id={user_id}"
        )
        self.family_id = family_id
        self.user_id = user_id


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
