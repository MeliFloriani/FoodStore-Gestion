"""
MetricasRepository — read-only aggregate queries for admin analytics.

Change 23: admin-metrics-dashboard.

All queries are read-only (SELECT + aggregation). No writes, no flush, no commit.
The session is injected by the service from the UnitOfWork context.

Architecture note:
  MetricasRepository takes AsyncSession directly (not a UoW-managed repo)
  because it is a read-only analytics module with no writes or transactions.
  The service receives the UoW and accesses uow.session to pass to this
  repository. This is a documented exception for read-only aggregate analytics
  (per design.md D-23 and architecture context).

Timezone note:
  created_at is DateTime() naive (timestamp without time zone in PostgreSQL).
  All datetime parameters passed here MUST be naive datetimes (tzinfo=None).
  Do not pass timezone-aware datetimes — SQLAlchemy raises a type mismatch.

DATE_TRUNC note:
  PostgreSQL DATE_TRUNC does not accept bind parameters for its first argument
  (the granularity string). Granularity is string-interpolated after validation
  against the _GRANULARIDAD_MAP whitelist. Raw user input is NEVER interpolated.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Safe mapping from validated API enum values to PostgreSQL DATE_TRUNC literals.
# Only these three values can reach this module (enforced by Literal type in router).
_GRANULARIDAD_MAP: dict[str, str] = {
    "dia": "day",
    "semana": "week",
    "mes": "month",
}


class MetricasRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_resumen(
        self,
        desde_dt: datetime,
        hasta_dt: datetime,
    ) -> dict:
        """Return aggregated KPI data for the given date range.

        Decision D-23-02: ventas_totales excludes CANCELADO orders only.
        PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO are all included —
        a PENDIENTE order represents committed intent.

        Decision D-23-07: user counts are a snapshot (no date filter).
        usuarios_activos = COUNT(*) FILTER (WHERE deleted_at IS NULL).
        """
        # Sales totals (exclude CANCELADO per D-23-02)
        ventas_result = await self.session.execute(
            text("""
                SELECT COALESCE(SUM(total), 0) AS ventas_totales,
                       COUNT(id)               AS total_pedidos
                FROM pedido
                WHERE created_at >= :desde_dt
                  AND created_at <  :hasta_dt
                  AND estado_codigo != 'CANCELADO'
            """),
            {"desde_dt": desde_dt, "hasta_dt": hasta_dt},
        )
        ventas_row = ventas_result.mappings().one()

        # Orders by state (all states in range — no state filter)
        estados_result = await self.session.execute(
            text("""
                SELECT estado_codigo, COUNT(id) AS cantidad
                FROM pedido
                WHERE created_at >= :desde_dt
                  AND created_at <  :hasta_dt
                GROUP BY estado_codigo
            """),
            {"desde_dt": desde_dt, "hasta_dt": hasta_dt},
        )
        pedidos_por_estado = [
            {"estado_codigo": r.estado_codigo, "cantidad": r.cantidad}
            for r in estados_result.mappings().all()
        ]

        # User counts — snapshot (D-23-07: no date filter)
        usuarios_result = await self.session.execute(
            text("""
                SELECT COUNT(*)                                    AS usuarios_total,
                       COUNT(*) FILTER (WHERE deleted_at IS NULL) AS usuarios_activos
                FROM usuario
            """)
        )
        usuarios_row = usuarios_result.mappings().one()

        return {
            "ventas_totales": Decimal(str(ventas_row["ventas_totales"])),
            "pedidos_por_estado": pedidos_por_estado,
            "usuarios_total": int(usuarios_row["usuarios_total"]),
            "usuarios_activos": int(usuarios_row["usuarios_activos"]),
        }

    async def get_ventas_series(
        self,
        desde_dt: datetime,
        hasta_dt: datetime,
        granularidad: str,  # 'dia' | 'semana' | 'mes' — already validated by router schema
    ) -> list[dict]:
        """Return time-series sales data grouped by the given granularity.

        Decision D-23-03: granularity enum is validated at the router layer via
        Literal['dia','semana','mes']. This method receives an already-validated
        value and resolves it to a PostgreSQL DATE_TRUNC literal via _GRANULARIDAD_MAP.
        String interpolation is safe because the input comes from a whitelist.

        Orders with estado_codigo = 'CANCELADO' are excluded per D-23-02.
        Results are ordered ASC by period.
        """
        pg_gran = _GRANULARIDAD_MAP[granularidad]
        result = await self.session.execute(
            text(f"""
                SELECT DATE_TRUNC('{pg_gran}', created_at) AS periodo,
                       COALESCE(SUM(total), 0)             AS monto_total,
                       COUNT(id)                           AS cantidad_pedidos
                FROM pedido
                WHERE created_at    >= :desde_dt
                  AND created_at    <  :hasta_dt
                  AND estado_codigo != 'CANCELADO'
                GROUP BY DATE_TRUNC('{pg_gran}', created_at)
                ORDER BY periodo ASC
            """),
            {"desde_dt": desde_dt, "hasta_dt": hasta_dt},
        )
        return [
            {
                "periodo": r.periodo,
                "monto_total": Decimal(str(r.monto_total)),
                "cantidad_pedidos": int(r.cantidad_pedidos),
            }
            for r in result.mappings().all()
        ]

    async def get_productos_top(
        self,
        desde_dt: datetime,
        hasta_dt: datetime,
        top: int,
    ) -> list[dict]:
        """Return the top N products by quantity sold in the given period.

        Decision D-23-04: uses a stricter state filter than resumen.
        Only orders that have progressed past PENDIENTE are counted:
        CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO. This ensures the ranking
        reflects products that were actually processed, not just pending.

        Decision D-23-08: nombre_snapshot is used as the product label.
        Products that were renamed appear under their original snapshot name —
        each snapshot name is treated as distinct.
        """
        result = await self.session.execute(
            text("""
                SELECT dp.producto_id::text,
                       dp.nombre_snapshot,
                       SUM(dp.cantidad)                      AS cantidad_vendida,
                       SUM(dp.cantidad * dp.precio_snapshot) AS ingreso_total
                FROM detalle_pedido dp
                JOIN pedido p ON p.id = dp.pedido_id
                WHERE p.created_at    >= :desde_dt
                  AND p.created_at    <  :hasta_dt
                  AND p.estado_codigo IN ('CONFIRMADO','EN_PREP','EN_CAMINO','ENTREGADO')
                GROUP BY dp.producto_id, dp.nombre_snapshot
                ORDER BY cantidad_vendida DESC
                LIMIT :top
            """),
            {"desde_dt": desde_dt, "hasta_dt": hasta_dt, "top": top},
        )
        return [
            {
                "producto_id": r.producto_id,
                "nombre_snapshot": r.nombre_snapshot,
                "cantidad_vendida": int(r.cantidad_vendida),
                "ingreso_total": Decimal(str(r.ingreso_total)),
            }
            for r in result.mappings().all()
        ]

    async def get_pedidos_por_estado(
        self,
        desde_dt: datetime,
        hasta_dt: datetime,
    ) -> list[dict]:
        """Return order count per state for all states in the given period.

        No state filter — all states are shown in the distribution chart.
        Only states with at least one order in the period appear in the result.
        Results ordered by count DESC.
        """
        result = await self.session.execute(
            text("""
                SELECT estado_codigo, COUNT(id) AS cantidad
                FROM pedido
                WHERE created_at >= :desde_dt
                  AND created_at <  :hasta_dt
                GROUP BY estado_codigo
                ORDER BY cantidad DESC
            """),
            {"desde_dt": desde_dt, "hasta_dt": hasta_dt},
        )
        return [
            {"estado_codigo": r.estado_codigo, "cantidad": int(r.cantidad)}
            for r in result.mappings().all()
        ]
