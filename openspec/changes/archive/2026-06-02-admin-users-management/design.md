# Design: admin-users-management

**Change**: 21  
**Sprint**: 8  
**Date**: 2026-06-02  

---

## 1. Data Model Deltas

### 1.1 No new tables

Change 21 requires no new database tables. All entities (`Usuario`, `Rol`, `UsuarioRol`, `RefreshToken`) already exist.

### 1.2 New indexes (migration required)

`Usuario` is searched by `nombre`, `apellido`, and `email` using case-insensitive ILIKE. Without indexes, queries on 10k+ rows become full table scans.

**Alembic migration `0013_admin_usuarios_search_indexes`** SHALL add:

```sql
-- Trigram index on email for ILIKE search (requires pg_trgm extension)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_usuario_email_trgm ON usuario USING gin (email gin_trgm_ops);

-- Trigram index on nombre for ILIKE search
CREATE INDEX IF NOT EXISTS ix_usuario_nombre_trgm ON usuario USING gin (nombre gin_trgm_ops);

-- Trigram index on apellido for ILIKE search
CREATE INDEX IF NOT EXISTS ix_usuario_apellido_trgm ON usuario USING gin (apellido gin_trgm_ops);
```

**Downgrade**: Drop the three indexes and the extension (if no other user).

> D-07: Trigram indexes selected over `lower()` functional indexes because ILIKE `%query%` (substring match) requires GIN pg_trgm; `lower()` only optimizes prefix `LIKE 'query%'`. GIN pg_trgm handles arbitrary substring matching which is the expected UX.

### 1.3 Soft delete field on Usuario

`Usuario` inherits `deleted_at: datetime | None` from `Base`. No migration needed.
- `deleted_at IS NULL` = usuario activo
- `deleted_at IS NOT NULL` = usuario desactivado (soft deleted)

The Historias de Usuario mention a boolean `activo` field, but Integrador v5.0 (higher precedence) uses the universal soft delete pattern. The existing code in `UsuarioRepository.get_by_email` and `BaseRepository.get_by_id` already filters `deleted_at IS NULL`. **No schema migration for `activo` field**.

---

## 2. Backend Architecture

### 2.1 File Structure

```
backend/app/
├── api/v1/
│   └── admin_usuarios.py           # NEW: router
├── services/
│   └── admin_usuarios.py           # NEW: AdminUsuariosService
├── repositories/
│   └── admin_usuarios.py           # NEW: AdminUsuariosRepository (extends BaseRepository)
├── schemas/
│   └── admin_usuarios.py           # NEW: Pydantic Read/Update/RolesUpdate schemas
```

### 2.2 Pydantic Schemas (`app/schemas/admin_usuarios.py`)

```python
# UsuarioAdminRead — response schema, NEVER exposes password_hash
class RolRead(BaseModel):
    id: UUID
    codigo: str
    nombre: str

class UsuarioAdminRead(BaseModel):
    id: UUID
    email: str
    nombre: str
    apellido: str
    created_at: datetime
    deleted_at: datetime | None  # None = activo, not-None = inactivo
    roles: list[RolRead]

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    model_config = ConfigDict(from_attributes=True)

# UsuarioAdminUpdate — editable fields for PUT /admin/usuarios/{id}
class UsuarioAdminUpdate(BaseModel):
    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)
    # email: NOT included — see D-01

    model_config = ConfigDict(extra="ignore")

# UsuarioRolesUpdate — payload for PUT /admin/usuarios/{id}/roles
class UsuarioRolesUpdate(BaseModel):
    roles: list[str] = Field(
        min_length=1,
        description="Set completo de roles. Roles válidos: ADMIN, STOCK, PEDIDOS, CLIENT."
    )

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:
        valid = {"ADMIN", "STOCK", "PEDIDOS", "CLIENT"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Roles inválidos: {invalid}")
        return list(set(v))  # deduplicate

# UsuarioEstadoUpdate — payload for PATCH /admin/usuarios/{id}/estado
class UsuarioEstadoUpdate(BaseModel):
    activo: bool  # False = desactivar (soft delete)
```

