"""
Unit tests for ProductoService.

TDD: tests written before implementation (Red → Green → Refactor).
Uses unittest.mock to isolate service from real DB.

Tasks 4.1–4.19.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.producto import (
    AsociarIngredienteRequest,
    DisponibilidadUpdate,
    ProductoCreate,
    ProductoUpdate,
)
from app.services.producto import ProductoService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_fake_producto(
    id: uuid.UUID | None = None,
    nombre: str = "Pizza Test",
    precio_base: float = 10.00,
    stock_cantidad: int = 5,
    disponible: bool = True,
    deleted_at: datetime | None = None,
    producto_categorias: list | None = None,
    producto_ingredientes: list | None = None,
) -> MagicMock:
    """Build a fake Producto ORM object."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.nombre = nombre
    obj.descripcion = None
    obj.imagen_url = None
    obj.precio_base = precio_base
    obj.stock_cantidad = stock_cantidad
    obj.disponible = disponible
    obj.created_at = _now()
    obj.updated_at = _now()
    obj.deleted_at = deleted_at
    obj.producto_categorias = producto_categorias or []
    obj.producto_ingredientes = producto_ingredientes or []
    return obj


def _make_fake_categoria(id: uuid.UUID | None = None, nombre: str = "Cat") -> MagicMock:
    """Build a fake Categoria ORM object."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.nombre = nombre
    obj.descripcion = None
    obj.parent_id = None
    obj.created_at = _now()
    obj.updated_at = _now()
    obj.deleted_at = None
    return obj


def _make_fake_ingrediente(
    id: uuid.UUID | None = None,
    nombre: str = "Sal",
    es_alergeno: bool = False,
    deleted_at: datetime | None = None,
) -> MagicMock:
    """Build a fake Ingrediente ORM object."""
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.nombre = nombre
    obj.es_alergeno = es_alergeno
    obj.created_at = _now()
    obj.updated_at = _now()
    obj.deleted_at = deleted_at
    return obj


def _make_fake_pi(
    producto_id: uuid.UUID | None = None,
    ingrediente_id: uuid.UUID | None = None,
    es_removible: bool = True,
    ingrediente: MagicMock | None = None,
) -> MagicMock:
    """Build a fake ProductoIngrediente pivot object."""
    obj = MagicMock()
    obj.producto_id = producto_id or uuid.uuid4()
    obj.ingrediente_id = ingrediente_id or uuid.uuid4()
    obj.es_removible = es_removible
    obj.ingrediente = ingrediente or _make_fake_ingrediente(id=ingrediente_id)
    return obj


def _make_fake_pc(
    producto_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    es_principal: bool = True,
    categoria: MagicMock | None = None,
) -> MagicMock:
    """Build a fake ProductoCategoria pivot object."""
    obj = MagicMock()
    obj.producto_id = producto_id or uuid.uuid4()
    obj.categoria_id = categoria_id or uuid.uuid4()
    obj.es_principal = es_principal
    obj.categoria = categoria or _make_fake_categoria(id=categoria_id)
    return obj


def _make_productos_repo(**kwargs) -> MagicMock:
    """Build a mock ProductoRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=kwargs.get("get_by_id", None))
    repo.list_paginated = AsyncMock(return_value=kwargs.get("list_paginated", ([], 0)))
    repo.get_with_relations = AsyncMock(return_value=kwargs.get("get_with_relations", None))
    repo.create = AsyncMock(side_effect=kwargs.get("create", None))
    repo.update = AsyncMock(return_value=kwargs.get("update", None))
    repo.soft_delete = AsyncMock(return_value=kwargs.get("soft_delete", True))
    repo.set_categorias = AsyncMock(return_value=kwargs.get("set_categorias", None))
    repo.add_ingrediente = AsyncMock(return_value=kwargs.get("add_ingrediente", None))
    repo.remove_ingrediente = AsyncMock(return_value=kwargs.get("remove_ingrediente", True))
    repo.get_ingredientes = AsyncMock(return_value=kwargs.get("get_ingredientes", []))
    repo.decrement_stock = AsyncMock(return_value=kwargs.get("decrement_stock", None))
    return repo


