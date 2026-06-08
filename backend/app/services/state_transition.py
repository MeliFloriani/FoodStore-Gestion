"""
FSM state transition service for Change 18.

Provides module-level functions (not a class) for:
- Validating FSM transitions per ALLOWED_TRANSITIONS map
- Advancing order states (PATCH /pedidos/{id}/estado)
- Client self-cancellation (DELETE /pedidos/{id})
- Restoring stock on cancellation from CONFIRMADO or EN_PREP

D-12: Functions, not class. Stateless. Imported by router.
D-09: uow.historial_pedido accessor introduced in Change 18.
D-10: Integrador §3.4 + RN-FS08 are authoritative — ADMIN can cancel EN_PREP.
D-11: motivo validation occurs here (service), not in Pydantic schema.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException

# FSM: PENDIENTE→CONFIRMADO for EFECTIVO: manual (staff). For MERCADOPAGO: Change 19 (webhook).
# actor_user_id=NULL in historial rows is reserved for SISTEMA (Change 19).
# Change 18 always writes non-NULL actor_user_id for manual human transitions.

ALLOWED_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "CONFIRMADO": {
        "EN_PREP": {"PEDIDOS", "ADMIN"},
        "CANCELADO": {"PEDIDOS", "ADMIN"},
    },
    "EN_PREP": {
        "EN_CAMINO": {"PEDIDOS", "ADMIN"},
        "CANCELADO": {"ADMIN"},  # Only ADMIN — RN-RB08, Integrador §3.4
    },
    "EN_CAMINO": {
        "ENTREGADO": {"PEDIDOS", "ADMIN"},
        # EN_CAMINO → CANCELADO is NOT valid — Integrador §3.4 / non-goal
    },
    # PENDIENTE → CONFIRMADO: manual for EFECTIVO (guarded in transition_state())
    # PENDIENTE → CONFIRMADO: Change 19 (automatic via MP webhook) for MERCADOPAGO
    # PENDIENTE → CANCELADO for CLIENT: via DELETE endpoint / cancel_own_client()
    # PENDIENTE → CANCELADO for staff: via PATCH / transition_state()
    "PENDIENTE": {
        "CANCELADO": {"PEDIDOS", "ADMIN"},
        "CONFIRMADO": {"PEDIDOS", "ADMIN"},  # Only for EFECTIVO — guarded in transition_state()
        # CLIENT cancels PENDIENTE exclusively via DELETE /pedidos/{id} — cancel_own_client()
    },
}

TERMINAL_STATES: frozenset[str] = frozenset({"ENTREGADO", "CANCELADO"})

STATES_REQUIRING_STOCK_RESTORE: frozenset[str] = frozenset({"CONFIRMADO", "EN_PREP"})


def validate_transition_allowed(
    current_state: str,
    nuevo_estado: str,
    user_roles: list[str],
) -> None:
    """Validate FSM transition. Raises HTTPException on failure.

    (a) FSM validation: checks ALLOWED_TRANSITIONS map.
    (b) RBAC fine-grained: checks role in allowed set for this specific transition.

    Layers: this is FSM+fine-RBAC. Coarse RBAC (require_role) is in the router.

    Args:
        current_state: Current order estado_codigo.
        nuevo_estado: Target estado_codigo for the transition.
        user_roles: List of role codes the authenticated user holds.

    Raises:
        HTTPException 409: If current state is terminal or transition is invalid.
        HTTPException 403: If user role is not permitted for this transition.
    """
    if current_state in TERMINAL_STATES:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "El pedido está en un estado terminal y no admite más transiciones.",
                "code": "TERMINAL_STATE",
            },
        )
    transitions = ALLOWED_TRANSITIONS.get(current_state, {})
    allowed_roles = transitions.get(nuevo_estado)
    if allowed_roles is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "La transición solicitada no es válida desde el estado actual.",
                "code": "INVALID_TRANSITION",
            },
        )
    # Fine-grained RBAC per transition
    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "Su rol no tiene permiso para cancelar pedidos en este estado.",
                "code": "CANCEL_NOT_ALLOWED_FOR_ROLE",
            },
        )


async def _restore_stock(uow, pedido_id: uuid.UUID) -> None:
    """Restore stock for all items in a cancelled order. Must be called inside same UoW.

    Only called when cancelling from CONFIRMADO or EN_PREP (stock was previously
    decremented by Change 19). Uses additive UPDATE to avoid race conditions.

    Args:
        uow: Active UnitOfWork (inside async with UnitOfWork() as uow).
        pedido_id: UUID of the order whose stock should be restored.
    """
    from sqlalchemy import select
    from sqlalchemy import update as sa_update

    from app.models.catalog import Producto
    from app.models.order import DetallePedido

    # Get all order items
    stmt = select(DetallePedido).where(DetallePedido.pedido_id == pedido_id)
    result = await uow._session.execute(stmt)
    detalles = result.scalars().all()

    for detalle in detalles:
        restore_stmt = (
            sa_update(Producto)
            .where(Producto.id == detalle.producto_id)
            .values(stock_cantidad=Producto.stock_cantidad + detalle.cantidad)
        )
        await uow._session.execute(restore_stmt)
    await uow._session.flush()


async def transition_state(
    uow,
    pedido_id: uuid.UUID,
    nuevo_estado: str,
    motivo: str | None,
    current_user,
) -> object:
    """Advance order state. Called by PATCH /pedidos/{id}/estado (staff only).

    Steps:
    1. SELECT pedido FOR UPDATE (pessimistic lock)
    2. Check terminal state
    3. Validate FSM transition + fine-grained RBAC
    4. Validate motivo if CANCELADO (RN-05)
    5. Restore stock if cancelling from CONFIRMADO or EN_PREP
    6. update_estado
    7. Append HistorialEstadoPedido

    actor_user_id is always non-NULL (human manual transition).
    NULL is reserved for SISTEMA (Change 19 webhook).

    Args:
        uow: Active UnitOfWork.
        pedido_id: UUID of the order to transition.
        nuevo_estado: Target estado_codigo.
        motivo: Reason for transition (required for CANCELADO — RN-05).
        current_user: Authenticated Usuario with .id and .roles attributes.

    Returns:
        Updated Pedido ORM instance.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 409: Terminal state or invalid FSM transition.
        HTTPException 403: Role not permitted for this transition.
        HTTPException 422: motivo required for CANCELADO but not provided.
    """
    from app.models.order import HistorialEstadoPedido

    # Step 1: Pessimistic lock
    pedido = await uow.pedidos.get_for_update(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    current_state = pedido.estado_codigo
    # current_user.usuario_roles → List[UsuarioRol]; each UsuarioRol has ur.rol.codigo (D-30)
    user_roles = [
        ur.rol.codigo
        for ur in current_user.usuario_roles
        if ur.rol is not None and ur.deleted_at is None
    ]

    # Steps 2-3: FSM + fine-grained RBAC
    validate_transition_allowed(current_state, nuevo_estado, user_roles)

    # PENDIENTE → CONFIRMADO is only valid for EFECTIVO orders (RN-new)
    # MERCADOPAGO orders transition automatically via webhook (Change 19).
    if nuevo_estado == "CONFIRMADO" and current_state == "PENDIENTE":
        if pedido.forma_pago_codigo != "EFECTIVO":
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "Los pedidos con MercadoPago se confirman automáticamente al recibir el pago.",
                    "code": "INVALID_TRANSITION",
                },
            )

    # Step 4: motivo required for CANCELADO (RN-05) — validated in service, not schema
    if nuevo_estado == "CANCELADO" and not motivo:
        raise HTTPException(
            status_code=422,
            detail={"detail": "motivo es obligatorio al cancelar", "code": "MOTIVO_REQUIRED"},
        )

    # Step 5: Stock restoration (only CONFIRMADO or EN_PREP origin)
    if nuevo_estado == "CANCELADO" and current_state in STATES_REQUIRING_STOCK_RESTORE:
        await _restore_stock(uow, pedido_id)

    # Step 6: Update estado
    pedido_updated = await uow.pedidos.update_estado(pedido_id, nuevo_estado)

    # Step 7: Append historial (actor_user_id = authenticated user, never NULL here)
    historial = HistorialEstadoPedido(
        pedido_id=pedido_id,
        estado_desde=current_state,
        estado_hasta=nuevo_estado,
        motivo=motivo,
        cambiado_por_id=current_user.id,  # Real column name
    )
    await uow.historial_pedido.append(historial)

    return pedido_updated


async def cancel_own_client(
    uow,
    pedido_id: uuid.UUID,
    motivo: str | None,
    current_user,
) -> object:
    """Cancel CLIENT's own order. Called by DELETE /pedidos/{id} (CLIENT only).

    CLIENT can cancel PENDIENTE or CONFIRMADO (Integrador §5.3).
    Stock is restored if origin is CONFIRMADO.

    RN-05: motivo is required if cancelling (always here since nuevo_estado=CANCELADO).

    Args:
        uow: Active UnitOfWork.
        pedido_id: UUID of the order to cancel.
        motivo: Reason for cancellation (required — RN-05).
        current_user: Authenticated Usuario with .id and .usuario_id attributes.

    Returns:
        Updated Pedido ORM instance.

    Raises:
        HTTPException 404: Order not found.
        HTTPException 403: Order not owned by current_user.
        HTTPException 409: Order not in PENDIENTE or CONFIRMADO state.
        HTTPException 422: motivo required but not provided.
    """
    from app.models.order import HistorialEstadoPedido

    # Step 1: Pessimistic lock
    pedido = await uow.pedidos.get_for_update(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # Step 2: Ownership check
    if pedido.usuario_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "No tiene permiso para operar sobre este pedido.",
                "code": "ORDER_NOT_OWNED",
            },
        )

    current_state = pedido.estado_codigo

    # Step 3: Only PENDIENTE or CONFIRMADO allowed for CLIENT via DELETE
    if current_state not in {"PENDIENTE", "CONFIRMADO"}:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint.",
                "code": "INVALID_TRANSITION",
            },
        )

    # Step 4: motivo required (RN-05) — service enforcement
    if not motivo:
        raise HTTPException(
            status_code=422,
            detail={"detail": "motivo es obligatorio al cancelar", "code": "MOTIVO_REQUIRED"},
        )

    # Step 5: Stock restoration (only CONFIRMADO — PENDIENTE has no stock decremented)
    if current_state in STATES_REQUIRING_STOCK_RESTORE:
        await _restore_stock(uow, pedido_id)

    # Step 6: Update estado
    pedido_updated = await uow.pedidos.update_estado(pedido_id, "CANCELADO")

    # Step 7: Append historial (actor_user_id = CLIENT, never NULL for human transitions)
    historial = HistorialEstadoPedido(
        pedido_id=pedido_id,
        estado_desde=current_state,
        estado_hasta="CANCELADO",
        motivo=motivo,
        cambiado_por_id=current_user.id,  # Real column name
    )
    await uow.historial_pedido.append(historial)

    return pedido_updated
