"""
Unit tests for CatalogPublicService.

Task 3.3 — verifies:
  - list_catalog assembles PaginatedCatalogProductos correctly.
  - get_catalog_detail raises NotFoundError when repo returns None.
  - excluir_alergenos validation raises 422 on bad input.
  - _to_publico_read maps tiene_stock correctly from stock_cantidad.
  - list_alergenos returns only allergen ingredients.
  - _parse_excluir_alergenos edge cases.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppValidationError, NotFoundError
from app.schemas.catalog_public import (
    CatalogProductosQuery,
    IngredientePublicoRead,
    PaginatedCatalogProductos,
    ProductoPublicoRead,
)
from app.services.catalog_public import CatalogPublicService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_producto_orm(
    stock_cantidad: int = 5,
    disponible: bool = True,
    precio_base: float = 10.00,
) -> MagicMock:
    """Build a fake Producto ORM object."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.nombre = "Pizza Test"
    p.descripcion = "Test description"
    p.imagen_url = None
    p.precio_base = precio_base
    p.stock_cantidad = stock_cantidad
    p.disponible = disponible
    p.deleted_at = None
    p.producto_categorias = []
    p.producto_ingredientes = []
    return p


def _make_ingrediente_orm(
    nombre: str = "Gluten",
    es_alergeno: bool = True,
) -> MagicMock:
    """Build a fake Ingrediente ORM object."""
    i = MagicMock()
    i.id = uuid.uuid4()
    i.nombre = nombre
    i.es_alergeno = es_alergeno
    i.deleted_at = None
    return i


def _make_uow(productos_repo=None, ingredientes_repo=None) -> MagicMock:
    """Build a fake UoW."""
    uow = MagicMock()
    if productos_repo is not None:
        uow.productos = productos_repo
    if ingredientes_repo is not None:
        uow.ingredientes = ingredientes_repo
    return uow


# ---------------------------------------------------------------------------
# _to_publico_read
# ---------------------------------------------------------------------------


class TestToPublicoRead:
    """Tests for CatalogPublicService._to_publico_read()."""

    def test_tiene_stock_true_when_stock_positive(self) -> None:
        """_to_publico_read must set tiene_stock=True when stock_cantidad > 0."""
        p = _make_producto_orm(stock_cantidad=5)
        result = CatalogPublicService._to_publico_read(p)
        assert result.tiene_stock is True

    def test_tiene_stock_false_when_stock_zero(self) -> None:
        """_to_publico_read must set tiene_stock=False when stock_cantidad == 0."""
        p = _make_producto_orm(stock_cantidad=0)
        result = CatalogPublicService._to_publico_read(p)
        assert result.tiene_stock is False

    def test_returns_producto_publico_read_instance(self) -> None:
        """_to_publico_read returns a ProductoPublicoRead instance."""
        p = _make_producto_orm()
        result = CatalogPublicService._to_publico_read(p)
        assert isinstance(result, ProductoPublicoRead)

    def test_precio_base_is_decimal(self) -> None:
        """_to_publico_read must convert precio_base to Decimal."""
        p = _make_producto_orm(precio_base=12.50)
        result = CatalogPublicService._to_publico_read(p)
        assert isinstance(result.precio_base, Decimal)

    def test_maps_all_fields(self) -> None:
        """_to_publico_read maps all expected fields correctly."""
        p = _make_producto_orm(stock_cantidad=3, disponible=True)
        p.nombre = "Test Producto"
        p.descripcion = "A description"
        p.imagen_url = "http://example.com/img.jpg"

        result = CatalogPublicService._to_publico_read(p)
        assert result.id == p.id
        assert result.nombre == "Test Producto"
        assert result.descripcion == "A description"
        assert result.imagen_url == "http://example.com/img.jpg"
        assert result.disponible is True


# ---------------------------------------------------------------------------
# _parse_excluir_alergenos
# ---------------------------------------------------------------------------


