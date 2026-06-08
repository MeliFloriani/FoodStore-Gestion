# DELTA: backend-data-model

**Change**: admin-users-management (Change 21)  
**Base spec**: `openspec/specs/backend-data-model/spec.md`  

---

## ADDED Requirements

### Requirement: pg_trgm GIN indexes on Usuario for ILIKE search

The system SHALL add a new Alembic migration `0013_admin_usuarios_search_indexes` that:
1. Enables the PostgreSQL `pg_trgm` extension.
2. Creates GIN trigram indexes on `usuario.email`, `usuario.nombre`, and `usuario.apellido`.

These indexes are required to support `ILIKE '%query%'` substring search in `AdminUsuariosRepository.list_paginated` without full table scans in production.

> D-07: GIN pg_trgm is preferred over functional `lower()` indexes because admin search UX requires arbitrary substring matching (`%query%`), not just prefix matching (`query%`). The `pg_trgm` extension provides the `gin_trgm_ops` operator class for this use case.

**Migration DDL** (upgrade):
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_usuario_email_trgm ON usuario USING gin (email gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_usuario_nombre_trgm ON usuario USING gin (nombre gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_usuario_apellido_trgm ON usuario USING gin (apellido gin_trgm_ops);
```

**Migration DDL** (downgrade):
```sql
DROP INDEX IF EXISTS ix_usuario_email_trgm;
DROP INDEX IF EXISTS ix_usuario_nombre_trgm;
DROP INDEX IF EXISTS ix_usuario_apellido_trgm;
-- NOTE: Do NOT drop pg_trgm extension — other indexes or functions may use it.
```

#### Scenario: GIN trigram indexes exist after migration 0013
- **WHEN** `alembic upgrade head` is run including migration 0013
- **THEN** `\d usuario` in psql shows three GIN indexes: `ix_usuario_email_trgm`, `ix_usuario_nombre_trgm`, `ix_usuario_apellido_trgm`
- **THEN** `pg_trgm` extension is installed

#### Scenario: ILIKE search uses index scan
- **GIVEN** migration 0013 is applied
- **WHEN** `EXPLAIN (ANALYZE) SELECT * FROM usuario WHERE nombre ILIKE '%maria%'` is executed
- **THEN** query plan uses bitmap index scan on `ix_usuario_nombre_trgm`
- **THEN** full sequential scan is NOT used (with 100+ rows in table)

#### Scenario: Downgrade removes indexes without error
- **WHEN** `alembic downgrade -1` is run from migration 0013
- **THEN** the three GIN indexes are removed
- **THEN** no error occurs
- **THEN** `pg_trgm` extension remains installed (not dropped)

---

### Requirement: Usuario.deleted_at is the deactivation mechanism (no activo field)

**Clarification for Change 21**: The `Usuario` model inherits `deleted_at: datetime | None` from `Base`. This field is the canonical mechanism for user deactivation:
- `deleted_at IS NULL` → user is active
- `deleted_at IS NOT NULL` → user is deactivated (soft deleted)

No `activo: bool` column exists or will be added. The Historias de Usuario (US-055) mention `activo` as a concept, but the Integrador v5.0 (higher precedence) specifies the universal soft delete pattern via `deleted_at`.

All queries that check user activity SHALL use `WHERE deleted_at IS NULL` (active) or `WHERE deleted_at IS NOT NULL` (inactive), consistent with the existing `UsuarioRepository.get_by_email` and `BaseRepository.get_by_id` implementations.

#### Scenario: deleted_at IS NULL means active user
- **WHEN** `usuario.deleted_at IS NULL`
- **THEN** the user is considered active for auth, login, and API access purposes

#### Scenario: deleted_at IS NOT NULL means deactivated user
- **WHEN** `usuario.deleted_at IS NOT NULL`
- **THEN** `UsuarioRepository.get_by_email` returns `None` (soft delete filter active)
- **THEN** `BaseRepository.get_by_id` returns `None` (soft delete filter active)
- **THEN** `GET /api/v1/auth/login` effectively returns 401 (email not found path)
- **THEN** any Bearer token for this user produces 401 from `get_current_user`
