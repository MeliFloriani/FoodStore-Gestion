"""
JWT security utilities — decode, issuance, and password hashing.

This module was initially decode-only (D-07). Change auth-register-login lifts
that restriction and adds:
  - hash_password / verify_password (passlib[bcrypt])
  - create_access_token / create_refresh_token (python-jose)

Design decisions:
- D-05: get_settings() called lazily inside each function — never at module level.
- D-07 (lifted): issuance functions now live here per change auth-register-login.
- RefreshToken cleartext is never persisted — only SHA-256 hex digest.
- datetime.now(timezone.utc) used throughout (datetime.utcnow() deprecated in 3.12).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.exceptions import UnauthorizedError

# ---------------------------------------------------------------------------
# CryptContext — lazy singleton pattern (D-05)
# ---------------------------------------------------------------------------

# We build the context lazily per call so that BCRYPT_COST from Settings
# is always respected, even in tests that override settings.
# The cost is read once when _get_crypt_context() is first called.
_crypt_context: CryptContext | None = None


def _get_crypt_context() -> CryptContext:
    """Return (or create) the passlib CryptContext with bcrypt rounds from settings."""
    global _crypt_context  # noqa: PLW0603
    if _crypt_context is None:
        from app.core.config import get_settings

        settings = get_settings()
        _crypt_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=settings.BCRYPT_COST,
        )
    return _crypt_context


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


# ---------------------------------------------------------------------------
# Password hashing (task 3.2)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt at the configured cost.

    Args:
        plain: The plaintext password string.

    Returns:
        A bcrypt hash string (60 characters, $2b$ format).
    """
    return _get_crypt_context().hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Returns False instead of raising on invalid/malformed hashes — prevents
    information leakage about the hash format or failure mode.

    Args:
        plain: The plaintext password to verify.
        hashed: The stored bcrypt hash string.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _get_crypt_context().verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token issuance (tasks 3.3, 3.4)
# ---------------------------------------------------------------------------


def create_access_token(subject: str, expires_in: int = 1800) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The 'sub' claim — typically the user UUID as a string.
        expires_in: Seconds until expiry (default: 1800 = 30 minutes).

    Returns:
        A signed JWT string with claims: sub, iat, exp, type="access".
    """
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + expires_in,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: str,
    expires_in: int = 7 * 24 * 3600,
) -> tuple[str, str]:
    """Create a signed JWT refresh token and its SHA-256 hex digest.

    The cleartext JWT is returned to the client.
    Only the SHA-256 hex digest is persisted in the database (D-20).

    Args:
        subject: The 'sub' claim — typically the user UUID as a string.
        expires_in: Seconds until expiry (default: 7 days).

    Returns:
        A tuple of (cleartext_jwt, sha256_hex_digest).
        The digest is exactly 64 hexadecimal characters.
    """
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + expires_in,
        "type": "refresh",
    }
    cleartext = jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    digest = hashlib.sha256(cleartext.encode()).hexdigest()
    return cleartext, digest
