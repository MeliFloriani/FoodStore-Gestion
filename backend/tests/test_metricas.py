"""
Tests for admin metrics endpoints — Change 23: admin-metrics-dashboard.

Coverage:
  Unit:
    - _resolve_date_range: default range, explicit range, half-open boundary,
      desde > hasta raises 422.

  RBAC / Auth:
    - GET /api/v1/admin/metricas/resumen: ADMIN → 200, CLIENT → 403, anon → 401
    - GET /api/v1/admin/metricas/ventas: valid granularity → 200, invalid → 422
    - GET /api/v1/admin/metricas/productos-top: ADMIN → 200
    - GET /api/v1/admin/metricas/pedidos-por-estado: ADMIN → 200

All integration tests use the seeded_session + async_client fixtures with the
SAVEPOINT-based rollback pattern for test isolation.

Architecture note:
  MetricasRepository uses uow.session — the tests exercise the full stack
  via the FastAPI ASGI transport. Data isolation is guaranteed by SAVEPOINT
  rollback in conftest.py (no data persists after tests).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uow import get_uow
from app.main import app
from app.modules.admin.metricas.service import _resolve_date_range
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "Secur3Pass!",
) -> str:
    """Register a user (gets CLIENT role) and return access_token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Test",
            "apellido": "Metricas",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


async def _promote_to_role(session: AsyncSession, email: str, role_code: str) -> None:
    """Assign an additional role to a user by manipulating the session directly."""
    from sqlalchemy import select

    from app.models.user import Rol, Usuario, UsuarioRol

    user = (await session.execute(select(Usuario).where(Usuario.email == email))).scalar_one()
    rol = (await session.execute(select(Rol).where(Rol.codigo == role_code))).scalar_one()

    usuario_rol = UsuarioRol(id=uuid.uuid4(), usuario_id=user.id, rol_id=rol.id)
    session.add(usuario_rol)
    await session.flush()


# ---------------------------------------------------------------------------
# Unit tests — _resolve_date_range
# ---------------------------------------------------------------------------


