## ADDED Requirements

### Requirement: Migration 0014 — admin_metrics_indexes
The system SHALL have a migration `0014_admin_metrics_indexes` at `backend/alembic/versions/<hash>_0014_admin_metrics_indexes.py` with:
- `down_revision = 'd1e2f3a4b5c6'` (migration 0013 — admin_usuarios_search_indexes)
- `upgrade()` creates two indexes:
  1. `ix_pedido_created_at_estado_codigo` — composite B-tree index on `pedido(created_at, estado_codigo)`
  2. `ix_detalle_pedido_producto_id` — B-tree index on `detalle_pedido(producto_id)`
- `downgrade()` drops both indexes using `DROP INDEX IF EXISTS`

**Verification**: Neither `ix_pedido_created_at_estado_codigo` nor `ix_detalle_pedido_producto_id` exist in any prior migration (migrations 0001–0013 inspected). The `ix_detalle_pedido_pedido_id` index exists (migration 0001) but `ix_detalle_pedido_producto_id` does not.

#### Scenario: Migration 0014 creates both indexes
- **WHEN** `alembic upgrade head` runs migration 0014
- **THEN** `ix_pedido_created_at_estado_codigo` exists on table `pedido`
- **THEN** `ix_detalle_pedido_producto_id` exists on table `detalle_pedido`

#### Scenario: Migration 0014 is reversible
- **WHEN** `alembic downgrade -1` runs from migration 0014
- **THEN** both indexes are dropped without error
- **THEN** pre-existing indexes from migrations 0001–0013 are unaffected

#### Scenario: Migration chain is unbroken after 0014
- **WHEN** `alembic history` is inspected
- **THEN** 0014 chain: `0014 → 0013 (d1e2f3a4b5c6) → 0012 (c0d1e2f3a4b5) → ...`
