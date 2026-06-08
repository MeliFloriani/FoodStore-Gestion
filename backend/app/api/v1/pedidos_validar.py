"""
Router de validación pre-checkout.

Expone el endpoint:
  POST /validar  (montado en build_v1_router con prefix="/pedidos")
  → Ruta final: POST /api/v1/pedidos/validar

Decisión D-01: Endpoint dedicado independiente de POST /api/v1/pedidos.
Decisión D-02: require_role(["CLIENT", "ADMIN"]) — no público (anti-scraping).
Decisión D-05: Siempre responde 200 OK con ok: bool y lista de cambios.
  Los errores de negocio (stock, precio) son datos en el payload, no 4xx.

Este router NO usa session.commit() — el UoW es solo lectura para esta operación.
La lógica de negocio vive exclusivamente en pedidos_validar_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.schemas.pedidos_validar import (
    ValidarPreCheckoutRequest,
    ValidarPreCheckoutResponse,
)
from app.services import pedidos_validar_service

pedidos_validar_router = APIRouter()


@pedidos_validar_router.post(
    "/validar",
    response_model=ValidarPreCheckoutResponse,
    summary="Validar carrito pre-checkout",
    description=(
        "Valida los ítems del carrito del cliente contra el estado actual de la BD. "
        "Stateless e idempotente: no crea pedidos, no modifica stock. "
        "Siempre devuelve HTTP 200 con ok flag y lista de cambios detectados. "
        "Requiere autenticación CLIENT o ADMIN (D-02)."
    ),
    tags=["pedidos-validacion"],
)
async def validar_pre_checkout(
    request: ValidarPreCheckoutRequest,
    uow: UnitOfWork = Depends(get_uow),
    _usuario=Depends(require_role("CLIENT", "ADMIN")),
) -> ValidarPreCheckoutResponse:
    """Valida el carrito del cliente y reporta discrepancias sin crear pedido.

    Args:
        request: Lista de ítems del carrito con precios percibidos.
        uow: UnitOfWork inyectado por FastAPI DI.
        _usuario: Usuario autenticado con rol CLIENT o ADMIN (validación RBAC).

    Returns:
        ValidarPreCheckoutResponse con ok, items y cambios detectados.
    """
    return await pedidos_validar_service.validar_pre_checkout(uow, request)