def _make_categorias_repo(**kwargs) -> MagicMock:
    """Build a mock CategoriaRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=kwargs.get("get_by_id", None))
    return repo


def _make_ingredientes_repo(**kwargs) -> MagicMock:
    """Build a mock IngredienteRepository with AsyncMock methods."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=kwargs.get("get_by_id", None))
    return repo


def _make_uow(
    productos_repo: MagicMock,
    categorias_repo: MagicMock | None = None,
    ingredientes_repo: MagicMock | None = None,
) -> MagicMock:
    """Build a fake UoW with mock repos."""
    uow = MagicMock()
    uow.productos = productos_repo
    uow.categorias = categorias_repo or _make_categorias_repo()
    uow.ingredientes = ingredientes_repo or _make_ingredientes_repo()
    uow.session = MagicMock()
    return uow


# ---------------------------------------------------------------------------
# Task 4.1 — list_productos returns PaginatedProductos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_productos_returns_paginated() -> None:
    """list_productos assembles PaginatedProductos from repo results.

    Task 4.1.
    """
    fake_prod = _make_fake_producto()
    productos_repo = _make_productos_repo(list_paginated=(
        [fake_prod], 15
    ))
    uow = _make_uow(productos_repo)

    result = await ProductoService.list_productos(
        uow=uow, page=1, size=10, categoria_id=None, disponible=None, search=None
    )

    assert result.total == 15
    assert result.page == 1
    assert result.size == 10
    assert result.pages == 2  # ceil(15/10) = 2
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_list_productos_pages_calculation() -> None:
    """list_productos calculates pages = ceil(total / size) correctly."""
    fake_prod = _make_fake_producto()
    productos_repo = _make_productos_repo(list_paginated=([fake_prod] * 20, 25))
    uow = _make_uow(productos_repo)

    result = await ProductoService.list_productos(
        uow=uow, page=1, size=20, categoria_id=None, disponible=None, search=None
    )

    assert result.total == 25
    assert result.pages == 2  # ceil(25/20) = 2


# ---------------------------------------------------------------------------
# Task 4.2 — get_producto_detail not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_producto_detail_not_found_raises_404() -> None:
    """get_producto_detail raises NotFoundError(PRODUCT_NOT_FOUND) when not found.

    Task 4.2.
    """
    productos_repo = _make_productos_repo(get_with_relations=None)
    uow = _make_uow(productos_repo)

    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.get_producto_detail(uow=uow, producto_id=uuid.uuid4())

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.3 — get_producto_detail returns ProductoDetail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_producto_detail_returns_ProductoDetail() -> None:
    """get_producto_detail returns ProductoDetail with relations mapped.

    Task 4.3.
    """
    cat_id = uuid.uuid4()
    fake_cat = _make_fake_categoria(id=cat_id, nombre="Pizzas")
    ing_id = uuid.uuid4()
    fake_ing = _make_fake_ingrediente(id=ing_id, nombre="Mozzarella")
    fake_pc = _make_fake_pc(categoria_id=cat_id, categoria=fake_cat)
    fake_pi = _make_fake_pi(ingrediente_id=ing_id, ingrediente=fake_ing, es_removible=True)

    fake_prod = _make_fake_producto(
        nombre="Pizza Margherita",
        producto_categorias=[fake_pc],
        producto_ingredientes=[fake_pi],
    )

    productos_repo = _make_productos_repo(get_with_relations=fake_prod)
    uow = _make_uow(productos_repo)

    result = await ProductoService.get_producto_detail(uow=uow, producto_id=fake_prod.id)

    assert result.nombre == "Pizza Margherita"
    assert len(result.categorias) == 1
    assert len(result.ingredientes) == 1
    assert result.categorias[0].nombre == "Pizzas"
    assert result.ingredientes[0].nombre == "Mozzarella"


