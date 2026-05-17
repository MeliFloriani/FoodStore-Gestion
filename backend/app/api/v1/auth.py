"""
Auth router — registration, login, refresh, logout, and /me endpoints.

Routes:
  POST /auth/register — create user account, returns UserRead (201)
  POST /auth/login    — validate credentials, return JWT pair (200)
                        rate-limited at 5 requests / 15 minutes per IP
  POST /auth/refresh  — rotate refresh token (200)
                        rate-limited at 30 requests / 15 minutes per IP
  POST /auth/logout   — revoke a single refresh token (204)
  GET  /auth/me       — return UserRead for the authenticated user (200)

Design decisions:
- Rate limiting applied via @limiter.limit() decorator. The limiter is obtained
  lazily via get_limiter() which is an lru_cache singleton (D-05). Calling
  get_limiter() at router-build time (inside the function, not at import level)
  avoids settings-before-test-fixture issues.
- ConflictError (409) and UnauthorizedError (401) are raised in the service
  and caught by the global AppError handler registered in app/api/errors.py.
- session.commit() is NEVER called here — UnitOfWork handles it.
- D-07-C (Opción A): replay detection uses a SECOND independent UoW in this
  router to call revoke_family() synchronously before returning HTTP 401.
  TokenReplayError MUST NOT be caught by any global handler — the explicit
  except block here is the sole catch point.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import TokenReplayError, UnauthorizedError
from app.core.logging import get_logger
from app.core.rate_limit import get_limiter
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth import AuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])

logger = get_logger(__name__)

# Obtain the limiter lazily — get_limiter() is lru_cache, first call creates it.
# Module-level call is intentional here: the conftest cache_clear autouse fixture
# clears get_limiter.cache_clear() between tests, so the limiter instance used by
# the decorator is recreated per test-batch. The decorator captures the limiter
# object, but slowapi checks the limiter's internal storage on each request.
_limiter = get_limiter()


def _get_client_ip(request: Request) -> str:
    """Resolve client IP with X-Forwarded-For support and null-safe fallback.

    Used for rate limiting and audit logging only — NOT for authorization.
    X-Forwarded-For may be spoofed if the app is not behind a trusted proxy.
    For Sprint 1 this is acceptable: the rate limiter exists and IP is for
    audit/logging purposes only, not for access control decisions.

    Behind reverse proxies (Railway, Render, Fly.io, nginx), request.client
    may be None because the proxy does not forward the original socket address
    as a FastAPI Request.client. Using request.client.host directly causes an
    AttributeError → HTTP 500. The X-Forwarded-For header contains the original
    client IP set by the proxy.

    Args:
        request: The FastAPI Request object.

    Returns:
        The resolved client IP string, or "unknown" if unavailable.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@auth_router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new user account and auto-assign the CLIENT role. "
        "Returns the created user's profile (UserRead) on success. "
        "Returns 409 if the email is already registered. "
        "Returns 422 if the request body fails validation (e.g. password < 8 chars)."
    ),
    tags=["auth"],
)
async def register(
    data: RegisterRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> UserRead:
    """Create a new user account and auto-assign the CLIENT role."""
    usuario = await AuthService.register_user(uow, data)
    return UserRead.model_validate(usuario)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive a JWT pair",
    description=(
        "Validate credentials and issue an access + refresh JWT pair. "
        "Rate-limited at 5 requests per 15 minutes per IP address. "
        "Returns 401 for invalid credentials (generic message — no email enumeration). "
        "Returns 429 when the rate limit is exceeded."
    ),
    tags=["auth"],
)
@_limiter.limit("5/15minutes")
async def login(
    request: Request,
    data: LoginRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> TokenResponse:
    """Validate credentials and issue an access + refresh JWT pair."""
    return await AuthService.login_user(uow, data, request)


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate a refresh token",
    description=(
        "Rotate a refresh token: revoke the presented token and issue a new "
        "access + refresh token pair. The new refresh token inherits the same "
        "family_id. "
        "If the presented token has already been rotated (replay attack detected), "
        "the entire token family is revoked and HTTP 401 is returned with "
        "code='token_replay_detected'. "
        "Rate-limited at 30 requests per 15 minutes per IP address."
    ),
    tags=["auth"],
    responses={
        200: {"description": "New token pair returned successfully"},
        401: {"description": "Token invalid, expired, or replay detected"},
        422: {"description": "Missing or malformed refresh_token field"},
        429: {"description": "Rate limit exceeded"},
    },
)
@_limiter.limit("30/15minutes")
async def refresh(
    request: Request,
    data: RefreshRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> TokenResponse:
    """Rotate a refresh token and return a new JWT pair.

    D-07-C (Opción A): If rotate_refresh raises TokenReplayError, this endpoint
    opens a SECOND independent UoW to call revoke_family synchronously before
    returning 401. The first UoW (injected via Depends) was already rolled back
    by UnitOfWork.__aexit__ when the exception propagated out of rotate_refresh.
    The second UoW commits the revocation independently of the first.

    CRITICAL: TokenReplayError must NOT be caught by any global exception_handler.
    This router's explicit except block is the sole catch point.
    """
    try:
        return await AuthService.rotate_refresh(
            uow,
            data.refresh_token,
            _get_client_ip(request),
            request.headers.get("user-agent", ""),
        )
    except TokenReplayError as e:
        # D-07-C Opción A: the first UoW was already rolled back by __aexit__.
        # Open a SECOND independent UoW to commit the family revocation.
        async with UnitOfWork() as uow2:
            await uow2.refresh_tokens.revoke_family(e.family_id)
        # uow2 commits on clean __aexit__ — revocation is now persisted.

        logger.warning(
            "auth.replay_detected",
            user_id=str(e.user_id),
            family_id=str(e.family_id),
            ip=_get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
        raise UnauthorizedError(
            "Sesión comprometida — la familia de tokens ha sido revocada",
            code="token_replay_detected",
        )


@auth_router.post(
    "/logout",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token (logout)",
    description=(
        "Revoke the provided refresh token. Bearer access token is NOT required — "
        "the logout is keyed exclusively on the refresh token. "
        "This operation is idempotent: unknown or already-revoked tokens return 204. "
        "The access token remains valid until its natural 30-minute TTL expires."
    ),
    tags=["auth"],
    responses={
        204: {"description": "Token revoked (or was already revoked / unknown)"},
        422: {"description": "Missing or malformed refresh_token field"},
    },
)
async def logout(
    data: LogoutRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> Response:
    """Revoke a single refresh token. Idempotent — always returns 204."""
    await AuthService.revoke_refresh(uow, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
    description=(
        "Return the profile of the currently authenticated user. "
        "Requires a valid Bearer access token in the Authorization header. "
        "Returns 401 if the token is missing, invalid, or expired. "
        "The response includes id, nombre, apellido, email, roles, and created_at. "
        "The response never includes password_hash."
    ),
    tags=["auth"],
    responses={
        200: {"description": "UserRead profile of the authenticated user"},
        401: {"description": "Missing, invalid, or expired Bearer token"},
    },
)
async def me(
    current_user: Usuario = Depends(get_current_user),
) -> UserRead:
    """Return UserRead for the bearer of a valid access token.

    get_current_user resolves the Usuario via uow.usuarios.get_by_id(), which
    triggers the model-level lazy='selectin' eager load on usuario_roles.
    UserRead.roles is then populated via the @computed_field that reads
    usuario_roles. No additional service method is required.
    """
    return UserRead.model_validate(current_user)
