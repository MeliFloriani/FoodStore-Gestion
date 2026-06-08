# Design: admin-metrics-dashboard (Change 23)

## Architecture Overview

### Backend Module Structure

The new metrics module follows the established `Router → Service → UoW → Repository → Model` layering. No new SQLModel tables are introduced — the module reads from existing `pedido`, `detalle_pedido`, `usuario`, and `pago` tables via aggregate queries.

```
backend/app/
├── api/
│   └── v1/
│       └── router.py                     ← MODIFIED: include metricas_router
├── modules/
│   └── admin/
│       └── metricas/
│           ├── __init__.py
│           ├── router.py                 ← NEW: FastAPI router, RBAC guard
│           ├── service.py                ← NEW: Stateless orchestration
│           ├── repository.py             ← NEW: Raw SQL aggregate queries
│           └── schemas.py                ← NEW: Pydantic v2 Read schemas
```

Note: `backend/app/modules/` is a new directory within the existing app structure. It follows the same pattern as `backend/app/repositories/`, `backend/app/services/`, etc., but groups by feature subdomain. This is the first "admin subdomain" module — it establishes the `modules/admin/` convention for future admin-exclusive features.

### Frontend FSD Layout

```
frontend/src/
├── pages/
│   └── admin/
│       └── dashboard/
│           ├── index.tsx                 ← AdminDashboardPage — tab orchestrator
│           └── tabs/
│               ├── MetricasTab.tsx       ← KPI + charts composition
│               ├── PedidosTab.tsx        ← Embeds OrdersManagementPanel
│               ├── ProductosTab.tsx      ← Embeds product management (existing endpoints)
│               └── StockTab.tsx          ← Embeds stock management (existing endpoints)
├── features/
│   └── admin-metrics/
│       ├── index.ts                      ← Public API barrel
│       ├── api/
│       │   ├── metricas.api.ts           ← Axios calls to /api/v1/admin/metricas/*
│       │   └── metricas.types.ts         ← TypeScript types matching Pydantic schemas
│       ├── hooks/
│       │   ├── useMetricasResumen.ts     ← TanStack Query hook
│       │   ├── useMetricasVentas.ts      ← TanStack Query hook
│       │   ├── useMetricasProductosTop.ts← TanStack Query hook
│       │   └── useMetricasPedidosPorEstado.ts
│       ├── components/
│       │   ├── KpiCard.tsx               ← Single KPI card
│       │   ├── KpiGrid.tsx               ← 4-card grid layout
│       │   ├── VentasLineChart.tsx        ← recharts LineChart wrapper
│       │   ├── ProductosBarChart.tsx      ← recharts BarChart wrapper
│       │   └── PedidosPieChart.tsx        ← recharts PieChart wrapper
│       └── widgets/
│           ├── DateRangeFilter.tsx        ← desde/hasta date inputs
│           └── GranularitySelector.tsx    ← dia/semana/mes select
```

### Route Tree

```
/admin                   ← RoleGuard roles={['ADMIN']} (already in routing spec)
├── /admin               ← AdminDashboardPage (index / redirect to /admin/metricas)
├── /admin/metricas      ← MetricasTab
├── /admin/pedidos       ← PedidosTab (embeds OrdersManagementPanel)
├── /admin/usuarios      ← Existing AdminUsersPage (Change 21)
├── /admin/productos     ← ProductosTab (embeds product management)
└── /admin/stock         ← StockTab (embeds stock management)
```

The `/admin` route is already declared in the routing spec with `RoleGuard roles={['ADMIN']}`. This change expands the nested subtree.

---

## Query Designs

### Date Range Contract (Decision D-23-01)

- `desde` and `hasta` are **inclusive UTC dates** in ISO 8601 format (`YYYY-MM-DD`).
- Backend interprets as **half-open interval**: `[desde 00:00:00 UTC, hasta+1day 00:00:00 UTC)`.
- SQL filter: `created_at >= :desde_dt AND created_at < :hasta_plus_one_dt`
- When omitted: default to last 30 days (`hasta = today`, `desde = today - 30 days`).
- Python: `desde_dt = datetime.combine(desde, time.min)`, `hasta_dt = datetime.combine(hasta + timedelta(days=1), time.min)`
- This avoids timezone edge cases on `hasta 23:59:59` interpretations.

> **Nota de implementación — timezone**: La columna `created_at` en `pedido` es `DateTime()` naive (PostgreSQL `timestamp without time zone`), no `TIMESTAMPTZ`. Al filtrar por rango, la implementación debe pasar objetos `datetime` sin timezone (`datetime.utcnow()` o `datetime.now(UTC).replace(tzinfo=None)`), o castear el parámetro en SQL como `CAST(:desde AS timestamp)`. No asumir que SQLAlchemy coerciona automáticamente objetos aware contra columnas naive.

### 1. Resumen KPI Query

