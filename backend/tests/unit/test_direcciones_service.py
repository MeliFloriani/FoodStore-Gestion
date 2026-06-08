"""
Unit tests for DireccionEntregaService.

Change 14: delivery-addresses-management.

Tests written per spec backend-direcciones-management/spec.md.
Uses unittest.mock to isolate service from real DB.

Scenarios covered:
  - First address gets es_principal=True (no limpiar_principal for count>0)
  - Limit of 20 active addresses → HTTPException(400)
  - marcar_principal idempotence when already principal
  - Auto-promote when principal is deleted and others exist
  - No promote when the only address is deleted
  - Ownership violation → HTTPException(404)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.direccion_entrega import DireccionEntregaCreate, DireccionEntregaUpdate
from app.services.direccion_entrega import DireccionEntregaService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_direccion(
    id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    linea1: str = "Av. Siempre Viva 742",
    es_principal: bool = False,
    deleted_at: datetime | None = None,
) -> MagicMock:
    """Build a fake DireccionEntrega ORM object (MagicMock with required attributes)."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.usuario_id = usuario_id or uuid.uuid4()
    obj.alias = None
    obj.linea1 = linea1
    obj.linea2 = None
    obj.ciudad = None
    obj.provincia = None
    obj.codigo_postal = None
    obj.referencia = None
    obj.es_principal = es_principal
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    obj.deleted_at = deleted_at
    # soft_delete sets deleted_at to now
    def _soft_delete():
        obj.deleted_at = datetime.now(timezone.utc)
    obj.soft_delete = _soft_delete
    return obj


def _make_direcciones_repo(**kwargs) -> MagicMock:
    """Build a mock DireccionEntregaRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.session = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()
    repo.get_by_id_and_usuario = AsyncMock(return_value=kwargs.get("get_by_id_and_usuario", None))
    repo.get_activos_por_usuario = AsyncMock(return_value=kwargs.get("get_activos_por_usuario", []))
    repo.count_activos_por_usuario = AsyncMock(return_value=kwargs.get("count_activos_por_usuario", 0))
    repo.limpiar_principal = AsyncMock()
    repo.set_principal = AsyncMock()
    repo.get_mas_reciente_activa = AsyncMock(return_value=kwargs.get("get_mas_reciente_activa", None))
    repo.create = AsyncMock(side_effect=kwargs.get("create_side_effect", None))
    if "create_return" in kwargs:
        repo.create = AsyncMock(return_value=kwargs["create_return"])
    return repo


def _make_uow(repo: MagicMock) -> MagicMock:
    """Build a fake UoW with a mock direcciones repo."""
    uow = MagicMock()
    uow.direcciones = repo
    return uow


# ---------------------------------------------------------------------------
# Task 6.1 — Primera dirección → es_principal=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_direccion_primera_es_principal() -> None:
    """First address for a user should be forced to es_principal=True."""
    usuario_id = uuid.uuid4()
    fake_dir = _make_fake_direccion(usuario_id=usuario_id, es_principal=True)
    repo = _make_direcciones_repo(
        count_activos_por_usuario=0,
        create_return=fake_dir,
    )
    uow = _make_uow(repo)

    data = DireccionEntregaCreate(linea1="Av. Siempre Viva 742")
    result = await DireccionEntregaService.crear_direccion(uow, usuario_id, data)

    # es_principal must be True for first address
    assert result.es_principal is True
    # limpiar_principal called as defensive measure
    repo.limpiar_principal.assert_awaited_once_with(usuario_id)


@pytest.mark.asyncio
async def test_crear_direccion_segunda_no_limpia_principal() -> None:
    """Second+ address must NOT call limpiar_principal — would deactivate existing principal."""
    usuario_id = uuid.uuid4()
    fake_dir = _make_fake_direccion(usuario_id=usuario_id, es_principal=False)
    repo = _make_direcciones_repo(
        count_activos_por_usuario=1,  # already has one address
        create_return=fake_dir,
    )
    uow = _make_uow(repo)

    data = DireccionEntregaCreate(linea1="Calle Falsa 123")
    result = await DireccionEntregaService.crear_direccion(uow, usuario_id, data)

    # Second address is NOT principal
    assert result.es_principal is False
    # CRITICAL: limpiar_principal must NOT be called (would kill existing principal)
    repo.limpiar_principal.assert_not_awaited()


# ---------------------------------------------------------------------------
# Task 6.4 — Límite de 20 direcciones activas → HTTPException(400)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_direccion_limite_20_lanza_400() -> None:
    """Creating a 21st address raises HTTPException(400)."""
    usuario_id = uuid.uuid4()
    repo = _make_direcciones_repo(count_activos_por_usuario=20)
    uow = _make_uow(repo)

    data = DireccionEntregaCreate(linea1="Av. Limite 20")
    with pytest.raises(HTTPException) as exc_info:
        await DireccionEntregaService.crear_direccion(uow, usuario_id, data)

    assert exc_info.value.status_code == 400
    assert "límite" in exc_info.value.detail.lower() or "20" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Task 6.1 — marcar_principal idempotente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marcar_principal_idempotente() -> None:
    """marcar_principal on an already-principal address returns 200 without DB writes."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    fake_dir = _make_fake_direccion(id=addr_id, usuario_id=usuario_id, es_principal=True)
    repo = _make_direcciones_repo(get_by_id_and_usuario=fake_dir)
    uow = _make_uow(repo)

    result = await DireccionEntregaService.marcar_principal(uow, usuario_id, addr_id)

    assert result.es_principal is True
    # No DB writes for idempotent case
    repo.limpiar_principal.assert_not_awaited()
    repo.set_principal.assert_not_awaited()


