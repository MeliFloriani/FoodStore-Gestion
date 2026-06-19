"""
Unit tests for pedidos_service.

Change 17: order-creation-with-snapshots — crear_pedido transactional flow.
Change 20: orders-visualization — list_pedidos, get_pedido_detail with RBAC.

Uses unittest.mock to isolate the service from the real DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.exceptions import AppError
from app.schemas.pedidos import (
    ItemPedidoCreate,
    PedidoCreate,
    PedidoEstadoUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_producto(
    producto_id: uuid.UUID | None = None,
    nombre: str = "Hamburguesa",
    precio_base: float = 1200.00,
    stock: int = 10,
    disponible: bool = True,
    deleted: bool = False,
) -> MagicMock:
    p = MagicMock()
    p.id = producto_id or uuid.uuid4()
    p.nombre = nombre
    p.precio_base = precio_base
    p.stock_cantidad = stock
    p.disponible = disponible
    p.deleted_at = datetime.now(timezone.utc) if deleted else None
    return p


def _make_forma_pago(codigo: str = "MERCADOPAGO", habilitado: bool = True) -> MagicMock:
    fp = MagicMock()
    fp.codigo = codigo
    fp.habilitado = habilitado
    return fp


def _make_direccion(direccion_id: uuid.UUID | None = None) -> MagicMock:
    d = MagicMock()
    d.id = direccion_id or uuid.uuid4()
    d.alias = "Casa"
    d.linea1 = "Av. Siempre Viva 742"
    d.linea2 = None
    d.ciudad = "Springfield"
    d.provincia = "BS AS"
    d.codigo_postal = "1900"
    d.referencia = None
    return d


def _make_mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.pedidos = MagicMock()
    uow.usuarios = MagicMock()
    uow.pagos = MagicMock()

    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[])
    uow.pedidos.get_ingredientes_batch = AsyncMock(return_value={})
    uow.pedidos.get_forma_pago = AsyncMock(return_value=None)
    uow.pedidos.get_direccion_usuario = AsyncMock(return_value=None)
    uow.pedidos.get_direccion_by_id = AsyncMock(return_value=None)
    uow.pedidos.create_pedido = AsyncMock()
    uow.pedidos.create_detalle = AsyncMock()
    uow.pedidos.decrement_stock = AsyncMock()
    uow.pedidos.create_historial = AsyncMock()
    uow.pedidos.get_by_id = AsyncMock(return_value=None)
    uow.pedidos.get_full_detail = AsyncMock(return_value=None)
    uow.pedidos.list_with_filters = AsyncMock(return_value=([], 0))

    uow.usuarios.get_by_id = AsyncMock(return_value=None)

    return uow


def _make_pedido_create(
    items: list[ItemPedidoCreate] | None = None,
    forma_pago_codigo: str = "MERCADOPAGO",
    direccion_id: uuid.UUID | None = None,
) -> PedidoCreate:
    if items is None:
        items = [ItemPedidoCreate(producto_id=uuid.uuid4(), cantidad=2)]
    return PedidoCreate(
        items=items,
        forma_pago_codigo=forma_pago_codigo,
        direccion_id=direccion_id,
        notas="Sin cebolla",
    )


def _make_usuario(roles: set[str] | None = None) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.nombre = "Juan"
    u.apellido = "Pérez"
    u.email = "juan@example.com"

    mock_roles = []
    for r in (roles or {"CLIENT"}):
        rol = MagicMock()
        rol.codigo = r
        ur = MagicMock()
        ur.rol = rol
        ur.deleted_at = None
        mock_roles.append(ur)

    u.usuario_roles = mock_roles
    return u


# ---------------------------------------------------------------------------
# crear_pedido — Change 17
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_pedido_cart_empty_raises():
    """Empty items list raises CartEmptyError."""
    from app.schemas.pedidos import PedidoCreate
    from app.services.pedidos_service import crear_pedido

    uow = _make_mock_uow()
    usuario_id = uuid.uuid4()
    request = PedidoCreate.model_construct(
        items=[], forma_pago_codigo="MERCADOPAGO"
    )

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "CART_EMPTY"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_product_not_found_raises():
    """Product not in locked products raises ProductNotFoundError."""
    from app.services.pedidos_service import crear_pedido

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[])

    usuario_id = uuid.uuid4()
    request = _make_pedido_create()

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_soft_deleted_raises():
    """Soft-deleted product raises ProductNotAvailableError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(deleted=True)
    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "PRODUCT_NOT_AVAILABLE"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_not_available_raises():
    """Product with disponible=False raises ProductNotAvailableError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(disponible=False)
    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "PRODUCT_NOT_AVAILABLE"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_insufficient_stock_raises():
    """Insufficient stock raises InsufficientStockError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=1)
    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(items=[ItemPedidoCreate(producto_id=producto.id, cantidad=5)])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_crear_pedido_invalid_customization_raises():
    """Exclusion for ingredient not in product raises InvalidCustomizationError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=10)
    bad_ing_id = uuid.uuid4()

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_ingredientes_batch = AsyncMock(return_value={producto.id: []})

    usuario_id = uuid.uuid4()
    item = ItemPedidoCreate(producto_id=producto.id, cantidad=2, exclusiones=[bad_ing_id])
    request = _make_pedido_create(items=[item])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "INVALID_CUSTOMIZATION"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_payment_method_not_found_raises():
    """Non-existent forma_pago raises PaymentMethodInvalidError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=10)
    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=None)

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "PAYMENT_METHOD_INVALID"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_payment_method_disabled_raises():
    """Disabled forma_pago raises PaymentMethodInvalidError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=10)
    forma_pago = _make_forma_pago(habilitado=False)

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=forma_pago)

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)])

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "PAYMENT_METHOD_INVALID"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_address_not_found_raises():
    """Non-existent direccion_id raises AddressNotFoundError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=10)
    forma_pago = _make_forma_pago(habilitado=True)
    direccion_id = uuid.uuid4()

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=forma_pago)
    uow.pedidos.get_direccion_usuario = AsyncMock(return_value=None)
    uow.pedidos.get_direccion_by_id = AsyncMock(return_value=None)

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(
        items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)],
        direccion_id=direccion_id,
    )

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "ADDRESS_NOT_FOUND"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_pedido_address_not_owned_raises():
    """Direccion belonging to another user raises AddressNotOwnedError."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(stock=10)
    forma_pago = _make_forma_pago(habilitado=True)
    direccion_id = uuid.uuid4()
    direccion = _make_direccion(direccion_id)

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=forma_pago)
    uow.pedidos.get_direccion_usuario = AsyncMock(return_value=None)
    uow.pedidos.get_direccion_by_id = AsyncMock(return_value=direccion)

    usuario_id = uuid.uuid4()
    request = _make_pedido_create(
        items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)],
        direccion_id=direccion_id,
    )

    with pytest.raises(AppError) as exc_info:
        await crear_pedido(uow, usuario_id, request)

    assert exc_info.value.code == "ADDRESS_NOT_OWNED"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_crear_pedido_success_con_envio():
    """Successful order creation with delivery address returns PedidoRead."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(producto_id=uuid.uuid4(), stock=10, precio_base=1000.00)
    forma_pago = _make_forma_pago(habilitado=True)
    direccion_id = uuid.uuid4()
    direccion = _make_direccion(direccion_id)
    usuario_id = uuid.uuid4()

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=forma_pago)
    uow.pedidos.get_direccion_usuario = AsyncMock(return_value=direccion)
    uow.pedidos.create_pedido = AsyncMock()

    async def _create_detalle_side_effect(detalle):
        detalle.id = uuid.uuid4()
    uow.pedidos.create_detalle = AsyncMock(side_effect=_create_detalle_side_effect)
    uow.pedidos.create_historial = AsyncMock()

    historial = MagicMock()
    historial.id = uuid.uuid4()
    historial.estado_desde = None
    historial.estado_hasta = "PENDIENTE"
    historial.motivo = None
    historial.created_at = datetime.now(timezone.utc)
    historial.cambiado_por_id = None
    uow.pedidos.create_historial = AsyncMock(return_value=None)

    request = _make_pedido_create(
        items=[ItemPedidoCreate(producto_id=producto.id, cantidad=2)],
        forma_pago_codigo="MERCADOPAGO",
        direccion_id=direccion_id,
    )

    result = await crear_pedido(uow, usuario_id, request)

    assert result.estado_codigo == "PENDIENTE"
    assert result.total == Decimal("2050.00")  # (1000 * 2) + 50 envio
    assert result.costo_envio == Decimal("50.00")
    assert result.usuario_id == usuario_id
    assert len(result.items) == 1
    assert len(result.historial) == 1
    uow.pedidos.decrement_stock.assert_awaited_once_with(producto.id, 2)


