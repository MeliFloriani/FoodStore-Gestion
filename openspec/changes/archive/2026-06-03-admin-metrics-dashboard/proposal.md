# Proposal: admin-metrics-dashboard (Change 23)

## Sprint
8

## User Stories Covered
- **US-056** — Dashboard de métricas generales (panel KPI, filtro por rango de fechas)
- **US-057** — Gráfico de ventas por período (LineChart, granularidad dia/semana/mes)
- **US-058** — Top productos más vendidos (BarChart, ranking por cantidad vendida)
- **US-059** — Métricas de pedidos por estado (PieChart, distribución)

---

## Why

The Food Store platform lacks any operational visibility for the ADMIN role. Currently, admins must query the database directly or rely on raw order lists to understand business performance. This change introduces a purpose-built metrics and analytics dashboard accessible exclusively to ADMIN users, enabling data-driven decisions on sales trends, product demand, and order flow.

The analytics are time-bounded (configurable date range) and aggregated server-side via PostgreSQL window/group functions, keeping the frontend thin and the data consistent across sessions.

---

## What Changes

### Backend — New Feature Module

A new backend module `backend/app/modules/admin/metricas/` is introduced with four read-only, ADMIN-exclusive endpoints under `/api/v1/admin/metricas`:

| Endpoint | Description |
|---|---|
| `GET /resumen` | KPI cards: total sales, orders by state, total/active users |
| `GET /ventas` | Time series: sales evolution grouped by granularity |
| `GET /productos-top` | Top-N products by quantity sold and revenue |
| `GET /pedidos-por-estado` | Order distribution by state (for PieChart) |

All endpoints enforce `require_role(['ADMIN'])` RBAC. Date range parameters `desde`/`hasta` are optional; defaulting to last 30 days when omitted.

The new router is registered in `backend/app/api/v1/router.py`.

### Database — Performance Indexes (Migration 0014)

Two new indexes are proposed to support analytics query performance:

1. **`ix_pedido_created_at_estado_codigo`** — composite index on `pedido(created_at, estado_codigo)`. Drives KPI summary and time-series queries that filter by date range and group by state simultaneously. **Verified: does not exist in any prior migration.**
2. **`ix_detalle_pedido_producto_id`** — index on `detalle_pedido(producto_id)`. Drives the top-products aggregation join. **Verified: does not exist in prior migrations.** Migration 0001 only created `ix_detalle_pedido_pedido_id` (by `pedido_id`), not by `producto_id`. This is a net-new index.

### Frontend — New Feature + Page

A new FSD feature `frontend/src/features/admin-metrics/` and page `frontend/src/pages/admin/dashboard/` are introduced. The dashboard composes:
- 4 KPI cards (ventas totales, pedidos pendientes, pedidos en curso, usuarios activos)
- `<LineChart>` — evolución de ventas (US-057)
- `<BarChart>` — top productos (US-058)
- `<PieChart>` — distribución por estado (US-059)
- `DateRangeFilter` + `GranularitySelector` widgets

The admin panel also embeds (not duplicates) existing panels:
- `OrdersManagementPanel` (from Change 20) at `/admin/pedidos` tab
- Product/stock management at `/admin/productos` and `/admin/stock` tabs via existing endpoints

Navigation item "Métricas" (path: `/admin/metricas` — corrige referencia anterior a `/admin/metrics`) declarada en el spec `frontend-navigation` es conectada a este nuevo dashboard. El subárbol de rutas `/admin` se expande con rutas anidadas.

---

## Non-Goals

The following are explicitly out of scope for this change:

- **Configuración del sistema** (US-060) — outside TPI scope
- **CSV/PDF export** — not required by user stories
- **Real-time updates / WebSockets** — only on-demand polling via TanStack Query refetch
- **Comparativas vs período anterior** — out of minimum viable scope
- **Alertas y umbrales** — not specified in user stories
- **Rewriting `OrdersManagementPanel`** or the products CRUD — embedded as-is
- **New RBAC code** — ADMIN aggregated permissions from Change 22 already grant access to catalog/orders endpoints; metrics endpoints use `require_role(['ADMIN'])` directly

---

## Dependencies

### Hard Dependencies (all archived)

| Change | Name | What It Provides |
|---|---|---|
| Change 19 | `payments-mercadopago-integration` | `Pago.mp_status='approved'` rows that feed revenue queries; `pedido.total` as the monetary field |
| Change 20 | `orders-visualization` | `OrdersManagementPanel` frontend widget reused in the admin panel; `backend-orders-listing` spec reused for order queries |
| Change 21 | `admin-users-management` | User repository (`backend-admin-users-management`) for `usuarios_total` and `usuarios_activos` KPIs |

### Soft Dependency / RBAC Enabler (archived)

| Change | Name | What It Provides |
|---|---|---|
| Change 22 | `admin-catalog-orders-aggregated-permissions` | ADMIN aggregated access to catalog/orders endpoints — embedded stock and order management work via existing endpoints without new RBAC code |

---

## Index Strategy Summary

Migration `0014_admin_metrics_indexes` introduces:
- Composite index on `pedido(created_at, estado_codigo)` — avoids seq scan on the primary analytics table
- Index on `detalle_pedido(producto_id)` — enables efficient GROUP BY in top-products join

Both are B-tree indexes. No existing indexes conflict (verified by inspecting all 13 prior migrations).

---

## Risks

- **Query performance on large datasets**: Without the proposed indexes, date-range + group-by queries on `pedido` will seq-scan. The migration is critical for production correctness.
- **`created_at` column name confirmed**: The real column name in the `pedido` model is `created_at` (inherited from `Base`), not `creado_en`. The spec uses `created_at` throughout.
- **Embedding complexity**: The dashboard embeds three distinct management panels. Tab routing must be carefully structured to avoid URL conflicts.
- **Decimal precision**: `pedido.total` is `DECIMAL(10,2)`. Frontend must format as string and display with locale formatting — no floating-point arithmetic client-side.