@pytest.mark.asyncio
async def test_marcar_principal_desactiva_anterior() -> None:
    """marcar_principal calls limpiar_principal then set_principal."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    fake_dir = _make_fake_direccion(id=addr_id, usuario_id=usuario_id, es_principal=False)
    repo = _make_direcciones_repo(get_by_id_and_usuario=fake_dir)
    uow = _make_uow(repo)

    # After set_principal, the object should reflect es_principal=True
    async def _refresh(obj):
        obj.es_principal = True
    repo.session.refresh = AsyncMock(side_effect=_refresh)

    await DireccionEntregaService.marcar_principal(uow, usuario_id, addr_id)

    repo.limpiar_principal.assert_awaited_once_with(usuario_id)
    repo.set_principal.assert_awaited_once_with(addr_id)


# ---------------------------------------------------------------------------
# Task 6.2 — eliminar_direccion con auto-promote
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eliminar_principal_con_otras_auto_promueve() -> None:
    """Deleting the principal address auto-promotes the most recent active address."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    candidata_id = uuid.uuid4()

    # The address to delete is principal
    fake_dir = _make_fake_direccion(id=addr_id, usuario_id=usuario_id, es_principal=True)
    # There is another active address to promote
    candidata = _make_fake_direccion(id=candidata_id, usuario_id=usuario_id, es_principal=False)

    repo = _make_direcciones_repo(
        get_by_id_and_usuario=fake_dir,
        get_mas_reciente_activa=candidata,
    )
    uow = _make_uow(repo)

    await DireccionEntregaService.eliminar_direccion(uow, usuario_id, addr_id)

    # set_principal called with the candidate's id
    repo.set_principal.assert_awaited_once_with(candidata_id)
    # limpiar_principal NOT called during auto-promote (post-soft-delete, no-op)
    repo.limpiar_principal.assert_not_awaited()


# ---------------------------------------------------------------------------
# Task 6.3 — eliminar_direccion única dirección → sin error, sin principal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eliminar_unica_direccion_sin_error() -> None:
    """Deleting the only address does not auto-promote and does not raise."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    fake_dir = _make_fake_direccion(id=addr_id, usuario_id=usuario_id, es_principal=True)

    repo = _make_direcciones_repo(
        get_by_id_and_usuario=fake_dir,
        get_mas_reciente_activa=None,  # no other active addresses
    )
    uow = _make_uow(repo)

    # Should complete without raising
    result = await DireccionEntregaService.eliminar_direccion(uow, usuario_id, addr_id)

    assert result is None
    repo.set_principal.assert_not_awaited()


# ---------------------------------------------------------------------------
# Task 6.5 — Ownership violation → HTTPException(404)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_direccion_ajena_lanza_404() -> None:
    """obtener_direccion for an address owned by another user raises HTTPException(404)."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    # repo returns None — address belongs to a different user
    repo = _make_direcciones_repo(get_by_id_and_usuario=None)
    uow = _make_uow(repo)

    with pytest.raises(HTTPException) as exc_info:
        await DireccionEntregaService.obtener_direccion(uow, usuario_id, addr_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_actualizar_direccion_ajena_lanza_404() -> None:
    """actualizar_direccion for an address owned by another user raises HTTPException(404)."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    repo = _make_direcciones_repo(get_by_id_and_usuario=None)
    uow = _make_uow(repo)

    data = DireccionEntregaUpdate(alias="Trabajo")
    with pytest.raises(HTTPException) as exc_info:
        await DireccionEntregaService.actualizar_direccion(uow, usuario_id, addr_id, data)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_marcar_principal_ajena_lanza_404() -> None:
    """marcar_principal for an address owned by another user raises HTTPException(404)."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    repo = _make_direcciones_repo(get_by_id_and_usuario=None)
    uow = _make_uow(repo)

    with pytest.raises(HTTPException) as exc_info:
        await DireccionEntregaService.marcar_principal(uow, usuario_id, addr_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_eliminar_direccion_ajena_lanza_404() -> None:
    """eliminar_direccion for an address owned by another user raises HTTPException(404)."""
    usuario_id = uuid.uuid4()
    addr_id = uuid.uuid4()
    repo = _make_direcciones_repo(get_by_id_and_usuario=None)
    uow = _make_uow(repo)

    with pytest.raises(HTTPException) as exc_info:
        await DireccionEntregaService.eliminar_direccion(uow, usuario_id, addr_id)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Task 6.1 — listar_direcciones returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_direcciones_retorna_lista() -> None:
    """listar_direcciones returns all active addresses for the user."""
    usuario_id = uuid.uuid4()
    fake_dirs = [
        _make_fake_direccion(usuario_id=usuario_id, es_principal=True),
        _make_fake_direccion(usuario_id=usuario_id, es_principal=False),
    ]
    repo = _make_direcciones_repo(get_activos_por_usuario=fake_dirs)
    uow = _make_uow(repo)

    result = await DireccionEntregaService.listar_direcciones(uow, usuario_id)

    assert len(result) == 2
