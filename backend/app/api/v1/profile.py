"""
Profile router — update profile and change password endpoints.

Change 13: customer-profile-management.

Routes:
  PATCH /profile/me        — update editable profile fields (nombre, apellido).
                             Email is immutable — ignored by ProfileUpdate schema.
                             Returns 200 UserRead.
  POST  /profile/me/password — change password with current-password verification.
                             Rate-limited at 5/15minutes per user_id.
                             Returns 204 No Content on success.
                             Returns 409 on current_password mismatch.

Design decisions:
  - D-02: email in PATCH body is silently ignored (ProfileUpdate extra='ignore').
  - D-03: wrong current_password → 409 ConflictError (not 401 or 403).
  - D-06: rate limit per user_id (not IP) — user_id from request.state, set inside
    the endpoint function AFTER get_current_user Depends runs. The key_func lambda
    accesses request.state.user_id which must be set before the limiter key_func runs.
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - HTTPException is NEVER raised here — ConflictError/NotFoundError from the service
    are handled by the global AppError handler in app/api/errors.py.
  - response_model is explicit on every endpoint decorator (project convention).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_current_user
from app.core.rate_limit import get_limiter
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario
from app.schemas.profile import PasswordChangeRequest, ProfileUpdate, UserRead
from app.services.profile import ProfileService

profile_router = APIRouter()

# Obtain the limiter lazily — get_limiter() is lru_cache, first call creates it.
_limiter = get_limiter()


@profile_router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated user profile",
    description=(
        "Update editable profile fields (nombre, apellido) for the authenticated user. "
        "The email field is immutable — if present in the request body it is silently "
        "ignored (not an error). "
        "Requires a valid Bearer access token."
    ),
    tags=["profile"],
    responses={
        200: {"description": "Updated UserRead profile"},
        401: {"description": "Missing, invalid, or expired Bearer token"},
        422: {"description": "Validation error (e.g., nombre > 80 chars)"},
    },
)
async def update_profile(
    request: Request,
    data: ProfileUpdate,
    current_user: Usuario = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_uow),
) -> UserRead:
    """Update editable fields for the authenticated user's profile.

    The user_id is ALWAYS extracted from the JWT via get_current_user.
    No path parameter or body field can override the user_id.
    """
    # Populate request.state.user_id for rate limiter key_func (D-06).
    request.state.user_id = str(current_user.id)
    return await ProfileService.update_profile(uow, current_user.id, data)


@profile_router.post(
    "/me/password",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change authenticated user password",
    description=(
        "Change the password for the authenticated user. "
        "Verifies the current password before hashing and storing the new one. "
        "On success: revokes ALL active refresh tokens for the user atomically. "
        "Rate-limited at 5 requests per 15 minutes per user_id. "
        "Returns 409 if current_password is wrong. "
        "Returns 429 if rate limit is exceeded."
    ),
    tags=["profile"],
    responses={
        204: {"description": "Password changed successfully; all refresh tokens revoked"},
        401: {"description": "Missing, invalid, or expired Bearer token"},
        409: {"description": "current_password does not match stored hash"},
        422: {"description": "Validation error (e.g., new_password < 8 chars)"},
        429: {"description": "Rate limit exceeded (5/15min per user)"},
    },
)
@_limiter.limit(
    "5/15minutes",
    key_func=lambda request: getattr(request.state, "user_id", "unknown"),
)
async def change_password(
    request: Request,
    data: PasswordChangeRequest,
    current_user: Usuario = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_uow),
) -> Response:
    """Change password and revoke all active refresh tokens atomically.

    rate-limiter key_func reads request.state.user_id. This attribute is set
    here (inside the function body) immediately after get_current_user runs via
    Depends. The order is: Depends(get_current_user) executes first → sets
    current_user → then this function body runs → sets request.state.user_id
    → the limiter key_func can read it.
    """
    # Set request.state.user_id so the rate-limiter key_func can read it.
    # This MUST be set before ProfileService is called (D-06).
    request.state.user_id = str(current_user.id)
    await ProfileService.change_password(uow, current_user.id, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