```sql
-- Sales total (non-CANCELADO terminal states)
SELECT SUM(p.total) AS ventas_totales,
       COUNT(p.id)  AS total_pedidos
FROM pedido p
WHERE p.created_at >= :desde_dt
  AND p.created_at <  :hasta_dt
  AND p.estado_codigo NOT IN ('CANCELADO');

-- Orders by state (all states, same date range)
SELECT p.estado_codigo,
       COUNT(p.id) AS cantidad
FROM pedido p
WHERE p.created_at >= :desde_dt
  AND p.created_at <  :hasta_dt
GROUP BY p.estado_codigo;

-- User counts (reuses admin-users-management repository)
SELECT COUNT(*)                              AS usuarios_total,
       COUNT(*) FILTER (WHERE deleted_at IS NULL) AS usuarios_activos
FROM usuario;
```

**Design decision D-23-02** (valid sale state filter): `ventas_totales` sums `pedido.total` for all orders **excluding CANCELADO**. This includes PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, and ENTREGADO. Rationale: a PENDIENTE order represents committed intent even if payment hasn't cleared. CANCELADO orders are excluded because they represent reversed transactions. This is a deliberate business decision — the service layer must document this filter in a comment.

### 2. Ventas Time Series Query

```sql
SELECT DATE_TRUNC(:granularidad, p.created_at) AS periodo,
       SUM(p.total)                             AS monto_total,
       COUNT(p.id)                              AS cantidad_pedidos
FROM pedido p
WHERE p.created_at >= :desde_dt
  AND p.created_at <  :hasta_dt
  AND p.estado_codigo NOT IN ('CANCELADO')
GROUP BY DATE_TRUNC(:granularidad, p.created_at)
ORDER BY periodo ASC;
```

**Granularity mapping (Decision D-23-03)**:
- `granularidad=dia`    → `DATE_TRUNC('day', created_at)`
- `granularidad=semana` → `DATE_TRUNC('week', created_at)`
- `granularidad=mes`    → `DATE_TRUNC('month', created_at)`

The mapping is enforced as a Python `Literal['dia', 'semana', 'mes']` query param. The service translates to the PostgreSQL string before passing to the repository. This prevents SQL injection through parameterization.

> **Nota de implementación — granularidad SQL**: `DATE_TRUNC` en PostgreSQL no acepta bind parameters en el primer argumento. La granularidad debe resolverse como string literal en la capa de service antes de construir la query: `'dia' → 'day'`, `'semana' → 'week'`, `'mes' → 'month'`. El string ya habrá sido validado contra `Literal['dia', 'semana', 'mes']` en el schema de entrada; el repository lo interpola directamente en el SQL (no como bind param). Nunca interpolar input crudo del usuario.

### 3. Top Productos Query

```sql
SELECT dp.producto_id,
       dp.nombre_snapshot,
       SUM(dp.cantidad)                            AS cantidad_vendida,
       SUM(dp.cantidad * dp.precio_snapshot)       AS ingreso_total
FROM detalle_pedido dp
JOIN pedido p ON p.id = dp.pedido_id
WHERE p.created_at    >= :desde_dt
  AND p.created_at    <  :hasta_dt
  AND p.estado_codigo IN ('CONFIRMADO', 'EN_PREP', 'EN_CAMINO', 'ENTREGADO')
GROUP BY dp.producto_id, dp.nombre_snapshot
ORDER BY cantidad_vendida DESC
LIMIT :top;
```

**Decision D-23-04** (top-products state filter): Uses a stricter filter than `resumen` — only orders that have progressed past `PENDIENTE` are counted. This ensures the ranking reflects products that were actually processed, not just added to pending orders. CANCELADO is excluded for the same reason as above. `nombre_snapshot` groups with `producto_id` to handle the case where a product was renamed; each snapshot name is treated as distinct (snapshot integrity).

### 4. Pedidos Por Estado Query

```sql
SELECT p.estado_codigo,
       COUNT(p.id) AS cantidad
FROM pedido p
WHERE p.created_at >= :desde_dt
  AND p.created_at <  :hasta_dt
GROUP BY p.estado_codigo
ORDER BY cantidad DESC;
```

No state filter — all states shown in the distribution chart.

---

## Index Analysis & Justification

### Migration 0014 — `admin_metrics_indexes`

**Verification performed** (read all 13 prior migration files):

| Index | Exists? | Source |
|---|---|---|
| `ix_pedido_created_at_estado_codigo` | **No** | Not in any migration |
| `ix_detalle_pedido_pedido_id` | Yes (exists) | Migration 0001 (line 216) |
| `ix_detalle_pedido_producto_id` | **No** | Not in any migration — `producto_id` FK has no index |
| `ix_pedido_estado_codigo` | Yes (exists) | Migration 0001 (line 197) — single column only |

**Indexes to create in migration 0014:**

1. **`ix_pedido_created_at_estado_codigo`** on `pedido(created_at, estado_codigo)`
   - Composite index: `created_at` first (range scan), `estado_codigo` second (equality filter in the same scan).
   - Eliminates the seq scan + filter pattern on the hot analytics path.
   - Used by all four endpoints.

2. **`ix_detalle_pedido_producto_id`** on `detalle_pedido(producto_id)`
   - Enables the hash join / index scan in the top-products GROUP BY query.
   - Without this, the join from `detalle_pedido` to `pedido` via `producto_id` requires a seq scan on a potentially large table.