class TestParseExcluirAlergenos:
    """Tests for CatalogPublicService._parse_excluir_alergenos()."""

    def test_none_input_returns_none(self) -> None:
        """None input returns None (no filter)."""
        result = CatalogPublicService._parse_excluir_alergenos(None)
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None (no filter, no 422)."""
        result = CatalogPublicService._parse_excluir_alergenos("")
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string returns None (no filter, no 422)."""
        result = CatalogPublicService._parse_excluir_alergenos("   ")
        assert result is None

    def test_valid_single_uuid(self) -> None:
        """Single valid UUID returns list with one UUID element."""
        uid = uuid.uuid4()
        result = CatalogPublicService._parse_excluir_alergenos(str(uid))
        assert result == [uid]

    def test_valid_multiple_uuids(self) -> None:
        """Multiple valid comma-separated UUIDs return correct list."""
        uid1, uid2, uid3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        ids_str = f"{uid1},{uid2},{uid3}"
        result = CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert result == [uid1, uid2, uid3]

    def test_whitespace_around_uuids_is_stripped(self) -> None:
        """Whitespace around UUIDs is stripped before parsing."""
        uid1, uid2 = uuid.uuid4(), uuid.uuid4()
        ids_str = f"{uid1}, {uid2}"
        result = CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert result == [uid1, uid2]

    def test_duplicate_uuids_are_deduplicated(self) -> None:
        """Duplicate UUIDs in input are deduplicated in output."""
        uid1, uid2 = uuid.uuid4(), uuid.uuid4()
        ids_str = f"{uid1},{uid2},{uid1}"
        result = CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert result == [uid1, uid2]

    def test_non_uuid_raises_app_validation_error(self) -> None:
        """Non-UUID value raises AppValidationError(code='INVALID_ALLERGEN_IDS')."""
        with pytest.raises(AppValidationError) as exc_info:
            CatalogPublicService._parse_excluir_alergenos("not-a-uuid")
        assert exc_info.value.code == "INVALID_ALLERGEN_IDS"
        assert exc_info.value.status_code == 422

    def test_integer_string_raises_app_validation_error(self) -> None:
        """Plain integer string (not a UUID) raises AppValidationError."""
        with pytest.raises(AppValidationError) as exc_info:
            CatalogPublicService._parse_excluir_alergenos("1")
        assert exc_info.value.code == "INVALID_ALLERGEN_IDS"

    def test_mixed_valid_and_invalid_raises_app_validation_error(self) -> None:
        """Mix of valid UUID and invalid value raises AppValidationError."""
        uid = uuid.uuid4()
        with pytest.raises(AppValidationError) as exc_info:
            CatalogPublicService._parse_excluir_alergenos(f"{uid},not-a-uuid")
        assert exc_info.value.code == "INVALID_ALLERGEN_IDS"
        assert exc_info.value.status_code == 422

    def test_over_20_unique_uuids_raises_app_validation_error(self) -> None:
        """More than 20 unique UUIDs raises AppValidationError."""
        ids_str = ",".join(str(uuid.uuid4()) for _ in range(21))  # 21 unique UUIDs
        with pytest.raises(AppValidationError) as exc_info:
            CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert exc_info.value.code == "INVALID_ALLERGEN_IDS"

    def test_exactly_20_unique_uuids_is_allowed(self) -> None:
        """Exactly 20 unique UUIDs is the maximum allowed — no error."""
        ids_str = ",".join(str(uuid.uuid4()) for _ in range(20))  # 20 unique UUIDs
        result = CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert result is not None
        assert len(result) == 20

    def test_21_uuids_with_duplicates_stays_within_20(self) -> None:
        """21 items but only 20 unique UUIDs after dedup — no error."""
        uids = [uuid.uuid4() for _ in range(20)]
        # Add the last UUID again as the 21st item
        ids_str = ",".join(str(u) for u in uids) + f",{uids[-1]}"
        result = CatalogPublicService._parse_excluir_alergenos(ids_str)
        assert result is not None
        assert len(result) == 20


# ---------------------------------------------------------------------------
# list_catalog
# ---------------------------------------------------------------------------


class TestListCatalog:
    """Tests for CatalogPublicService.list_catalog()."""

    @pytest.mark.asyncio
    async def test_returns_paginated_catalog_productos(self) -> None:
        """list_catalog returns PaginatedCatalogProductos with correct shape."""
        productos = [_make_producto_orm(stock_cantidad=i) for i in range(3)]
        repo = MagicMock()
        repo.list_public = AsyncMock(return_value=(productos, 3))
        uow = _make_uow(productos_repo=repo)

        filters = CatalogProductosQuery(page=1, size=20)
        result = await CatalogPublicService.list_catalog(uow, filters)

        assert isinstance(result, PaginatedCatalogProductos)
        assert result.total == 3
        assert result.page == 1
        assert result.size == 20
        assert result.pages == 1
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_items_do_not_have_stock_cantidad(self) -> None:
        """Items in list_catalog result must NOT have stock_cantidad field."""
        import json as _json

        productos = [_make_producto_orm(stock_cantidad=5)]
        repo = MagicMock()
        repo.list_public = AsyncMock(return_value=(productos, 1))
        uow = _make_uow(productos_repo=repo)

        filters = CatalogProductosQuery()
        result = await CatalogPublicService.list_catalog(uow, filters)

        data = _json.loads(result.model_dump_json())
        for item in data["items"]:
            assert "stock_cantidad" not in item, f"stock_cantidad in item: {item}"
            assert "tiene_stock" in item

    @pytest.mark.asyncio
    async def test_pages_calculated_correctly(self) -> None:
        """pages = ceil(total / size)."""
        repo = MagicMock()
        repo.list_public = AsyncMock(return_value=([], 25))
        uow = _make_uow(productos_repo=repo)

        filters = CatalogProductosQuery(page=1, size=10)
        result = await CatalogPublicService.list_catalog(uow, filters)

        assert result.pages == 3  # ceil(25/10)

    @pytest.mark.asyncio
    async def test_invalid_alergenos_raises_before_repo_call(self) -> None:
        """Invalid excluir_alergenos raises AppValidationError before hitting repo."""
        repo = MagicMock()
        repo.list_public = AsyncMock(return_value=([], 0))
        uow = _make_uow(productos_repo=repo)

        filters = CatalogProductosQuery(excluir_alergenos="not-a-uuid")

        with pytest.raises(AppValidationError) as exc_info:
            await CatalogPublicService.list_catalog(uow, filters)

        assert exc_info.value.code == "INVALID_ALLERGEN_IDS"
        repo.list_public.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_alergenos_string_skips_filter(self) -> None:
        """Empty excluir_alergenos string is treated as None (no filter, no error)."""
        repo = MagicMock()
        repo.list_public = AsyncMock(return_value=([], 0))
        uow = _make_uow(productos_repo=repo)

        filters = CatalogProductosQuery(excluir_alergenos="")
        result = await CatalogPublicService.list_catalog(uow, filters)

        # Should pass None for parsed_alergenos
        call_kwargs = repo.list_public.call_args
        assert call_kwargs.kwargs.get("parsed_alergenos") is None
        assert isinstance(result, PaginatedCatalogProductos)


