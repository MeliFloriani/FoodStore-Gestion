/**
 * TypeScript interfaces mirroring Pydantic Read schemas for admin metrics.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Money fields (ventas_totales, monto_total, ingreso_total) arrive as strings
 * (Decimal serialized on the backend). Use Intl.NumberFormat for display —
 * never perform floating-point arithmetic on these values.
 */

export interface PedidoEstadoCountRead {
  estado_codigo: string
  cantidad: number
}

export interface MetricasResumenRead {
  ventas_totales: string        // Decimal → str (money)
  pedidos_por_estado: PedidoEstadoCountRead[]
  usuarios_total: number
  usuarios_activos: number
}

export interface VentasPeriodoRead {
  periodo: string               // ISO datetime string from PostgreSQL DATE_TRUNC
  monto_total: string           // Decimal → str (money)
  cantidad_pedidos: number
}

export interface ProductoTopRead {
  producto_id: string
  nombre_snapshot: string
  cantidad_vendida: number
  ingreso_total: string         // Decimal → str (money)
}

export interface PedidoEstadoDistribucionRead {
  estado_codigo: string
  cantidad: number
}

// Query parameter types
export interface DateRangeParams {
  desde?: string   // YYYY-MM-DD
  hasta?: string   // YYYY-MM-DD
}

export type Granularidad = 'dia' | 'semana' | 'mes'