@pytest.mark.asyncio
async def test_crear_pedido_success_sin_envio():
    """Successful order creation without delivery address (retiro en local)."""
    from app.services.pedidos_service import crear_pedido

    producto = _make_producto(producto_id=uuid.uuid4(), stock=10, precio_base=500.00)
    forma_pago = _make_forma_pago(habilitado=True)
    usuario_id = uuid.uuid4()

    uow = _make_mock_uow()
    uow.pedidos.lock_productos_for_update = AsyncMock(return_value=[producto])
    uow.pedidos.get_forma_pago = AsyncMock(return_value=forma_pago)
    uow.pedidos.create_pedido = AsyncMock()

    async def _create_detalle_side_effect(detalle):
        detalle.id = uuid.uuid4()
    uow.pedidos.create_detalle = AsyncMock(side_effect=_create_detalle_side_effect)
    uow.pedidos.create_historial = AsyncMock()

    request = _make_pedido_create(
        items=[ItemPedidoCreate(producto_id=producto.id, cantidad=3)],
        forma_pago_codigo="EFECTIVO",
        direccion_id=None,
    )

    result = await crear_pedido(uow, usuario_id, request)

    assert result.estado_codigo == "PENDIENTE"
    assert result.total == Decimal("1500.00")  # 500 * 3, sin envio
    assert result.costo_envio == Decimal("0.00")
    assert result.forma_pago_codigo == "EFECTIVO"


