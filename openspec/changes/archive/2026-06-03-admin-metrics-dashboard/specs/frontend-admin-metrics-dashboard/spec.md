# frontend-admin-metrics-dashboard Specification

## Purpose
ADMIN-exclusive analytics dashboard page and feature providing KPI cards, sales evolution chart, top-products chart, orders-by-state chart, and date range controls. Embeds (does not duplicate) existing management panels. Introduced in Change 23 (admin-metrics-dashboard). Sprint 8.

---

## ADDED Requirements

### Requirement: Feature module SHALL be provided at frontend/src/features/admin-metrics/

The system SHALL provide an FSD feature module at `frontend/src/features/admin-metrics/` with:
- `index.ts` — barrel file exporting public API
- `api/metricas.api.ts` — Axios calls to `/api/v1/admin/metricas/*`
- `api/metricas.types.ts` — TypeScript types mirroring Pydantic Read schemas
- `hooks/useMetricasResumen.ts` — TanStack Query hook
- `hooks/useMetricasVentas.ts` — TanStack Query hook
- `hooks/useMetricasProductosTop.ts` — TanStack Query hook
- `hooks/useMetricasPedidosPorEstado.ts` — TanStack Query hook
- `components/KpiCard.tsx`
- `components/KpiGrid.tsx`
- `components/VentasLineChart.tsx`
- `components/ProductosBarChart.tsx`
- `components/PedidosPieChart.tsx`
- `widgets/DateRangeFilter.tsx`
- `widgets/GranularitySelector.tsx`

#### Scenario: Feature barrel exports all public components
- **WHEN** `import { KpiGrid, VentasLineChart } from '@/features/admin-metrics'` is used
- **THEN** the imports resolve without error

---

### Requirement: TanStack Query hooks SHALL be parameterized by date range and granularidad

The system SHALL provide four TanStack Query hooks. Each hook SHALL:
- Accept `{ desde?: string; hasta?: string }` params (ISO date strings)
- Use `staleTime: 30_000` (30 seconds)
- Include `desde`, `hasta` in the query key so queries are invalidated when the filter changes

`useMetricasVentas` SHALL additionally accept `granularidad: 'dia' | 'semana' | 'mes'` and include it in the query key.

#### Scenario: Date range change triggers re-fetch
- **GIVEN** `useMetricasResumen({ desde: '2026-01-01', hasta: '2026-01-31' })` is mounted
- **WHEN** props change to `{ desde: '2026-02-01', hasta: '2026-02-28' }`
- **THEN** a new network request is issued (different query key)

#### Scenario: Granularity change triggers re-fetch
- **GIVEN** `useMetricasVentas({ granularidad: 'dia' })` is mounted
- **WHEN** granularidad changes to `'mes'`
- **THEN** a new network request is issued

---

### Requirement: KpiGrid SHALL render exactly 4 KPI cards

The system SHALL render a `<KpiGrid>` component with exactly 4 `<KpiCard>` items:
1. **Ventas Totales** — `MetricasResumenRead.ventas_totales` (formatted as currency)
2. **Pedidos Pendientes** — count of PENDIENTE from `pedidos_por_estado`
3. **Pedidos En Curso** — sum of CONFIRMADO + EN_PREP + EN_CAMINO from `pedidos_por_estado`
4. **Usuarios Activos** — `MetricasResumenRead.usuarios_activos`

#### Scenario: KPI cards render with data
- **GIVEN** `useMetricasResumen` returns data
- **WHEN** `MetricasTab` is rendered
- **THEN** four KPI cards are visible with their respective labels and values

#### Scenario: Loading state shown while fetching
- **GIVEN** `useMetricasResumen` is in loading state
- **WHEN** `MetricasTab` is rendered
- **THEN** a skeleton or spinner is shown in place of KPI values

---

### Requirement: VentasLineChart SHALL render a recharts LineChart

The system SHALL render a recharts `<LineChart>` in `VentasLineChart.tsx` using data from `useMetricasVentas`. The chart SHALL:
- Show `periodo` on the X axis (formatted as date string)
- Show `monto_total` on the Y axis
- Render a `<Tooltip>` showing both `monto_total` and `cantidad_pedidos`
- Handle empty data with a "Sin datos para el período" placeholder

#### Scenario: Chart renders with time series data
- **GIVEN** `useMetricasVentas` returns an array of `VentasPeriodoRead`
- **WHEN** `VentasLineChart` is rendered
- **THEN** a line chart is visible with one data point per period

