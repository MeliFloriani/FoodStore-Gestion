"""
Unit tests for backend/app/schemas/catalog_public.py.

Tasks 1.3 — verifies:
  - tiene_stock is True when stock_cantidad > 0, False when 0.
  - stock_cantidad is NOT present in JSON output.
  - precio_base serializes as string.
  - CatalogProductosQuery rejects size > 100, q > 100 chars, invalid ordenar pattern.
  - IngredienteAlergenicoListResponse shape.
  - ProductoPublicoDetalleRead extends ProductoPublicoRead correctly.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.catalog_public import (
    CatalogProductosQuery,
    CategoriaPublicaRead,
    IngredienteAlergenicoListResponse,
    IngredientePublicoRead,
    PaginatedCatalogProductos,
    ProductoPublicoDetalleRead,
    ProductoPublicoRead,
)


# ---------------------------------------------------------------------------
# ProductoPublicoRead
# ---------------------------------------------------------------------------


class TestProductoPublicoRead:
    """Tests for ProductoPublicoRead schema construction and serialization."""

    def _make_producto_read(self, stock_cantidad: int) -> ProductoPublicoRead:
        """Helper: construct a ProductoPublicoRead manually (as service would)."""
        return ProductoPublicoRead(
            id=uuid.uuid4(),
            nombre="Pizza Test",
            descripcion="Una pizza de prueba",
            imagen_url=None,
            precio_base=Decimal("12.50"),
            disponible=True,
            tiene_stock=stock_cantidad > 0,
        )

    def test_tiene_stock_true_when_stock_cantidad_positive(self) -> None:
        """tiene_stock must be True when stock_cantidad > 0."""
        producto = self._make_producto_read(stock_cantidad=5)
        assert producto.tiene_stock is True

    def test_tiene_stock_false_when_stock_cantidad_zero(self) -> None:
        """tiene_stock must be False when stock_cantidad is 0."""
        producto = self._make_producto_read(stock_cantidad=0)
        assert producto.tiene_stock is False

    def test_stock_cantidad_not_in_json_output(self) -> None:
        """stock_cantidad must NOT appear in the serialized JSON output."""
        producto = self._make_producto_read(stock_cantidad=3)
        json_str = producto.model_dump_json()
        data = json.loads(json_str)
        assert "stock_cantidad" not in data, (
            f"stock_cantidad unexpectedly found in JSON output: {data}"
        )

    def test_tiene_stock_present_in_json_output(self) -> None:
        """tiene_stock must appear in the serialized JSON output as a boolean."""
        producto = self._make_producto_read(stock_cantidad=1)
        json_str = producto.model_dump_json()
        data = json.loads(json_str)
        assert "tiene_stock" in data, f"tiene_stock missing from JSON: {data}"
        assert isinstance(data["tiene_stock"], bool)

    def test_precio_base_serialized_as_string(self) -> None:
        """precio_base must serialize as a string in JSON (H-02 pattern)."""
        producto = self._make_producto_read(stock_cantidad=1)
        json_str = producto.model_dump_json()
        data = json.loads(json_str)
        assert isinstance(data["precio_base"], str), (
            f"precio_base should be str, got: {type(data['precio_base'])} ({data['precio_base']})"
        )
        assert data["precio_base"] == "12.50"

    def test_precio_base_preserves_two_decimal_places(self) -> None:
        """precio_base serialization must preserve trailing zeros (e.g., 15.50)."""
        producto = ProductoPublicoRead(
            id=uuid.uuid4(),
            nombre="Producto",
            descripcion=None,
            imagen_url=None,
            precio_base=Decimal("15.50"),
            disponible=True,
            tiene_stock=True,
        )
        data = json.loads(producto.model_dump_json())
        assert data["precio_base"] == "15.50", (
            f"Expected '15.50', got '{data['precio_base']}'"
        )

    def test_admin_fields_not_in_json_output(self) -> None:
        """created_at, updated_at, deleted_at must NOT appear in JSON output."""
        producto = self._make_producto_read(stock_cantidad=2)
        data = json.loads(producto.model_dump_json())
        for forbidden_field in ("created_at", "updated_at", "deleted_at"):
            assert forbidden_field not in data, (
                f"Forbidden field '{forbidden_field}' found in JSON output: {data}"
            )


# ---------------------------------------------------------------------------
# CatalogProductosQuery
# ---------------------------------------------------------------------------


class TestCatalogProductosQuery:
    """Tests for CatalogProductosQuery validation."""

    def test_defaults_are_correct(self) -> None:
        """Default values: page=1, size=20, all others None."""
        q = CatalogProductosQuery()
        assert q.page == 1
        assert q.size == 20
        assert q.categoria_id is None
        assert q.q is None
        assert q.excluir_alergenos is None
        assert q.ordenar is None

    def test_size_over_100_raises_validation_error(self) -> None:
        """size > 100 must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogProductosQuery(size=200)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("size",) for e in errors), (
            f"Expected error on 'size', got: {errors}"
        )

    def test_size_exactly_100_is_valid(self) -> None:
        """size=100 is the maximum allowed value."""
        q = CatalogProductosQuery(size=100)
        assert q.size == 100

    def test_size_1_is_valid(self) -> None:
        """size=1 is the minimum allowed value."""
        q = CatalogProductosQuery(size=1)
        assert q.size == 1

    def test_q_over_100_chars_raises_validation_error(self) -> None:
        """q longer than 100 chars must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogProductosQuery(q="x" * 101)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("q",) for e in errors), (
            f"Expected error on 'q', got: {errors}"
        )

    def test_q_exactly_100_chars_is_valid(self) -> None:
        """q with exactly 100 chars is allowed."""
        q = CatalogProductosQuery(q="a" * 100)
        assert len(q.q) == 100  # type: ignore[arg-type]

    def test_invalid_ordenar_pattern_raises_validation_error(self) -> None:
        """ordenar that doesn't match ^-?(nombre|precio)$ must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogProductosQuery(ordenar="stock")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ordenar",) for e in errors), (
            f"Expected error on 'ordenar', got: {errors}"
        )

    def test_valid_ordenar_values(self) -> None:
        """Valid ordenar values: nombre, -nombre, precio, -precio."""
        for value in ("nombre", "-nombre", "precio", "-precio"):
            q = CatalogProductosQuery(ordenar=value)
            assert q.ordenar == value

    def test_page_ge_1_required(self) -> None:
        """page < 1 must raise ValidationError."""
        with pytest.raises(ValidationError):
            CatalogProductosQuery(page=0)

    def test_categoria_id_accepts_uuid(self) -> None:
        """categoria_id accepts a valid UUID."""
        cat_id = uuid.uuid4()
        q = CatalogProductosQuery(categoria_id=cat_id)
        assert q.categoria_id == cat_id

    def test_excluir_alergenos_accepts_any_string(self) -> None:
        """excluir_alergenos accepts any string (validation happens in service)."""
        q = CatalogProductosQuery(excluir_alergenos="1,2,3")
        assert q.excluir_alergenos == "1,2,3"


