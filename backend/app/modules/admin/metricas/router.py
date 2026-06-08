"""
Admin Métricas Router — Change 23: admin-metrics-dashboard.

All endpoints:
  - RBAC: require_role("ADMIN")  — matches the variadic signature of require_role in app.api.deps
  - Read-only (GET only)
  - Prefix applied externally in build_v1_router: /admin/metricas

Final mounted paths:
  GET /api/v1/admin/metricas/resumen
  GET /api/v1/admin/metricas/ventas
  GET /api/v1/admin/metricas/productos-top
  GET /api/v1/admin/metricas/pedidos-por-estado
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario

from .schemas import (
    MetricasResumenRead,
    PedidoEstadoDistribucionRead,
    ProductoTopRead,
    VentasPeriodoRead,
)
from .service import MetricasService

metricas_router = APIRouter()
_service = MetricasService()


@metricas_router.get(
    "/resumen",
    response_model=MetricasResumenRead,
    summary="KPI resumen: ventas totales, pedidos por estado, usuarios",
    tags=["admin-metricas"],
)
async def get_resumen(
    desde: Annotated[
        date | None,
        Query(description="Fecha inicio (YYYY-MM-DD, inclusive). Default: last 30 days."),
    ] = None,
    hasta: Annotated[
        date | None,
        Query(description="Fecha fin (YYYY-MM-DD, inclusive). Default: today."),
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    _admin: Usuario = Depends(require_role("ADMIN")),
) -> MetricasResumenRead:
    """Return KPI summary: total sales, orders per state, total/active users.

    Date range defaults to last 30 days when desde/hasta are omitted.
    CANCELADO orders are excluded from ventas_totales (D-23-02).
    User counts are a snapshot (no date filter — D-23-07).
    """
    return await _service.get_resumen(uow, desde, hasta)


@metricas_router.get(
    "/ventas",
    response_model=list[VentasPeriodoRead],
    summary="Evolución de ventas por período (DATE_TRUNC)",
    tags=["admin-metricas"],
)
async def get_ventas_series(
    desde: Annotated[date | None, Query(description="Fecha inicio (YYYY-MM-DD, inclusive).")] = None,
    hasta: Annotated[date | None, Query(description="Fecha fin (YYYY-MM-DD, inclusive).")] = None,
    granularidad: Annotated[
        Literal["dia", "semana", "mes"],
        Query(description="Granularidad de agrupación: dia, semana, mes."),
    ] = "dia",
    uow: UnitOfWork = Depends(get_uow),
    _admin: Usuario = Depends(require_role("ADMIN")),
) -> list[VentasPeriodoRead]:
    """Return time-series sales data grouped by granularity.

    granularidad values:
      dia    → DATE_TRUNC('day', created_at)
      semana → DATE_TRUNC('week', created_at)
      mes    → DATE_TRUNC('month', created_at)

    Results are ordered ASC by period. CANCELADO orders excluded.
    Invalid granularidad values return HTTP 422 (Pydantic validation).
    """
    return await _service.get_ventas_series(uow, desde, hasta, granularidad)


@metricas_router.get(
    "/productos-top",
    response_model=list[ProductoTopRead],
    summary="Top productos más vendidos por cantidad",
    tags=["admin-metricas"],
)
async def get_productos_top(
    top: Annotated[
        int,
        Query(ge=1, le=50, description="Número de productos a retornar (default: 10, max: 50)."),
    ] = 10,
    desde: Annotated[date | None, Query(description="Fecha inicio (YYYY-MM-DD, inclusive).")] = None,
    hasta: Annotated[date | None, Query(description="Fecha fin (YYYY-MM-DD, inclusive).")] = None,
    uow: UnitOfWork = Depends(get_uow),
    _admin: Usuario = Depends(require_role("ADMIN")),
) -> list[ProductoTopRead]:
    """Return top N products by quantity sold in the given period.

    Only orders with estado_codigo IN ('CONFIRMADO','EN_PREP','EN_CAMINO','ENTREGADO')
    are counted (D-23-04). PENDIENTE and CANCELADO orders are excluded.
    Results ordered by cantidad_vendida DESC.
    """
    return await _service.get_productos_top(uow, desde, hasta, top)


@metricas_router.get(
    "/pedidos-por-estado",
    response_model=list[PedidoEstadoDistribucionRead],
    summary="Distribución de pedidos por estado",
    tags=["admin-metricas"],
)
async def get_pedidos_por_estado(
    desde: Annotated[date | None, Query(description="Fecha inicio (YYYY-MM-DD, inclusive).")] = None,
    hasta: Annotated[date | None, Query(description="Fecha fin (YYYY-MM-DD, inclusive).")] = None,
    uow: UnitOfWork = Depends(get_uow),
    _admin: Usuario = Depends(require_role("ADMIN")),
) -> list[PedidoEstadoDistribucionRead]:
    """Return order count per state for all states in the given period.

    No state filter — all states that have at least one order in the period
    are included. Results ordered by count DESC.
    """
    return await _service.get_pedidos_por_estado(uow, desde, hasta)
