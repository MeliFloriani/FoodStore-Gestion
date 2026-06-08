# backend-admin-users-management Specification

## Purpose
Backend capability for the ADMIN users management panel. Provides paginated listing with search and filters, data and roles editing (with last-admin guard), and logical deactivation with global refresh token revocation. Introduced in Change 21 (admin-users-management).

## Files

| File | Description |
|------|-------------|
| `backend/app/schemas/admin_usuarios.py` | Pydantic schemas: RolRead, UsuarioAdminRead, UsuarioAdminUpdate, UsuarioRolesUpdate, UsuarioEstadoUpdate |
| `backend/app/repositories/admin_usuarios.py` | AdminUsuariosRepository extending BaseRepository[Usuario] |
| `backend/app/services/admin_usuarios.py` | AdminUsuariosService stateless service class |
| `backend/app/api/v1/admin_usuarios.py` | FastAPI router with 5 endpoints |
| `backend/alembic/versions/d1e2f3a4b5c6_0013_admin_usuarios_search_indexes.py` | Migration 0013: pg_trgm GIN indexes |

## Requirements

### Requirement: Pydantic schemas for admin user operations

`backend/app/schemas/admin_usuarios.py` SHALL define:

- `RolRead(BaseModel)` with `id: UUID`, `codigo: str`, `nombre: str`. `from_attributes=True`.
- `UsuarioAdminRead(BaseModel)` with `id: UUID`, `email: str`, `nombre: str`, `apellido: str`, `created_at: datetime`, `deleted_at: datetime | None`, `roles: list[RolRead]`. `from_attributes=True`. **SHALL NOT** include `password_hash`.
- `UsuarioAdminUpdate(BaseModel)` with `nombre: str | None = None` (max 80), `apellido: str | None = None` (max 80). `extra='ignore'` (email dropped silently, D-01).
- `UsuarioRolesUpdate(BaseModel)` with `roles: list[str]` (min 1 item), with `@field_validator` that validates each item is in `{"ADMIN","STOCK","PEDIDOS","CLIENT"}` and deduplicates.
- `UsuarioEstadoUpdate(BaseModel)` with `activo: bool`.

#### Scenario: UsuarioAdminRead never exposes password_hash
- **WHEN** `UsuarioAdminRead` is instantiated from a `Usuario` ORM object
- **THEN** serialization to JSON does NOT include any `password_hash` field
- **THEN** `UsuarioAdminRead.model_fields` does NOT contain `password_hash`

#### Scenario: UsuarioAdminUpdate drops email silently
- **WHEN** `UsuarioAdminUpdate(nombre="Ana", email="hack@test.com")` is instantiated
- **THEN** the resulting model has `nombre="Ana"` and no `email` attribute
- **THEN** no `ValidationError` is raised

#### Scenario: UsuarioRolesUpdate rejects unknown roles
- **WHEN** `UsuarioRolesUpdate(roles=["ADMIN","SUPERUSER"])` is instantiated
- **THEN** a `ValidationError` is raised mentioning the invalid role `"SUPERUSER"`

#### Scenario: UsuarioRolesUpdate deduplicates roles
- **WHEN** `UsuarioRolesUpdate(roles=["ADMIN","ADMIN","CLIENT"])` is instantiated
- **THEN** `model.roles` contains exactly `["ADMIN","CLIENT"]` (order may vary)

---

### Requirement: AdminUsuariosRepository with paginated search

`backend/app/repositories/admin_usuarios.py` SHALL define `AdminUsuariosRepository(BaseRepository[Usuario])` with:

- `async def list_paginated(self, *, page: int, size: int, q: str | None, rol: str | None, activo: bool | None) -> tuple[list[Usuario], int]`: Loads users with `selectinload(Usuario.usuario_roles).selectinload(UsuarioRol.rol)`. Applies ILIKE filter on `nombre`, `apellido`, `email` when `q` is provided. Joins to `Rol` and filters by `rol.codigo` when `rol` is provided. Filters `deleted_at IS NULL` when `activo=True`, `deleted_at IS NOT NULL` when `activo=False`. Orders by `created_at DESC`.
- `async def count_active_admins(self, *, exclude_user_id: UUID) -> int`: Counts users with ADMIN role, `deleted_at IS NULL`, excluding the specified user. Uses `SELECT ... FOR UPDATE` on the target user row to prevent TOCTOU race condition (D-03).

#### Scenario: list_paginated returns correct page
- **GIVEN** 25 active users in the database
- **WHEN** `list_paginated(page=2, size=10, q=None, rol=None, activo=None)` is called
- **THEN** returns `(items, total)` where `len(items) == 10` and `total == 25`

#### Scenario: list_paginated ILIKE search
- **GIVEN** users with names "Juan Pérez" and "Ana García"
- **WHEN** `list_paginated(q="juan", ...)` is called
- **THEN** only "Juan Pérez" appears in results (case-insensitive match)