class TestResolveDateRange:
    def test_default_range_is_last_30_days(self) -> None:
        """When both desde and hasta are None, returns last 30 days."""
        desde_dt, hasta_dt = _resolve_date_range(None, None)
        today = date.today()
        expected_desde = datetime.combine(today - timedelta(days=30), time.min)
        expected_hasta = datetime.combine(today + timedelta(days=1), time.min)
        assert desde_dt == expected_desde
        assert hasta_dt == expected_hasta

    def test_explicit_range(self) -> None:
        """Explicit dates are converted to naive datetime half-open interval."""
        desde = date(2026, 1, 1)
        hasta = date(2026, 1, 31)
        desde_dt, hasta_dt = _resolve_date_range(desde, hasta)
        assert desde_dt == datetime(2026, 1, 1, 0, 0, 0)
        assert hasta_dt == datetime(2026, 2, 1, 0, 0, 0)  # hasta+1day

    def test_half_open_boundary_single_day(self) -> None:
        """A single-day range results in [day 00:00:00, day+1 00:00:00)."""
        d = date(2026, 6, 3)
        desde_dt, hasta_dt = _resolve_date_range(d, d)
        assert desde_dt == datetime(2026, 6, 3, 0, 0, 0)
        assert hasta_dt == datetime(2026, 6, 4, 0, 0, 0)

    def test_datetimes_are_naive(self) -> None:
        """Returned datetimes must be naive (no tzinfo) for PostgreSQL naive columns."""
        desde_dt, hasta_dt = _resolve_date_range(date(2026, 1, 1), date(2026, 1, 31))
        assert desde_dt.tzinfo is None
        assert hasta_dt.tzinfo is None

    def test_desde_greater_than_hasta_raises_422(self) -> None:
        """desde > hasta raises HTTPException 422."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _resolve_date_range(date(2026, 2, 1), date(2026, 1, 1))
        assert exc_info.value.status_code == 422

    def test_default_hasta_is_today(self) -> None:
        """When hasta is None, hasta defaults to today."""
        _, hasta_dt = _resolve_date_range(date(2026, 1, 1), None)
        today = date.today()
        assert hasta_dt == datetime.combine(today + timedelta(days=1), time.min)


# ---------------------------------------------------------------------------
# Integration tests — RBAC / auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resumen_admin_gets_200(seeded_session: AsyncSession, async_client: AsyncClient) -> None:
    """ADMIN role gets HTTP 200 from GET /resumen."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_resumen@test.com")
    await _promote_to_role(seeded_session, "admin_resumen@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/resumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ventas_totales" in data
    assert "pedidos_por_estado" in data
    assert "usuarios_total" in data
    assert "usuarios_activos" in data
    # ventas_totales must be a string (Decimal → str serialization)
    assert isinstance(data["ventas_totales"], str)


@pytest.mark.asyncio
async def test_resumen_client_gets_403(seeded_session: AsyncSession, async_client: AsyncClient) -> None:
    """CLIENT role gets HTTP 403 from GET /resumen (ADMIN-only endpoint)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "client_resumen@test.com")

    response = await async_client.get(
        "/api/v1/admin/metricas/resumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resumen_unauthenticated_gets_401(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """Unauthenticated request gets HTTP 401 from GET /resumen."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)

    response = await async_client.get("/api/v1/admin/metricas/resumen")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ventas_valid_granularity_gets_200(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """ADMIN gets HTTP 200 from GET /ventas with valid granularidad."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_ventas@test.com")
    await _promote_to_role(seeded_session, "admin_ventas@test.com", "ADMIN")

    for gran in ["dia", "semana", "mes"]:
        response = await async_client.get(
            "/api/v1/admin/metricas/ventas",
            params={"granularidad": gran},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, f"Expected 200 for granularidad={gran}, got {response.status_code}"
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_ventas_invalid_granularity_gets_422(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """Invalid granularidad returns HTTP 422 (Pydantic validation)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_ventas422@test.com")
    await _promote_to_role(seeded_session, "admin_ventas422@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/ventas",
        params={"granularidad": "hora"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_productos_top_admin_gets_200(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """ADMIN gets HTTP 200 from GET /productos-top."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_productos@test.com")
    await _promote_to_role(seeded_session, "admin_productos@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/productos-top",
        params={"top": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    # Empty result is valid — no orders in test DB
    assert len(response.json()) <= 5


@pytest.mark.asyncio
async def test_pedidos_por_estado_admin_gets_200(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """ADMIN gets HTTP 200 from GET /pedidos-por-estado."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_estados@test.com")
    await _promote_to_role(seeded_session, "admin_estados@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/pedidos-por-estado",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_resumen_date_range_params_accepted(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """GET /resumen accepts desde/hasta params without error."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_daterange@test.com")
    await _promote_to_role(seeded_session, "admin_daterange@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/resumen",
        params={"desde": "2026-01-01", "hasta": "2026-01-31"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_resumen_invalid_date_range_returns_422(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """GET /resumen with desde > hasta returns HTTP 422."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_invdate@test.com")
    await _promote_to_role(seeded_session, "admin_invdate@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/resumen",
        params={"desde": "2026-02-01", "hasta": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ventas_totales_is_string(
    seeded_session: AsyncSession, async_client: AsyncClient
) -> None:
    """ventas_totales is returned as a string (Decimal serialization)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    token = await _register_and_login(async_client, "admin_decimal@test.com")
    await _promote_to_role(seeded_session, "admin_decimal@test.com", "ADMIN")

    response = await async_client.get(
        "/api/v1/admin/metricas/resumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # Verify it's a string, not a float
    assert isinstance(data["ventas_totales"], str)
    # Verify it's parseable as a decimal number
    Decimal(data["ventas_totales"])  # raises InvalidOperation if not a valid decimal
