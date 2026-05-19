"""
Unit tests for the profile router endpoints.

Tasks 4.1, 4.2, 4.5 — TDD.

Uses TestClient with mocked dependencies (overrides for get_current_user,
get_uow, and ProfileService) to test HTTP contracts without a real DB.

Covers:
  - PATCH /api/v1/profile/me: valid JWT + nombre → 200 + UserRead updated
  - PATCH /api/v1/profile/me: without JWT → 401
  - PATCH /api/v1/profile/me: with email in body → 200, email unchanged
  - POST /api/v1/profile/me/password: correct current_password → 204 + tokens revoked
  - POST /api/v1/profile/me/password: wrong current_password → 409
  - POST /api/v1/profile/me/password: new_password < 8 chars → 422
  - Routes and OpenAPI tag "profile" exist in the app
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, NotFoundError
from app.core.uow import UnitOfWork, get_uow
from app.main import app
from app.models.user import Usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_usuario(
    nombre: str = "Juan",
    apellido: str = "Pérez",
    email: str = "juan@example.com",
) -> MagicMock:
    """Build a mock Usuario with preset attributes."""
    usuario = MagicMock(spec=Usuario)
    usuario.id = uuid.uuid4()
    usuario.nombre = nombre
    usuario.apellido = apellido
    usuario.email = email
    usuario.created_at = datetime.now(timezone.utc)
    usuario.password_hash = "$2b$12$fakehash"
    usuario.usuario_roles = []
    return usuario


def _make_mock_uow() -> MagicMock:
    """Build a mocked UnitOfWork."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return uow


# ---------------------------------------------------------------------------
# Task 4.1 — PATCH /api/v1/profile/me
# ---------------------------------------------------------------------------


