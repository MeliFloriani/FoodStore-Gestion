"""
JWT decode helper — decode-only scope.

This module provides ONLY token validation/decoding functionality.
Token issuance (create_access_token, create_refresh_token) and password
hashing (verify_password, hash_password) are intentionally deferred to
Change 09 (auth-jwt-issuance / auth-register-login).

The only consumer of this module within this change is api/deps.py::get_current_user.

Design decision D-07: decode-only to keep this change focused on infrastructure
plumbing without introducing issuance complexity that belongs in the auth domain.
"""

from __future__ import annotations

from jose import JWTError, jwt

from app.core.exceptions import UnauthorizedError


def decode_access_token(token: str) -> dict:  # type: ignore[type-arg]
    """Decode and validate a JWT access token, returning the payload as a dict.

    This function is DECODE-ONLY. It does not issue tokens.

    Validates:
      - Signature (verify_signature=True)
      - Expiration (verify_exp=True)
      - Not-before (verify_nbf=True)
      - Issued-at (verify_iat=True)

    Deferred to Change 09:
      - Audience verification (verify_aud=False)
      - Issuer verification (verify_iss=False)

    Args:
        token: Raw JWT string extracted from the Authorization header.

    Returns:
        Decoded payload dict containing at minimum the 'sub' claim
        (user UUID as string).

    Raises:
        UnauthorizedError: For any JWT validation failure (expired, wrong signature,
            malformed, nbf in future, etc.). The original jose exception is chained
            but its detail is NOT forwarded to the client to prevent information leakage
            about the specific failure mode (RFC 7807 compliance).
    """
    # Import get_settings lazily to respect D-05 (lazy singleton pattern).
    # Do NOT call get_settings() at module level — it would force settings
    # initialization before test fixtures have a chance to configure the environment.
    from app.core.config import get_settings

    settings = get_settings()

    try:
        payload: dict = jwt.decode(  # type: ignore[type-arg]
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": False,   # NON-GOAL: audience policy deferred to Change 09
                "verify_iss": False,   # NON-GOAL: issuer policy deferred to Change 09
            },
        )
        return payload
    except JWTError as exc:
        # Wrap all jose exceptions in a single generic error type.
        # "Token inválido o expirado" is intentionally vague — the client MUST NOT
        # know whether the failure was due to an expired token, a wrong signature,
        # a malformed header, or an nbf violation (prevents timing-based attacks).
        raise UnauthorizedError(
            "Token inválido o expirado",
            code="invalid_token",
        ) from exc
