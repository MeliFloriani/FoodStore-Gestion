"""
MetricasService — stateless orchestration for admin analytics endpoints.

Change 23: admin-metrics-dashboard.

All methods raise HTTPException on validation failures.
No session.commit() — this is a read-only service.

Date range contract (D-23-01):
  desde/hasta are inclusive calendar dates (YYYY-MM-DD).
  Backend converts to half-open datetime interval:
    [desde 00:00:00, hasta+1day 00:00:00)
  This avoids end-of-day 23:59:59 interpretation edge cases.

Timezone contract:
  created_at column is DateTime() naive in PostgreSQL (timestamp without
  time zone). All datetime values passed to MetricasRepository are naive UTC
  (tzinfo=None) to avoid SQLAlchemy type mismatch.

Session access pattern:
  The service receives a UnitOfWork and accesses uow.session to pass to
  MetricasRepository. This is a documented exception for read-only analytics
  (see design.md). The UoW auto-commit is a no-op since there are no writes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import HTTPException

from app.core.uow import UnitOfWork

from .repository import MetricasRepository
from .schemas import (
    MetricasResumenRead,
    PedidoEstadoCountRead,
    PedidoEstadoDistribucionRead,
    ProductoTopRead,
    VentasPeriodoRead,
)


def _resolve_date_range(
    desde: date | None,
    hasta: date | None,
) -> tuple[datetime, datetime]:
    """Convert optional date params to naive datetime half-open interval.

    Defaults to last 30 days when both params are None (hasta=today,
    desde=today-30days). Either param may be independently provided.

    Returns: (desde_dt, hasta_dt) where:
      desde_dt = datetime.combine(desde, time.min)       ← 00:00:00, naive
      hasta_dt = datetime.combine(hasta+1day, time.min)  ← exclusive upper bound

    Raises:
      HTTPException 422: if desde > hasta.
    """
    today = date.today()
    if hasta is None:
        hasta = today
    if desde is None:
        desde = today - timedelta(days=30)
    if desde > hasta:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "desde must be <= hasta",
                "code": "INVALID_DATE_RANGE",
            },
        )
    desde_dt = datetime.combine(desde, time.min)
    hasta_dt = datetime.combine(hasta + timedelta(days=1), time.min)
    return desde_dt, hasta_dt


class MetricasService:
    async def get_resumen(
        self,
        uow: UnitOfWork,
        desde: date | None,
        hasta: date | None,
    ) -> MetricasResumenRead:
        desde_dt, hasta_dt = _resolve_date_range(desde, hasta)
        repo = MetricasRepository(uow.session)
        data = await repo.get_resumen(desde_dt, hasta_dt)
        return MetricasResumenRead(
            ventas_totales=data["ventas_totales"],
            pedidos_por_estado=[
                PedidoEstadoCountRead(**row) for row in data["pedidos_por_estado"]
            ],
            usuarios_total=data["usuarios_total"],
            usuarios_activos=data["usuarios_activos"],
        )

    async def get_ventas_series(
        self,
        uow: UnitOfWork,
        desde: date | None,
        hasta: date | None,
        granularidad: Literal["dia", "semana", "mes"],
    ) -> list[VentasPeriodoRead]:
        desde_dt, hasta_dt = _resolve_date_range(desde, hasta)
        repo = MetricasRepository(uow.session)
        rows = await repo.get_ventas_series(desde_dt, hasta_dt, granularidad)
        return [VentasPeriodoRead(**row) for row in rows]

    async def get_productos_top(
        self,
        uow: UnitOfWork,
        desde: date | None,
        hasta: date | None,
        top: int,
    ) -> list[ProductoTopRead]:
        desde_dt, hasta_dt = _resolve_date_range(desde, hasta)
        repo = MetricasRepository(uow.session)
        rows = await repo.get_productos_top(desde_dt, hasta_dt, top)
        return [ProductoTopRead(**row) for row in rows]

    async def get_pedidos_por_estado(
        self,
        uow: UnitOfWork,
        desde: date | None,
        hasta: date | None,
    ) -> list[PedidoEstadoDistribucionRead]:
        desde_dt, hasta_dt = _resolve_date_range(desde, hasta)
        repo = MetricasRepository(uow.session)
        rows = await repo.get_pedidos_por_estado(desde_dt, hasta_dt)
        return [PedidoEstadoDistribucionRead(**row) for row in rows]
