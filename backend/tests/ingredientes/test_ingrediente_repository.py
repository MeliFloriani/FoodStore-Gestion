"""
Unit/integration tests for IngredienteRepository.

TDD: tests written before implementation.
Uses the SAVEPOINT-based async_session fixture from conftest.py.
All DB mutations are rolled back after each test.

Tasks 3.1–3.10: repository method tests.
Note: These tests require a live test database.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.catalog import Ingrediente
from app.repositories.ingrediente import IngredienteRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ingrediente(
    nombre: str,
    es_alergeno: bool = False,
) -> Ingrediente:
    """Build an unsaved Ingrediente for testing."""
    return Ingrediente(nombre=nombre, es_alergeno=es_alergeno)


# ---------------------------------------------------------------------------
# Task 3.1 — list_active returns ordered by nombre ASC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_returns_ordered_by_nombre(async_session) -> None:
    """list_active() returns 3 active ingredients ordered by nombre ASC.

    Task 3.1.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    # Create with non-alphabetical insertion order
    await repo.create(_make_ingrediente(f"Zanahoria_{suffix}"))
    await repo.create(_make_ingrediente(f"Azucar_{suffix}"))
    await repo.create(_make_ingrediente(f"Miel_{suffix}"))

    results = await repo.list_active()
    # Filter to our test items
    our_items = [r for r in results if r.nombre.endswith(f"_{suffix}")]

    assert len(our_items) == 3
    nombres = [r.nombre for r in our_items]
    assert nombres == sorted(nombres), f"Expected ASC order, got: {nombres}"


# ---------------------------------------------------------------------------
# Task 3.2 — list_active filters by es_alergeno=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_filters_by_es_alergeno_true(async_session) -> None:
    """list_active(es_alergeno=True) returns only allergen ingredients.

    Task 3.2.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    await repo.create(_make_ingrediente(f"Gluten_{suffix}", es_alergeno=True))
    await repo.create(_make_ingrediente(f"Sal_{suffix}", es_alergeno=False))
    await repo.create(_make_ingrediente(f"Lactosa_{suffix}", es_alergeno=True))

    results = await repo.list_active(es_alergeno=True)
    our_items = [r for r in results if r.nombre.endswith(f"_{suffix}")]

    assert len(our_items) == 2
    for item in our_items:
        assert item.es_alergeno is True


# ---------------------------------------------------------------------------
# Task 3.3 — list_active filters by es_alergeno=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_filters_by_es_alergeno_false(async_session) -> None:
    """list_active(es_alergeno=False) returns only non-allergen ingredients.

    Task 3.3.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    await repo.create(_make_ingrediente(f"Gluten_{suffix}", es_alergeno=True))
    await repo.create(_make_ingrediente(f"Sal_{suffix}", es_alergeno=False))
    await repo.create(_make_ingrediente(f"Harina_{suffix}", es_alergeno=False))

    results = await repo.list_active(es_alergeno=False)
    our_items = [r for r in results if r.nombre.endswith(f"_{suffix}")]

    assert len(our_items) == 2
    for item in our_items:
        assert item.es_alergeno is False


# ---------------------------------------------------------------------------
# Task 3.4 — list_active excludes soft-deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_excludes_soft_deleted(async_session) -> None:
    """list_active() does not return soft-deleted ingredients.

    Task 3.4.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    active = await repo.create(_make_ingrediente(f"Active_{suffix}"))
    deleted = await repo.create(_make_ingrediente(f"Deleted_{suffix}"))
    await repo.soft_delete(deleted.id)

    results = await repo.list_active()
    our_ids = {r.id for r in results if r.nombre.endswith(f"_{suffix}")}

    assert active.id in our_ids, "Active ingredient should appear in list"
    assert deleted.id not in our_ids, "Soft-deleted ingredient must not appear in list"


# ---------------------------------------------------------------------------
# Task 3.5 — get_by_nombre_active returns None for soft-deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_nombre_active_returns_none_for_deleted(async_session) -> None:
    """get_by_nombre_active() returns None for a soft-deleted ingredient.

    Task 3.5.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]
    nombre = f"Tomate_{suffix}"

    created = await repo.create(_make_ingrediente(nombre))
    await repo.soft_delete(created.id)

    result = await repo.get_by_nombre_active(nombre)
    assert result is None


# ---------------------------------------------------------------------------
# Task 3.6 — get_by_nombre_active returns ingredient when active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_nombre_active_returns_ingredient_when_active(async_session) -> None:
    """get_by_nombre_active() returns the active ingredient found by exact nombre.

    Task 3.6.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]
    nombre = f"Pimienta_{suffix}"

    created = await repo.create(_make_ingrediente(nombre, es_alergeno=False))

    result = await repo.get_by_nombre_active(nombre)
    assert result is not None
    assert result.id == created.id
    assert result.nombre == nombre


# ---------------------------------------------------------------------------
# Task 3.10 — smoke test: BaseRepository methods work for Ingrediente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_base_repository_get_by_id_works(async_session) -> None:
    """BaseRepository.get_by_id returns the created Ingrediente by UUID.

    Task 3.10: smoke test for inherited BaseRepository methods.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    created = await repo.create(_make_ingrediente(f"Oregano_{suffix}"))
    found = await repo.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_base_repository_update_takes_id_and_dict(async_session) -> None:
    """BaseRepository.update(id, dict) updates the given fields.

    Task 3.10: verify update(id, dict) signature — NOT update(entity).
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    created = await repo.create(_make_ingrediente(f"Cilantro_{suffix}", es_alergeno=False))
    updated = await repo.update(created.id, {"es_alergeno": True})

    assert updated is not None
    assert updated.es_alergeno is True


@pytest.mark.asyncio
async def test_base_repository_soft_delete_works(async_session) -> None:
    """BaseRepository.soft_delete marks the ingredient as deleted.

    Task 3.10: verify soft_delete behaviour for Ingrediente.
    """
    repo = IngredienteRepository(async_session)
    suffix = uuid.uuid4().hex[:8]

    created = await repo.create(_make_ingrediente(f"Cebolla_{suffix}"))
    result = await repo.soft_delete(created.id)

    assert result is True
    found = await repo.get_by_id(created.id)  # default: active-only
    assert found is None  # soft-deleted; not returned by default

    found_deleted = await repo.get_by_id(created.id, include_deleted=True)
    assert found_deleted is not None
    assert found_deleted.deleted_at is not None
