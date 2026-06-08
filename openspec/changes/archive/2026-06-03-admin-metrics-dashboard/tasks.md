# Tasks: admin-metrics-dashboard (Change 23)

All tasks are unchecked. Do NOT mark any task as done during the propose phase.

---

## Backend

### Module Setup
- [x] Create directory `backend/app/modules/admin/metricas/` with `__init__.py`
- [x] Create `backend/app/modules/admin/metricas/schemas.py` — Pydantic v2 Read schemas (`MetricasResumenRead`, `VentasPeriodoRead`, `ProductoTopRead`, `PedidoEstadoCountRead`) with `field_serializer` for `Decimal → str`
- [x] Create `backend/app/modules/admin/metricas/repository.py` — raw SQL aggregate queries using `text()` or SQLAlchemy Core; no ORM session.commit()
  - [x] `get_ventas_totales(session, desde_dt, hasta_dt) -> Decimal`
  - [x] `get_pedidos_por_estado(session, desde_dt, hasta_dt) -> list[dict]`
  - [x] `get_ventas_series(session, desde_dt, hasta_dt, granularidad_sql) -> list[dict]`
  - [x] `get_productos_top(session, desde_dt, hasta_dt, top) -> list[dict]`
- [x] Create `backend/app/modules/admin/metricas/service.py` — stateless orchestration; raises `HTTPException`; translates `granularidad` enum to SQL string; computes default date range (last 30 days) when params are `None`; reuses admin-users-management repository for user counts
  - **Nota**: Reutilizar `AdminUsuariosRepository` (Change 21) para conteo de usuarios; lógica de `deleted_at IS NULL` ya encapsulada ahí.
- [x] Create `backend/app/modules/admin/metricas/router.py` — four endpoints with `require_role(['ADMIN'])`, `response_model` explicit, `Depends(get_session)`, `Depends(get_current_user)`

### Router Registration
- [x] Modify `backend/app/api/v1/router.py` — import `metricas_router` and call `router.include_router(metricas_router, prefix="/admin/metricas", tags=["admin-metricas"])` inside `build_v1_router`

### Date Range Logic
- [x] Implement `_resolve_date_range(desde: date | None, hasta: date | None) -> tuple[datetime, datetime]` in `service.py` that returns half-open interval `[desde 00:00:00Z, hasta+1day 00:00:00Z)` and defaults to last 30 days when params are `None`

---

## Migrations

- [x] Create migration file `backend/alembic/versions/<hash>_0014_admin_metrics_indexes.py`
  - [x] Set `down_revision = 'd1e2f3a4b5c6'`
  - [x] `upgrade()`: create `ix_pedido_created_at_estado_codigo` on `pedido(created_at, estado_codigo)` using `op.execute()`
  - [x] `upgrade()`: create `ix_detalle_pedido_producto_id` on `detalle_pedido(producto_id)` using `op.execute()`
  - [x] `downgrade()`: drop both indexes with `DROP INDEX IF EXISTS`
  - [x] Add docstring documenting index rationale and verification of non-existence in prior migrations

---

## Frontend

### API Layer
- [x] Create `frontend/src/features/admin-metrics/api/metricas.types.ts` — TypeScript interfaces mirroring Pydantic schemas (`MetricasResumenRead`, `VentasPeriodoRead`, `ProductoTopRead`, `PedidoEstadoCountRead`)
- [x] Create `frontend/src/features/admin-metrics/api/metricas.api.ts` — four Axios functions using the shared HTTP client with `/api/v1/admin/metricas/*` paths; accept `DateRangeParams` and `granularidad`

### TanStack Query Hooks
- [x] Create `frontend/src/features/admin-metrics/hooks/useMetricasResumen.ts` — query key includes `['metricas', 'resumen', desde, hasta]`; `staleTime: 30_000`
- [x] Create `frontend/src/features/admin-metrics/hooks/useMetricasVentas.ts` — query key includes `['metricas', 'ventas', desde, hasta, granularidad]`
- [x] Create `frontend/src/features/admin-metrics/hooks/useMetricasProductosTop.ts` — query key includes `['metricas', 'productos-top', desde, hasta, top]`
- [x] Create `frontend/src/features/admin-metrics/hooks/useMetricasPedidosPorEstado.ts` — query key includes `['metricas', 'pedidos-por-estado', desde, hasta]`

