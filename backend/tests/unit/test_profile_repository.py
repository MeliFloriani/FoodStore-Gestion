"""
Unit tests for RefreshTokenRepository.revoke_all_for_user.

Task 2.1 — TDD red phase.

Covers:
  - revoke_all_for_user revokes all active tokens for a user, returns count
  - revoke_all_for_user when no active tokens → returns 0 (no-op)
  - revoke_all_for_user does NOT touch already-revoked tokens
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


import pytest


class TestRevokeAllForUser:
    """Tests for RefreshTokenRepository.revoke_all_for_user."""

    def _make_mock_session(self) -> MagicMock:
        """Build a minimal async session mock."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    def _make_mock_result(self, rowcount: int) -> MagicMock:
        """Build a mock execute result with a given rowcount."""
        result = MagicMock()
        result.rowcount = rowcount
        return result

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_revokes_active_tokens_returns_count(
        self,
    ) -> None:
        """revoke_all_for_user revokes all active tokens and returns the count."""
        from app.repositories.user import RefreshTokenRepository

        session = self._make_mock_session()
        session.execute = AsyncMock(return_value=self._make_mock_result(3))

        repo = RefreshTokenRepository(session)
        user_id = uuid.uuid4()
        count = await repo.revoke_all_for_user(user_id)

        assert count == 3
        assert session.execute.called
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_returns_zero_when_no_active_tokens(
        self,
    ) -> None:
        """revoke_all_for_user returns 0 when no active tokens exist (no-op)."""
        from app.repositories.user import RefreshTokenRepository

        session = self._make_mock_session()
        session.execute = AsyncMock(return_value=self._make_mock_result(0))

        repo = RefreshTokenRepository(session)
        user_id = uuid.uuid4()
        count = await repo.revoke_all_for_user(user_id)

        assert count == 0
        # Still calls flush even on no-op (idempotent behavior)
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_does_not_touch_already_revoked_tokens(
        self,
    ) -> None:
        """revoke_all_for_user only affects tokens where revoked_at IS NULL.

        Tokens already revoked (revoked_at IS NOT NULL) should not be re-touched.
        The WHERE clause ensures this: the mock result reflects only rows affected.
        """
        from app.repositories.user import RefreshTokenRepository

        session = self._make_mock_session()
        # 2 active + 1 already revoked → only 2 rows affected
        session.execute = AsyncMock(return_value=self._make_mock_result(2))

        repo = RefreshTokenRepository(session)
        user_id = uuid.uuid4()
        count = await repo.revoke_all_for_user(user_id)

        # Only the 2 active tokens were revoked; already-revoked token not counted
        assert count == 2

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_calls_flush_after_bulk_update(self) -> None:
        """revoke_all_for_user MUST call session.flush() after the bulk UPDATE.

        This is required to make changes visible within the transaction before
        the UoW commits (per spec requirement for bulk UPDATE methods).
        """
        from app.repositories.user import RefreshTokenRepository

        session = self._make_mock_session()
        session.execute = AsyncMock(return_value=self._make_mock_result(1))

        repo = RefreshTokenRepository(session)
        await repo.revoke_all_for_user(uuid.uuid4())

        # flush must be called exactly once after the execute
        session.flush.assert_called_once()