# ---------------------------------------------------------------------------
# Task 4.4 — create_producto with invalid categoria raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_producto_with_invalid_categoria_raises_404() -> None:
    """create_producto raises NotFoundError(CATEGORY_NOT_FOUND) for missing category.

    Task 4.4.
    """
    fake_cat_id = uuid.uuid4()

    async def _create(obj):
        return _make_fake_producto(id=uuid.uuid4())

    productos_repo = _make_productos_repo(create=_create)
    categorias_repo = _make_categorias_repo(get_by_id=None)  # category not found
    uow = _make_uow(productos_repo, categorias_repo=categorias_repo)

    data = ProductoCreate(
        nombre="Pizza",
        precio_base=Decimal("10.00"),
        categoria_ids=[fake_cat_id],
    )

    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.create_producto(uow=uow, data=data)

    assert exc_info.value.code == "CATEGORY_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.5 — create_producto with valid data returns ProductoRead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_producto_valid_data_returns_ProductoRead() -> None:
    """create_producto creates product and returns ProductoRead.

    Task 4.5.
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id, nombre="Pizza Margherita", precio_base=12.50)

    async def _create(obj):
        return fake_prod

    productos_repo = _make_productos_repo(create=_create)
    uow = _make_uow(productos_repo)

    data = ProductoCreate(nombre="Pizza Margherita", precio_base=Decimal("12.50"))
    result = await ProductoService.create_producto(uow=uow, data=data)

    assert result.id == prod_id
    assert result.nombre == "Pizza Margherita"


# ---------------------------------------------------------------------------
# Task 4.6 — update_producto partial preserves untouched fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_producto_partial_preserves_untouched_fields() -> None:
    """update_producto only updates fields in model_fields_set.

    Task 4.6: sending only 'nombre' must NOT touch precio_base or categoria_ids.
    """
    prod_id = uuid.uuid4()
    original = _make_fake_producto(id=prod_id, nombre="Original", precio_base=10.00)
    updated = _make_fake_producto(id=prod_id, nombre="Actualizado", precio_base=10.00)

    productos_repo = _make_productos_repo(
        get_by_id=original,
        update=updated,
    )
    uow = _make_uow(productos_repo)

    data = ProductoUpdate(nombre="Actualizado")
    result = await ProductoService.update_producto(uow=uow, producto_id=prod_id, data=data)

    # update() should be called with ONLY nombre (not precio_base, not stock)
    call_kwargs = productos_repo.update.call_args
    assert call_kwargs is not None
    update_dict = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("data", {})
    # categoria_ids should NOT trigger set_categorias
    productos_repo.set_categorias.assert_not_called()


# ---------------------------------------------------------------------------
# Task 4.7 — update_producto not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_producto_not_found_raises_404() -> None:
    """update_producto raises NotFoundError when product not found.

    Task 4.7.
    """
    productos_repo = _make_productos_repo(get_by_id=None)
    uow = _make_uow(productos_repo)

    data = ProductoUpdate(nombre="Nuevo")
    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.update_producto(uow=uow, producto_id=uuid.uuid4(), data=data)

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.8 — update_producto with empty categoria_ids removes all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_producto_with_empty_categoria_ids_removes_all() -> None:
    """update_producto with categoria_ids=[] calls set_categorias with empty list.

    Task 4.8.
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)
    updated_prod = _make_fake_producto(id=prod_id)

    productos_repo = _make_productos_repo(
        get_by_id=fake_prod,
        update=updated_prod,
    )
    uow = _make_uow(productos_repo)

    # categoria_ids=[] — this IS in model_fields_set (explicit empty list)
    data = ProductoUpdate(categoria_ids=[])
    await ProductoService.update_producto(uow=uow, producto_id=prod_id, data=data)

    # set_categorias should be called with empty list
    productos_repo.set_categorias.assert_called_once()
    call_args = productos_repo.set_categorias.call_args
    categoria_ids_arg = call_args[0][2] if len(call_args[0]) >= 3 else call_args[1].get("categoria_ids", None)
    assert categoria_ids_arg == [], f"set_categorias should be called with [], got {categoria_ids_arg}"


