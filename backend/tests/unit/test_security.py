"""
Unit tests for the extended security.py module.

Tasks 3.5, 3.6, 3.7 — hash_password, verify_password, create_access_token,
create_refresh_token.

These tests use override_settings to ensure get_settings() works correctly
and the test SECRET_KEY is used for JWT operations.
"""

from __future__ import annotations

import hashlib
import time

import pytest
from jose import jwt


# ---------------------------------------------------------------------------
# Task 3.5 — hash_password and verify_password
# ---------------------------------------------------------------------------


class TestHashPassword:
    """Tests for hash_password."""

    def test_hash_password_returns_string(self, override_settings) -> None:
        """hash_password should return a non-empty string."""
        from app.core.security import hash_password

        result = hash_password("MyPassword123!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_bcrypt_format(self, override_settings) -> None:
        """hash_password should return a bcrypt-formatted hash starting with $2b$."""
        from app.core.security import hash_password

        result = hash_password("MyPassword123!")
        assert result.startswith("$2b$") or result.startswith("$2a$")

    def test_hash_password_different_each_time(self, override_settings) -> None:
        """Two hashes of the same password should differ (bcrypt uses random salt)."""
        from app.core.security import hash_password

        h1 = hash_password("SamePassword!")
        h2 = hash_password("SamePassword!")
        assert h1 != h2


class TestVerifyPassword:
    """Tests for verify_password."""

    def test_verify_password_happy_path(self, override_settings) -> None:
        """verify_password returns True when plain matches the hash."""
        from app.core.security import hash_password, verify_password

        plain = "CorrectPassword123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_wrong_password(self, override_settings) -> None:
        """verify_password returns False when plain does not match the hash."""
        from app.core.security import hash_password, verify_password

        hashed = hash_password("CorrectPassword123!")
        assert verify_password("WrongPassword!", hashed) is False

    def test_verify_password_invalid_hash(self, override_settings) -> None:
        """verify_password returns False (not raises) for an invalid hash."""
        from app.core.security import verify_password

        assert verify_password("AnyPassword!", "not-a-valid-bcrypt-hash") is False

    def test_verify_password_empty_hash(self, override_settings) -> None:
        """verify_password returns False for an empty hash string."""
        from app.core.security import verify_password

        assert verify_password("AnyPassword!", "") is False


# ---------------------------------------------------------------------------
# Task 3.6 — create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    """Tests for create_access_token."""

    def test_create_access_token_returns_string(self, override_settings) -> None:
        """create_access_token should return a non-empty string."""
        from app.core.security import create_access_token

        token = create_access_token("user-uuid-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_decodable(self, override_settings) -> None:
        """The token should be decodable using decode_access_token."""
        from app.core.security import create_access_token, decode_access_token

        token = create_access_token("user-uuid-123")
        payload = decode_access_token(token)
        assert isinstance(payload, dict)

    def test_create_access_token_correct_sub(self, override_settings) -> None:
        """The decoded payload should contain the correct 'sub' claim."""
        from app.core.security import create_access_token, decode_access_token

        subject = "some-user-id-xyz"
        token = create_access_token(subject)
        payload = decode_access_token(token)
        assert payload["sub"] == subject

    def test_create_access_token_type_claim(self, override_settings) -> None:
        """The decoded payload should have type='access'."""
        from app.core.config import get_settings
        from app.core.security import create_access_token

        settings = get_settings()
        token = create_access_token("user-id")
        # Decode manually to inspect all claims
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert payload["type"] == "access"

    def test_create_access_token_respects_expires_in(self, override_settings) -> None:
        """create_access_token should respect a custom expires_in value."""
        from app.core.config import get_settings
        from app.core.security import create_access_token

        settings = get_settings()
        now = int(time.time())
        expires_in = 7200  # 2 hours
        token = create_access_token("user-id", expires_in=expires_in)
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert payload["exp"] >= now + expires_in - 5  # 5 second tolerance

    def test_create_access_token_has_iat(self, override_settings) -> None:
        """The access token payload should include an iat (issued at) claim."""
        from app.core.config import get_settings
        from app.core.security import create_access_token

        settings = get_settings()
        token = create_access_token("user-id")
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert "iat" in payload


# ---------------------------------------------------------------------------
# Task 3.7 — create_refresh_token
# ---------------------------------------------------------------------------


class TestCreateRefreshToken:
    """Tests for create_refresh_token."""

    def test_create_refresh_token_returns_tuple(self, override_settings) -> None:
        """create_refresh_token should return a 2-tuple."""
        from app.core.security import create_refresh_token

        result = create_refresh_token("user-uuid-123")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_create_refresh_token_digest_is_64_hex(self, override_settings) -> None:
        """The digest should be exactly 64 hexadecimal characters."""
        from app.core.security import create_refresh_token

        _, digest = create_refresh_token("user-uuid-123")
        assert len(digest) == 64
        # Must be valid hex
        int(digest, 16)

    def test_create_refresh_token_digest_matches_cleartext(self, override_settings) -> None:
        """SHA-256 of the cleartext JWT should equal the returned digest."""
        from app.core.security import create_refresh_token

        cleartext, digest = create_refresh_token("user-uuid-123")
        expected = hashlib.sha256(cleartext.encode()).hexdigest()
        assert digest == expected

    def test_create_refresh_token_payload_type(self, override_settings) -> None:
        """The refresh token payload type claim should be 'refresh'."""
        from app.core.config import get_settings
        from app.core.security import create_refresh_token

        settings = get_settings()
        cleartext, _ = create_refresh_token("user-id")
        payload = jwt.decode(
            cleartext,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert payload["type"] == "refresh"

    def test_create_refresh_token_correct_sub(self, override_settings) -> None:
        """The refresh token should carry the correct 'sub' claim."""
        from app.core.config import get_settings
        from app.core.security import create_refresh_token

        settings = get_settings()
        subject = "refresh-user-id"
        cleartext, _ = create_refresh_token(subject)
        payload = jwt.decode(
            cleartext,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert payload["sub"] == subject
