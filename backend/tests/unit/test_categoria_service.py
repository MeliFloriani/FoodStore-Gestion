"""
Unit tests for CategoriaService.

TDD: tests written before implementation.
Uses unittest.mock to isolate service from real DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.schemas.categoria import CategoriaCreate, CategoriaTreeNode, CategoriaUpdate
from app.services.categoria import CategoriaService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_categoria(
    id: uuid.UUID | None = None,
    nombre: str = "Test",
    parent_id: uuid.UUID | None = None,
    descripcion: str | None = None,
) -> MagicMock:
    """Build a fake Categoria ORM object (MagicMock with required attributes)."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.nombre = nombre
    obj.parent_id = parent_id
    obj.descripcion = descripcion
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    obj.deleted_at = None
    return obj


def _make_uow(categorias_repo: MagicMock) -> MagicMock:
    """Build a fake UoW with a mock categorias repo."""
    uow = MagicMock()
    uow.categorias = categorias_repo
    return uow


def _make_repo(**kwargs) -> MagicMock:
    """Build a mock CategoriaRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=kwargs.get("get_by_id", None))
    repo.get_tree = AsyncMock(return_value=kwargs.get("get_tree", []))
    repo.create = AsyncMock(side_effect=kwargs.get("create", None))
    repo.update = AsyncMock(return_value=kwargs.get("update", None))
    repo.soft_delete = AsyncMock(return_value=kwargs.get("soft_delete", True))
    repo.count_active_children = AsyncMock(return_value=kwargs.get("count_active_children", 0))
    repo.count_active_products = AsyncMock(return_value=kwargs.get("count_active_products", 0))
    repo.get_depth = AsyncMock(return_value=kwargs.get("get_depth", 1))
    repo.get_subtree_height = AsyncMock(return_value=kwargs.get("get_subtree_height", 0))
    repo.would_create_cycle = AsyncMock(return_value=kwargs.get("would_create_cycle", False))
    return repo


# ---------------------------------------------------------------------------
# Task 4.1 — test_create_valid_root_category (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_valid_root_category() -> None:
    """create_categoria with no parent_id creates a root category."""
    cat_id = uuid.uuid4()
    fake_cat = _make_fake_categoria(id=cat_id, nombre="Bebidas")

    async def _create(obj):
        return fake_cat

    repo = _make_repo(create=_create)
    uow = _make_uow(repo)

    data = CategoriaCreate(nombre="Bebidas")
    result = await CategoriaService.create_categoria(data, uow)

    assert result.id == cat_id
    assert result.nombre == "Bebidas"
    assert result.parent_id is None


# ---------------------------------------------------------------------------
# Task 4.2 — test_create_with_nonexistent_parent_raises_not_found (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_nonexistent_parent_raises_not_found() -> None:
    """create_categoria raises NotFoundError when parent_id does not exist."""
    repo = _make_repo(get_by_id=None)  # parent not found
    uow = _make_uow(repo)

    data = CategoriaCreate(nombre="Jugos", parent_id=uuid.uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await CategoriaService.create_categoria(data, uow)

    assert "CATEGORY_NOT_FOUND" in str(exc_info.value.code)


# ---------------------------------------------------------------------------
# Task 4.3 — test_create_duplicate_name_same_level_raises_conflict (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_duplicate_name_same_level_raises_conflict() -> None:
    """create_categoria raises ConflictError on IntegrityError (duplicate nombre)."""
    parent = _make_fake_categoria(nombre="Parent")

    async def _raise_integrity(obj):
        raise IntegrityError("UNIQUE constraint", None, None)

    repo = _make_repo(get_by_id=parent, get_depth=1, create=_raise_integrity)
    uow = _make_uow(repo)

    data = CategoriaCreate(nombre="Bebidas", parent_id=parent.id)

    with pytest.raises(ConflictError) as exc_info:
        await CategoriaService.create_categoria(data, uow)

    assert exc_info.value.code == "CATEGORY_NAME_DUPLICATE"


# ---------------------------------------------------------------------------
# Task 4.4 — test_create_same_name_different_parent_allowed (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_same_name_different_parent_allowed() -> None:
    """create_categoria allows same nombre under different parents."""
    parent = _make_fake_categoria(nombre="ParentB")
    new_cat = _make_fake_categoria(nombre="Frutas", parent_id=parent.id)

    async def _create(obj):
        return new_cat

    repo = _make_repo(get_by_id=parent, get_depth=1, create=_create)
    uow = _make_uow(repo)

    data = CategoriaCreate(nombre="Frutas", parent_id=parent.id)
    result = await CategoriaService.create_categoria(data, uow)

    assert result.nombre == "Frutas"
    assert result.parent_id == parent.id


# ---------------------------------------------------------------------------
# Task 4.5 — test_create_beyond_max_depth_raises_validation_error (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_beyond_max_depth_raises_validation_error() -> None:
    """create_categoria raises AppValidationError when parent is at depth 5."""
    parent = _make_fake_categoria(nombre="DeepParent")

    repo = _make_repo(get_by_id=parent, get_depth=5)
    uow = _make_uow(repo)

    data = CategoriaCreate(nombre="TooDeep", parent_id=parent.id)

    with pytest.raises(AppValidationError) as exc_info:
        await CategoriaService.create_categoria(data, uow)

    assert exc_info.value.code == "CATEGORY_MAX_DEPTH_EXCEEDED"


# ---------------------------------------------------------------------------
# Task 4.5b — test_update_reparent_subtree_exceeds_max_depth (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_reparent_subtree_exceeds_max_depth_raises_validation_error() -> None:
    """update_categoria raises AppValidationError when 3+1+2=6 > 5."""
    cat_id = uuid.uuid4()
    new_parent_id = uuid.uuid4()
    cat = _make_fake_categoria(id=cat_id, nombre="C")
    new_parent = _make_fake_categoria(id=new_parent_id, nombre="NewParent")

    # get_by_id returns the category on first call, parent on second
    get_by_id_calls = [cat, new_parent]
    call_count = [0]

    async def _get_by_id(id, **kwargs):
        result = get_by_id_calls[call_count[0]]
        call_count[0] += 1
        return result

    repo = _make_repo()
    repo.get_by_id = _get_by_id
    repo.would_create_cycle = AsyncMock(return_value=False)
    repo.get_depth = AsyncMock(return_value=3)         # new parent at depth 3
    repo.get_subtree_height = AsyncMock(return_value=2)  # subtree height 2
    # 3 + 1 + 2 = 6 > 5 → should fail
    uow = _make_uow(repo)

    data = CategoriaUpdate.model_validate({"parent_id": str(new_parent_id)})

    with pytest.raises(AppValidationError) as exc_info:
        await CategoriaService.update_categoria(cat_id, data, uow)

    assert exc_info.value.code == "CATEGORY_MAX_DEPTH_EXCEEDED"


# ---------------------------------------------------------------------------
# Task 4.6 — test_update_self_parent_raises_validation_error (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_self_parent_raises_validation_error() -> None:
    """update_categoria raises AppValidationError when parent_id == category_id."""
    cat_id = uuid.uuid4()
    cat = _make_fake_categoria(id=cat_id, nombre="SelfParent")

    repo = _make_repo()
    repo.get_by_id = AsyncMock(return_value=cat)
    uow = _make_uow(repo)

    # Set parent_id to the same id as the category
    data = CategoriaUpdate.model_validate({"parent_id": str(cat_id)})

    with pytest.raises(AppValidationError) as exc_info:
        await CategoriaService.update_categoria(cat_id, data, uow)

    assert exc_info.value.code == "CATEGORY_SELF_PARENT"


# ---------------------------------------------------------------------------
# Task 4.7 — test_update_cycle_raises_validation_error (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_cycle_raises_validation_error() -> None:
    """update_categoria raises AppValidationError when cycle detected."""
    cat_id = uuid.uuid4()
    desc_id = uuid.uuid4()
    cat = _make_fake_categoria(id=cat_id, nombre="Ancestor")
    descendant = _make_fake_categoria(id=desc_id, nombre="Descendant")

    get_by_id_calls = {cat_id: cat, desc_id: descendant}

    async def _get_by_id(id, **kwargs):
        return get_by_id_calls.get(id)

    repo = _make_repo()
    repo.get_by_id = _get_by_id
    repo.would_create_cycle = AsyncMock(return_value=True)
    uow = _make_uow(repo)

    # Try to make the ancestor a child of its descendant
    data = CategoriaUpdate.model_validate({"parent_id": str(desc_id)})

    with pytest.raises(AppValidationError) as exc_info:
        await CategoriaService.update_categoria(cat_id, data, uow)

    assert exc_info.value.code == "CATEGORY_CYCLE_DETECTED"


# ---------------------------------------------------------------------------
# Task 4.8 — test_delete_with_active_children_raises_conflict (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_with_active_children_raises_conflict() -> None:
    """delete_categoria raises ConflictError when category has active children."""
    cat = _make_fake_categoria(nombre="Parent")
    repo = _make_repo(count_active_children=1, count_active_products=0)
    repo.get_by_id = AsyncMock(return_value=cat)
    uow = _make_uow(repo)

    with pytest.raises(ConflictError) as exc_info:
        await CategoriaService.delete_categoria(cat.id, uow)

    assert exc_info.value.code == "CATEGORY_HAS_ACTIVE_CHILDREN"


# ---------------------------------------------------------------------------
# Task 4.9 — test_delete_leaf_category_soft_deletes (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_leaf_category_soft_deletes() -> None:
    """delete_categoria calls soft_delete for a leaf category."""
    cat = _make_fake_categoria(nombre="Leaf")
    repo = _make_repo(count_active_children=0, count_active_products=0)
    repo.get_by_id = AsyncMock(return_value=cat)
    uow = _make_uow(repo)

    await CategoriaService.delete_categoria(cat.id, uow)

    repo.soft_delete.assert_called_once_with(cat.id)


# ---------------------------------------------------------------------------
# Task 4.10 — test_get_tree_assembles_hierarchy_correctly (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tree_assembles_hierarchy_correctly() -> None:
    """get_tree assembles flat rows into nested CategoriaTreeNode hierarchy."""
    root_id = uuid.uuid4()
    child1_id = uuid.uuid4()
    child2_id = uuid.uuid4()

    # Simulate flat rows returned by the repository
    class FlatRow:
        def __init__(self, id, nombre, descripcion, parent_id, depth):
            self.id = id
            self.nombre = nombre
            self.descripcion = descripcion
            self.parent_id = parent_id
            self.depth = depth

    flat_rows = [
        FlatRow(root_id, "Root", None, None, 1),
        FlatRow(child1_id, "Child1", None, root_id, 2),
        FlatRow(child2_id, "Child2", None, root_id, 2),
    ]

    repo = _make_repo(get_tree=flat_rows)
    uow = _make_uow(repo)

    result = await CategoriaService.get_tree(uow)

    assert len(result) == 1  # one root
    root_node = result[0]
    assert root_node.id == root_id
    assert root_node.nombre == "Root"
    assert len(root_node.subcategorias) == 2  # two children

    child_names = {c.nombre for c in root_node.subcategorias}
    assert "Child1" in child_names
    assert "Child2" in child_names

    # Children should have empty subcategorias
    for child in root_node.subcategorias:
        assert child.subcategorias == []


# ---------------------------------------------------------------------------
# Additional: test get_by_id raises NotFoundError when not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_raises_not_found_when_none() -> None:
    """get_by_id raises NotFoundError when category does not exist."""
    repo = _make_repo(get_by_id=None)
    uow = _make_uow(repo)

    with pytest.raises(NotFoundError) as exc_info:
        await CategoriaService.get_by_id(uuid.uuid4(), uow)

    assert exc_info.value.code == "CATEGORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_by_id_returns_categoria_read_when_found() -> None:
    """get_by_id returns CategoriaRead when category exists."""
    cat = _make_fake_categoria(nombre="Found")
    repo = _make_repo(get_by_id=cat)
    uow = _make_uow(repo)

    result = await CategoriaService.get_by_id(cat.id, uow)
    assert result.id == cat.id
    assert result.nombre == "Found"