### 2.3 HTTP Endpoints

All endpoints require `require_role("ADMIN")`. All errors are RFC 7807 `{ detail, code, field? }`.

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/api/v1/admin/usuarios` | query params | `Page[UsuarioAdminRead]` | Listado paginado con búsqueda y filtros |
| GET | `/api/v1/admin/usuarios/{id}` | — | `UsuarioAdminRead` | Detalle de un usuario |
| PUT | `/api/v1/admin/usuarios/{id}` | `UsuarioAdminUpdate` | `UsuarioAdminRead` | Editar datos del usuario |
| PUT | `/api/v1/admin/usuarios/{id}/roles` | `UsuarioRolesUpdate` | `UsuarioAdminRead` | Reemplazar roles del usuario |
| PATCH | `/api/v1/admin/usuarios/{id}/estado` | `UsuarioEstadoUpdate` | `UsuarioAdminRead` | Activar/desactivar usuario |

#### GET `/api/v1/admin/usuarios`

Query params:
- `page: int = 1` — número de página (1-based)
- `size: int = 20` — items por página (max 100)
- `q: str | None = None` — búsqueda full-text por nombre, apellido o email (ILIKE `%q%`)
- `rol: str | None = None` — filtrar por código de rol (ej: `"ADMIN"`, `"CLIENT"`)
- `activo: bool | None = None` — `True` = solo activos (`deleted_at IS NULL`), `False` = solo inactivos, `None` = todos

Response: `Page[UsuarioAdminRead]` con `{ items, total, page, size, pages }`.

#### PUT `/api/v1/admin/usuarios/{id}/roles`

Semantics: **replace** — el payload contiene el set completo de roles deseados. La implementación:
1. Obtiene los roles actuales del usuario.
2. Calcula diff (agregar / quitar).
3. Valida guarda "último ADMIN" ANTES de remover cualquier rol ADMIN.
4. Hard delete de `UsuarioRol` quitados (patrón D-31, eliminación hard en pivot).
5. Inserta nuevos `UsuarioRol`.
6. Revoca todos los refresh tokens del usuario (para forzar re-login con nuevo set de roles).
7. Retorna `UsuarioAdminRead` actualizado.

#### PATCH `/api/v1/admin/usuarios/{id}/estado`

- `activo: True` → revisar si el usuario está desactivado. Si ya está activo, es idempotente (no error).
  - **OQ-02 CERRADA (usuario, 2026-06-02)**: la reactivación queda soportada **únicamente en backend** vía `PATCH /estado` con `activo=true`. El frontend de este change **NO** expone botón "Reactivar"; cualquier reactivación se hará por API directa hasta que un change posterior decida exponerla. Ver D-05.
- `activo: False` → soft delete: `usuario.soft_delete()`. Revoca todos los refresh tokens. Valida guarda "último ADMIN".

**Response 409** si intento de desactivar al último ADMIN: `{ "detail": "No se puede desactivar al último administrador del sistema", "code": "LAST_ADMIN_PROTECTED" }`.

### 2.4 AdminUsuariosRepository (`app/repositories/admin_usuarios.py`)

Extends `BaseRepository[Usuario]`. New methods:

```python
async def list_paginated(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    q: str | None,
    rol: str | None,
    activo: bool | None,
) -> tuple[list[Usuario], int]:
    """Returns (items, total) for pagination. Loads usuario_roles eagerly."""

async def count_active_admins(session: AsyncSession, exclude_user_id: UUID) -> int:
    """Count active ADMINs excluding a specific user. Used in last-admin guard.
    
    Query (inside transaction for atomicity):
        SELECT COUNT(*)
        FROM usuario u
        JOIN usuario_rol ur ON ur.usuario_id = u.id
        JOIN rol r ON r.id = ur.rol_id
        WHERE r.codigo = 'ADMIN'
          AND u.deleted_at IS NULL
          AND ur.deleted_at IS NULL
          AND u.id != :exclude_user_id
        FOR UPDATE OF u  -- D-03: lock to prevent race condition
    """