### UI Components
- [x] Create `frontend/src/features/admin-metrics/components/KpiCard.tsx` — accepts `label: string`, `value: string | number`, optional `icon`; Tailwind styled
- [x] Create `frontend/src/features/admin-metrics/components/KpiGrid.tsx` — renders 4 `<KpiCard>` items in responsive grid; derives Pedidos Pendientes, Pedidos En Curso from `pedidos_por_estado` array
- [x] Create `frontend/src/features/admin-metrics/components/VentasLineChart.tsx` — recharts `<LineChart>` with `periodo` X axis, `monto_total` Y axis, `<Tooltip>`, empty-state placeholder
- [x] Create `frontend/src/features/admin-metrics/components/ProductosBarChart.tsx` — recharts `<BarChart>` horizontal, `nombre_snapshot` Y axis, `cantidad_vendida` X axis, `<Tooltip>` with `ingreso_total`, empty-state placeholder
- [x] Create `frontend/src/features/admin-metrics/components/PedidosPieChart.tsx` — recharts `<PieChart>` with `<Legend>`, empty-state placeholder

### Widgets
- [x] Create `frontend/src/features/admin-metrics/widgets/DateRangeFilter.tsx` — two date inputs, default last 30 days, calls `onChange(desde, hasta)`
- [x] Create `frontend/src/features/admin-metrics/widgets/GranularitySelector.tsx` — select with Día/Semana/Mes options

### Barrel
- [x] Create `frontend/src/features/admin-metrics/index.ts` — export all public components, hooks, and widgets

### Page
- [x] Create `frontend/src/pages/admin/dashboard/index.tsx` — `AdminDashboardPage` with tab navigation (Métricas, Pedidos, Usuarios, Productos, Stock); URL-based tab activation; uses Zustand only for UI-only state if needed
- [x] Create `frontend/src/pages/admin/dashboard/tabs/MetricasTab.tsx` — composes `DateRangeFilter`, `GranularitySelector`, `KpiGrid`, `VentasLineChart`, `ProductosBarChart`, `PedidosPieChart`
- [x] Create `frontend/src/pages/admin/dashboard/tabs/PedidosTab.tsx` — renders `<OrdersManagementPanel>` (imported from `features/orders-management`, not re-implemented)
- [x] Create `frontend/src/pages/admin/dashboard/tabs/ProductosTab.tsx` — renders product management using existing products entity and endpoints
- [x] Create `frontend/src/pages/admin/dashboard/tabs/StockTab.tsx` — renders stock management using existing stock endpoints

### Routing
- [x] Modify `frontend/src/app/router/` — expand `/admin/*` nested routes: add `/admin/metricas`, `/admin/pedidos`, redirect `/admin` → `/admin/metricas`

### Navigation
- [x] Modify `frontend/src/shared/lib/navigation/items.ts` — update "Métricas" item path from `/admin/metrics` to `/admin/metricas` (Spanish-language route correction)

---

## Tests

### Backend Unit Tests
- [x] Test `service.py` — `_resolve_date_range`: default range (last 30 days), explicit range, half-open interval boundary
- [x] Test `repository.py` — mock DB session; verify SQL queries use correct state filters for each endpoint
- [x] Test `router.py` — ADMIN gets 200, CLIENT gets 403, unauthenticated gets 401; invalid `granularidad` gets 422

### Backend Integration Tests
- [x] Test `GET /api/v1/admin/metricas/resumen` — with fixture data, verify correct sums; CANCELADO excluded
- [x] Test `GET /api/v1/admin/metricas/ventas` — verify `DATE_TRUNC` grouping returns correct periods for `dia`, `semana`, `mes`
- [x] Test `GET /api/v1/admin/metricas/productos-top` — verify only `CONFIRMADO/EN_PREP/EN_CAMINO/ENTREGADO` orders counted; top=2 returns at most 2 items
- [x] Test `GET /api/v1/admin/metricas/pedidos-por-estado` — all states present, correct counts

### Frontend Unit Tests
- [x] Test `_resolve_date_range` equivalent in hooks — when no params, defaults to last 30 days
- [x] Test `KpiGrid` — renders 4 cards with correct labels; Pedidos En Curso = sum of CONFIRMADO + EN_PREP + EN_CAMINO
- [x] Test `DateRangeFilter` — calls onChange when dates change
- [x] Test `GranularitySelector` — calls onChange with correct value
- [x] Test `useMetricasResumen` — query key changes when desde/hasta change (use TanStack Query test utilities)

### Migration Tests
- [x] Verify migration 0014 upgrade creates both indexes (alembic check + pg inspection)
- [x] Verify migration 0014 downgrade drops both indexes without error