> **Coexistencia de índices**: El índice `ix_pedido_estado_codigo` creado en migración 0001 **se conserva** — cubre queries que filtran solo por `estado_codigo` sin rango de fechas (ej. conteos del panel FSM, filtros del panel de pedidos del rol PEDIDOS). El nuevo índice compuesto `ix_pedido_created_at_estado_codigo` agrega la dimensión `created_at` para las queries de analytics. Ambos coexisten; **la migración 0014 no debe eliminar `ix_pedido_estado_codigo`**.

**Revision chain**: `down_revision = 'd1e2f3a4b5c6'` (migration 0013 — `admin_usuarios_search_indexes`, verified as the last migration).

---

## RBAC

All metrics endpoints declare `require_role(['ADMIN'])` (not the aggregated set from Change 22). Metrics are ADMIN-exclusive per US-056 actor definition. The aggregated permissions from Change 22 are orthogonal — they enable ADMIN to call catalog/order endpoints, but do not grant PEDIDOS or STOCK roles access to metrics.

Frontend: the `/admin` route subtree is already guarded by `RoleGuard roles={['ADMIN']}` per the existing routing spec. No additional frontend guard is needed for the metrics tab.

---

## Pydantic v2 Read Schemas

```python
# schemas.py

from __future__ import annotations
from decimal import Decimal
from datetime import datetime
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
    def serialize_decimal(self, v: Decimal) -> str:
        return str(v)

class VentasPeriodoRead(BaseModel):
    periodo: datetime
    monto_total: Decimal
    cantidad_pedidos: int

    @field_serializer("monto_total")
    def serialize_decimal(self, v: Decimal) -> str:
        return str(v)

class ProductoTopRead(BaseModel):
    producto_id: str
    nombre_snapshot: str
    cantidad_vendida: int
    ingreso_total: Decimal

    @field_serializer("ingreso_total")
    def serialize_decimal(self, v: Decimal) -> str:
        return str(v)
```

All `Decimal` fields are serialized to `str` for JSON output per project money convention.

---

## Decision Log

> **Nota**: Este log usa D-23-01 a D-23-09. La enumeración del brief/auditoría usa D-23-01 a D-23-08. Correspondencia: D-23-05 (embed) y D-23-06 (brief) son equivalentes; D-23-09 (índices detalle) corresponde al D-23-05 del brief.

| ID | Decision | Rationale |
|---|---|---|
| D-23-01 | Date range is half-open `[desde, hasta+1day)` | Avoids end-of-day edge cases; consistent with ISO date semantics |
| D-23-02 | `ventas_totales` excludes CANCELADO only | Pending orders represent committed business; only cancellations are reversed |
| D-23-03 | Granularity enum `dia/semana/mes` maps to `DATE_TRUNC('day'/'week'/'month')` | SQL `DATE_TRUNC` supports exactly these groupings; enum prevents injection |
| D-23-04 | Top-products filter: `IN ('CONFIRMADO','EN_PREP','EN_CAMINO','ENTREGADO')` | Stricter than resumen — only actually-processed orders count toward product ranking |
| D-23-05 | Embed, don't duplicate: `OrdersManagementPanel` and product management | FSD cross-feature import rule; feature boundaries must not be duplicated |
| D-23-06 | No server-side cache TTL at this stage | Analytics data changes with every order; client-side staleTime in TanStack Query is sufficient (30s suggested) |
| D-23-07 | User counts ignore date range | `usuarios_activos` reporta un **snapshot actual** de usuarios no eliminados lógicamente (`deleted_at IS NULL`), no usuarios creados dentro del período consultado. La decisión refleja semántica de snapshot, no ausencia de datos. Un KPI futuro de "registros en período" puede incorporar `Usuario.created_at` como filtro adicional si se requiere. |
| D-23-08 | `nombre_snapshot` used for product ranking label | Products can be renamed; snapshot preserves historical accuracy |
| D-23-09 | `ix_detalle_pedido_producto_id` is net-new | Verified: migration 0001 only creates `ix_detalle_pedido_pedido_id` — the `producto_id` FK has no index |

---

## Risks

1. **`created_at` column drift**: The `Pedido` model inherits `created_at` from `Base`. If Base is ever changed, analytics queries break. Mitigated by using the column name string in raw SQL (not ORM attribute), making it explicit.
2. **`nombre_snapshot` duplicates in top-products**: If the same product had two different snapshot names in the same period, they appear as separate rows. This is acceptable — snapshot integrity is the design choice.
3. **Performance on large pedido table**: The composite index on `(created_at, estado_codigo)` is essential. Without it, any analytics query over a 30-day window on a production table will full-scan. Migration 0014 must run before the feature is enabled.
4. **Frontend chart rendering with empty data**: recharts charts must handle empty arrays gracefully (no data state). The feature must implement empty-state UI for each chart.
5. **Embedding tab navigation state**: The active tab (metricas/pedidos/usuarios/productos/stock) may need Zustand client state or URL-based routing. URL-based routing is preferred (clean URLs, shareable links, back-button support).
