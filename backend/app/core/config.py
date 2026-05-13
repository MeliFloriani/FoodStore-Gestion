"""
Typed application settings powered by pydantic-settings.

Design decisions:
- D-14: APP_VERSION NOT in Settings — use get_app_version() from importlib.metadata.
- D-05: get_settings() is @lru_cache(maxsize=1) — lazy singleton, never at module level.
- Pydantic v2: BaseSettings from pydantic_settings, field_validator, SettingsConfigDict.
"""

from __future__ import annotations

import importlib.metadata
import json
from functools import lru_cache
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Disable pydantic-settings' automatic JSON parsing for complex types
        # so our field_validator can handle the raw string value first.
        env_parse_none_str="null",
    )

    # --- Required ---
    DATABASE_URL: str  # No default — must be set in environment
    SECRET_KEY: SecretStr  # No default — must be set in environment (JWT signing key)

    # --- Optional with sensible defaults ---
    ENVIRONMENT: str = "development"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Declared as str so pydantic-settings won't pre-parse as JSON;
    # assemble_cors_origins converts it to list[str].
    BACKEND_CORS_ORIGINS: str | list[str] = ["http://localhost:5173"]
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        """Accept both comma-separated string and JSON array for CORS origins."""
        if isinstance(v, list):
            return [str(item).strip() for item in v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Try JSON array first
            if v.startswith("["):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except json.JSONDecodeError:
                    pass
            # Fall back to comma-separated string
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        raise ValueError(f"Invalid BACKEND_CORS_ORIGINS value: {v!r}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance.

    This is the ONLY access point to Settings throughout the codebase.
    Decorated with @lru_cache(maxsize=1) for lazy initialization (D-05).
    """
    return Settings()  # type: ignore[call-arg]  # DATABASE_URL is loaded from env/.env


def get_app_version() -> str:
    """Return the installed package version, or '0.0.0' as fallback.

    Implements decision D-14: version comes from package metadata, not Settings.
    The fallback handles the case where the package is not installed (e.g., during
    some test environments or CI scenarios without pip install -e .).
    """
    try:
        return importlib.metadata.version("foodstore-backend")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