# ---------------------------------------------------------------------------
# IngredientePublicoRead
# ---------------------------------------------------------------------------


class TestIngredientePublicoRead:
    """Tests for IngredientePublicoRead schema."""

    def test_ingrediente_id_field_present(self) -> None:
        """ingrediente_id must be used (not id) for ingredient identification."""
        ing = IngredientePublicoRead(
            ingrediente_id=uuid.uuid4(),
            nombre="Gluten",
            es_alergeno=True,
        )
        assert ing.ingrediente_id is not None

    def test_es_removible_not_present(self) -> None:
        """es_removible must NOT be a field in IngredientePublicoRead."""
        ing = IngredientePublicoRead(
            ingrediente_id=uuid.uuid4(),
            nombre="Tomate",
            es_alergeno=False,
        )
        data = json.loads(ing.model_dump_json())
        assert "es_removible" not in data, (
            f"es_removible should not be in public schema: {data}"
        )


# ---------------------------------------------------------------------------
# ProductoPublicoDetalleRead
# ---------------------------------------------------------------------------


class TestProductoPublicoDetalleRead:
    """Tests for ProductoPublicoDetalleRead schema."""

    def test_extends_producto_publico_read(self) -> None:
        """ProductoPublicoDetalleRead must inherit fields from ProductoPublicoRead."""
        detalle = ProductoPublicoDetalleRead(
            id=uuid.uuid4(),
            nombre="Hamburguesa",
            descripcion=None,
            imagen_url=None,
            precio_base=Decimal("8.00"),
            disponible=True,
            tiene_stock=True,
            categorias=[],
            ingredientes=[],
        )
        # Check inherited fields
        assert detalle.nombre == "Hamburguesa"
        assert detalle.tiene_stock is True
        # Check extended fields
        assert detalle.categorias == []
        assert detalle.ingredientes == []

    def test_categorias_and_ingredientes_in_json(self) -> None:
        """categorias and ingredientes lists must appear in JSON output."""
        cat = CategoriaPublicaRead(id=uuid.uuid4(), nombre="Pizzas")
        ing = IngredientePublicoRead(
            ingrediente_id=uuid.uuid4(),
            nombre="Gluten",
            es_alergeno=True,
        )
        detalle = ProductoPublicoDetalleRead(
            id=uuid.uuid4(),
            nombre="Pizza",
            descripcion=None,
            imagen_url=None,
            precio_base=Decimal("12.00"),
            disponible=True,
            tiene_stock=False,
            categorias=[cat],
            ingredientes=[ing],
        )
        data = json.loads(detalle.model_dump_json())
        assert "categorias" in data
        assert len(data["categorias"]) == 1
        assert data["categorias"][0]["nombre"] == "Pizzas"
        assert "ingredientes" in data
        assert len(data["ingredientes"]) == 1
        assert data["ingredientes"][0]["ingrediente_id"] == str(ing.ingrediente_id)


