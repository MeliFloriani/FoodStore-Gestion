"""
Unit tests for Producto Pydantic v2 schemas.

Tasks 2.11: Tests for ProductoCreate, ProductoUpdate, ProductoRead,
ProductoIngredienteRead, AsociarIngredienteRequest.

TDD Red-Green-Refactor: these tests were written BEFORE the schema
implementation (Red), then the schemas were implemented to make them
pass (Green).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.producto import (
    AsociarIngredienteRequest,
    ProductoCreate,
    ProductoRead,
    ProductoUpdate,
)


# ---------------------------------------------------------------------------
# ProductoCreate — precio_base validation
# ---------------------------------------------------------------------------


def test_create_rejects_negative_precio() -> None:
    """ProductoCreate raises ValidationError when precio_base < 0."""
    with pytest.raises(ValidationError) as exc_info:
        ProductoCreate(precio_base=Decimal("-1"), nombre="X")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "precio_base" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, f"Expected error on 'precio_base', got: {errors}"


def test_create_rejects_negative_stock() -> None:
    """ProductoCreate raises ValidationError when stock_cantidad < 0."""
    with pytest.raises(ValidationError) as exc_info:
        ProductoCreate(stock_cantidad=-1, precio_base=Decimal("5"), nombre="X")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "stock_cantidad" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, f"Expected error on 'stock_cantidad', got: {errors}"


def test_create_validates_precio_decimal_precision() -> None:
    """ProductoCreate accepts Decimal('19.99') with exact 2-decimal precision."""
    obj = ProductoCreate(precio_base=Decimal("19.99"), nombre="Pizza Margherita")
    assert obj.precio_base == Decimal("19.99")


def test_create_rejects_too_many_decimal_places() -> None:
    """ProductoCreate raises ValidationError when precio_base has > 2 decimal places."""
    with pytest.raises(ValidationError) as exc_info:
        ProductoCreate(precio_base=Decimal("19.999"), nombre="X")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "precio_base" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, f"Expected error on 'precio_base' precision, got: {errors}"


def test_create_accepts_zero_precio() -> None:
    """ProductoCreate accepts precio_base = 0 (ge=0 allows zero)."""
    obj = ProductoCreate(precio_base=Decimal("0.00"), nombre="Gratis")
    assert obj.precio_base == Decimal("0.00")


def test_create_accepts_zero_stock() -> None:
    """ProductoCreate accepts stock_cantidad = 0 (ge=0 allows zero)."""
    obj = ProductoCreate(precio_base=Decimal("5.00"), nombre="Sin Stock", stock_cantidad=0)
    assert obj.stock_cantidad == 0


def test_create_rejects_nombre_empty() -> None:
    """ProductoCreate raises ValidationError when nombre is empty."""
    with pytest.raises(ValidationError) as exc_info:
        ProductoCreate(precio_base=Decimal("5.00"), nombre="")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "nombre" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, f"Expected error on 'nombre', got: {errors}"


def test_create_defaults_stock_to_zero() -> None:
    """ProductoCreate defaults stock_cantidad to 0 if not supplied."""
    obj = ProductoCreate(precio_base=Decimal("5.00"), nombre="Producto")
    assert obj.stock_cantidad == 0


def test_create_defaults_disponible_to_true() -> None:
    """ProductoCreate defaults disponible to True if not supplied."""
    obj = ProductoCreate(precio_base=Decimal("5.00"), nombre="Producto")
    assert obj.disponible is True


def test_create_accepts_categoria_ids() -> None:
    """ProductoCreate accepts a list of category UUIDs."""
    cat_ids = [uuid.uuid4(), uuid.uuid4()]
    obj = ProductoCreate(
        precio_base=Decimal("10.00"),
        nombre="Con Categorias",
        categoria_ids=cat_ids,
    )
    assert obj.categoria_ids == cat_ids


def test_create_categoria_ids_defaults_to_none() -> None:
    """ProductoCreate defaults categoria_ids to None when not supplied."""
    obj = ProductoCreate(precio_base=Decimal("5.00"), nombre="Producto")
    assert obj.categoria_ids is None


# ---------------------------------------------------------------------------
# ProductoRead — precio_base serialization as string
# ---------------------------------------------------------------------------


def test_read_precio_serializes_as_string() -> None:
    """ProductoRead.model_dump_json() serializes precio_base as string '19.99', not float.

    H-02 compliance: prevents float precision loss in JSON API responses.
    """
    now = datetime.now(timezone.utc)
    obj = ProductoRead(
        id=uuid.uuid4(),
        nombre="Pizza",
        descripcion=None,
        imagen_url=None,
        precio_base=Decimal("19.99"),
        stock_cantidad=10,
        disponible=True,
        created_at=now,
        updated_at=now,
    )
    json_str = obj.model_dump_json()
    parsed = json.loads(json_str)

    assert isinstance(parsed["precio_base"], str), (
        f"precio_base should be string in JSON, got {type(parsed['precio_base'])}: {parsed['precio_base']}"
    )
    assert parsed["precio_base"] == "19.99", (
        f"precio_base JSON value should be '19.99', got: {parsed['precio_base']}"
    )


def test_read_precio_15_50_serializes_correctly() -> None:
    """ProductoRead serializes Decimal('15.50') as string '15.50', preserving trailing zero."""
    now = datetime.now(timezone.utc)
    obj = ProductoRead(
        id=uuid.uuid4(),
        nombre="Producto",
        descripcion=None,
        imagen_url=None,
        precio_base=Decimal("15.50"),
        stock_cantidad=5,
        disponible=True,
        created_at=now,
        updated_at=now,
    )
    json_str = obj.model_dump_json()
    parsed = json.loads(json_str)

    assert isinstance(parsed["precio_base"], str)
    assert parsed["precio_base"] == "15.50", (
        f"Expected '15.50', got: {parsed['precio_base']}"
    )


def test_read_precio_not_float_in_json() -> None:
    """ProductoRead JSON output does NOT contain a float for precio_base."""
    now = datetime.now(timezone.utc)
    obj = ProductoRead(
        id=uuid.uuid4(),
        nombre="Hamburguesa",
        descripcion=None,
        imagen_url=None,
        precio_base=Decimal("8.99"),
        stock_cantidad=20,
        disponible=True,
        created_at=now,
        updated_at=now,
    )
    json_str = obj.model_dump_json()
    parsed = json.loads(json_str)
    # Must be str, not float (float would be 8.99 as number, not "8.99" as string)
    assert not isinstance(parsed["precio_base"], float), (
        "precio_base must not be float in JSON output"
    )


# ---------------------------------------------------------------------------
# ProductoUpdate — model_fields_set sentinel behavior for categoria_ids
# ---------------------------------------------------------------------------


def test_update_model_fields_set_absent_categoria_ids() -> None:
    """ProductoUpdate(nombre='X') has 'categoria_ids' NOT in model_fields_set."""
    obj = ProductoUpdate(nombre="Nuevo Nombre")
    assert "categoria_ids" not in obj.model_fields_set, (
        f"'categoria_ids' should not be in model_fields_set when absent from payload, "
        f"got: {obj.model_fields_set}"
    )


def test_update_model_fields_set_empty_categoria_ids() -> None:
    """ProductoUpdate(categoria_ids=[]) has 'categoria_ids' IN model_fields_set."""
    obj = ProductoUpdate(categoria_ids=[])
    assert "categoria_ids" in obj.model_fields_set, (
        f"'categoria_ids' should be in model_fields_set when explicitly set to [], "
        f"got: {obj.model_fields_set}"
    )
    assert obj.categoria_ids == []


def test_update_model_fields_set_with_uuids() -> None:
    """ProductoUpdate(categoria_ids=[uuid]) has 'categoria_ids' in model_fields_set."""
    cat_id = uuid.uuid4()
    obj = ProductoUpdate(categoria_ids=[cat_id])
    assert "categoria_ids" in obj.model_fields_set
    assert obj.categoria_ids == [cat_id]


def test_update_absent_fields_not_in_model_fields_set() -> None:
    """All fields absent from payload are NOT in model_fields_set."""
    obj = ProductoUpdate.model_validate({})
    assert len(obj.model_fields_set) == 0


def test_update_only_nombre_in_fields_set() -> None:
    """ProductoUpdate with only nombre has only nombre in model_fields_set."""
    obj = ProductoUpdate.model_validate({"nombre": "Nuevo"})
    assert "nombre" in obj.model_fields_set
    assert "precio_base" not in obj.model_fields_set
    assert "categoria_ids" not in obj.model_fields_set


# ---------------------------------------------------------------------------
# AsociarIngredienteRequest — es_removible is required
# ---------------------------------------------------------------------------


def test_asociar_ingrediente_requires_es_removible() -> None:
    """AsociarIngredienteRequest without es_removible raises ValidationError.

    es_removible has no default — it MUST always be explicitly provided.
    """
    with pytest.raises(ValidationError) as exc_info:
        AsociarIngredienteRequest(ingrediente_id=uuid.uuid4())

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "es_removible" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, (
        f"Expected ValidationError on 'es_removible', got: {errors}"
    )


def test_asociar_ingrediente_accepts_es_removible_true() -> None:
    """AsociarIngredienteRequest accepts es_removible=True."""
    ing_id = uuid.uuid4()
    obj = AsociarIngredienteRequest(ingrediente_id=ing_id, es_removible=True)
    assert obj.ingrediente_id == ing_id
    assert obj.es_removible is True


def test_asociar_ingrediente_accepts_es_removible_false() -> None:
    """AsociarIngredienteRequest accepts es_removible=False."""
    ing_id = uuid.uuid4()
    obj = AsociarIngredienteRequest(ingrediente_id=ing_id, es_removible=False)
    assert obj.es_removible is False
