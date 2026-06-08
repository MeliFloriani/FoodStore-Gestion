## MODIFIED Requirements

### Requirement: Pago tiene campos MercadoPago todos únicos
The system SHALL update the `Pago` model and database schema such that `external_reference` is NO LONGER subject to a UNIQUE constraint, allowing multiple `Pago` rows per `Pedido` (1:N cardinality for payment retry support — RN-PA08, US-048).

The updated constraint set for `Pago` SHALL be:
- `mp_payment_id`: `BIGINT`, nullable, `UNIQUE` (preserve — each MP payment ID is globally unique; NULL until webhook fires)
- `mp_preference_id`: `VARCHAR(100)`, nullable, `UNIQUE`, indexed — NEW COLUMN (migration 0011) — Checkout Pro preference ID. Set when `POST /api/v1/pagos` creates the preference; NULL for rows predating migration.
- `mp_status`: `VARCHAR(30)`, NOT NULL, values: `pending | approved | rejected | in_process | cancelled`
- `mp_status_detail`: `VARCHAR(100)`, nullable, NEW COLUMN (migration 0010) — stores MP's `status_detail`
- `external_reference`: `VARCHAR(100)`, NOT NULL, **NOT UNIQUE** (MODIFIED — was UQ, now has non-unique index only)
- `idempotency_key`: `VARCHAR(100)`, NOT NULL, `UNIQUE` (preserve — each payment attempt has a unique key)
- `monto`: `DECIMAL(10,2)`, nullable (preserve)
- `pedido_id`: `UUID FK → pedido.id`, NOT NULL, `ON DELETE RESTRICT`, indexed (preserve)

A non-unique index `ix_pago_pedido_id_created_at` on `(pedido_id, created_at DESC)` SHALL be created to support efficient `get_latest_by_pedido_id` queries.

**Alembic migration 0010** (already applied):
```sql
-- Drop the unique constraint on external_reference
ALTER TABLE pago DROP CONSTRAINT IF EXISTS uq_pago_external_reference;

-- Add mp_status_detail column
ALTER TABLE pago ADD COLUMN IF NOT EXISTS mp_status_detail VARCHAR(100);

-- Add performance index for per-pedido queries
CREATE INDEX IF NOT EXISTS ix_pago_pedido_id_created_at ON pago(pedido_id, created_at DESC);
```

**Alembic migration 0011** (Checkout Pro — adds mp_preference_id):
```sql
-- Add mp_preference_id column (nullable for backward compat)
ALTER TABLE pago ADD COLUMN mp_preference_id VARCHAR(100);

-- Add unique constraint
ALTER TABLE pago ADD CONSTRAINT uq_pago_mp_preference_id UNIQUE (mp_preference_id);

-- Add index for fast lookups
CREATE INDEX ix_pago_mp_preference_id ON pago(mp_preference_id);
```

Downgrade:
```sql
DROP INDEX IF EXISTS ix_pago_pedido_id_created_at;
ALTER TABLE pago DROP COLUMN IF EXISTS mp_status_detail;
ALTER TABLE pago ADD CONSTRAINT uq_pago_external_reference UNIQUE (external_reference);
```

> **Downgrade safety pre-check (MANDATORY)**: Before executing the downgrade, the migration `downgrade()` function SHALL verify that no duplicate `external_reference` values exist in the `pago` table. If duplicates are found, the downgrade MUST abort with an exception rather than silently applying a constraint that would fail at the DB level:
> ```python
> # In downgrade():
> result = op.get_bind().execute(
>     text(
>         "SELECT external_reference, count(*) FROM pago "
>         "GROUP BY external_reference HAVING count(*) > 1"
>     )
> )
> duplicates = result.fetchall()
> if duplicates:
>     raise Exception(
>         "Cannot downgrade: duplicate external_references exist. "
>         "Manual cleanup required before re-adding uq_pago_external_reference."
>     )
> ```
> This prevents data corruption if the system processed payment retries (1:N Pago per Pedido) after the upgrade was applied.

> **Rationale**: The Integrador ERD v5 marks `external_reference` as `UQ` (single Pago per Pedido). This conflicts with RN-PA08 ("Un pedido puede tener múltiples intentos de pago — 1:N") and US-048 (retry rejected payment on same order). The functional requirement (retry) takes precedence. Idempotency is preserved via `idempotency_key` UNIQUE (each payment attempt) and `mp_payment_id` UNIQUE (each MP-assigned payment ID). The `external_reference` value (pedido UUID) is repeated across retries by design.

#### Scenario: Multiple Pago rows for same pedido_id are allowed
- **GIVEN** an existing `Pago` row with `external_reference = "pedido-uuid-123"`
- **WHEN** a second `Pago` row is inserted with `external_reference = "pedido-uuid-123"` and a different `idempotency_key`
- **THEN** the INSERT succeeds without UNIQUE constraint violation
- **THEN** both rows exist in the `pago` table with the same `external_reference`

#### Scenario: idempotency_key UNIQUE constraint is preserved
- **GIVEN** an existing `Pago` row with `idempotency_key = "ik-abc-123"`
- **WHEN** a second INSERT is attempted with the same `idempotency_key = "ik-abc-123"`
- **THEN** the INSERT fails with a UNIQUE constraint violation on `idempotency_key`

#### Scenario: mp_payment_id UNIQUE constraint is preserved
- **GIVEN** an existing `Pago` row with `mp_payment_id = 987654321`
- **WHEN** a second INSERT is attempted with the same `mp_payment_id = 987654321`
- **THEN** the INSERT fails with a UNIQUE constraint violation on `mp_payment_id`

#### Scenario: ix_pago_pedido_id_created_at index exists after migration
- **WHEN** Alembic migration is applied
- **THEN** the index `ix_pago_pedido_id_created_at` exists on the `pago` table
- **THEN** `SELECT ... FROM pago WHERE pedido_id = :id ORDER BY created_at DESC LIMIT 1` uses an index scan

#### Scenario: mp_status_detail column exists and is nullable
- **WHEN** the migration is applied
- **THEN** the `pago` table has a column `mp_status_detail VARCHAR(100)` that allows NULL values
- **THEN** existing rows have `mp_status_detail = NULL` (no data loss)