---

### Requirement: ProductosBarChart SHALL render a recharts BarChart

The system SHALL render a recharts `<BarChart>` in `ProductosBarChart.tsx` using data from `useMetricasProductosTop`. The chart SHALL:
- Show `nombre_snapshot` on the Y axis (horizontal bar chart)
- Show `cantidad_vendida` on the X axis
- Render a `<Tooltip>` showing `ingreso_total` formatted as currency
- Handle empty data gracefully

#### Scenario: Bar chart renders top products
- **GIVEN** `useMetricasProductosTop` returns product data
- **WHEN** `ProductosBarChart` is rendered
- **THEN** one bar per product is visible ordered by `cantidad_vendida`

---

### Requirement: PedidosPieChart SHALL render a recharts PieChart

The system SHALL render a recharts `<PieChart>` in `PedidosPieChart.tsx` using data from `useMetricasPedidosPorEstado`. The chart SHALL:
- Show one slice per `estado_codigo`
- Render a `<Legend>` with state labels
- Handle empty data gracefully

#### Scenario: Pie chart renders state distribution
- **GIVEN** `useMetricasPedidosPorEstado` returns data with multiple states
- **WHEN** `PedidosPieChart` is rendered
- **THEN** one slice per state is visible with a legend

---

### Requirement: DateRangeFilter and GranularitySelector widgets SHALL be provided

`DateRangeFilter` SHALL:
- Accept `desde: string`, `hasta: string`, `onChange: (desde: string, hasta: string) => void`
- Render two `<input type="date">` fields
- Default values: last 30 days

`GranularitySelector` SHALL:
- Accept `value: 'dia' | 'semana' | 'mes'`, `onChange: (v: 'dia' | 'semana' | 'mes') => void`
- Render a `<select>` with three options: Día, Semana, Mes

#### Scenario: DateRangeFilter triggers onChange on date change
- **WHEN** the user changes the "hasta" date input
- **THEN** `onChange` is called with the new date values

#### Scenario: GranularitySelector triggers onChange on selection change
- **WHEN** the user selects "Mes" in the granularity selector
- **THEN** `onChange` is called with `'mes'`

---

### Requirement: AdminDashboardPage SHALL provide tab-based navigation at /admin

The system SHALL provide `frontend/src/pages/admin/dashboard/index.tsx` composing:
- Tab navigation: Métricas | Pedidos | Usuarios | Productos | Stock
- Route-based tab activation: each tab corresponds to a nested route
- `MetricasTab` at `/admin/metricas` — KPI + charts
- `PedidosTab` at `/admin/pedidos` — embeds `OrdersManagementPanel` (Change 20, unchanged)
- `UsuariosTab` at `/admin/usuarios` — renders existing `AdminUsersPage` (Change 21, unchanged)
- `ProductosTab` at `/admin/productos` — product management via existing endpoints
- `StockTab` at `/admin/stock` — stock management via existing endpoints

#### Scenario: Metrics tab renders charts on /admin/metricas
- **GIVEN** an ADMIN user navigates to `/admin/metricas`
- **WHEN** the page loads
- **THEN** KPI cards and all three charts are rendered

#### Scenario: Pedidos tab embeds OrdersManagementPanel
- **GIVEN** an ADMIN user navigates to `/admin/pedidos`
- **WHEN** the tab renders
- **THEN** `OrdersManagementPanel` is rendered (not a re-implementation)

---

### Requirement: FSD import discipline SHALL prohibit cross-feature imports

The `admin-metrics` feature SHALL NOT import from any other feature module (e.g., `orders-management`, `products`). Pages can import from multiple features. If shared types are needed, they go in `shared/`.

#### Scenario: admin-metrics feature has no cross-feature imports
- **WHEN** `frontend/src/features/admin-metrics/**` files are analyzed
- **THEN** no import resolves to `frontend/src/features/<other-feature>`

---

### Requirement: Money values SHALL be formatted client-side

`ventas_totales` and `ingreso_total` arrive as strings from the API. The system SHALL format them using `Intl.NumberFormat` with locale `'es-AR'` and style `'currency'` / currency `'ARS'`. No floating-point arithmetic on these values client-side.

#### Scenario: Currency string formatted correctly
- **GIVEN** `ventas_totales = "12345.67"`
- **WHEN** rendered in a KPI card
- **THEN** the displayed value is formatted as ARS currency (e.g., "$ 12.345,67")