# ---------------------------------------------------------------------------
# get_catalog_detail
# ---------------------------------------------------------------------------


class TestGetCatalogDetail:
    """Tests for CatalogPublicService.get_catalog_detail()."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_repo_returns_none(self) -> None:
        """get_catalog_detail raises NotFoundError when repo returns None."""
        repo = MagicMock()
        repo.get_public_by_id = AsyncMock(return_value=None)
        uow = _make_uow(productos_repo=repo)

        with pytest.raises(NotFoundError) as exc_info:
            await CatalogPublicService.get_catalog_detail(uow, uuid.uuid4())

        assert exc_info.value.code == "PRODUCT_NOT_FOUND"
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_producto_publico_detalle_read(self) -> None:
        """get_catalog_detail returns ProductoPublicoDetalleRead on success."""
        from app.schemas.catalog_public import ProductoPublicoDetalleRead

        p = _make_producto_orm(stock_cantidad=3)
        repo = MagicMock()
        repo.get_public_by_id = AsyncMock(return_value=p)
        uow = _make_uow(productos_repo=repo)

        result = await CatalogPublicService.get_catalog_detail(uow, p.id)

        assert isinstance(result, ProductoPublicoDetalleRead)
        assert result.id == p.id
        assert result.tiene_stock is True  # stock_cantidad=3 > 0


# ---------------------------------------------------------------------------
# list_alergenos
# ---------------------------------------------------------------------------


class TestListAlergenos:
    """Tests for CatalogPublicService.list_alergenos()."""

    @pytest.mark.asyncio
    async def test_returns_only_allergen_ingredients(self) -> None:
        """list_alergenos returns IngredienteAlergenicoListResponse with allergens."""
        gluten = _make_ingrediente_orm("Gluten", es_alergeno=True)
        lactosa = _make_ingrediente_orm("Lactosa", es_alergeno=True)

        ingredientes_repo = MagicMock()
        ingredientes_repo.list_public_alergenos = AsyncMock(
            return_value=[gluten, lactosa]
        )
        uow = _make_uow(ingredientes_repo=ingredientes_repo)

        result = await CatalogPublicService.list_alergenos(uow)

        assert result.total == 2
        assert len(result.items) == 2
        for item in result.items:
            assert isinstance(item, IngredientePublicoRead)
            assert item.es_alergeno is True

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_allergens(self) -> None:
        """list_alergenos returns empty response when no allergens exist."""
        ingredientes_repo = MagicMock()
        ingredientes_repo.list_public_alergenos = AsyncMock(return_value=[])
        uow = _make_uow(ingredientes_repo=ingredientes_repo)

        result = await CatalogPublicService.list_alergenos(uow)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_ingrediente_id_mapped_from_orm_id(self) -> None:
        """list_alergenos maps Ingrediente.id to IngredientePublicoRead.ingrediente_id."""
        gluten = _make_ingrediente_orm("Gluten", es_alergeno=True)

        ingredientes_repo = MagicMock()
        ingredientes_repo.list_public_alergenos = AsyncMock(return_value=[gluten])
        uow = _make_uow(ingredientes_repo=ingredientes_repo)

        result = await CatalogPublicService.list_alergenos(uow)

        assert result.items[0].ingrediente_id == gluten.id
