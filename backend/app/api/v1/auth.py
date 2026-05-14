"""
Auth router — registration and login endpoints.

Routes:
  POST /auth/register — create user account, returns UserRead (201)
  POST /auth/login   — validate credentials, return JWT pair (200)
                       rate-limited at 5 requests / 15 minutes per IP

Design decisions:
- Rate limiting applied via @limiter.limit() decorator. The limiter is obtained
  lazily via get_limiter() which is an lru_cache singleton (D-05). Calling
  get_limiter() at router-build time (inside the function, not at import level)
  avoids settings-before-test-fixture issues.
- ConflictError (409) and UnauthorizedError (401) are raised in the service
  and caught by the global AppError handler registered in app/api/errors.py.
- session.commit() is NEVER called here — UnitOfWork handles it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.core.rate_limit import get_limiter
from app.core.uow import UnitOfWork, get_uow
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth import AuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# Obtain the limiter lazily — get_limiter() is lru_cache, first call creates it.
# Module-level call is intentional here: the conftest cache_clear autouse fixture
# clears get_limiter.cache_clear() between tests, so the limiter instance used by
# the decorator is recreated per test-batch. The decorator captures the limiter
# object, but slowapi checks the limiter's internal storage on each request.
_limiter = get_limiter()


@auth_router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: RegisterRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> UserRead:
    """Create a new user account and auto-assign the CLIENT role.

    Returns the created user's profile (UserRead) on success.
    Returns 409 if the email is already registered.
    Returns 422 if the request body fails validation (e.g. password < 8 chars).
    """
    usuario = await AuthService.register_user(uow, data)
    return UserRead.model_validate(usuario)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive a JWT pair",
)
@_limiter.limit("5/15minutes")
async def login(
    request: Request,
    data: LoginRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> TokenResponse:
    """Validate credentials and issue an access + refresh JWT pair.

    Rate-limited at 5 requests per 15 minutes per IP address.
    Returns 401 for invalid credentials (generic message — no email enumeration).
    Returns 429 when the rate limit is exceeded.
    """
    return await AuthService.login_user(uow, data, request)
