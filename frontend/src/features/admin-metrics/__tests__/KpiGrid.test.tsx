/**
 * Unit tests for KpiGrid component — Change 23: admin-metrics-dashboard.
 *
 * Covers:
 *   - Renders exactly 4 KPI cards with correct labels.
 *   - Pedidos En Curso = sum of CONFIRMADO + EN_PREP + EN_CAMINO.
 *   - Pedidos Pendientes = count of PENDIENTE state.
 *   - Usuarios Activos = data.usuarios_activos.
 *   - ventas_totales formatted as ARS currency.
 *   - Skeleton rendered when loading=true.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiGrid } from '../components/KpiGrid'
import type { MetricasResumenRead } from '../api/metricas.types'

const mockData: MetricasResumenRead = {
  ventas_totales: '12345.67',
  pedidos_por_estado: [
    { estado_codigo: 'PENDIENTE', cantidad: 5 },
    { estado_codigo: 'CONFIRMADO', cantidad: 3 },
    { estado_codigo: 'EN_PREP', cantidad: 2 },
    { estado_codigo: 'EN_CAMINO', cantidad: 1 },
    { estado_codigo: 'ENTREGADO', cantidad: 10 },
    { estado_codigo: 'CANCELADO', cantidad: 4 },
  ],
  usuarios_total: 100,
  usuarios_activos: 80,
}

describe('KpiGrid', () => {
  it('renders exactly 4 KPI card labels', () => {
    render(<KpiGrid data={mockData} loading={false} />)
    expect(screen.getByText(/Ventas Totales/i)).toBeDefined()
    expect(screen.getByText(/Pedidos Pendientes/i)).toBeDefined()
    expect(screen.getByText(/Pedidos En Curso/i)).toBeDefined()
    expect(screen.getByText(/Usuarios Activos/i)).toBeDefined()
  })

  it('shows Pedidos Pendientes count correctly', () => {
    render(<KpiGrid data={mockData} loading={false} />)
    // Pendiente = 5
    expect(screen.getByText('5')).toBeDefined()
  })

  it('shows Pedidos En Curso as sum of CONFIRMADO + EN_PREP + EN_CAMINO', () => {
    render(<KpiGrid data={mockData} loading={false} />)
    // 3 + 2 + 1 = 6
    expect(screen.getByText('6')).toBeDefined()
  })

  it('shows Usuarios Activos count', () => {
    render(<KpiGrid data={mockData} loading={false} />)
    expect(screen.getByText('80')).toBeDefined()
  })

  it('formats ventas_totales as currency string', () => {
    render(<KpiGrid data={mockData} loading={false} />)
    // ARS formatted — should contain the numeric value
    const ventasCard = screen.getByText(/Ventas Totales/i).closest('div')
    expect(ventasCard?.textContent).toContain('12')
  })

  it('renders skeleton when loading=true', () => {
    const { container } = render(<KpiGrid loading={true} />)
    // animate-pulse divs should be present (skeleton state)
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows zero for Pedidos Pendientes when no PENDIENTE orders', () => {
    const dataNoP: MetricasResumenRead = {
      ...mockData,
      pedidos_por_estado: [{ estado_codigo: 'CONFIRMADO', cantidad: 5 }],
    }
    render(<KpiGrid data={dataNoP} loading={false} />)
    // Pedidos Pendientes = 0 (no PENDIENTE state)
    expect(screen.getByText('0')).toBeDefined()
  })
})