# ---------------------------------------------------------------------------
# Task 4.9 — delete_producto calls soft_delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_producto_calls_soft_delete() -> None:
    """delete_producto fetches product then calls soft_delete.

    Task 4.9.
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)

    productos_repo = _make_productos_repo(get_by_id=fake_prod)
    uow = _make_uow(productos_repo)

    await ProductoService.delete_producto(uow=uow, producto_id=prod_id)

    productos_repo.soft_delete.assert_called_once_with(prod_id)


# ---------------------------------------------------------------------------
# Task 4.10 — delete_producto not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_producto_not_found_raises_404() -> None:
    """delete_producto raises NotFoundError when product not found.

    Task 4.10.
    """
    productos_repo = _make_productos_repo(get_by_id=None)
    uow = _make_uow(productos_repo)

    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.delete_producto(uow=uow, producto_id=uuid.uuid4())

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.11 — set_disponibilidad updates field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_disponibilidad_updates_field() -> None:
    """set_disponibilidad sets disponible and returns updated ProductoRead.

    Task 4.11.
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id, disponible=True)
    updated_prod = _make_fake_producto(id=prod_id, disponible=False)

    productos_repo = _make_productos_repo(
        get_by_id=fake_prod,
        update=updated_prod,
    )
    uow = _make_uow(productos_repo)

    data = DisponibilidadUpdate(disponible=False)
    result = await ProductoService.set_disponibilidad(
        uow=uow, producto_id=prod_id, data=data
    )

    # update should be called with {'disponible': False}
    productos_repo.update.assert_called_once()
    call_data = productos_repo.update.call_args[0][1]
    assert call_data.get("disponible") is False