```

### 2.5 AdminUsuariosService (`app/services/admin_usuarios.py`)

All methods are `@staticmethod`. No `session.commit()` — UoW owns commits. No `HTTPException` — raises `AppError` subclasses.

#### Method: `list_usuarios`
Returns `Page[UsuarioAdminRead]`.

#### Method: `get_usuario`
Returns `UsuarioAdminRead` or raises `NotFoundError`.

#### Method: `update_usuario_data`
Updates `nombre`/`apellido`. Returns `UsuarioAdminRead`. Raises `NotFoundError`.

#### Method: `update_usuario_roles`

```
1. Load target user (404 if not found)
2. Validate all role codes are valid (422 if unknown)
3. Load current UsuarioRol records for user
4. IF 'ADMIN' is being removed:
   a. Lock target user row with SELECT FOR UPDATE (D-03)
   b. count_active_admins(exclude_user_id=target.id)
   c. IF count == 0 → raise ConflictError("LAST_ADMIN_PROTECTED", 409)
5. Hard delete removed UsuarioRol records
6. Insert new UsuarioRol records (with asignado_por_id = current admin user id)
7. revoke_all_for_user(target.id) — forces re-login
8. Return updated UsuarioAdminRead
```

#### Method: `deactivate_usuario`

```
1. Load target user (404 if not found)
2. IF activo=False (deactivation):
   a. IF user has ADMIN role:
      i. Lock target user row with SELECT FOR UPDATE (D-03)
      ii. count_active_admins(exclude_user_id=target.id)
      iii. IF count == 0 → raise ConflictError("LAST_ADMIN_PROTECTED", 409)
   b. IF user already deleted_at IS NOT NULL → idempotent, skip
   c. user.soft_delete()  — sets deleted_at = now()
   d. revoke_all_for_user(target.id)
3. IF activo=True (reactivation — D-05):
   a. IF user already deleted_at IS NULL → idempotent, skip
   b. user.deleted_at = None
4. Return updated UsuarioAdminRead
```

### 2.6 Auth Integration (no code changes needed)

The existing code already blocks deactivated users:

- **Login** (`POST /auth/login` via `AuthService.login_user`): calls `uow.usuarios.get_by_email()` which filters `WHERE deleted_at IS NULL`. Deleted user returns `None` → dummy password check + `UnauthorizedError("Invalid credentials")`. No info leak (same error as wrong password per RN-AU08).

- **get_current_user** (any authenticated endpoint): calls `uow.usuarios.get_by_id()` which filters `WHERE deleted_at IS NULL`. Deleted user returns `None` → `UnauthorizedError`. Existing Bearer tokens become immediately invalid after soft delete.

- **Refresh** (`POST /auth/refresh`): does NOT re-validate user active status directly, but all refresh tokens are revoked at deactivation time, so any rotation attempt returns 401 (revoked token).

**Delta spec action**: Update `backend-auth-register-login` and `backend-auth-dependencies` to document this invariant explicitly.

### 2.7 Router (`app/api/v1/admin_usuarios.py`)

URL convention: `/admin/usuarios` (Spanish plural, with `/admin/` prefix for clarity, aligning with Historias de Usuario note: `GET /api/admin/usuarios`). However, project convention is `/api/v1/` + resource in Spanish plural. Since no other admin endpoints exist yet (they'll be added in Changes 22/23), introducing `/api/v1/admin/` prefix establishes the admin namespace.

The router is mounted in `build_v1_router` under prefix `/admin/usuarios`.

```python
admin_usuarios_router = APIRouter()