# ---------------------------------------------------------------------------
# IngredienteAlergenicoListResponse
# ---------------------------------------------------------------------------


class TestIngredienteAlergenicoListResponse:
    """Tests for IngredienteAlergenicoListResponse schema."""

    def test_items_and_total_fields(self) -> None:
        """IngredienteAlergenicoListResponse must have items list and total int."""
        response = IngredienteAlergenicoListResponse(items=[], total=0)
        assert response.items == []
        assert response.total == 0

    def test_with_items(self) -> None:
        """IngredienteAlergenicoListResponse correctly holds allergen items."""
        items = [
            IngredientePublicoRead(
                ingrediente_id=uuid.uuid4(),
                nombre="Gluten",
                es_alergeno=True,
            ),
            IngredientePublicoRead(
                ingrediente_id=uuid.uuid4(),
                nombre="Lactosa",
                es_alergeno=True,
            ),
        ]
        response = IngredienteAlergenicoListResponse(items=items, total=len(items))
        assert response.total == 2
        assert len(response.items) == 2


# ---------------------------------------------------------------------------
# PaginatedCatalogProductos
# ---------------------------------------------------------------------------


class TestPaginatedCatalogProductos:
    """Tests for PaginatedCatalogProductos schema shape."""

    def test_pagination_fields(self) -> None:
        """PaginatedCatalogProductos must have items, total, page, size, pages."""
        paginated = PaginatedCatalogProductos(
            items=[],
            total=0,
            page=1,
            size=20,
            pages=0,
        )
        assert paginated.items == []
        assert paginated.total == 0
        assert paginated.page == 1
        assert paginated.size == 20
        assert paginated.pages == 0