# ---------------------------------------------------------------------------
# Task 4.12 — set_disponibilidad not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_disponibilidad_not_found_raises_404() -> None:
    """set_disponibilidad raises NotFoundError when product not found.

    Task 4.12.
    """
    productos_repo = _make_productos_repo(get_by_id=None)
    uow = _make_uow(productos_repo)

    data = DisponibilidadUpdate(disponible=True)
    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.set_disponibilidad(
            uow=uow, producto_id=uuid.uuid4(), data=data
        )

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.13 — get_producto_ingredientes not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_producto_ingredientes_not_found_raises_404() -> None:
    """get_producto_ingredientes raises NotFoundError when product not found.

    Task 4.13.
    """
    productos_repo = _make_productos_repo(get_by_id=None)
    uow = _make_uow(productos_repo)

    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.get_producto_ingredientes(
            uow=uow, producto_id=uuid.uuid4()
        )

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.14 — add_ingrediente producto not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ingrediente_producto_not_found_raises_404() -> None:
    """add_ingrediente raises NotFoundError(PRODUCT_NOT_FOUND) when product absent.

    Task 4.14.
    """
    productos_repo = _make_productos_repo(get_by_id=None)
    uow = _make_uow(productos_repo)

    data = AsociarIngredienteRequest(ingrediente_id=uuid.uuid4(), es_removible=True)
    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.add_ingrediente(
            uow=uow, producto_id=uuid.uuid4(), data=data
        )

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.15 — add_ingrediente ingrediente not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ingrediente_ingrediente_not_found_raises_404() -> None:
    """add_ingrediente raises NotFoundError(INGREDIENT_NOT_FOUND) when ingredient absent.

    Task 4.15.
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)

    productos_repo = _make_productos_repo(get_by_id=fake_prod)
    ingredientes_repo = _make_ingredientes_repo(get_by_id=None)  # ingredient not found
    uow = _make_uow(productos_repo, ingredientes_repo=ingredientes_repo)

    data = AsociarIngredienteRequest(ingrediente_id=uuid.uuid4(), es_removible=True)
    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.add_ingrediente(
            uow=uow, producto_id=prod_id, data=data
        )

    assert exc_info.value.code == "INGREDIENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.16 — add_ingrediente duplicate raises 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ingrediente_duplicate_raises_409() -> None:
    """add_ingrediente raises ConflictError(PRODUCT_INGREDIENT_DUPLICATE) on IntegrityError.

    Task 4.16.
    """
    prod_id = uuid.uuid4()
    ing_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)
    fake_ing = _make_fake_ingrediente(id=ing_id)

    async def _add_ingrediente(*args, **kwargs):
        raise IntegrityError("duplicate", {}, Exception("unique violation"))

    productos_repo = _make_productos_repo(get_by_id=fake_prod)
    productos_repo.add_ingrediente = AsyncMock(side_effect=_add_ingrediente)
    ingredientes_repo = _make_ingredientes_repo(get_by_id=fake_ing)
    uow = _make_uow(productos_repo, ingredientes_repo=ingredientes_repo)

    data = AsociarIngredienteRequest(ingrediente_id=ing_id, es_removible=True)
    with pytest.raises(ConflictError) as exc_info:
        await ProductoService.add_ingrediente(
            uow=uow, producto_id=prod_id, data=data
        )

    assert exc_info.value.code == "PRODUCT_INGREDIENT_DUPLICATE"


# ---------------------------------------------------------------------------
# Task 4.17 — add_ingrediente success returns ProductoIngredienteRead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ingrediente_success_returns_ProductoIngredienteRead() -> None:
    """add_ingrediente returns ProductoIngredienteRead on success.

    Task 4.17.
    """
    prod_id = uuid.uuid4()
    ing_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)
    fake_ing = _make_fake_ingrediente(id=ing_id, nombre="Queso", es_alergeno=False)
    fake_pi = _make_fake_pi(
        producto_id=prod_id,
        ingrediente_id=ing_id,
        es_removible=True,
        ingrediente=fake_ing,
    )

    productos_repo = _make_productos_repo(
        get_by_id=fake_prod,
        add_ingrediente=fake_pi,
    )
    ingredientes_repo = _make_ingredientes_repo(get_by_id=fake_ing)
    uow = _make_uow(productos_repo, ingredientes_repo=ingredientes_repo)

    data = AsociarIngredienteRequest(ingrediente_id=ing_id, es_removible=True)
    result = await ProductoService.add_ingrediente(
        uow=uow, producto_id=prod_id, data=data
    )

    assert result.ingrediente_id == ing_id
    assert result.nombre == "Queso"
    assert result.es_removible is True


# ---------------------------------------------------------------------------
# Task 4.18 — remove_ingrediente not found raises 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_ingrediente_not_found_raises_404() -> None:
    """remove_ingrediente raises NotFoundError when association not found.

    Task 4.18: repo returns False → service raises NotFoundError(PRODUCT_INGREDIENT_NOT_FOUND).
    """
    prod_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)

    productos_repo = _make_productos_repo(
        get_by_id=fake_prod,
        remove_ingrediente=False,
    )
    uow = _make_uow(productos_repo)

    with pytest.raises(NotFoundError) as exc_info:
        await ProductoService.remove_ingrediente(
            uow=uow, producto_id=prod_id, ingrediente_id=uuid.uuid4()
        )

    assert exc_info.value.code == "PRODUCT_INGREDIENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Task 4.19 — remove_ingrediente success returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_ingrediente_success_returns_none() -> None:
    """remove_ingrediente returns None on success (no error).

    Task 4.19.
    """
    prod_id = uuid.uuid4()
    ing_id = uuid.uuid4()
    fake_prod = _make_fake_producto(id=prod_id)

    productos_repo = _make_productos_repo(
        get_by_id=fake_prod,
        remove_ingrediente=True,
    )
    uow = _make_uow(productos_repo)

    result = await ProductoService.remove_ingrediente(
        uow=uow, producto_id=prod_id, ingrediente_id=ing_id
    )

    assert result is None