@admin_usuarios_router.get("/", response_model=Page[UsuarioAdminRead])
async def list_usuarios(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    rol: str | None = Query(None),
    activo: bool | None = Query(None),
    _admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
): ...

@admin_usuarios_router.get("/{id}", response_model=UsuarioAdminRead)
async def get_usuario(id: UUID, ...): ...

@admin_usuarios_router.put("/{id}", response_model=UsuarioAdminRead)
async def update_usuario_data(id: UUID, body: UsuarioAdminUpdate, ...): ...

@admin_usuarios_router.put("/{id}/roles", response_model=UsuarioAdminRead)
async def update_usuario_roles(id: UUID, body: UsuarioRolesUpdate, ...): ...

@admin_usuarios_router.patch("/{id}/estado", response_model=UsuarioAdminRead)
async def update_usuario_estado(id: UUID, body: UsuarioEstadoUpdate, ...): ...
```

> Route order matters: `/{id}/roles` and `/{id}/estado` MUST be declared BEFORE `/{id}` (generic dynamic segment) to avoid path matching ambiguity.

---

## 3. Frontend Architecture

### 3.1 FSD Layer Mapping

```
src/
├── pages/
│   └── AdminUsersPage/
│       └── index.tsx                # Página principal /admin/users
├── features/
│   └── admin-users/
│       ├── index.ts                 # Public API barrel
│       ├── api/
│       │   ├── useUsersQuery.ts          # GET /admin/usuarios paginado
│       │   ├── useUserQuery.ts           # GET /admin/usuarios/{id}
│       │   ├── useUpdateUserMutation.ts  # PUT /admin/usuarios/{id}
│       │   ├── useUpdateUserRolesMutation.ts  # PUT /admin/usuarios/{id}/roles
│       │   └── useDeactivateUserMutation.ts   # PATCH /admin/usuarios/{id}/estado
│       ├── ui/
│       │   ├── UsersTable.tsx            # Tabla paginada
│       │   ├── UserSearchBar.tsx         # Input búsqueda con debounce 400ms
│       │   ├── UserFilters.tsx           # Select rol + filtro activo
│       │   ├── EditUserModal.tsx         # Modal edición de nombre/apellido
│       │   ├── EditUserRolesModal.tsx    # Modal edición de roles (checkboxes)
│       │   └── DeactivateUserModal.tsx   # Modal confirmación destructiva
│       └── types.ts                      # UsuarioAdminRead, RolRead types
```

### 3.2 Page: AdminUsersPage (`/admin/users`)

```
AdminUsersPage
├── Header: "Gestión de Usuarios"
├── UserSearchBar (debounce 400ms, min 3 chars)
├── UserFilters (rol select, activo toggle)
├── UsersTable
│   ├── Columns: Nombre, Email, Roles (badges), Estado (badge), Fecha registro, Acciones
│   ├── Actions per row: [Editar datos] [Editar roles] [Desactivar]
│   └── Pagination controls
├── EditUserModal (lazy, opens on "Editar datos")
├── EditUserRolesModal (lazy, opens on "Editar roles")
└── DeactivateUserModal (opens on "Desactivar")
```

### 3.3 TanStack Query Hooks

```typescript
// useUsersQuery.ts
export function useUsersQuery(params: UsersQueryParams) {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => apiClient.get<Page<UsuarioAdminRead>>('/admin/usuarios', { params }),
    staleTime: 30_000,
  });
}

// useUpdateUserMutation.ts
export function useUpdateUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UsuarioAdminUpdate }) =>
      apiClient.put<UsuarioAdminRead>(`/admin/usuarios/${id}`, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] });
      qc.invalidateQueries({ queryKey: ['admin', 'user', id] });
    },
  });
}

// useUpdateUserRolesMutation.ts — same pattern

