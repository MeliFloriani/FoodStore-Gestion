"""
Integration tests for app/core/security.py — decode_access_token.

Covers spec scenarios from backend-auth-dependencies spec:
- Valid token decodes to payload dict
- Expired token raises UnauthorizedError
- Wrong signature raises UnauthorizedError
- nbf claim in future raises UnauthorizedError
- security.py does not contain issuance functions

Coverage target: ≥92% on core/security.py
"""

from __future__ import annotations

import time

import pytest
from jose import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token

# Test secret key — not the production key
_TEST_SECRET = "test-secret-key-for-development-only-change-in-production"
_ALGORITHM = "HS256"


def _make_token(
    payload: dict,  # type: ignore[type-arg]
    secret: str = _TEST_SECRET,
    algorithm: str = _ALGORITHM,
) -> str:
    """Helper: encode a JWT with the given payload."""
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Scenario: Valid token decodes to payload dict
# ---------------------------------------------------------------------------


def test_decode_valid_token_returns_payload(override_settings) -> None:
    """A valid JWT signed with the correct key returns the decoded payload dict."""
    exp = int(time.time()) + 3600
    token = _make_token({"sub": "some-user-id", "exp": exp})
    result = decode_access_token(token)
    assert isinstance(result, dict)
    assert result["sub"] == "some-user-id"


def test_decode_valid_token_contains_sub(override_settings) -> None:
    """Decoded payload contains the 'sub' claim."""
    exp = int(time.time()) + 3600
    import uuid

    user_id = str(uuid.uuid4())
    token = _make_token({"sub": user_id, "exp": exp})
    result = decode_access_token(token)
    assert result["sub"] == user_id


# ---------------------------------------------------------------------------
# Scenario: Expired token raises UnauthorizedError
# ---------------------------------------------------------------------------


def test_decode_expired_token_raises_unauthorized(override_settings) -> None:
    """An expired JWT raises UnauthorizedError (not JWTError)."""
    exp = int(time.time()) - 3600  # in the past
    token = _make_token({"sub": "user-id", "exp": exp})
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == "invalid_token"
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Scenario: Wrong signature raises UnauthorizedError
# ---------------------------------------------------------------------------


def test_decode_wrong_signature_raises_unauthorized(override_settings) -> None:
    """A JWT signed with a different key raises UnauthorizedError."""
    exp = int(time.time()) + 3600
    token = _make_token({"sub": "user-id", "exp": exp}, secret="wrong-secret-key")
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == "invalid_token"


# ---------------------------------------------------------------------------
# Scenario: nbf claim in future raises UnauthorizedError
# ---------------------------------------------------------------------------


def test_decode_future_nbf_raises_unauthorized(override_settings) -> None:
    """A JWT with nbf in the future raises UnauthorizedError."""
    exp = int(time.time()) + 3600
    nbf = int(time.time()) + 3600  # not valid yet
    token = _make_token({"sub": "user-id", "exp": exp, "nbf": nbf})
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == "invalid_token"


# ---------------------------------------------------------------------------
# Scenario: Malformed token raises UnauthorizedError
# ---------------------------------------------------------------------------


def test_decode_malformed_token_raises_unauthorized(override_settings) -> None:
    """A completely malformed string raises UnauthorizedError."""
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token("not.a.valid.jwt.at.all")
    assert exc_info.value.code == "invalid_token"


# ---------------------------------------------------------------------------
# Scenario: security.py now contains issuance functions (D-07 lifted by change auth-register-login)
# ---------------------------------------------------------------------------


def test_security_module_has_issuance_functions() -> None:
    """security.py must expose create_access_token and create_refresh_token.

    NOTE: D-07 (decode-only) was intentionally lifted by change auth-register-login.
    These functions now exist in security.py as per the change design.
    """
    import app.core.security as sec

    assert hasattr(sec, "create_access_token"), (
        "create_access_token must exist in security.py (D-07 lifted by auth-register-login)"
    )
    assert hasattr(sec, "create_refresh_token"), (
        "create_refresh_token must exist in security.py (D-07 lifted by auth-register-login)"
    )


def test_security_module_has_bcrypt_functions() -> None:
    """security.py must expose hash_password and verify_password (D-07 lifted).

    NOTE: D-07 (decode-only) was intentionally lifted by change auth-register-login.
    Password hashing functions now live in security.py.
    """
    import app.core.security as sec

    assert hasattr(sec, "hash_password"), (
        "hash_password must exist in security.py (D-07 lifted by auth-register-login)"
    )
    assert hasattr(sec, "verify_password"), (
        "verify_password must exist in security.py (D-07 lifted by auth-register-login)"
    )


def test_security_module_has_no_create_token_source() -> None:
    """security.py must define create_access_token and create_refresh_token functions.

    NOTE: Previously this test verified they did NOT exist (D-07 decode-only).
    D-07 was lifted by change auth-register-login; now they MUST exist.
    """
    import app.core.security as sec

    # Functions must be callable
    assert callable(getattr(sec, "create_access_token", None)), (
        "create_access_token must be callable in security.py"
    )
    assert callable(getattr(sec, "create_refresh_token", None)), (
        "create_refresh_token must be callable in security.py"
    )


# ---------------------------------------------------------------------------
# Scenario: Error class generic — does not expose failure mode
# ---------------------------------------------------------------------------


def test_expired_token_error_message_is_generic(override_settings) -> None:
    """UnauthorizedError detail must be generic, not 'Signature verification failed'."""
    exp = int(time.time()) - 3600
    token = _make_token({"sub": "user-id", "exp": exp})
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token)
    # Detail must NOT contain implementation-specific error details
    assert "signature" not in exc_info.value.detail.lower()
    assert "expired" not in exc_info.value.detail.lower()


def test_wrong_signature_error_message_is_generic(override_settings) -> None:
    """Wrong signature error detail must be generic (not 'Signature verification failed')."""
    exp = int(time.time()) + 3600
    token = _make_token({"sub": "user-id", "exp": exp}, secret="wrong")
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token)
    assert "signature" not in exc_info.value.detail.lower()
