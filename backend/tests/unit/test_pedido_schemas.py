"""
Unit tests for DetallePedidoRead schema — focus on legacy NULL handling.

Regression coverage for the 500 we hit on GET /api/v1/pedidos when the DB has
detalle_pedido rows with `personalizacion = NULL` (created before the service
fix that always persists `[]`).

The schema must coerce None → [] so the public API contract always returns a
list, never null.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.pedidos import DetallePedidoRead


def _row(personalizacion):
    """Build an object that mimics a SQLModel DetallePedido ORM row."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        producto_id=uuid.uuid4(),
        nombre_snapshot="Hamburguesa",
        precio_snapshot=Decimal("1200.00"),
        cantidad=2,
        personalizacion=personalizacion,
    )


def test_model_validate_coerces_none_personalizacion_to_empty_list():
    """ORM row with personalizacion=NULL must serialize as []."""
    row = _row(personalizacion=None)

    read = DetallePedidoRead.model_validate(row)

    assert read.personalizacion == []
    dumped = read.model_dump()
    assert dumped["personalizacion"] == []


def test_model_validate_preserves_non_empty_personalizacion():
    """Non-null UUID list must pass through unchanged."""
    ingrediente_id = uuid.uuid4()
    row = _row(personalizacion=[ingrediente_id])

    read = DetallePedidoRead.model_validate(row)

    assert read.personalizacion == [ingrediente_id]


def test_construct_with_missing_personalizacion_defaults_to_empty_list():
    """default_factory still kicks in when the field is omitted entirely."""
    read = DetallePedidoRead(
        id=uuid.uuid4(),
        producto_id=uuid.uuid4(),
        nombre_snapshot="Hamburguesa",
        precio_snapshot=Decimal("1200.00"),
        cantidad=1,
    )
    assert read.personalizacion == []


def test_construct_with_explicit_none_personalizacion_coerced_to_empty_list():
    """Explicit None passed to constructor must also be coerced to []."""
    read = DetallePedidoRead(
        id=uuid.uuid4(),
        producto_id=uuid.uuid4(),
        nombre_snapshot="Hamburguesa",
        precio_snapshot=Decimal("1200.00"),
        cantidad=1,
        personalizacion=None,  # type: ignore[arg-type]
    )
    assert read.personalizacion == []
