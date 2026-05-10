"""
Infrastructure tests for backend-core-foundation.

Tests are atomic — one assertion focus per test function.
All tests use the override_settings / async_client fixtures from conftest.py.

Coverage targets:
- app/core/config.py: Settings, get_settings, get_app_version
- app/api/errors.py: all four handlers
- app/api/v1/router.py: GET /api/v1/health
- app/core/middleware.py: RequestIDMiddleware (X-Request-ID header propagation)
- CORS headers on configured origins
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import APIRouter
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.main import app

# ---------------------------------------------------------------------------
# Register test-only routes on the app to exercise error handlers.
# These routes raise domain exceptions so error handler coverage is exercised
# without needing real domain endpoints.
# ---------------------------------------------------------------------------

_test_router = APIRouter(prefix="/_test", tags=["_test"])


@_test_router.get("/not-found")
async def _trigger_not_found() -> dict:
    raise NotFoundError(detail="Item not found in test", code="test.not_found")


@_test_router.get("/conflict")
async def _trigger_conflict() -> dict:
    raise ConflictError(detail="Conflict triggered in test", code="test.conflict")


@_test_router.post("/validate")
async def _trigger_validation(body: dict) -> dict:
    # Just returns the body — validation failure is triggered by bad request body
    return body


app.include_router(_test_router)


# ---------------------------------------------------------------------------
# 13.4.1 — Settings loads DATABASE_URL from .env
# ---------------------------------------------------------------------------


def test_settings_database_url_loaded(override_settings):
    """get_settings().DATABASE_URL must be non-empty when .env is populated."""
    settings = get_settings()
    assert settings.DATABASE_URL, "DATABASE_URL should be set from TEST_DATABASE_URL"
    assert len(settings.DATABASE_URL) > 0


# ---------------------------------------------------------------------------
# 13.4.2 — Liveness probe (no DB dependency)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_liveness(async_client: AsyncClient):
    """GET /health -> 200 with {"status": "ok"} (no DB)."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 13.4.3 — Readiness probe (requires PostgreSQL test DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_readiness(async_client: AsyncClient):
    """GET /api/v1/health -> 200 with database: ok (requires PostgreSQL)."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "version" in data


# ---------------------------------------------------------------------------
# 13.4.4 — NotFoundError -> 404 RFC 7807
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_found_error_returns_problem_json(async_client: AsyncClient):
    """Endpoint that raises NotFoundError -> 404 application/problem+json."""
    response = await async_client.get("/_test/not-found")
    assert response.status_code == 404
    assert "application/problem+json" in response.headers.get("content-type", "")
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "detail" in body
    assert "instance" in body


# ---------------------------------------------------------------------------
# 13.4.5 — ConflictError -> 409 RFC 7807
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conflict_error_returns_problem_json(async_client: AsyncClient):
    """Endpoint that raises ConflictError -> 409 application/problem+json."""
    response = await async_client.get("/_test/conflict")
    assert response.status_code == 409
    assert "application/problem+json" in response.headers.get("content-type", "")
    body = response.json()
    assert body["status"] == 409
    assert body["title"] == "Conflict"


# ---------------------------------------------------------------------------
# 13.4.6 — Validation error -> single 422 with errors extension
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_error_returns_single_problem_with_errors_extension(
    async_client: AsyncClient,
):
    """Invalid request body -> 422 with application/problem+json and errors:[...] extension."""
    from pydantic import BaseModel

    class _Body(BaseModel):
        name: str
        age: int

    # Monkey-patch a route that requires the body model to trigger validation error
    from fastapi import APIRouter as _APIRouter

    _vr = _APIRouter()

    @_vr.post("/_test/validate-typed")
    async def _validate_body(body: _Body) -> dict:
        return body.model_dump()

    app.include_router(_vr)

    response = await async_client.post(
        "/_test/validate-typed",
        json={"name": 123, "age": "not-a-number"},  # wrong types
    )
    # FastAPI validates the body against _Body; age="not-a-number" fails validation
    assert response.status_code == 422
    assert "application/problem+json" in response.headers.get("content-type", "")
    body = response.json()
    assert body["status"] == 422
    assert "errors" in body
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) >= 1


# ---------------------------------------------------------------------------
# 13.4.7 — CORS headers present for allowed origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_headers_present(async_client: AsyncClient):
    """Request from allowed origin -> Access-Control-Allow-Origin header present."""
    response = await async_client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


# ---------------------------------------------------------------------------
# 13.4.8 — X-Request-ID header present in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_id_header_present(async_client: AsyncClient):
    """Response must include X-Request-ID header with a valid UUID v4."""
    response = await async_client.get("/health")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None, "X-Request-ID header missing from response"
    # Validate it's a valid UUID
    parsed = uuid.UUID(request_id)
    assert parsed.version == 4


# ---------------------------------------------------------------------------
# 13.4.9 — X-Request-ID propagated when provided by client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_id_propagated_when_provided(async_client: AsyncClient):
    """When client sends X-Request-ID, response must echo the same value."""
    client_request_id = str(uuid.uuid4())
    response = await async_client.get(
        "/health",
        headers={"X-Request-ID": client_request_id},
    )
    echoed = response.headers.get("x-request-id")
    assert echoed == client_request_id, (
        f"Expected X-Request-ID to be propagated as {client_request_id!r}, got {echoed!r}"
    )


# ---------------------------------------------------------------------------
# Additional coverage: logging, models, config helpers, error handler branches
# ---------------------------------------------------------------------------


def test_configure_logging_development():
    """configure_logging('INFO', 'development') runs without exceptions."""
    from app.core.logging import configure_logging, get_logger

    configure_logging("INFO", "development")
    logger = get_logger("test-cov")
    logger.info("coverage test log line")


def test_configure_logging_production():
    """configure_logging('WARNING', 'production') uses JSONRenderer without exceptions."""
    from app.core.logging import configure_logging, get_logger

    configure_logging("WARNING", "production")
    logger = get_logger("test-cov-prod")
    logger.warning("coverage test json log")
    # Reset to development for subsequent tests
    configure_logging("INFO", "development")


def test_get_app_version_returns_string():
    """get_app_version() returns a non-empty string."""
    from app.core.config import get_app_version

    version = get_app_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_cors_validator_comma_separated():
    """BACKEND_CORS_ORIGINS accepts a comma-separated string."""
    from app.core.config import Settings

    s = Settings(  # type: ignore[call-arg]
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        BACKEND_CORS_ORIGINS="http://a.com,http://b.com",
    )
    assert "http://a.com" in s.BACKEND_CORS_ORIGINS
    assert "http://b.com" in s.BACKEND_CORS_ORIGINS


def test_cors_validator_json_array():
    """BACKEND_CORS_ORIGINS accepts a JSON array string."""
    from app.core.config import Settings

    s = Settings(  # type: ignore[call-arg]
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        BACKEND_CORS_ORIGINS='["http://a.com","http://b.com"]',
    )
    assert "http://a.com" in s.BACKEND_CORS_ORIGINS
    assert "http://b.com" in s.BACKEND_CORS_ORIGINS


def test_base_model_soft_delete():
    """Base.soft_delete() sets deleted_at and is_deleted returns True."""
    import uuid
    from datetime import UTC, datetime

    from app.models.base import Base

    # Instantiate with required fields (table=False so no DB needed)
    instance = Base(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    assert instance.is_deleted is False
    instance.soft_delete()
    assert instance.is_deleted is True
    assert instance.deleted_at is not None


def test_base_model_is_deleted_false_by_default():
    """A freshly created Base instance is not deleted."""
    import uuid
    from datetime import UTC, datetime

    from app.models.base import Base

    instance = Base(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    assert instance.is_deleted is False


def test_db_base_naming_convention():
    """SQLModel.metadata.naming_convention is set after importing app.db.base."""
    from sqlmodel import SQLModel

    import app.db.base  # noqa: F401

    assert "pk" in SQLModel.metadata.naming_convention
    assert "fk" in SQLModel.metadata.naming_convention


def test_create_pagination_meta_normal():
    """create_pagination_meta with normal inputs calculates pages correctly."""
    from app.schemas.base import create_pagination_meta

    meta = create_pagination_meta(total=100, page=1, size=10)
    assert meta["pages"] == 10
    assert meta["total"] == 100


def test_create_pagination_meta_zero_size():
    """create_pagination_meta with size=0 returns pages=0 (edge case)."""
    from app.schemas.base import create_pagination_meta

    meta = create_pagination_meta(total=100, page=1, size=0)
    assert meta["pages"] == 0


def test_app_error_hierarchy():
    """AppError subclasses carry correct status_code and title."""
    from app.core.exceptions import (
        AppValidationError,
        ConflictError,
        ForbiddenError,
        NotFoundError,
        UnauthorizedError,
    )

    assert NotFoundError("x").status_code == 404
    assert ConflictError("x").status_code == 409
    assert AppValidationError("x").status_code == 422
    assert UnauthorizedError("x").status_code == 401
    assert ForbiddenError("x").status_code == 403


def test_problem_detail_extra_fields():
    """ProblemDetail with extra='allow' accepts arbitrary RFC 7807 extensions."""
    from app.schemas.base import ProblemDetail

    p = ProblemDetail(
        type="about:blank",
        title="Test",
        status=400,
        detail="test detail",
        instance="/test",
        custom_extension="value",  # type: ignore[call-arg]
    )
    dumped = p.model_dump()
    assert dumped["custom_extension"] == "value"


@pytest.mark.asyncio
async def test_v1_health_db_failure_returns_503(async_client: AsyncClient):
    """Simulate DB failure -> /api/v1/health returns 503."""
    from unittest.mock import AsyncMock, patch

    from sqlalchemy.exc import OperationalError

    with patch(
        "app.db.session.get_session_factory",
        return_value=lambda: AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    execute=AsyncMock(
                        side_effect=OperationalError("conn", None, Exception("DB down"))
                    )
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 503