#### Scenario: list_paginated activo filter
- **GIVEN** 3 active users and 2 inactive users (deleted_at IS NOT NULL)
- **WHEN** `list_paginated(activo=True, ...)` is called
- **THEN** `total == 3` and all items have `deleted_at IS NULL`

#### Scenario: count_active_admins excludes target user
- **GIVEN** 2 users with ADMIN role, both active
- **WHEN** `count_active_admins(exclude_user_id=<user_A_id>)` is called
- **THEN** returns `1` (only user B counted)

---

### Requirement: AdminUsuariosService with last-admin guard

`backend/app/services/admin_usuarios.py` SHALL define `AdminUsuariosService` with `@staticmethod` methods. All methods follow the Service-only HTTPException invariant (no `HTTPException` raised — uses `AppError` subclasses). All DB access through UoW.

Methods:
- `list_usuarios(uow, *, page, size, q, rol, activo) -> Page[UsuarioAdminRead]`
- `get_usuario(uow, user_id) -> UsuarioAdminRead` — raises `NotFoundError(code="USER_NOT_FOUND")`
- `update_usuario_data(uow, user_id, data: UsuarioAdminUpdate) -> UsuarioAdminRead` — raises `NotFoundError`
- `update_usuario_roles(uow, user_id, new_roles: list[str], admin_id: UUID) -> UsuarioAdminRead` — raises `NotFoundError`, `ConflictError(code="LAST_ADMIN_PROTECTED")` (409)
- `deactivate_usuario(uow, user_id, activo: bool) -> UsuarioAdminRead` — raises `NotFoundError`, `ConflictError(code="LAST_ADMIN_PROTECTED")` (409)

#### Scenario: update_usuario_roles protects last ADMIN
- **GIVEN** exactly one user with role ADMIN (the only administrator)
- **WHEN** `update_usuario_roles(uow, that_user.id, new_roles=["CLIENT"], ...)` is called
- **THEN** `ConflictError` is raised with `code="LAST_ADMIN_PROTECTED"` and `status_code=409`
- **THEN** the user retains their ADMIN role (no change committed)

#### Scenario: update_usuario_roles revokes refresh tokens
- **GIVEN** a user with 3 active refresh tokens and role CLIENT
- **WHEN** `update_usuario_roles(uow, user_id, new_roles=["ADMIN"], ...)` is called
- **THEN** all 3 refresh tokens are revoked (revoked_at IS NOT NULL)
- **THEN** the user now has role ADMIN

#### Scenario: deactivate_usuario soft-deletes and revokes tokens
- **GIVEN** an active user with 2 active refresh tokens
- **WHEN** `deactivate_usuario(uow, user_id, activo=False)` is called
- **THEN** `usuario.deleted_at IS NOT NULL`
- **THEN** both refresh tokens have `revoked_at IS NOT NULL`

#### Scenario: deactivate_usuario is idempotent
- **GIVEN** a user with `deleted_at IS NOT NULL` (already deactivated)
- **WHEN** `deactivate_usuario(uow, user_id, activo=False)` is called again
- **THEN** no error is raised
- **THEN** no additional refresh token revocations occur

#### Scenario: deactivate_usuario protects last ADMIN
- **GIVEN** exactly one user with ADMIN role (the only active administrator)
- **WHEN** `deactivate_usuario(uow, that_user.id, activo=False)` is called
- **THEN** `ConflictError` is raised with `code="LAST_ADMIN_PROTECTED"` and `status_code=409`
- **THEN** `usuario.deleted_at IS NULL` (user remains active)

#### Scenario: concurrency — two simultaneous ADMIN demotions of last ADMIN
- **GIVEN** exactly one ADMIN user in the system
- **WHEN** two concurrent transactions attempt to demote that user's ADMIN role simultaneously
- **THEN** exactly one transaction succeeds and one receives `ConflictError(LAST_ADMIN_PROTECTED)`
- **THEN** the user retains their ADMIN role

---

### Requirement: HTTP endpoints for admin user management

`backend/app/api/v1/admin_usuarios.py` SHALL define `admin_usuarios_router = APIRouter()` with 5 endpoints, all protected by `Depends(require_role("ADMIN"))`:

| Method | Path | Response | HTTP Codes |
|--------|------|----------|------------|
| GET | `/` | `Page[UsuarioAdminRead]` | 200, 401, 403 |
| GET | `/{id}` | `UsuarioAdminRead` | 200, 401, 403, 404 |
| PUT | `/{id}` | `UsuarioAdminRead` | 200, 401, 403, 404, 422 |
| PUT | `/{id}/roles` | `UsuarioAdminRead` | 200, 401, 403, 404, 409, 422 |
| PATCH | `/{id}/estado` | `UsuarioAdminRead` | 200, 401, 403, 404, 409, 422 |