# ---------------------------------------------------------------------------
# list_pedidos — Change 20
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pedidos_client_role():
    """CLIENT role filters by current_user.id, ignores admin params."""
    from app.services.pedidos_service import ListPedidosParams, list_pedidos

    current_user = _make_usuario(roles={"CLIENT"})
    uow = _make_mock_uow()
    uow.pedidos.list_with_filters = AsyncMock(return_value=([], 0))
    params = ListPedidosParams(estado="PENDIENTE", page=1, size=20)

    items, total = await list_pedidos(uow, current_user, params)

    assert total == 0
    uow.pedidos.list_with_filters.assert_awaited_once()
    call_kwargs = uow.pedidos.list_with_filters.await_args[1]
    assert call_kwargs["usuario_id"] == current_user.id
    assert call_kwargs["desde"] is None
    assert call_kwargs["hasta"] is None
    assert call_kwargs["cliente"] is None


@pytest.mark.asyncio
async def test_list_pedidos_admin_role():
    """PEDIDOS role sees all orders with filters applied."""
    from app.services.pedidos_service import ListPedidosParams, list_pedidos

    current_user = _make_usuario(roles={"PEDIDOS"})
    uow = _make_mock_uow()
    uow.pedidos.list_with_filters = AsyncMock(return_value=([], 0))
    params = ListPedidosParams(estado="CONFIRMADO", page=1, size=20)

    items, total = await list_pedidos(uow, current_user, params)

    assert total == 0
    call_kwargs = uow.pedidos.list_with_filters.await_args[1]
    assert call_kwargs["usuario_id"] is None
    assert call_kwargs["estado"] == "CONFIRMADO"


# ---------------------------------------------------------------------------
# get_pedido_detail — Change 20
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pedido_detail_stock_role_403():
    """STOCK role always gets 403."""
    from app.services.pedidos_service import get_pedido_detail

    uow = _make_mock_uow()
    pedido_id = uuid.uuid4()
    current_user = _make_usuario(roles={"STOCK"})

    with pytest.raises(HTTPException) as exc_info:
        await get_pedido_detail(uow, pedido_id, current_user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_pedido_detail_not_found_404():
    """Non-existent pedido returns 404."""
    from app.services.pedidos_service import get_pedido_detail

    uow = _make_mock_uow()
    uow.pedidos.get_full_detail = AsyncMock(return_value=None)

    pedido_id = uuid.uuid4()
    current_user = _make_usuario(roles={"PEDIDOS"})

    with pytest.raises(HTTPException) as exc_info:
        await get_pedido_detail(uow, pedido_id, current_user)

    assert exc_info.value.status_code == 404
