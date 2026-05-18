"""
Unit tests for Categoria Pydantic v2 schemas.

Task 3.7: Tests for CategoriaCreate, CategoriaUpdate, CategoriaTreeNode.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaTreeNode,
    CategoriaUpdate,
)


# ---------------------------------------------------------------------------
# CategoriaCreate — nombre length validation
# ---------------------------------------------------------------------------


def test_categoria_create_rejects_nombre_over_100_chars() -> None:
    """CategoriaCreate raises ValidationError when nombre > 100 chars."""
    with pytest.raises(ValidationError) as exc_info:
        CategoriaCreate(nombre="x" * 101)

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "nombre" in str(e.get("loc", []))]
    assert len(field_errors) >= 1, "Expected a validation error on 'nombre'"


def test_categoria_create_rejects_empty_nombre() -> None:
    """CategoriaCreate raises ValidationError when nombre is empty string."""
    with pytest.raises(ValidationError) as exc_info:
        CategoriaCreate(nombre="")

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "nombre" in str(e.get("loc", []))]
    assert len(field_errors) >= 1


def test_categoria_create_accepts_max_length_nombre() -> None:
    """CategoriaCreate accepts nombre of exactly 100 chars."""
    obj = CategoriaCreate(nombre="x" * 100)
    assert obj.nombre == "x" * 100


def test_categoria_create_root_category() -> None:
    """CategoriaCreate with no parent_id creates a root category spec."""
    obj = CategoriaCreate(nombre="Bebidas")
    assert obj.parent_id is None


def test_categoria_create_with_parent_id() -> None:
    """CategoriaCreate with parent_id stores it correctly."""
    parent = uuid.uuid4()
    obj = CategoriaCreate(nombre="Jugos", parent_id=parent)
    assert obj.parent_id == parent


# ---------------------------------------------------------------------------
# CategoriaUpdate — model_fields_set sentinel behavior
# ---------------------------------------------------------------------------


def test_categoria_update_absent_parent_id_not_in_fields_set() -> None:
    """When parent_id is absent from payload, it is NOT in model_fields_set."""
    obj = CategoriaUpdate(nombre="Nuevo")
    assert "parent_id" not in obj.model_fields_set
    assert obj.nombre == "Nuevo"


def test_categoria_update_explicit_null_parent_id_in_fields_set() -> None:
    """When parent_id is explicitly None in payload, it IS in model_fields_set."""
    obj = CategoriaUpdate.model_validate({"parent_id": None})
    assert "parent_id" in obj.model_fields_set
    assert obj.parent_id is None


def test_categoria_update_uuid_parent_id_in_fields_set() -> None:
    """When parent_id is a UUID, it IS in model_fields_set with that value."""
    new_parent = uuid.uuid4()
    obj = CategoriaUpdate.model_validate({"parent_id": str(new_parent)})
    assert "parent_id" in obj.model_fields_set
    assert obj.parent_id == new_parent


def test_categoria_update_all_fields_absent_returns_empty_fields_set() -> None:
    """An empty payload has an empty model_fields_set."""
    obj = CategoriaUpdate.model_validate({})
    assert len(obj.model_fields_set) == 0


def test_categoria_update_nombre_only_sets_only_nombre() -> None:
    """Updating only nombre leaves parent_id absent from model_fields_set."""
    obj = CategoriaUpdate.model_validate({"nombre": "Nuevo"})
    assert "nombre" in obj.model_fields_set
    assert "parent_id" not in obj.model_fields_set


# ---------------------------------------------------------------------------
# CategoriaTreeNode — forward reference and nested structure
# ---------------------------------------------------------------------------


def test_categoria_tree_node_forward_ref_resolves() -> None:
    """CategoriaTreeNode can be instantiated without forward-ref errors."""
    node = CategoriaTreeNode(
        id=uuid.uuid4(),
        nombre="Root",
        descripcion=None,
        subcategorias=[],
    )
    assert node.nombre == "Root"
    assert node.subcategorias == []


def test_categoria_tree_node_nested_serializes_correctly() -> None:
    """Nested CategoriaTreeNode serializes correctly without errors."""
    grandchild = CategoriaTreeNode(
        id=uuid.uuid4(),
        nombre="Grandchild",
        subcategorias=[],
    )
    child = CategoriaTreeNode(
        id=uuid.uuid4(),
        nombre="Child",
        subcategorias=[grandchild],
    )
    root = CategoriaTreeNode(
        id=uuid.uuid4(),
        nombre="Root",
        subcategorias=[child],
    )

    dumped = root.model_dump()
    assert dumped["nombre"] == "Root"
    assert len(dumped["subcategorias"]) == 1
    assert dumped["subcategorias"][0]["nombre"] == "Child"
    assert len(dumped["subcategorias"][0]["subcategorias"]) == 1
    assert dumped["subcategorias"][0]["subcategorias"][0]["nombre"] == "Grandchild"


def test_categoria_tree_node_json_serialization() -> None:
    """CategoriaTreeNode can be serialized to JSON with nested children."""
    child_id = uuid.uuid4()
    root_id = uuid.uuid4()

    child = CategoriaTreeNode(id=child_id, nombre="Child", subcategorias=[])
    root = CategoriaTreeNode(id=root_id, nombre="Root", subcategorias=[child])

    json_str = root.model_dump_json()
    assert "Root" in json_str
    assert "Child" in json_str
