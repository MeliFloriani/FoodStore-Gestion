"""
Rate limiting configuration using slowapi.

Design decisions:
- D-05 / P-02: get_limiter() is @lru_cache(maxsize=1) — lazy, never at module level.
  If limiter were created at module level, importing this module in tests would trigger
  Settings instantiation before the test can override DATABASE_URL.
"""

from __future__ import annotations

from functools import lru_cache

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_limiter() -> Limiter:
    """Return the singleton Limiter instance.

    Lazy: constructed on first call using get_settings().
    The default_limits come from RATE_LIMIT_DEFAULT in Settings.

    Correction P-02: limiter is NOT instantiated at module level.
    """
    settings = get_settings()
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
    )
