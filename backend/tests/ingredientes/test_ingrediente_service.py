"""
Unit tests for IngredienteService.

TDD: tests written before implementation.
Uses unittest.mock to isolate service from real DB.

Tasks 4.1–4.12.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.ingrediente import IngredienteCreate, IngredienteUpdate
from app.services.ingrediente import IngredienteService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_ingrediente(
    id: uuid.UUID | None = None,
    nombre: str = "Sal",
    es_alergeno: bool = False,
    deleted_at: datetime | None = None,
) -> MagicMock:
    """Build a fake Ingrediente ORM object (MagicMock with required attributes)."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.nombre = nombre
    obj.es_alergeno = es_alergeno
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    obj.deleted_at = deleted_at
    return obj


def _make_uow(ingredientes_repo: MagicMock) -> MagicMock:
    """Build a fake UoW with a mock ingredientes repo."""
    uow = MagicMock()
    uow.ingredientes = ingredientes_repo
    return uow


def _make_repo(**kwargs) -> MagicMock:
    """Build a mock IngredienteRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=kwargs.get("get_by_id", None))
    repo.list_active = AsyncMock(return_value=kwargs.get("list_active", []))
    repo.create = AsyncMock(side_effect=kwargs.get("create", None))
    repo.update = AsyncMock(return_value=kwargs.get("update", None))
    repo.soft_delete = AsyncMock(return_value=kwargs.get("soft_delete", True))
    repo.get_by_nombre_active = AsyncMock(return_value=kwargs.get("get_by_nombre_active", None))
    return repo


# ---------------------------------------------------------------------------
# Task 4.1 — test_create_valid_ingrediente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_valid_ingrediente() -> None:
    """create_ingrediente with valid data creates and returns IngredienteRead.

    Task 4.1.
    """
    ing_id = uuid.uuid4()
    fake_ing = _make_fake_ingrediente(id=ing_id, nombre="Sal", es_alergeno=False)

    async def _create(obj):
        return fake_ing

    repo = _make_repo(create=_create)
    uow = _make_uow(repo)

    data = IngredienteCreate(nombre="Sal", es_alergeno=False)
    result = await IngredienteService.create_ingrediente(data, uow)

    assert result.id == ing_id
    assert result.nombre == "Sal"
    assert result.es_alergeno is False


# ---------------------------------------------------------------------------
# Task 4.2 — test_create_duplicate_nombre_raises_409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_duplicate_nombre_raises_409() -> None:
    """create_ingrediente raises ConflictError on IntegrityError (duplicate nombre).

    Task 4.2.
    """

    async def _create_raises(obj):
        raise IntegrityError("unique violation", {}, None)

    repo = _make_repo(create=_create_raises)
    uow = _make_uow(repo)

    data = IngredienteCreate(nombre="Sal")
    with pytest.raises(ConflictError) as exc_info:
        await IngredienteService.create_ingrediente(data, uow)

    assert exc_info.value.code == "INGREDIENT_NAME_DUPLICATE"


# ---------------------------------------------------------------------------
# Task 4.3 — test_create_soft_deleted_nombre_allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_soft_deleted_nombre_allowed() -> None:
    """create_ingrediente with same nombre as soft-deleted ingredient succeeds.

    Task 4.3: partial index allows name reuse after soft delete — no IntegrityError.
    """
    ing_id = uuid.uuid4()
    fake_ing = _make_fake_ingrediente(id=ing_id, nombre="Sal")

    async def _create(obj):
        return fake_ing  # no IntegrityError raised

    repo = _make_repo(create=_create)
    uow = _make_uow(repo)

    data = IngredienteCreate(nombre="Sal")
    result = await IngredienteService.create_ingrediente(data, uow)
    assert result.id == ing_id


# ---------------------------------------------------------------------------
# Task 4.4 — test_get_ingrediente_not_found_raises_404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingrediente_not_found_raises_404() -> None:
    """get_ingrediente raises NotFoundError when repo returns None.

    Task 4.4.
    """
    repo = _make_repo(get_by_id=None)
    uow = _make_uow(repo)

    with pytest.raises(NotFoundError) as exc_info:
        await IngredienteService.get_ingrediente(uuid.uuid4(), uow)

    assert exc_info.value.code == "INGREDIENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.5 — test_get_ingrediente_soft_deleted_raises_404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingrediente_soft_deleted_raises_404() -> None:
    """get_ingrediente raises NotFoundError for soft-deleted ingredient.

    Task 4.5: BaseRepository.get_by_id returns None for soft-deleted records
    (default active-only filter). So service sees None and raises NotFoundError.
    """
    # Repo returns None (soft-deleted → filtered out by get_by_id default)
    repo = _make_repo(get_by_id=None)
    uow = _make_uow(repo)

    with pytest.raises(NotFoundError) as exc_info:
        await IngredienteService.get_ingrediente(uuid.uuid4(), uow)

    assert exc_info.value.code == "INGREDIENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.6 — test_update_ingrediente_nombre_only_preserves_es_alergeno
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ingrediente_nombre_only_preserves_es_alergeno() -> None:
    """update_ingrediente with only nombre in payload preserves es_alergeno.

    Task 4.6: model_fields_set — 'es_alergeno' absent from payload → not included
    in update_data → repo.update called with only {'nombre': 'Sal marina'}.
    """
    ing_id = uuid.uuid4()
    existing = _make_fake_ingrediente(id=ing_id, nombre="Sal", es_alergeno=True)
    updated_entity = _make_fake_ingrediente(id=ing_id, nombre="Sal marina", es_alergeno=True)

    repo = _make_repo(get_by_id=existing, update=updated_entity)
    uow = _make_uow(repo)

    data = IngredienteUpdate(nombre="Sal marina")
    # "es_alergeno" must NOT be in model_fields_set
    assert "es_alergeno" not in data.model_fields_set

    result = await IngredienteService.update_ingrediente(ing_id, data, uow)

    # Verify repo.update was called with only nombre in update_data
    call_args = repo.update.call_args
    update_dict = call_args[0][1] if call_args[0] else call_args[1].get("data", {})
    assert "es_alergeno" not in update_dict, (
        f"es_alergeno should NOT be in update_data when absent from model_fields_set: {update_dict}"
    )
    assert "nombre" in update_dict
    assert result.nombre == "Sal marina"


# ---------------------------------------------------------------------------
# Task 4.7 — test_update_ingrediente_on_deleted_raises_404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ingrediente_on_deleted_raises_404() -> None:
    """update_ingrediente on a soft-deleted ingredient raises NotFoundError.

    Task 4.7: get_by_id returns None for soft-deleted → NotFoundError.
    """
    repo = _make_repo(get_by_id=None)
    uow = _make_uow(repo)

    data = IngredienteUpdate(nombre="Nuevo")
    with pytest.raises(NotFoundError) as exc_info:
        await IngredienteService.update_ingrediente(uuid.uuid4(), data, uow)

    assert exc_info.value.code == "INGREDIENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.8 — test_update_ingrediente_duplicate_nombre_raises_409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ingrediente_duplicate_nombre_raises_409() -> None:
    """update_ingrediente raises ConflictError on IntegrityError from duplicate nombre.

    Task 4.8.
    """
    ing_id = uuid.uuid4()
    existing = _make_fake_ingrediente(id=ing_id, nombre="Sal")

    repo = _make_repo(get_by_id=existing)
    repo.update = AsyncMock(side_effect=IntegrityError("unique violation", {}, None))
    uow = _make_uow(repo)

    data = IngredienteUpdate(nombre="Azucar")
    with pytest.raises(ConflictError) as exc_info:
        await IngredienteService.update_ingrediente(ing_id, data, uow)

    assert exc_info.value.code == "INGREDIENT_NAME_DUPLICATE"


# ---------------------------------------------------------------------------
# Task 4.9 — test_delete_ingrediente_calls_soft_delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_calls_soft_delete() -> None:
    """delete_ingrediente calls get_by_id first, then soft_delete.

    Task 4.9: mandatory pre-check before soft_delete (D-03).
    """
    ing_id = uuid.uuid4()
    existing = _make_fake_ingrediente(id=ing_id)

    repo = _make_repo(get_by_id=existing)
    uow = _make_uow(repo)

    await IngredienteService.delete_ingrediente(ing_id, uow)

    repo.get_by_id.assert_awaited_once_with(ing_id)
    repo.soft_delete.assert_awaited_once_with(ing_id)


# ---------------------------------------------------------------------------
# Task 4.10 — test_delete_ingrediente_not_found_raises_404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_not_found_raises_404() -> None:
    """delete_ingrediente raises NotFoundError when ingredient is absent.

    Task 4.10.
    """
    repo = _make_repo(get_by_id=None)
    uow = _make_uow(repo)

    with pytest.raises(NotFoundError) as exc_info:
        await IngredienteService.delete_ingrediente(uuid.uuid4(), uow)

    assert exc_info.value.code == "INGREDIENT_NOT_FOUND"
    repo.soft_delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Task 4.11 — test_list_ingredientes_no_filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_ingredientes_no_filter() -> None:
    """list_ingredientes(None) returns all active ingredients.

    Task 4.11.
    """
    fake_list = [
        _make_fake_ingrediente(nombre="Azucar"),
        _make_fake_ingrediente(nombre="Sal"),
    ]
    repo = _make_repo(list_active=fake_list)
    uow = _make_uow(repo)

    results = await IngredienteService.list_ingredientes(None, uow)

    repo.list_active.assert_awaited_once_with(None)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Task 4.12 — test_list_ingredientes_with_es_alergeno_filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_ingredientes_with_es_alergeno_filter() -> None:
    """list_ingredientes(True) passes es_alergeno=True filter to repo.

    Task 4.12.
    """
    fake_list = [_make_fake_ingrediente(nombre="Gluten", es_alergeno=True)]
    repo = _make_repo(list_active=fake_list)
    uow = _make_uow(repo)

    results = await IngredienteService.list_ingredientes(True, uow)

    repo.list_active.assert_awaited_once_with(True)
    assert len(results) == 1
    assert results[0].es_alergeno is True
