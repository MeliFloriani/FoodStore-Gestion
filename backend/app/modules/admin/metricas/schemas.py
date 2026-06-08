"""
Pydantic v2 Read schemas for admin metrics — Change 23: admin-metrics-dashboard.

All Decimal fields are serialized to str for JSON output (project money convention).
This prevents floating-point precision loss on the frontend for currency values.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_serializer


class PedidoEstadoCountRead(BaseModel):
    estado_codigo: str
    cantidad: int


class MetricasResumenRead(BaseModel):
    ventas_totales: Decimal
    pedidos_por_estado: list[PedidoEstadoCountRead]
    usuarios_total: int
    usuarios_activos: int

    @field_serializer("ventas_totales")
    def serialize_ventas(self, v: Decimal) -> str:
        return str(v)


class VentasPeriodoRead(BaseModel):
    periodo: datetime
    monto_total: Decimal
    cantidad_pedidos: int

    @field_serializer("monto_total")
    def serialize_monto(self, v: Decimal) -> str:
        return str(v)


class ProductoTopRead(BaseModel):
    producto_id: str
    nombre_snapshot: str
    cantidad_vendida: int
    ingreso_total: Decimal

    @field_serializer("ingreso_total")
    def serialize_ingreso(self, v: Decimal) -> str:
        return str(v)


class PedidoEstadoDistribucionRead(BaseModel):
    estado_codigo: str
    cantidad: int
