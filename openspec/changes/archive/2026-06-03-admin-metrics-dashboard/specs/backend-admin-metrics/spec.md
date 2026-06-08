# backend-admin-metrics Specification

## Purpose
ADMIN-exclusive metrics API module providing aggregated analytics over orders, products, and users. Introduced in Change 23 (admin-metrics-dashboard). Sprint 8.

---

## ADDED Requirements

### Requirement: Module structure SHALL follow Router → Service → UoW → Repository → Model layering

The system SHALL provide a feature module at `backend/app/modules/admin/metricas/` with the following files:
- `__init__.py`
- `router.py` — FastAPI router, RBAC, no business logic
- `service.py` — stateless orchestration, raises HTTPException
- `repository.py` — raw SQL aggregate queries, no business logic
- `schemas.py` — Pydantic v2 Read schemas, `field_serializer` for Decimal → str

#### Scenario: Module files exist at expected paths
- **WHEN** the `admin-metrics-dashboard` change is applied
- **THEN** all five files exist under `backend/app/modules/admin/metricas/`

---

### Requirement: GET /api/v1/admin/metricas/resumen SHALL return KPI summary

The system SHALL provide `GET /api/v1/admin/metricas/resumen` with optional query params `desde: date` and `hasta: date`. The endpoint SHALL:
- Require `ADMIN` role (`require_role(['ADMIN'])`)
- Return `MetricasResumenRead` with `ventas_totales` (Decimal → str), `pedidos_por_estado` (list), `usuarios_total`, `usuarios_activos`
- Default date range to last 30 days when `desde`/`hasta` are omitted
- Use half-open interval: `[desde 00:00:00 UTC, hasta+1day 00:00:00 UTC)`
- Exclude CANCELADO orders from `ventas_totales` sum

#### Scenario: Authenticated ADMIN gets KPI summary
- **GIVEN** a valid ADMIN JWT
- **WHEN** `GET /api/v1/admin/metricas/resumen` is called without params
- **THEN** HTTP 200 is returned with `ventas_totales`, `pedidos_por_estado`, `usuarios_total`, `usuarios_activos`

#### Scenario: Non-ADMIN gets 403
- **GIVEN** a valid CLIENT JWT
- **WHEN** `GET /api/v1/admin/metricas/resumen` is called
- **THEN** HTTP 403 is returned

#### Scenario: Date range filter applied
- **GIVEN** orders exist in and out of the date range
- **WHEN** `GET /api/v1/admin/metricas/resumen?desde=2026-01-01&hasta=2026-01-31` is called
- **THEN** only orders with `created_at` in `[2026-01-01T00:00:00Z, 2026-02-01T00:00:00Z)` are aggregated

#### Scenario: CANCELADO orders excluded from ventas_totales
- **GIVEN** a CANCELADO order exists in the date range
- **WHEN** `GET /api/v1/admin/metricas/resumen` is called
- **THEN** the CANCELADO order total is NOT included in `ventas_totales`

---

### Requirement: GET /api/v1/admin/metricas/ventas SHALL return sales time series

The system SHALL provide `GET /api/v1/admin/metricas/ventas` with query params `desde: date`, `hasta: date`, `granularidad: Literal['dia','semana','mes']` (default `'dia'`). The endpoint SHALL:
- Require `ADMIN` role
- Return `list[VentasPeriodoRead]` ordered by `periodo ASC`
- Use `DATE_TRUNC` with the mapped granularity string
- Exclude CANCELADO orders

Granularity mapping: `dia` → `'day'`, `semana` → `'week'`, `mes` → `'month'`.

#### Scenario: Daily granularity groups by day
- **GIVEN** orders across multiple days in the range
- **WHEN** `GET /api/v1/admin/metricas/ventas?granularidad=dia` is called
- **THEN** response contains one entry per day with `monto_total` and `cantidad_pedidos`
- **THEN** entries are ordered by `periodo ASC`