// useDeactivateUserMutation.ts
export function useDeactivateUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, activo }: { id: string; activo: boolean }) =>
      apiClient.patch<UsuarioAdminRead>(`/admin/usuarios/${id}/estado`, { activo }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
    onError: (err) => {
      // Handle LAST_ADMIN_PROTECTED → show specific error message
    },
  });
}
```

### 3.4 Role Management UI

`EditUserRolesModal` renders a checkbox group with the 4 available roles (ADMIN, STOCK, PEDIDOS, CLIENT). The submit handler calls `useUpdateUserRolesMutation`. On `LAST_ADMIN_PROTECTED` error, shows a clear message: "No se puede quitar el rol ADMIN al único administrador del sistema."

### 3.5 Deactivate Confirmation Modal

`DeactivateUserModal` renders a destructive confirmation dialog with:
- User's name and email.
- Warning text: "Esta acción cerrará todas las sesiones activas del usuario e impedirá su acceso al sistema. Los pedidos históricos no serán afectados."
- "Desactivar" (destructive) and "Cancelar" buttons.

### 3.6 Routing

The router already has `/admin/*` → `RoleGuard roles={['ADMIN']}` → `AdminPage` (from Change 08 routing spec). Change 21 adds a subroute under `/admin`:

```tsx
// Subroute within /admin/* tree
<Route path="users" element={<Suspense fallback={<PageSpinner />}><AdminUsersPage /></Suspense>} />
```

The `RoleGuard roles={['ADMIN']}` from the parent `/admin/*` route already enforces access.

### 3.7 Navigation

The `frontend-navigation` spec (Change 08) already declares:
```typescript
{ key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] }
```
No change to `NAVIGATION_ITEMS` is required.

---

## 4. Transactions and Invariants

### 4.1 Unit of Work for Role Update

```
AdminUsuariosService.update_usuario_roles(uow, target_id, new_roles, admin_id):
  async with uow:
    1. load target user (404 if not found)
    2. load current usuario_roles
    3. IF ADMIN role being removed:
       a. SELECT usuario_rol JOINING rol WHERE codigo='ADMIN' AND usuario.deleted_at IS NULL
          AND usuario.id != target_id
          FOR UPDATE  ← D-03 pessimistic lock
       b. count = result.rowcount
       c. IF count == 0 → raise ConflictError(code="LAST_ADMIN_PROTECTED") → HTTP 409
    4. Hard-delete removed UsuarioRol records (session.delete(ur))
    5. Insert new UsuarioRol records
    6. revoke_all_for_user(target_id)  ← US-054 explicit requirement
    7. reload user with get_with_roles(target_id)
  → commit on __aexit__
```

### 4.2 Unit of Work for Deactivation

```
AdminUsuariosService.deactivate_usuario(uow, target_id, activo, admin_id):
  async with uow:
    1. load target user (404 if not found)
    2. IF NOT activo (deactivate):
       a. IF user has ADMIN role AND user.deleted_at IS NULL:
          i. SELECT ... FOR UPDATE  ← D-03
          ii. count = count_active_admins(exclude=target_id)
          iii. IF count == 0 → raise ConflictError(code="LAST_ADMIN_PROTECTED")
       b. IF already deleted_at IS NOT NULL → idempotent, skip remaining
       c. user.soft_delete()
       d. revoke_all_for_user(target_id)  ← US-055 explicit requirement
    3. IF activo (reactivate):
       a. IF already deleted_at IS NULL → idempotent, skip
       b. user.deleted_at = None
  → commit on __aexit__
```

### 4.3 Last-Admin Guard — Concurrency Safety (D-03)

```
Decision D-03: SELECT FOR UPDATE (pessimistic row lock)

Scenario: Two ADMIN users (A and B) simultaneously attempt to:
  - A degrades B's ADMIN role
  - B degrades A's ADMIN role
Both would pass the count check independently (count=1 for each).

Solution: Lock the target user's row with SELECT FOR UPDATE before counting.
  - Transaction T1 locks user B's row
  - Transaction T2 attempts to lock user A's row
  - When T1 counts: count of admins excluding B = 1 (A is still ADMIN) → allowed
  - When T2 counts: count of admins excluding A = 0 (B already degraded by T1) → 409

Alternative considered: PostgreSQL advisory lock pg_advisory_xact_lock(hash(user_id))
  - Pro: coarser grain, simpler implementation
  - Con: advisory locks don't integrate with SQLAlchemy transaction context naturally
  - Decision: SELECT FOR UPDATE preferred (standard SQL, integrates with UoW)
```

---

## 5. Design Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-01 | Email is immutable for ADMIN editing another user's profile | Consistent with Change 13 (email immutable for own profile). Email uniqueness enforcement across concurrent operations would require extra SELECT FOR UPDATE. Integrador v5.0 doesn't grant email modification to ADMIN. |
| D-02 | Role update is PUT (replace full set) not PATCH (delta add/remove) | Simpler payload, atomic (single operation), avoids partial state. Downside: requires client to always send full desired set. Frontend sends checkbox selection. |
| D-03 | Pessimistic SELECT FOR UPDATE for last-admin guard | Standard SQL, integrates cleanly with async SQLAlchemy and UoW context manager. Prevents TOCTOU race condition between concurrent ADMIN degradation operations. |
| D-04 | URL prefix `/admin/usuarios` (not `/usuarios` with role guard) | Admin namespace is semantically distinct from future user self-service endpoints. Prepares for Change 22 (`/admin/*` router namespace). Consistent with Historias de Usuario note: `GET /api/admin/usuarios`. |
| D-05 | PATCH `/estado` supports both `activo=true` (reactivation) and `activo=false` (deactivation) | US-055 only explicitly requires deactivation, but the endpoint accepts `activo` bool. Reactivation is implemented but NOT wired to the frontend in this change. The endpoint exists in the API for future use or admin tooling. |
| D-06 | Roles update always revokes all refresh tokens | Required by US-054 ("Invalidar refresh tokens del usuario modificado para forzar re-login con nuevo rol"). Uses existing `revoke_all_for_user` method from Change 07. |
| D-07 | pg_trgm GIN indexes for ILIKE search | Enables `%substring%` matching. Pure `lower()` functional indexes only help `prefix%` queries. GIN pg_trgm is the correct choice for search UX. Requires `CREATE EXTENSION pg_trgm`. |
| D-08 | Hard delete for removed UsuarioRol records | Consistent with existing pattern in Change 09 (UsuarioRol assignment is operational hard delete, D-31). `deleted_at` on UsuarioRol is "dormant" per D-29. |

---

## 6. Error Catalog

| HTTP | Code | When |
|------|------|------|
| 404 | `USER_NOT_FOUND` | Target user ID does not exist |
| 409 | `LAST_ADMIN_PROTECTED` | Operation would leave system with zero ADMIN users |
| 422 | Pydantic validation | Invalid role codes, missing required fields |
| 403 | `forbidden` | Non-ADMIN caller (from `require_role`) |
| 401 | `missing_token` / `invalid_token` | Missing or invalid Bearer token |

---

## 7. Open Questions (carried from proposal)

| ID | Question | Impact on Design |
|----|----------|-----------------|
| OQ-01 | ADMIN editar email de otro usuario | **CERRADA (2026-06-02)**: email inmutable. `UsuarioAdminUpdate` NO incluye `email`. Si llega en payload, se ignora silenciosamente o el schema lo rechaza (extra="forbid"). |
| OQ-02 | Endpoint de reactivación expuesto en frontend | **CERRADA (2026-06-02)**: backend soporta `activo=true`; el frontend NO expone "Reactivar" en este change. Solo botón "Desactivar". |
| OQ-03 | PUT vs PATCH for roles (resolved as D-02: PUT replace) | Already decided. |
| OQ-04 | SELECT FOR UPDATE vs advisory lock (resolved as D-03: SELECT FOR UPDATE) | Already decided. |
