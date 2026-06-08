"""
Service de creación transaccional de pedidos.

Change 17: order-creation-with-snapshots.

Implementa la función crear_pedido que crea un pedido de forma atómica dentro de
un único UnitOfWork con SELECT FOR UPDATE para prevenir overselling concurrente.

Design decisions:
- D-01: Este service NO confía en los resultados de Change 16 (pedidos_validar_service).
  Re-ejecuta TODAS las validaciones dentro de su propia transacción.
- D-02: Usa SELECT FOR UPDATE (lock pesimista) sobre los productos del carrito.
  ORDER BY id previene deadlocks entre transacciones concurrentes.
- D-03: Copia nombre → nombre_snapshot y precio_base → precio_snapshot al crear
  DetallePedido. Estos valores son write-once (inmutables).
- D-04: direccion_id = None → retiro en local. Válido. costo_envio = 0.00.
- D-05: costo_envio calculado server-side. El frontend NO puede fijarlo.
- D-07: Toda la operación ocurre dentro de un único UoW. Si cualquier paso falla,
  el UoW hace rollback automático y ningún dato se persiste.
- D-11: subtotal, costo_envio, total calculados server-side desde precio_base actual.
  Los totales del frontend son ignorados.

Orden de operaciones (contrato inmutable, D-07):
  1. Validar carrito no vacío.
  2. lock_productos_for_update (ORDER BY id).
  3. Validar cada producto: existencia, disponibilidad, stock.
  4. Validar personalización (batch query, sin N+1).
  5. Validar forma de pago.
  6. Validar dirección (si not None).
  7. Calcular totales server-side.
  8. CREATE Pedido + flush.
  9. CREATE DetallePedido[] + flush por cada uno.
  10. DECREMENT stock por cada producto.
  11. CREATE HistorialEstadoPedido inicial + flush.
  12. UoW COMMIT automático al salir del async with.

Este service NO llama session.commit() directamente en ningún punto.

Change 20: orders-visualization.
  Agrega list_pedidos() con discriminación RBAC y get_pedido_detail() con RBAC+404/403.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.uow import UnitOfWork
from app.models.order import DetallePedido, HistorialEstadoPedido, Pedido
from app.schemas.pedidos import (
    DetallePedidoRead,
    DireccionBasic,
    HistorialEstadoPedidoRead,
    PedidoCreate,
    PedidoDetail,
    PedidoListItem,
    PedidoRead,
    UsuarioBasic,
)

if TYPE_CHECKING:
    from app.models.user import Usuario


class CartEmptyError(AppError):
    """Raised when the cart is empty (no items)."""

    status_code = 400
    title = "Bad Request"


class ProductNotFoundError(AppError):
    """Raised when a producto_id does not exist or is soft-deleted."""

    status_code = 400
    title = "Bad Request"


class ProductNotAvailableError(AppError):
    """Raised when a product is not available for purchase."""

    status_code = 400
    title = "Bad Request"


class InsufficientStockError(ConflictError):
    """Raised when stock_cantidad < cantidad requested (post-lock)."""

    pass


class InvalidCustomizationError(AppError):
    """Raised when an exclusion ingredient is invalid for the product."""

    status_code = 400
    title = "Bad Request"


class PaymentMethodInvalidError(AppError):
    """Raised when the payment method code is not found or is disabled."""

    status_code = 400
    title = "Bad Request"


class AddressNotFoundError(AppError):
    """Raised when direccion_id does not exist in the database."""

    status_code = 400
    title = "Bad Request"


class AddressNotOwnedError(ForbiddenError):
    """Raised when direccion_id exists but belongs to a different user."""

    pass


async def crear_pedido(
    uow: UnitOfWork,
    usuario_id: uuid.UUID,
    request: PedidoCreate,
) -> PedidoRead:
    """Crea un pedido de forma atómica con todas las validaciones transaccionales.

    Esta función debe ser llamada dentro de un `async with UnitOfWork() as uow:`.
    No llama session.commit() — el UoW lo hace automáticamente al salir del context manager.

    Args:
        uow: UnitOfWork activo (ya dentro de __aenter__).
        usuario_id: UUID del usuario autenticado (del JWT — nunca del request body).
        request: PedidoCreate con ítems, forma_pago_codigo, direccion_id, notas.

    Returns:
        PedidoRead con todos los campos del pedido creado, incluyendo detalles e historial.

    Raises:
        CartEmptyError: Si items está vacío (CART_EMPTY).
        ProductNotFoundError: Si algún producto_id no existe en BD (PRODUCT_NOT_FOUND).
        ProductNotAvailableError: Si algún producto está soft-deleted o disponible=False.
        InsufficientStockError: Si stock_cantidad < cantidad (post-lock).
        InvalidCustomizationError: Si una exclusión es inválida para el producto.
        PaymentMethodInvalidError: Si forma_pago_codigo no existe o habilitado=False.
        AddressNotFoundError: Si direccion_id no existe en BD.
        AddressNotOwnedError: Si direccion_id pertenece a otro usuario.
    """
    # -------------------------------------------------------------------------
    # PASO 1: Validar carrito no vacío
    # -------------------------------------------------------------------------
    if not request.items:
        raise CartEmptyError(
            "El carrito está vacío. Agregá al menos un producto.",
            code="CART_EMPTY",
        )

    # -------------------------------------------------------------------------
    # PASO 2: Ordenar IDs para el lock (ORDER BY id → anti-deadlock, D-02)
    # -------------------------------------------------------------------------
    producto_ids = [item.producto_id for item in request.items]
    producto_ids_sorted = sorted(set(producto_ids))

    # -------------------------------------------------------------------------
    # PASO 3: SELECT FOR UPDATE — lock pesimista sobre todos los productos
    # -------------------------------------------------------------------------
    productos_locked = await uow.pedidos.lock_productos_for_update(producto_ids_sorted)
    productos_por_id = {p.id: p for p in productos_locked}  # type: ignore[union-attr]

    # -------------------------------------------------------------------------
    # PASO 4: Validar cada ítem (existencia, disponibilidad, stock)
    # -------------------------------------------------------------------------
    for item in request.items:
        producto = productos_por_id.get(item.producto_id)

        if producto is None:
            raise ProductNotFoundError(
                f"El producto '{item.producto_id}' no existe en el catálogo.",
                code="PRODUCT_NOT_FOUND",
            )

        if producto.deleted_at is not None:  # type: ignore[union-attr]
            raise ProductNotAvailableError(
                f"El producto '{producto.nombre}' no está disponible.",  # type: ignore[union-attr]
                code="PRODUCT_NOT_AVAILABLE",
            )

        if not producto.disponible:  # type: ignore[union-attr]
            raise ProductNotAvailableError(
                f"El producto '{producto.nombre}' no está disponible.",  # type: ignore[union-attr]
                code="PRODUCT_NOT_AVAILABLE",
            )

        if producto.stock_cantidad < item.cantidad:  # type: ignore[union-attr]
            raise InsufficientStockError(
                f"Stock insuficiente para '{producto.nombre}'.",  # type: ignore[union-attr]
                code="INSUFFICIENT_STOCK",
                status_code=409,
            )

    # -------------------------------------------------------------------------
    # PASO 5: Validar personalización (batch query, sin N+1)
    # -------------------------------------------------------------------------
    ids_con_exclusiones = [item.producto_id for item in request.items if item.exclusiones]

    if ids_con_exclusiones:
        ingredientes_map = await uow.pedidos.get_ingredientes_batch(ids_con_exclusiones)

        for item in request.items:
            if not item.exclusiones:
                continue

            ingredientes_del_producto = ingredientes_map.get(item.producto_id, [])
            removibles_por_id = {
                pi.ingrediente_id: bool(pi.es_removible)  # type: ignore[union-attr]
                for pi in ingredientes_del_producto
            }

            for ing_id in item.exclusiones:
                if ing_id not in removibles_por_id:
                    raise InvalidCustomizationError(
                        f"El ingrediente '{ing_id}' no pertenece al producto o no existe.",
                        code="INVALID_CUSTOMIZATION",
                    )
                if not removibles_por_id[ing_id]:
                    raise InvalidCustomizationError(
                        f"El ingrediente '{ing_id}' no es removible.",
                        code="INVALID_CUSTOMIZATION",
                    )

    # -------------------------------------------------------------------------
    # PASO 6: Validar forma de pago
    # -------------------------------------------------------------------------
    forma_pago = await uow.pedidos.get_forma_pago(request.forma_pago_codigo)
    if forma_pago is None:
        raise PaymentMethodInvalidError(
            f"La forma de pago '{request.forma_pago_codigo}' no existe.",
            code="PAYMENT_METHOD_INVALID",
        )
    if not forma_pago.habilitado:  # type: ignore[union-attr]
        raise PaymentMethodInvalidError(
            f"La forma de pago '{request.forma_pago_codigo}' no está habilitada.",
            code="PAYMENT_METHOD_INVALID",
        )

    # -------------------------------------------------------------------------
    # PASO 7: Validar dirección (si not None)
    # -------------------------------------------------------------------------
    if request.direccion_id is not None:
        # Check ownership first
        direccion = await uow.pedidos.get_direccion_usuario(
            request.direccion_id, usuario_id
        )
        if direccion is None:
            # Distinguish ADDRESS_NOT_FOUND from ADDRESS_NOT_OWNED
            direccion_exists = await uow.pedidos.get_direccion_by_id(request.direccion_id)
            if direccion_exists is None:
                raise AddressNotFoundError(
                    f"La dirección '{request.direccion_id}' no existe.",
                    code="ADDRESS_NOT_FOUND",
                )
            else:
                raise AddressNotOwnedError(
                    "La dirección no pertenece al usuario autenticado.",
                    code="ADDRESS_NOT_OWNED",
                )

    # -------------------------------------------------------------------------
    # PASO 8: Calcular totales server-side (D-11)
    # -------------------------------------------------------------------------
    subtotal = Decimal("0.00")
    for item in request.items:
        producto = productos_por_id[item.producto_id]
        precio = Decimal(str(producto.precio_base))  # type: ignore[union-attr]
        subtotal += precio * item.cantidad

    costo_envio = (
        Decimal("50.00") if request.direccion_id is not None else Decimal("0.00")
    )
    total = subtotal + costo_envio

    # -------------------------------------------------------------------------
    # PASO 9: CREATE Pedido + flush (necesitamos el id para las FKs)
    # -------------------------------------------------------------------------
    pedido = Pedido(
        usuario_id=usuario_id,
        estado_codigo="PENDIENTE",
        forma_pago_codigo=request.forma_pago_codigo,
        direccion_id=request.direccion_id,
        total=float(total),
        costo_envio=float(costo_envio),
        notas=request.notas,
    )
    await uow.pedidos.create_pedido(pedido)

    # -------------------------------------------------------------------------
    # PASO 10: CREATE DetallePedido por cada ítem (con snapshots) + flush
    # -------------------------------------------------------------------------
    detalles: list[DetallePedido] = []
    for item in request.items:
        producto = productos_por_id[item.producto_id]
        detalle = DetallePedido(
            pedido_id=pedido.id,  # type: ignore[union-attr]
            producto_id=item.producto_id,
            nombre_snapshot=str(producto.nombre),  # type: ignore[union-attr]
            precio_snapshot=float(producto.precio_base),  # type: ignore[union-attr]
            cantidad=item.cantidad,
            # Always persist [] (never None) so future GETs don't need to
            # coerce NULL. Schema also coerces None→[] defensively for legacy rows.
            personalizacion=item.exclusiones if item.exclusiones else [],
        )
        await uow.pedidos.create_detalle(detalle)
        detalles.append(detalle)

    # -------------------------------------------------------------------------
    # PASO 11: DECREMENT stock por cada producto (UPDATE atómico)
    # -------------------------------------------------------------------------
    for item in request.items:
        await uow.pedidos.decrement_stock(item.producto_id, item.cantidad)

    # -------------------------------------------------------------------------
    # PASO 12: CREATE HistorialEstadoPedido inicial + flush
    # -------------------------------------------------------------------------
    historial_inicial = HistorialEstadoPedido(
        pedido_id=pedido.id,  # type: ignore[union-attr]
        estado_desde=None,    # RN-02: None para la transición inicial
        estado_hasta="PENDIENTE",
        cambiado_por_id=None,
        motivo=None,
    )
    await uow.pedidos.create_historial(historial_inicial)

    # -------------------------------------------------------------------------
    # PASO 13: Construir PedidoRead y retornar
    # El UoW hará COMMIT automático al salir del async with en el router.
    # -------------------------------------------------------------------------
    detalles_read = [
        DetallePedidoRead(
            id=d.id,  # type: ignore[union-attr]
            producto_id=d.producto_id,
            nombre_snapshot=d.nombre_snapshot,
            precio_snapshot=Decimal(str(d.precio_snapshot)),
            cantidad=d.cantidad,
            personalizacion=d.personalizacion or [],
        )
        for d in detalles
    ]

    historial_read = [
        HistorialEstadoPedidoRead(
            id=historial_inicial.id,  # type: ignore[union-attr]
            estado_desde=historial_inicial.estado_desde,
            estado_hacia=historial_inicial.estado_hasta,
            motivo=historial_inicial.motivo,
            created_at=historial_inicial.created_at,  # type: ignore[union-attr]
        )
    ]

    return PedidoRead(
        id=pedido.id,  # type: ignore[union-attr]
        usuario_id=pedido.usuario_id,
        estado_codigo=pedido.estado_codigo,
        forma_pago_codigo=pedido.forma_pago_codigo,
        direccion_id=pedido.direccion_id,
        subtotal=subtotal,
        costo_envio=costo_envio,
        total=total,
        notas=pedido.notas,
        items=detalles_read,
        historial=historial_read,
        created_at=pedido.created_at,  # type: ignore[union-attr]
    )


# ---------------------------------------------------------------------------
# Change 20 — orders-visualization
# ---------------------------------------------------------------------------


@dataclass
class ListPedidosParams:
    """Query parameters for list_pedidos.

    Change 20 (task 3.1): RBAC-aware listing parameters.
    CLIENT mode: only estado, page, size are meaningful (usuario_id forced by service).
    PEDIDOS/ADMIN mode: all filters applied.
    """

    estado: str | None = None
    desde: date | None = None
    hasta: date | None = None
    cliente: str | None = None
    page: int = 1
    size: int = 20


def _get_user_roles(current_user: "Usuario") -> set[str]:
    """Extract active role codes from a Usuario instance.

    Args:
        current_user: The authenticated Usuario with usuario_roles loaded.

    Returns:
        Set of role code strings (e.g. {"CLIENT"}, {"PEDIDOS", "ADMIN"}).
    """
    return {
        ur.rol.codigo
        for ur in current_user.usuario_roles
        if ur.rol is not None and ur.deleted_at is None
    }


async def list_pedidos(
    uow: UnitOfWork,
    current_user: "Usuario",
    params: ListPedidosParams,
) -> tuple[list[PedidoListItem], int]:
    """List pedidos with RBAC discrimination.

    Change 20 (task 3.1 — D-15 final):
    - Role CLIENT → ALWAYS filter WHERE pedido.usuario_id = current_user.id.
      Ignore admin filters (desde, hasta, cliente).
    - Role PEDIDOS or ADMIN → NO usuario_id filter; see ALL orders.
      Apply optional filters: estado, desde, hasta, cliente.
    - Role STOCK → caller must have already rejected via require_role.

    No direct session.commit() — UoW pattern enforced.

    Args:
        uow: Active UnitOfWork.
        current_user: Authenticated Usuario (must have valid roles loaded).
        params: ListPedidosParams with filter values.

    Returns:
        Tuple (list[PedidoListItem], total_count) for Page construction.
    """
    roles = _get_user_roles(current_user)
    is_client = "CLIENT" in roles

    if is_client:
        # CLIENT mode: filter by usuario_id, ignore admin filters
        pedidos, total = await uow.pedidos.list_with_filters(
            usuario_id=current_user.id,
            estado=params.estado,
            desde=None,   # ignored for CLIENT
            hasta=None,   # ignored for CLIENT
            cliente=None, # ignored for CLIENT
            page=params.page,
            size=params.size,
        )
    else:
        # PEDIDOS/ADMIN mode: no usuario_id filter, apply all optional filters
        pedidos, total = await uow.pedidos.list_with_filters(
            usuario_id=None,
            estado=params.estado,
            desde=params.desde,
            hasta=params.hasta,
            cliente=params.cliente,
            page=params.page,
            size=params.size,
        )

    # Build PedidoListItem list
    items: list[PedidoListItem] = []
    for pedido in pedidos:
        # Load usuario data for PEDIDOS/ADMIN responses (D-12)
        usuario_nombre: str | None = None
        usuario_email: str | None = None

        if not is_client:
            usuario = await uow.usuarios.get_by_id(pedido.usuario_id)
            if usuario is not None:
                usuario_nombre = f"{usuario.nombre} {usuario.apellido}"
                usuario_email = usuario.email

        items_count = len(pedido.detalles) if pedido.detalles is not None else 0

        items.append(
            PedidoListItem(
                id=pedido.id,  # type: ignore[union-attr]
                estado_codigo=pedido.estado_codigo,
                total=Decimal(str(pedido.total)),
                forma_pago_codigo=pedido.forma_pago_codigo,
                items_count=items_count,
                created_at=pedido.created_at,  # type: ignore[union-attr]
                usuario_nombre=usuario_nombre,
                usuario_email=usuario_email,
            )
        )

    return items, total


async def get_pedido_detail(
    uow: UnitOfWork,
    pedido_id: uuid.UUID,
    current_user: "Usuario",
) -> PedidoDetail:
    """Get full detail of a pedido with RBAC validation.

    Change 20 (task 3.2 — D-02, D-03, D-04):
    - If pedido not found → 404 ORDER_NOT_FOUND.
    - If role STOCK → 403 FORBIDDEN.
    - If role CLIENT and pedido.usuario_id != current_user.id → 403 ORDER_NOT_OWNED.
    - PEDIDOS/ADMIN → can access any pedido.

    Args:
        uow: Active UnitOfWork.
        pedido_id: UUID of the pedido to retrieve.
        current_user: Authenticated Usuario.

    Returns:
        PedidoDetail with items, historial, usuario, direccion and pago.

    Raises:
        HTTPException(404): If pedido does not exist.
        HTTPException(403): If STOCK role, or CLIENT accessing another user's pedido.
    """
    from sqlalchemy import select

    from app.models.order import HistorialEstadoPedido as HistorialModel

    roles = _get_user_roles(current_user)

    # STOCK → always 403
    if "STOCK" in roles and "CLIENT" not in roles and "PEDIDOS" not in roles and "ADMIN" not in roles:
        raise HTTPException(
            status_code=403,
            detail={"detail": "No tiene permiso para acceder a este recurso.", "code": "FORBIDDEN"},
        )

    # Fetch pedido with detalles and historial eager-loaded
    pedido = await uow.pedidos.get_full_detail(pedido_id)

    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # CLIENT ownership check (D-02)
    if "CLIENT" in roles and pedido.usuario_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"detail": "No tiene permiso para ver este pedido.", "code": "ORDER_NOT_OWNED"},
        )

    # Load related usuario (separate query — D-02)
    usuario_data: UsuarioBasic | None = None
    usuario = await uow.usuarios.get_by_id(pedido.usuario_id)
    if usuario is not None:
        usuario_data = UsuarioBasic(
            id=usuario.id,  # type: ignore[union-attr]
            nombre=usuario.nombre,
            apellido=usuario.apellido,
            email=usuario.email,
        )

    # Load direccion best-effort (D-04 / OQ-01)
    direccion_data: DireccionBasic | None = None
    if pedido.direccion_id is not None:
        # Use the already-loaded relation (lazy="selectin" on Pedido.direccion)
        if pedido.direccion is not None:
            direccion_data = DireccionBasic(
                alias=pedido.direccion.alias,
                linea1=pedido.direccion.linea1,
                linea2=pedido.direccion.linea2,
                ciudad=pedido.direccion.ciudad,
                provincia=pedido.direccion.provincia,
                codigo_postal=pedido.direccion.codigo_postal,
                referencia=pedido.direccion.referencia,
            )

    # Load pago (separate query per spec — task 2.2)
    pago = await uow.pagos.get_latest_by_pedido_id(pedido_id)

    # Build historial ordered by created_at ASC
    # Pedido.historial is loaded via selectinload — sort in Python
    historial_sorted = sorted(
        pedido.historial or [],
        key=lambda h: h.created_at,
    )
    historial_read = [
        HistorialEstadoPedidoRead.model_validate(h) for h in historial_sorted
    ]

    # Build items read
    items_read = [
        DetallePedidoRead.model_validate(d) for d in (pedido.detalles or [])
    ]

    # Build pago response
    pago_response = None
    if pago is not None:
        from app.pagos.schemas import PagoResponse
        pago_response = PagoResponse.model_validate(pago)

    return PedidoDetail(
        id=pedido.id,  # type: ignore[union-attr]
        usuario_id=pedido.usuario_id,
        usuario=usuario_data,
        estado_codigo=pedido.estado_codigo,
        forma_pago_codigo=pedido.forma_pago_codigo,
        subtotal=Decimal(str(pedido.total)) - Decimal(str(pedido.costo_envio)),
        costo_envio=Decimal(str(pedido.costo_envio)),
        total=Decimal(str(pedido.total)),
        notas=pedido.notas,
        direccion_id=pedido.direccion_id,
        direccion=direccion_data,
        items=items_read,
        historial=historial_read,
        pago=pago_response,
        created_at=pedido.created_at,  # type: ignore[union-attr]
    )
