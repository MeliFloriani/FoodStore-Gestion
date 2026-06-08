"""
Tests unitarios del service de creación de pedidos (Change 17).

Epic 6 del tasks.md: unit tests del service crear_pedido con UoW mockeado.

Design:
- No usan BD real — todos los datos son objetos mock (MagicMock / AsyncMock).
- Verifican que el service lance las excepciones correctas en cada escenario.
- Verifican que los campos snapshot sean copiados correctamente.
- Verifican que los totales se calculen server-side.
- Verifican que clearCart y el historial inicial cumplan RN-02.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.pedidos import ItemPedidoCreate, PedidoCreate
from app.services.pedidos_service import (
    AddressNotFoundError,
    AddressNotOwnedError,
    CartEmptyError,
    InsufficientStockError,
    InvalidCustomizationError,
    PaymentMethodInvalidError,
    ProductNotAvailableError,
    ProductNotFoundError,
    crear_pedido,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = uuid.uuid4()
PRODUCTO_ID = uuid.uuid4()
INGREDIENTE_ID = uuid.uuid4()
DIRECCION_ID = uuid.uuid4()
FORMA_PAGO = "EFECTIVO"


def _make_producto(
    producto_id=None,
    nombre="Pizza Test",
    precio_base=100.0,
    stock_cantidad=10,
    disponible=True,
    deleted_at=None,
):
    p = MagicMock()
    p.id = producto_id or PRODUCTO_ID
    p.nombre = nombre
    p.precio_base = precio_base
    p.stock_cantidad = stock_cantidad
    p.disponible = disponible
    p.deleted_at = deleted_at
    return p


def _make_forma_pago(codigo=FORMA_PAGO, habilitado=True):
    fp = MagicMock()
    fp.codigo = codigo
    fp.habilitado = habilitado
    return fp


def _make_direccion(usuario_id=None):
    d = MagicMock()
    d.id = DIRECCION_ID
    d.usuario_id = usuario_id or USER_ID
    d.deleted_at = None
    return d


def _make_pedido(pedido_id=None):
    p = MagicMock()
    p.id = pedido_id or uuid.uuid4()
    p.usuario_id = USER_ID
    p.estado_codigo = "PENDIENTE"
    p.forma_pago_codigo = FORMA_PAGO
    p.direccion_id = None
    p.total = 100.0
    p.costo_envio = 0.0
    p.notas = None
    p.created_at = MagicMock()
    return p


def _make_detalle(pedido_id=None, producto_id=None):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.pedido_id = pedido_id or uuid.uuid4()
    d.producto_id = producto_id or PRODUCTO_ID
    d.nombre_snapshot = "Pizza Test"
    d.precio_snapshot = 100.0
    d.cantidad = 1
    d.personalizacion = None
    return d


def _make_historial(pedido_id=None):
    h = MagicMock()
    h.id = uuid.uuid4()
    h.pedido_id = pedido_id or uuid.uuid4()
    h.estado_desde = None
    h.estado_hasta = "PENDIENTE"
    h.motivo = None
    h.created_at = MagicMock()
    return h


def _make_uow_with_pedidos_repo(
    productos=None,
    forma_pago=None,
    direccion=None,
    ingredientes_batch=None,
    pedido_mock=None,
    detalle_mock=None,
    historial_mock=None,
):
    """Build a UoW mock with a fully-wired pedidos repository."""
    uow = MagicMock()
    repo = MagicMock()

    # lock_productos_for_update
    repo.lock_productos_for_update = AsyncMock(return_value=productos or [])

    # get_forma_pago
    repo.get_forma_pago = AsyncMock(return_value=forma_pago)

    # get_direccion_usuario
    repo.get_direccion_usuario = AsyncMock(return_value=direccion)

    # get_direccion_by_id (for ADDRESS_NOT_FOUND vs ADDRESS_NOT_OWNED disambiguation)
    repo.get_direccion_by_id = AsyncMock(return_value=None)

    # get_ingredientes_batch
    repo.get_ingredientes_batch = AsyncMock(return_value=ingredientes_batch or {})

    # create_pedido — returns a mock Pedido with id populated
    _pedido = pedido_mock or _make_pedido()
    repo.create_pedido = AsyncMock(return_value=_pedido)

    # create_detalle — returns a mock DetallePedido
    _detalle = detalle_mock or _make_detalle(pedido_id=_pedido.id)
    repo.create_detalle = AsyncMock(return_value=_detalle)

    # create_historial — returns a mock HistorialEstadoPedido
    _historial = historial_mock or _make_historial(pedido_id=_pedido.id)
    repo.create_historial = AsyncMock(return_value=_historial)

    # decrement_stock
    repo.decrement_stock = AsyncMock(return_value=None)

    uow.pedidos = repo
    return uow


# ---------------------------------------------------------------------------
# PASO 1: Validación de carrito vacío
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_empty_cart():
    """Task 6.2: carrito vacío → CartEmptyError 400 CART_EMPTY.

    Note: PedidoCreate has min_length=1 on items — Pydantic catches this before
    the service can. To test the service-level guard, we bypass Pydantic validation
    by constructing the request with model_construct (no validation).
    This also verifies the service has its own guard as a defense-in-depth layer.
    """
    uow = MagicMock()
    # Bypass Pydantic min_length=1 to test service-level guard
    request = PedidoCreate.model_construct(items=[], forma_pago_codigo=FORMA_PAGO)

    with pytest.raises(CartEmptyError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "CART_EMPTY"
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# PASO 3: Validación de producto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_product_not_found():
    """Task 6.3: producto inexistente (no retornado por lock_for_update) → PRODUCT_NOT_FOUND."""
    uow = _make_uow_with_pedidos_repo(productos=[])  # empty → not found
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(ProductNotFoundError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_order_product_soft_deleted():
    """Task 6.4: producto con deleted_at no nulo → PRODUCT_NOT_AVAILABLE."""
    from datetime import datetime

    producto = _make_producto(producto_id=PRODUCTO_ID, deleted_at=datetime.utcnow())
    uow = _make_uow_with_pedidos_repo(productos=[producto])
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(ProductNotAvailableError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "PRODUCT_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_create_order_product_not_disponible():
    """Task 6.5: producto con disponible=False → PRODUCT_NOT_AVAILABLE."""
    producto = _make_producto(producto_id=PRODUCTO_ID, disponible=False)
    uow = _make_uow_with_pedidos_repo(productos=[producto])
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(ProductNotAvailableError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "PRODUCT_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_create_order_insufficient_stock():
    """Task 6.6: stock < cantidad solicitada → InsufficientStockError 409 INSUFFICIENT_STOCK."""
    producto = _make_producto(producto_id=PRODUCTO_ID, stock_cantidad=2)
    uow = _make_uow_with_pedidos_repo(productos=[producto])
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=5)],  # 5 > 2
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(InsufficientStockError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# PASO 5: Validación de personalización
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_invalid_customization_not_removable():
    """Task 6.7: ingrediente no removible → INVALID_CUSTOMIZATION."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    # Ingredient exists but es_removible=False
    pi = MagicMock()
    pi.ingrediente_id = INGREDIENTE_ID
    pi.es_removible = False
    ingredientes_batch = {PRODUCTO_ID: [pi]}

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        ingredientes_batch=ingredientes_batch,
    )
    request = PedidoCreate(
        items=[
            ItemPedidoCreate(
                producto_id=PRODUCTO_ID,
                cantidad=1,
                exclusiones=[INGREDIENTE_ID],
            )
        ],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(InvalidCustomizationError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "INVALID_CUSTOMIZATION"


@pytest.mark.asyncio
async def test_create_order_invalid_customization_wrong_product():
    """Task 6.7b: ingrediente que no pertenece al producto → INVALID_CUSTOMIZATION."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    ingredientes_batch = {PRODUCTO_ID: []}  # No ingredients for this product

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        ingredientes_batch=ingredientes_batch,
    )
    request = PedidoCreate(
        items=[
            ItemPedidoCreate(
                producto_id=PRODUCTO_ID,
                cantidad=1,
                exclusiones=[INGREDIENTE_ID],  # Doesn't belong to product
            )
        ],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(InvalidCustomizationError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "INVALID_CUSTOMIZATION"


# ---------------------------------------------------------------------------
# PASO 6: Validación de forma de pago
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_payment_method_not_found():
    """Task 6.8: forma de pago inexistente → PAYMENT_METHOD_INVALID."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=None,  # Not found
    )
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo="INEXISTENTE",
    )

    with pytest.raises(PaymentMethodInvalidError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "PAYMENT_METHOD_INVALID"


@pytest.mark.asyncio
async def test_create_order_payment_method_disabled():
    """Task 6.9: forma de pago con habilitado=False → PAYMENT_METHOD_INVALID."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    forma_pago = _make_forma_pago(habilitado=False)
    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
    )
    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    with pytest.raises(PaymentMethodInvalidError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "PAYMENT_METHOD_INVALID"


# ---------------------------------------------------------------------------
# PASO 7: Validación de dirección
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_address_not_owned():
    """Task 6.10: direccion_id existe pero pertenece a otro usuario → ADDRESS_NOT_OWNED."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    forma_pago = _make_forma_pago()
    otra_direccion = _make_direccion(usuario_id=uuid.uuid4())  # Different user

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        direccion=None,  # get_direccion_usuario returns None (not owned)
    )
    # get_direccion_by_id returns the address (exists but wrong user)
    uow.pedidos.get_direccion_by_id = AsyncMock(return_value=otra_direccion)

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
        direccion_id=DIRECCION_ID,
    )

    with pytest.raises(AddressNotOwnedError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "ADDRESS_NOT_OWNED"


@pytest.mark.asyncio
async def test_create_order_address_not_found():
    """ADDRESS_NOT_FOUND when direccion_id doesn't exist at all."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    forma_pago = _make_forma_pago()

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        direccion=None,  # get_direccion_usuario returns None
    )
    # get_direccion_by_id also returns None (doesn't exist)
    uow.pedidos.get_direccion_by_id = AsyncMock(return_value=None)

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
        direccion_id=DIRECCION_ID,
    )

    with pytest.raises(AddressNotFoundError) as exc_info:
        await crear_pedido(uow, USER_ID, request)

    assert exc_info.value.code == "ADDRESS_NOT_FOUND"


# ---------------------------------------------------------------------------
# Happy path: retiro en local (direccion_id=None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_success_pickup():
    """Task 6.11: direccion_id=None → costo_envio=0.00, estado PENDIENTE."""
    producto = _make_producto(producto_id=PRODUCTO_ID, precio_base=100.0)
    forma_pago = _make_forma_pago()
    pedido_mock = _make_pedido()
    pedido_mock.direccion_id = None
    pedido_mock.costo_envio = 0.0
    pedido_mock.total = 100.0
    detalle_mock = _make_detalle(pedido_id=pedido_mock.id, producto_id=PRODUCTO_ID)
    historial_mock = _make_historial(pedido_id=pedido_mock.id)

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        pedido_mock=pedido_mock,
        detalle_mock=detalle_mock,
        historial_mock=historial_mock,
    )

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
        direccion_id=None,
    )

    result = await crear_pedido(uow, USER_ID, request)

    assert result.estado_codigo == "PENDIENTE"
    assert result.costo_envio == Decimal("0.00")
    assert result.direccion_id is None


@pytest.mark.asyncio
async def test_create_order_success_with_address():
    """Task 6.12: con dirección válida → costo_envio=50.00."""
    producto = _make_producto(producto_id=PRODUCTO_ID, precio_base=100.0)
    forma_pago = _make_forma_pago()
    direccion = _make_direccion()
    pedido_mock = _make_pedido()
    pedido_mock.direccion_id = DIRECCION_ID
    pedido_mock.costo_envio = 50.0
    pedido_mock.total = 150.0
    detalle_mock = _make_detalle(pedido_id=pedido_mock.id)
    historial_mock = _make_historial(pedido_id=pedido_mock.id)

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        direccion=direccion,
        pedido_mock=pedido_mock,
        detalle_mock=detalle_mock,
        historial_mock=historial_mock,
    )

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
        direccion_id=DIRECCION_ID,
    )

    result = await crear_pedido(uow, USER_ID, request)

    assert result.costo_envio == Decimal("50.00")


# ---------------------------------------------------------------------------
# Totales calculados server-side (Task 6.13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_totals_server_side():
    """Task 6.13: totales calculados en service, no desde el request."""
    # Two products with different prices
    pid1 = uuid.uuid4()
    pid2 = uuid.uuid4()
    producto1 = _make_producto(producto_id=pid1, precio_base=100.0)
    producto2 = _make_producto(producto_id=pid2, precio_base=50.0)
    forma_pago = _make_forma_pago()
    pedido_mock = _make_pedido()
    pedido_mock.costo_envio = 0.0
    pedido_mock.total = 250.0
    detalle_mock1 = _make_detalle(pedido_id=pedido_mock.id, producto_id=pid1)
    detalle_mock2 = _make_detalle(pedido_id=pedido_mock.id, producto_id=pid2)

    call_count = 0

    async def create_detalle_side_effect(detalle):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return detalle_mock1
        return detalle_mock2

    historial_mock = _make_historial(pedido_id=pedido_mock.id)

    uow = _make_uow_with_pedidos_repo(
        productos=[producto1, producto2],
        forma_pago=forma_pago,
        pedido_mock=pedido_mock,
        detalle_mock=detalle_mock1,
        historial_mock=historial_mock,
    )
    uow.pedidos.create_detalle = AsyncMock(side_effect=create_detalle_side_effect)

    request = PedidoCreate(
        items=[
            ItemPedidoCreate(producto_id=pid1, cantidad=2),  # 100 * 2 = 200
            ItemPedidoCreate(producto_id=pid2, cantidad=1),  # 50 * 1 = 50
        ],
        forma_pago_codigo=FORMA_PAGO,
        direccion_id=None,
    )

    result = await crear_pedido(uow, USER_ID, request)

    # subtotal = 200 + 50 = 250, costo_envio = 0, total = 250
    assert result.subtotal == Decimal("250.00")
    assert result.costo_envio == Decimal("0.00")
    assert result.total == Decimal("250.00")


# ---------------------------------------------------------------------------
# Snapshots inmutables (Tasks 6.14, 6.15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_snapshots_frozen():
    """Tasks 6.14-6.15: nombre_snapshot y precio_snapshot se copian del producto."""
    producto = _make_producto(
        producto_id=PRODUCTO_ID,
        nombre="Pizza Margherita",
        precio_base=850.0,
    )
    forma_pago = _make_forma_pago()
    pedido_mock = _make_pedido()

    # The detalle we return captures the snapshot values
    detalle_mock = _make_detalle(pedido_id=pedido_mock.id)
    detalle_mock.nombre_snapshot = "Pizza Margherita"
    detalle_mock.precio_snapshot = 850.0

    captured_detalle = {}

    async def capture_create_detalle(detalle):
        captured_detalle["obj"] = detalle
        return detalle_mock

    historial_mock = _make_historial(pedido_id=pedido_mock.id)

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        pedido_mock=pedido_mock,
        historial_mock=historial_mock,
    )
    uow.pedidos.create_detalle = AsyncMock(side_effect=capture_create_detalle)

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    await crear_pedido(uow, USER_ID, request)

    # Verify the detalle was created with snapshot values from the product
    detalle_created = captured_detalle["obj"]
    assert detalle_created.nombre_snapshot == "Pizza Margherita"
    assert float(detalle_created.precio_snapshot) == 850.0


# ---------------------------------------------------------------------------
# Historial inicial (Task 6.16)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_initial_history():
    """Task 6.16: HistorialEstadoPedido creado con estado_desde=None, estado_hasta=PENDIENTE."""
    producto = _make_producto(producto_id=PRODUCTO_ID)
    forma_pago = _make_forma_pago()
    pedido_mock = _make_pedido()
    detalle_mock = _make_detalle(pedido_id=pedido_mock.id)

    captured_historial = {}

    async def capture_create_historial(historial):
        captured_historial["obj"] = historial
        h = _make_historial(pedido_id=pedido_mock.id)
        h.estado_desde = historial.estado_desde
        h.estado_hasta = historial.estado_hasta
        return h

    uow = _make_uow_with_pedidos_repo(
        productos=[producto],
        forma_pago=forma_pago,
        pedido_mock=pedido_mock,
        detalle_mock=detalle_mock,
    )
    uow.pedidos.create_historial = AsyncMock(side_effect=capture_create_historial)

    request = PedidoCreate(
        items=[ItemPedidoCreate(producto_id=PRODUCTO_ID, cantidad=1)],
        forma_pago_codigo=FORMA_PAGO,
    )

    result = await crear_pedido(uow, USER_ID, request)

    # Verify historial in response
    assert len(result.historial) == 1
    h = result.historial[0]
    assert h.estado_desde is None  # RN-02
    assert h.estado_hacia == "PENDIENTE"

    # Verify what was passed to create_historial
    h_created = captured_historial["obj"]
    assert h_created.estado_desde is None
    assert h_created.estado_hasta == "PENDIENTE"


# ---------------------------------------------------------------------------
# Lock order (Task 6.18)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_order_ascending_by_id():
    """Task 6.18: los productos se lockan en orden ascendente por ID (anti-deadlock)."""
    pid_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    pid_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    pid_c = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    producto_a = _make_producto(producto_id=pid_a)
    producto_b = _make_producto(producto_id=pid_b)
    producto_c = _make_producto(producto_id=pid_c)

    called_with_ids = []

    async def lock_side_effect(ids):
        called_with_ids.extend(ids)
        return [producto_a, producto_b, producto_c]

    uow = _make_uow_with_pedidos_repo(
        productos=[producto_a, producto_b, producto_c],
        forma_pago=_make_forma_pago(),
    )
    uow.pedidos.lock_productos_for_update = AsyncMock(side_effect=lock_side_effect)

    pedido_mock = _make_pedido()
    detalle_mock = _make_detalle(pedido_id=pedido_mock.id)
    historial_mock = _make_historial(pedido_id=pedido_mock.id)
    uow.pedidos.create_pedido = AsyncMock(return_value=pedido_mock)
    uow.pedidos.create_detalle = AsyncMock(return_value=detalle_mock)
    uow.pedidos.create_historial = AsyncMock(return_value=historial_mock)

    # Request with items in NON-sorted order: C, A, B
    request = PedidoCreate(
        items=[
            ItemPedidoCreate(producto_id=pid_c, cantidad=1),
            ItemPedidoCreate(producto_id=pid_a, cantidad=1),
            ItemPedidoCreate(producto_id=pid_b, cantidad=1),
        ],
        forma_pago_codigo=FORMA_PAGO,
    )

    await crear_pedido(uow, USER_ID, request)

    # Lock should be called with IDs sorted ascending: A < B < C
    assert called_with_ids == sorted([pid_a, pid_b, pid_c])


# ---------------------------------------------------------------------------
# Schemas: PedidoCreate rechaza carrito vacío a nivel Pydantic
# ---------------------------------------------------------------------------


def test_pedido_create_rejects_empty_items():
    """Schema validation: min_length=1 on items."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PedidoCreate(items=[], forma_pago_codigo="EFECTIVO")


def test_item_pedido_create_rejects_zero_cantidad():
    """Schema validation: cantidad ge=1."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ItemPedidoCreate(producto_id=uuid.uuid4(), cantidad=0)
