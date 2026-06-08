"""
Router de pedidos.

Change 17: POST /pedidos — order creation with snapshots.
Change 18: PATCH /pedidos/{id}/estado — FSM state transitions (staff).
           DELETE /pedidos/{id} — client self-cancellation.
           GET /pedidos/{id}/historial — order state history.
Change 20: GET /pedidos — paginated listing with RBAC discrimination.
           GET /pedidos/{id} — full order detail.

Expone los endpoints (montados con prefix="/pedidos" en build_v1_router):
  POST   /                → POST /api/v1/pedidos         (Change 17)
  GET    /                → GET  /api/v1/pedidos          (Change 20)
  PATCH  /{id}/estado     → PATCH /api/v1/pedidos/{id}/estado (Change 18)
  GET    /{id}/historial  → GET /api/v1/pedidos/{id}/historial (Change 18)
  GET    /{id}            → GET /api/v1/pedidos/{id}      (Change 20)
  DELETE /{id}            → DELETE /api/v1/pedidos/{id}   (Change 18)

IMPORTANT: Route declaration order matters for FastAPI path matching.
Static/root paths BEFORE dynamic {id} paths to avoid ambiguity.
Declared order: POST / → GET / → PATCH /{id}/estado → GET /{id}/historial
                → GET /{id} → DELETE /{id}.

Coexiste con pedidos_validar_router (Change 16) que expone POST /validar.
Ambos se montan con prefix="/pedidos" en build_v1_router — no hay colisión.

Design decisions:
- D-01: El router extrae usuario_id del JWT (current_user.id) y lo pasa al service.
  No acepta usuario_id del body del request.
- D-02: require_role("CLIENT", "ADMIN") — same roles as /pedidos/validar (POST).
- D-07: El UoW se abre DENTRO del service handler, no en el router.
- RFC 7807: Los errores del domain (stock, personalización, etc.) son
  AppError subclasses que el error handler de errors.py convierte a RFC 7807.
- Change 18 / D-12: service functions are imported from state_transition.py —
  not inline logic. Router only does: inject deps → call service → return response.
- Change 20 / D-15: GET / uses require_role(CLIENT, PEDIDOS, ADMIN) — STOCK is 403.
  GET /{id} uses get_current_user — service enforces RBAC (D-02).

session.commit() es NUNCA llamado aquí — UnitOfWork lo maneja en __aexit__.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import get_current_user, require_role
from app.core.uow import UnitOfWork
from app.models.order import DetallePedido, HistorialEstadoPedido, Pedido
from app.models.user import Usuario
from app.schemas.base import Page, create_pagination_meta
from app.schemas.pedidos import (
    DetallePedidoRead,
    HistorialEstadoPedidoRead,
    PedidoCreate,
    PedidoDetail,
    PedidoEstadoUpdate,
    PedidoListItem,
    PedidoRead,
)
from app.services.pedidos_service import (
    ListPedidosParams,
    crear_pedido,
    get_pedido_detail,
    list_pedidos,
)
from app.services.state_transition import cancel_own_client, transition_state

pedidos_router = APIRouter()


async def _load_pedido_for_response(uow, pedido_id: uuid.UUID) -> PedidoRead:
    """Load a Pedido with all relations needed for PedidoRead response.

    Used by PATCH /{id}/estado and DELETE /{id} after state transition.
    Fetches Pedido with detalles (selectin) and historial (ordered ASC).

    Args:
        uow: Active UnitOfWork.
        pedido_id: UUID of the pedido to load.

    Returns:
        PedidoRead with all fields populated.
    """
    from decimal import Decimal

    # Load pedido with detalles (selectin is default on Pedido.detalles)
    pedido = await uow.pedidos.get_by_id(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # Load historial ordered ASC
    stmt = (
        select(HistorialEstadoPedido)
        .where(HistorialEstadoPedido.pedido_id == pedido_id)
        .order_by(HistorialEstadoPedido.created_at.asc())
    )
    result = await uow.session.execute(stmt)
    historial_rows = result.scalars().all()

    detalles_read = [
        DetallePedidoRead.model_validate(d) for d in pedido.detalles
    ]
    historial_read = [
        HistorialEstadoPedidoRead.model_validate(h) for h in historial_rows
    ]

    return PedidoRead(
        id=pedido.id,  # type: ignore[arg-type]
        usuario_id=pedido.usuario_id,
        estado_codigo=pedido.estado_codigo,
        forma_pago_codigo=pedido.forma_pago_codigo,
        direccion_id=pedido.direccion_id,
        subtotal=Decimal(str(pedido.total)) - Decimal(str(pedido.costo_envio)),
        costo_envio=Decimal(str(pedido.costo_envio)),
        total=Decimal(str(pedido.total)),
        notas=pedido.notas,
        items=detalles_read,
        historial=historial_read,
        created_at=pedido.created_at,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Route 1: POST / — Create order (Change 17)
# ---------------------------------------------------------------------------


@pedidos_router.post(
    "",
    response_model=PedidoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear pedido",
    description=(
        "Crea un pedido de forma atómica con SELECT FOR UPDATE para prevenir overselling. "
        "Re-ejecuta todas las validaciones (stock, disponibilidad, personalización, "
        "forma de pago, dirección) dentro de la misma transacción. "
        "Retorna HTTP 201 con el pedido creado incluyendo snapshots y primer historial. "
        "Requiere autenticación CLIENT o ADMIN (D-02)."
    ),
    tags=["pedidos"],
)
async def crear_pedido_endpoint(
    request: PedidoCreate,
    current_user: Usuario = Depends(require_role("CLIENT", "ADMIN")),
) -> PedidoRead:
    """Crea un pedido transaccional para el usuario autenticado.

    El usuario_id se extrae del JWT (current_user.id) — nunca del request body.
    El UoW se abre dentro del handler para garantizar que el COMMIT ocurra después
    de que el response model sea validado.

    Args:
        request: PedidoCreate con ítems, forma_pago_codigo, direccion_id, notas.
        current_user: Usuario autenticado con rol CLIENT o ADMIN.

    Returns:
        PedidoRead con todos los campos del pedido creado.

    Raises:
        CartEmptyError (400): Si items está vacío.
        ProductNotFoundError (400): Si algún producto no existe.
        ProductNotAvailableError (400): Si algún producto no está disponible.
        InsufficientStockError (409): Si stock insuficiente.
        InvalidCustomizationError (400): Si exclusión inválida.
        PaymentMethodInvalidError (400): Si forma de pago inválida.
        AddressNotFoundError (400): Si dirección no existe.
        AddressNotOwnedError (403): Si dirección no pertenece al usuario.
    """
    async with UnitOfWork() as uow:
        return await crear_pedido(uow, current_user.id, request)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Route 2: GET / — Paginated listing with RBAC (Change 20)
# ---------------------------------------------------------------------------


@pedidos_router.get(
    "",
    response_model=Page[PedidoListItem],
    summary="Listar pedidos paginado",
    description=(
        "Retorna pedidos paginados con discriminación por rol. "
        "CLIENT ve únicamente sus propios pedidos. "
        "PEDIDOS y ADMIN ven todos los pedidos del sistema con filtros opcionales. "
        "STOCK recibe HTTP 403. "
        "Ordenado por created_at DESC."
    ),
    tags=["pedidos"],
)
async def list_pedidos_endpoint(
    estado: str | None = Query(default=None, description="Filtrar por estado_codigo"),
    desde: date | None = Query(default=None, description="Fecha de inicio (ISO 8601, solo PEDIDOS/ADMIN)"),
    hasta: date | None = Query(default=None, description="Fecha de fin (ISO 8601, solo PEDIDOS/ADMIN)"),
    cliente: str | None = Query(default=None, description="Búsqueda por email o nombre (solo PEDIDOS/ADMIN, mínimo 3 chars)"),
    page: int = Query(default=1, ge=1, description="Número de página (1-based)"),
    size: int = Query(default=20, ge=1, le=100, description="Tamaño de página (máximo 100)"),
    current_user: Usuario = Depends(require_role("CLIENT", "PEDIDOS", "ADMIN")),
) -> Page[PedidoListItem]:
    """Paginated order listing with RBAC discrimination.

    CLIENT → filtered by current_user.id, admin params ignored.
    PEDIDOS/ADMIN → all orders, optional filters applied.
    STOCK → blocked at require_role level (403).

    If desde > hasta (for PEDIDOS/ADMIN), returns 422 INVALID_DATE_RANGE.

    Args:
        estado: Optional estado_codigo filter.
        desde: Optional lower bound date (PEDIDOS/ADMIN only).
        hasta: Optional upper bound date (PEDIDOS/ADMIN only).
        cliente: Optional client search string (PEDIDOS/ADMIN only, ≥3 chars to apply).
        page: Current page (1-based).
        size: Page size (max 100).
        current_user: Authenticated user with CLIENT, PEDIDOS, or ADMIN role.

    Returns:
        Page[PedidoListItem] with pagination metadata.
    """
    # Validate date range (for PEDIDOS/ADMIN — CLIENT ignores desde/hasta anyway)
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "El parámetro 'desde' no puede ser posterior a 'hasta'.",
                "code": "INVALID_DATE_RANGE",
            },
        )

    params = ListPedidosParams(
        estado=estado,
        desde=desde,
        hasta=hasta,
        cliente=cliente,
        page=page,
        size=size,
    )

    async with UnitOfWork() as uow:
        items, total = await list_pedidos(uow, current_user, params)

    meta = create_pagination_meta(total=total, page=page, size=size)
    return Page[PedidoListItem](items=items, **meta)


# ---------------------------------------------------------------------------
# Route 3: PATCH /{pedido_id}/estado — FSM state transition (Change 18)
# ---------------------------------------------------------------------------


@pedidos_router.patch(
    "/{pedido_id}/estado",
    response_model=PedidoRead,
    summary="Avanzar estado de pedido",
    description=(
        "Avanza el estado de un pedido siguiendo la FSM definida. "
        "Solo roles PEDIDOS y ADMIN pueden usar este endpoint. "
        "Validación FSM + RBAC fino por transición. "
        "motivo obligatorio para CANCELADO (RN-05). "
        "Restaura stock si se cancela desde CONFIRMADO o EN_PREP."
    ),
    tags=["pedidos"],
)
async def avanzar_estado_pedido(
    pedido_id: uuid.UUID,
    body: PedidoEstadoUpdate,
    current_user: Usuario = Depends(require_role("PEDIDOS", "ADMIN")),
) -> PedidoRead:
    """Advance order state (staff only). Validates FSM + RBAC per transition.

    Args:
        pedido_id: UUID of the order to transition.
        body: PedidoEstadoUpdate with nuevo_estado and optional motivo.
        current_user: Authenticated usuario with PEDIDOS or ADMIN role.

    Returns:
        PedidoRead with updated order state.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 409: Terminal state or invalid FSM transition.
        HTTPException 403: Role not permitted for this specific transition.
        HTTPException 422: motivo required for CANCELADO but not provided.
    """
    async with UnitOfWork() as uow:
        await transition_state(
            uow, pedido_id, body.nuevo_estado, body.motivo, current_user
        )
        # Load full pedido with detalles and historial for the response
        pedido_full = await _load_pedido_for_response(uow, pedido_id)
    return pedido_full


# ---------------------------------------------------------------------------
# Route 4: GET /{pedido_id}/historial — Order state history (Change 18)
# ---------------------------------------------------------------------------


@pedidos_router.get(
    "/{pedido_id}/historial",
    response_model=list[HistorialEstadoPedidoRead],
    summary="Historial de estados del pedido",
    description=(
        "Retorna el historial completo de transiciones de estado del pedido, "
        "ordenado cronológicamente (ASC). "
        "CLIENT solo puede ver historial de sus propios pedidos. "
        "PEDIDOS y ADMIN pueden ver cualquier pedido."
    ),
    tags=["pedidos"],
)
async def get_historial_pedido(
    pedido_id: uuid.UUID,
    current_user: Usuario = Depends(require_role("CLIENT", "PEDIDOS", "ADMIN")),
) -> list[HistorialEstadoPedidoRead]:
    """Get order state history. Ordered by created_at ASC.

    Authorization: owner OR staff. CLIENT must own the order.

    Args:
        pedido_id: UUID of the order to retrieve history for.
        current_user: Authenticated usuario with CLIENT, PEDIDOS, or ADMIN role.

    Returns:
        List of HistorialEstadoPedidoRead ordered by created_at ASC.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 403: CLIENT trying to view another user's order.
    """
    async with UnitOfWork() as uow:
        # Use get_by_id from BaseRepository — includes deleted_at IS NULL filter
        # which is correct since orders are not soft-deleted
        pedido = await uow.pedidos.get_by_id(pedido_id)
        if pedido is None:
            raise HTTPException(
                status_code=404,
                detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
            )
        # CLIENT ownership check
        # current_user.usuario_roles → List[UsuarioRol]; each UsuarioRol has ur.rol.codigo
        roles = [
            ur.rol.codigo
            for ur in current_user.usuario_roles
            if ur.rol is not None and ur.deleted_at is None
        ]
        if "CLIENT" in roles and pedido.usuario_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail={
                    "detail": "No tiene permiso para operar sobre este pedido.",
                    "code": "ORDER_NOT_OWNED",
                },
            )
        # Fetch historial ordered ASC
        stmt = (
            select(HistorialEstadoPedido)
            .where(HistorialEstadoPedido.pedido_id == pedido_id)
            .order_by(HistorialEstadoPedido.created_at.asc())
        )
        result = await uow.session.execute(stmt)
        historial_rows = result.scalars().all()

    return [HistorialEstadoPedidoRead.model_validate(h) for h in historial_rows]


# ---------------------------------------------------------------------------
# Route 5: GET /{pedido_id} — Full order detail (Change 20)
# ---------------------------------------------------------------------------


@pedidos_router.get(
    "/{pedido_id}",
    response_model=PedidoDetail,
    summary="Detalle completo del pedido",
    description=(
        "Retorna el detalle completo de un pedido incluyendo items con snapshots, "
        "historial de estados, datos del usuario y pago más reciente. "
        "CLIENT solo puede ver sus propios pedidos (403 para pedidos ajenos). "
        "PEDIDOS y ADMIN pueden ver cualquier pedido. "
        "STOCK recibe 403 siempre."
    ),
    tags=["pedidos"],
)
async def get_pedido_detail_endpoint(
    pedido_id: uuid.UUID,
    current_user: Usuario = Depends(get_current_user),
) -> PedidoDetail:
    """Get full order detail with RBAC validation.

    Authorization enforced by the service layer:
    - CLIENT: must own the order (403 if not owner, 404 if not found).
    - PEDIDOS/ADMIN: can access any order.
    - STOCK: 403 always.

    Args:
        pedido_id: UUID of the pedido to retrieve.
        current_user: Authenticated Usuario (any role).

    Returns:
        PedidoDetail with items, historial, usuario, direccion, pago.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 403: STOCK role, or CLIENT accessing another user's order.
    """
    async with UnitOfWork() as uow:
        return await get_pedido_detail(uow, pedido_id, current_user)


# ---------------------------------------------------------------------------
# Route 6: DELETE /{pedido_id} — Client self-cancellation (Change 18)
# ---------------------------------------------------------------------------


@pedidos_router.delete(
    "/{pedido_id}",
    response_model=PedidoRead,
    summary="Cancelar pedido propio (cliente)",
    description=(
        "Permite al cliente cancelar su propio pedido en estado PENDIENTE o CONFIRMADO. "
        "motivo obligatorio (RN-05). "
        "Restaura stock si el pedido estaba en CONFIRMADO."
    ),
    tags=["pedidos"],
)
async def cancelar_pedido_cliente(
    pedido_id: uuid.UUID,
    body: PedidoEstadoUpdate = Body(
        default=PedidoEstadoUpdate(nuevo_estado="CANCELADO")
    ),
    current_user: Usuario = Depends(require_role("CLIENT")),
) -> PedidoRead:
    """Cancel own order (CLIENT only). Accepts PENDIENTE or CONFIRMADO.

    Args:
        pedido_id: UUID of the order to cancel.
        body: PedidoEstadoUpdate — nuevo_estado is ignored (always CANCELADO),
              motivo is required.
        current_user: Authenticated usuario with CLIENT role.

    Returns:
        PedidoRead with cancelled order.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 403: Order not owned by current_user.
        HTTPException 409: Order not in PENDIENTE or CONFIRMADO.
        HTTPException 422: motivo required but not provided.
    """
    async with UnitOfWork() as uow:
        await cancel_own_client(uow, pedido_id, body.motivo, current_user)
        # Load full pedido with detalles and historial for the response
        pedido_full = await _load_pedido_for_response(uow, pedido_id)
    return pedido_full