Route declaration order: `GET /`, `GET /{id}`, `PUT /{id}/roles`, `PATCH /{id}/estado`, `PUT /{id}`. Static sub-paths (`/roles`, `/estado`) MUST be declared before the generic `/{id}` path.

Query params for `GET /`: `page` (int, ≥1, default=1), `size` (int, ≥1, ≤100, default=20), `q` (str|None), `rol` (str|None), `activo` (bool|None).

#### Scenario: GET /api/v1/admin/usuarios returns Page response
- **WHEN** an authenticated ADMIN calls `GET /api/v1/admin/usuarios`
- **THEN** HTTP 200 with body `{ "items": [...], "total": N, "page": 1, "size": 20, "pages": P }`
- **THEN** no item in `items` contains `password_hash`

#### Scenario: Non-ADMIN is forbidden
- **WHEN** an authenticated CLIENT calls `GET /api/v1/admin/usuarios`
- **THEN** HTTP 403 with RFC 7807 body `{ "code": "forbidden" }`

#### Scenario: PUT /{id}/roles with last ADMIN returns 409
- **WHEN** an ADMIN calls `PUT /api/v1/admin/usuarios/{last_admin_id}/roles` with `{ "roles": ["CLIENT"] }`
- **THEN** HTTP 409 with body `{ "code": "LAST_ADMIN_PROTECTED", "detail": "..." }`

#### Scenario: PATCH /{id}/estado with activo=false blocks subsequent login
- **GIVEN** user U has active credentials
- **WHEN** ADMIN calls `PATCH /api/v1/admin/usuarios/{U.id}/estado` with `{ "activo": false }`
- **THEN** HTTP 200 (deactivation successful)
- **WHEN** user U calls `POST /api/v1/auth/login` with valid credentials
- **THEN** HTTP 401 (user is blocked — deleted_at IS NOT NULL, treated as credentials not found)

---

### Requirement: pg_trgm search indexes on Usuario

**Alembic migration** `0013_admin_usuarios_search_indexes` SHALL:

1. Enable extension: `CREATE EXTENSION IF NOT EXISTS pg_trgm`
2. Create GIN trigram index on `usuario.email`: `ix_usuario_email_trgm`
3. Create GIN trigram index on `usuario.nombre`: `ix_usuario_nombre_trgm`
4. Create GIN trigram index on `usuario.apellido`: `ix_usuario_apellido_trgm`

Downgrade removes the three indexes (does NOT drop the extension — it may be shared).

#### Scenario: Trigram indexes enable ILIKE substring search
- **WHEN** migration 0013 is applied
- **THEN** `EXPLAIN (ANALYZE) SELECT * FROM usuario WHERE email ILIKE '%example%'` uses bitmap index scan on `ix_usuario_email_trgm`
- **THEN** full table scan is NOT used

---

### Requirement: UnitOfWork exposes admin_usuarios repository

`backend/app/core/uow.py` SHALL add `admin_usuarios: AdminUsuariosRepository` property following the existing lazy-initialization pattern.

#### Scenario: uow.admin_usuarios returns AdminUsuariosRepository instance
- **WHEN** `uow.admin_usuarios` is accessed inside an active UoW context
- **THEN** the returned object is an instance of `AdminUsuariosRepository`
- **THEN** it shares the same `AsyncSession` as other repos in the same UoW

---

### Requirement: admin-usuarios router registered in build_v1_router

`backend/app/api/v1/router.py` `build_v1_router` SHALL include `admin_usuarios_router` with `prefix="/admin/usuarios"` and `tags=["admin-usuarios"]`.

Final endpoints accessible at:
- `GET /api/v1/admin/usuarios`
- `GET /api/v1/admin/usuarios/{id}`
- `PUT /api/v1/admin/usuarios/{id}`
- `PUT /api/v1/admin/usuarios/{id}/roles`
- `PATCH /api/v1/admin/usuarios/{id}/estado`

#### Scenario: admin-usuarios endpoints reachable
- **WHEN** app boots and routes are inspected
- **THEN** all 5 endpoints exist under tag `"admin-usuarios"`
- **THEN** existing routers (`/auth/*`, `/pedidos/*`, etc.) are unaffected

## Design Decisions

| ID | Decision |
|----|----------|
| D-01 | Email immutable: UsuarioAdminUpdate excludes email field |
| D-02 | Roles update uses PUT replace (full set semantics) |
| D-03 | SELECT FOR UPDATE for last-admin concurrency guard |
| D-05 | Backend supports reactivation (activo=true), frontend does NOT expose it in Change 21 |
| D-07 | GIN pg_trgm indexes for ILIKE substring search |
| D-08 | Hard delete for removed UsuarioRol records |