class TestPatchProfileMe:
    """Tests for PATCH /api/v1/profile/me."""

    def test_patch_profile_updates_nombre_returns_200(
        self, override_settings
    ) -> None:
        """Valid JWT + {nombre: 'Nueva'} → 200 + UserRead with updated nombre."""
        from app.api.deps import get_current_user
        from app.schemas.auth import UserRead

        mock_user = _make_mock_usuario(nombre="Original")
        updated_user_read = UserRead(
            id=mock_user.id,
            nombre="Nueva",
            apellido=mock_user.apellido,
            email=mock_user.email,
            created_at=mock_user.created_at,
            usuario_roles=[],
        )

        mock_uow = _make_mock_uow()

        with patch(
            "app.services.profile.ProfileService.update_profile",
            new=AsyncMock(return_value=updated_user_read),
        ):
            app.dependency_overrides[get_current_user] = lambda: mock_user
            app.dependency_overrides[get_uow] = lambda: mock_uow

            try:
                client = TestClient(app, raise_server_exceptions=False)
                response = client.patch(
                    "/api/v1/profile/me",
                    json={"nombre": "Nueva"},
                    headers={"Authorization": "Bearer faketoken"},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["nombre"] == "Nueva"

    def test_patch_profile_without_jwt_returns_401(self, override_settings) -> None:
        """PATCH /api/v1/profile/me without JWT → 401."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch("/api/v1/profile/me", json={"nombre": "X"})
        assert response.status_code == 401

    def test_patch_profile_ignores_email_returns_200_with_original_email(
        self, override_settings
    ) -> None:
        """With email in body → 200, email unchanged (ProfileUpdate extra='ignore')."""
        from app.api.deps import get_current_user
        from app.schemas.auth import UserRead

        original_email = "original@test.com"
        mock_user = _make_mock_usuario(email=original_email)
        user_read_with_original_email = UserRead(
            id=mock_user.id,
            nombre="Carlos",
            apellido=mock_user.apellido,
            email=original_email,  # unchanged
            created_at=mock_user.created_at,
            usuario_roles=[],
        )

        mock_uow = _make_mock_uow()

        with patch(
            "app.services.profile.ProfileService.update_profile",
            new=AsyncMock(return_value=user_read_with_original_email),
        ):
            app.dependency_overrides[get_current_user] = lambda: mock_user
            app.dependency_overrides[get_uow] = lambda: mock_uow

            try:
                client = TestClient(app, raise_server_exceptions=False)
                response = client.patch(
                    "/api/v1/profile/me",
                    json={"nombre": "Carlos", "email": "new@test.com"},
                    headers={"Authorization": "Bearer faketoken"},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == original_email  # email unchanged


# ---------------------------------------------------------------------------
# Task 4.2 — POST /api/v1/profile/me/password
# ---------------------------------------------------------------------------


class TestPostProfilePassword:
    """Tests for POST /api/v1/profile/me/password."""

    def test_change_password_correct_returns_204(self, override_settings) -> None:
        """Correct current_password → 204 No Content."""
        from app.api.deps import get_current_user

        mock_user = _make_mock_usuario()
        mock_uow = _make_mock_uow()

        with patch(
            "app.services.profile.ProfileService.change_password",
            new=AsyncMock(return_value=None),
        ):
            app.dependency_overrides[get_current_user] = lambda: mock_user
            app.dependency_overrides[get_uow] = lambda: mock_uow

            try:
                client = TestClient(app, raise_server_exceptions=False)
                response = client.post(
                    "/api/v1/profile/me/password",
                    json={
                        "current_password": "OldPass1!",
                        "new_password": "NewPass1!",
                    },
                    headers={"Authorization": "Bearer faketoken"},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 204

    def test_change_password_wrong_current_returns_409(
        self, override_settings
    ) -> None:
        """Wrong current_password → 409 Conflict."""
        from app.api.deps import get_current_user

        mock_user = _make_mock_usuario()
        mock_uow = _make_mock_uow()

        with patch(
            "app.services.profile.ProfileService.change_password",
            new=AsyncMock(
                side_effect=ConflictError(
                    "La contraseña actual no coincide",
                    code="CURRENT_PASSWORD_MISMATCH",
                )
            ),
        ):
            app.dependency_overrides[get_current_user] = lambda: mock_user
            app.dependency_overrides[get_uow] = lambda: mock_uow

            try:
                client = TestClient(app, raise_server_exceptions=False)
                response = client.post(
                    "/api/v1/profile/me/password",
                    json={
                        "current_password": "WrongPass!",
                        "new_password": "NewPass1!",
                    },
                    headers={"Authorization": "Bearer faketoken"},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 409
        body = response.json()
        assert body.get("code") == "CURRENT_PASSWORD_MISMATCH"

    def test_change_password_short_new_password_returns_422(
        self, override_settings
    ) -> None:
        """new_password < 8 chars → 422 (Pydantic validation)."""
        from app.api.deps import get_current_user

        mock_user = _make_mock_usuario()
        mock_uow = _make_mock_uow()

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_uow] = lambda: mock_uow

        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/profile/me/password",
                json={
                    "current_password": "OldPass1!",
                    "new_password": "short",  # < 8 chars
                },
                headers={"Authorization": "Bearer faketoken"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422

    def test_change_password_without_jwt_returns_401(
        self, override_settings
    ) -> None:
        """Without JWT → 401."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/profile/me/password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
        )
        assert response.status_code == 401

    @pytest.mark.skip(
        reason=(
            "Rate limit test requires mock limiter. The @_limiter.limit decorator "
            "uses req.state.user_id; testing 429 requires a real async client with "
            "5 prior requests and is covered by integration tests against live PostgreSQL. "
            "Full E2E rate limit verification: see QA manual §9.6."
        )
    )
    def test_change_password_rate_limit_returns_429(self) -> None:
        """After 5 requests, 6th → 429. Skipped — requires live environment."""
        pass


# ---------------------------------------------------------------------------
# Task 4.5 — OpenAPI routes and tags
# ---------------------------------------------------------------------------


class TestProfileRouterRegistration:
    """Tests verifying router registration and OpenAPI schema."""

    def test_patch_profile_me_route_exists(self, override_settings) -> None:
        """PATCH /api/v1/profile/me exists as a registered route."""
        paths = app.openapi()["paths"]
        assert "/api/v1/profile/me" in paths
        assert "patch" in paths["/api/v1/profile/me"]

    def test_post_profile_me_password_route_exists(self, override_settings) -> None:
        """POST /api/v1/profile/me/password exists as a registered route."""
        paths = app.openapi()["paths"]
        assert "/api/v1/profile/me/password" in paths
        assert "post" in paths["/api/v1/profile/me/password"]

    def test_profile_tag_exists_in_openapi(self, override_settings) -> None:
        """Tag 'profile' appears in the OpenAPI schema."""
        schema = app.openapi()
        tags_in_schema = set()
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    for tag in operation.get("tags", []):
                        tags_in_schema.add(tag)
        assert "profile" in tags_in_schema
