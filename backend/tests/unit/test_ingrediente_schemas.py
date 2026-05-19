"""
Unit tests for Ingrediente Pydantic v2 schemas.

Task 2.6: Tests for IngredienteCreate, IngredienteUpdate, IngredienteRead.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.ingrediente import (
    IngredienteCreate,
    IngredienteRead,
    IngredienteUpdate,
)


# ---------------------------------------------------------------------------
# IngredienteCreate — nombre length and whitespace validation
# ---------------------------------------------------------------------------


def test_create_rejects_nombre_over_100_chars() -> None:
    """IngredienteCreate raises ValidationError when nombre > 100 chars."""
    with pytest.raises(ValidationError) as exc_info:
        IngredienteCreate(nombre="a" * 101)

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "nombre" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, "Expected a validation error on 'nombre'"


def test_create_strips_whitespace_from_nombre() -> None:
    """IngredienteCreate strips leading/trailing whitespace from nombre."""
    obj = IngredienteCreate(nombre="  Sal  ")
    assert obj.nombre == "Sal"


def test_create_rejects_whitespace_only_nombre() -> None:
    """IngredienteCreate raises ValidationError when nombre is whitespace-only."""
    with pytest.raises(ValidationError) as exc_info:
        IngredienteCreate(nombre="   ")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "nombre" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, "Expected a validation error on 'nombre'"


def test_create_accepts_max_length_nombre() -> None:
    """IngredienteCreate accepts nombre of exactly 100 chars."""
    obj = IngredienteCreate(nombre="x" * 100)
    assert obj.nombre == "x" * 100


def test_create_defaults_es_alergeno_to_false() -> None:
    """IngredienteCreate defaults es_alergeno to False when not supplied."""
    obj = IngredienteCreate(nombre="Sal")
    assert obj.es_alergeno is False


def test_create_accepts_es_alergeno_true() -> None:
    """IngredienteCreate accepts es_alergeno=True explicitly."""
    obj = IngredienteCreate(nombre="Gluten", es_alergeno=True)
    assert obj.es_alergeno is True


# ---------------------------------------------------------------------------
# IngredienteUpdate — model_fields_set sentinel behavior
# ---------------------------------------------------------------------------


def test_update_model_fields_set_absent_field() -> None:
    """IngredienteUpdate(es_alergeno=True) has 'nombre' not in model_fields_set."""
    obj = IngredienteUpdate(es_alergeno=True)
    assert "nombre" not in obj.model_fields_set


def test_update_model_fields_set_present_field() -> None:
    """IngredienteUpdate(nombre='Sal') has 'nombre' in model_fields_set."""
    obj = IngredienteUpdate(nombre="Sal")
    assert "nombre" in obj.model_fields_set


def test_update_es_alergeno_absent_not_in_fields_set() -> None:
    """When es_alergeno is absent from payload, it is NOT in model_fields_set."""
    obj = IngredienteUpdate(nombre="Harina")
    assert "es_alergeno" not in obj.model_fields_set


def test_update_es_alergeno_present_in_fields_set() -> None:
    """When es_alergeno is explicitly set, it IS in model_fields_set."""
    obj = IngredienteUpdate.model_validate({"es_alergeno": True})
    assert "es_alergeno" in obj.model_fields_set


def test_update_all_fields_absent_returns_empty_fields_set() -> None:
    """An empty payload has an empty model_fields_set."""
    obj = IngredienteUpdate.model_validate({})
    assert len(obj.model_fields_set) == 0


def test_update_both_fields_present_in_fields_set() -> None:
    """When both fields are provided, both appear in model_fields_set."""
    obj = IngredienteUpdate.model_validate({"nombre": "Sal", "es_alergeno": False})
    assert "nombre" in obj.model_fields_set
    assert "es_alergeno" in obj.model_fields_set


# ---------------------------------------------------------------------------
# IngredienteRead — from_attributes and UUID id type
# ---------------------------------------------------------------------------


def test_read_id_is_uuid() -> None:
    """IngredienteRead.id is typed as uuid.UUID (not int or str)."""
    now = datetime.now(timezone.utc)
    obj = IngredienteRead(
        id=uuid.uuid4(),
        nombre="Sal",
        es_alergeno=False,
        created_at=now,
        updated_at=now,
    )
    assert isinstance(obj.id, uuid.UUID)


def test_read_from_attributes() -> None:
    """IngredienteRead can be built from an ORM-like object via model_validate."""
    from unittest.mock import MagicMock

    now = datetime.now(timezone.utc)
    fake_orm = MagicMock()
    fake_orm.id = uuid.uuid4()
    fake_orm.nombre = "Azucar"
    fake_orm.es_alergeno = True
    fake_orm.created_at = now
    fake_orm.updated_at = now

    obj = IngredienteRead.model_validate(fake_orm)
    assert obj.nombre == "Azucar"
    assert obj.es_alergeno is True
    assert isinstance(obj.id, uuid.UUID)