#### Scenario: Invalid granularity rejected
- **WHEN** `GET /api/v1/admin/metricas/ventas?granularidad=hora` is called
- **THEN** HTTP 422 is returned

---

### Requirement: GET /api/v1/admin/metricas/productos-top SHALL return top products ranking

The system SHALL provide `GET /api/v1/admin/metricas/productos-top` with query params `top: int` (default 10, max 50), `desde: date`, `hasta: date`. The endpoint SHALL:
- Require `ADMIN` role
- Return `list[ProductoTopRead]` ordered by `cantidad_vendida DESC`
- Only include orders with `estado_codigo IN ('CONFIRMADO','EN_PREP','EN_CAMINO','ENTREGADO')` (excludes PENDIENTE and CANCELADO)
- Use `nombre_snapshot` from `detalle_pedido` as the product label

#### Scenario: Returns top N products ordered by quantity
- **GIVEN** multiple products sold in the period
- **WHEN** `GET /api/v1/admin/metricas/productos-top?top=5` is called
- **THEN** response contains at most 5 items ordered by `cantidad_vendida DESC`

#### Scenario: PENDIENTE and CANCELADO orders excluded from ranking
- **GIVEN** a product appears only in PENDIENTE orders
- **WHEN** `GET /api/v1/admin/metricas/productos-top` is called
- **THEN** that product does NOT appear in the ranking

---

### Requirement: GET /api/v1/admin/metricas/pedidos-por-estado SHALL return state distribution

The system SHALL provide `GET /api/v1/admin/metricas/pedidos-por-estado` with query params `desde: date`, `hasta: date`. The endpoint SHALL:
- Require `ADMIN` role
- Return `list[PedidoEstadoCountRead]` for ALL states (no state filter)
- Include only states that have at least one order in the period

#### Scenario: Returns distribution for all states present
- **GIVEN** orders in PENDIENTE, CONFIRMADO, and CANCELADO states
- **WHEN** `GET /api/v1/admin/metricas/pedidos-por-estado` is called
- **THEN** response includes entries for all three states with correct counts

---

### Requirement: Schemas SHALL use Pydantic v2 with Decimal serialization

The system SHALL define schemas in `backend/app/modules/admin/metricas/schemas.py`:
- `PedidoEstadoCountRead(estado_codigo: str, cantidad: int)`
- `MetricasResumenRead(ventas_totales: Decimal, pedidos_por_estado: list[PedidoEstadoCountRead], usuarios_total: int, usuarios_activos: int)` — `ventas_totales` serialized to str via `field_serializer`
- `VentasPeriodoRead(periodo: datetime, monto_total: Decimal, cantidad_pedidos: int)` — `monto_total` serialized to str
- `ProductoTopRead(producto_id: str, nombre_snapshot: str, cantidad_vendida: int, ingreso_total: Decimal)` — `ingreso_total` serialized to str

#### Scenario: Decimal fields serialized as strings in JSON
- **WHEN** `MetricasResumenRead(ventas_totales=Decimal("1234.56"), ...)` is serialized
- **THEN** JSON output contains `"ventas_totales": "1234.56"` (string, not float)

---

### Requirement: Migration 0014 SHALL create admin_metrics_indexes

The system SHALL have a migration `0014_admin_metrics_indexes` that creates:
1. Composite index `ix_pedido_created_at_estado_codigo` on `pedido(created_at, estado_codigo)`
2. Index `ix_detalle_pedido_producto_id` on `detalle_pedido(producto_id)`

`down_revision` SHALL be `'d1e2f3a4b5c6'` (migration 0013).

#### Scenario: Indexes created by upgrade
- **WHEN** `alembic upgrade head` runs migration 0014
- **THEN** `ix_pedido_created_at_estado_codigo` exists on `pedido`
- **THEN** `ix_detalle_pedido_producto_id` exists on `detalle_pedido`

#### Scenario: Indexes dropped by downgrade
- **WHEN** `alembic downgrade -1` runs from migration 0014
- **THEN** both indexes are dropped
