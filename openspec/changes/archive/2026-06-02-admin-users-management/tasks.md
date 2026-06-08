# Tasks: admin-users-management

**Change**: 21  
**Sprint**: 8  
**Date**: 2026-06-02  

---

## Legend

- [ ] Pending
- [x] Done
- Each task is atomic and independently verifiable
- Integration tests are marked `@pytest.mark.integration`

---

## Phase 1 — Backend: Data Layer

### Task 1.1 — Alembic migration: pg_trgm indexes

**File**: `backend/alembic/versions/0013_admin_usuarios_search_indexes.py`

- [x] Create migration `0013` with `upgrade()`:
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE INDEX ix_usuario_email_trgm ON usuario USING gin (email gin_trgm_ops);
  CREATE INDEX ix_usuario_nombre_trgm ON usuario USING gin (nombre gin_trgm_ops);
  CREATE INDEX ix_usuario_apellido_trgm ON usuario USING gin (apellido gin_trgm_ops);
  ```
- [x] `downgrade()` drops the three indexes (conditionally: `DROP INDEX IF EXISTS`).
- [x] Migration runs without error: `alembic upgrade head`.
- [x] Verify with `\d usuario` in psql: three GIN indexes appear.

---

### Task 1.2 — Pydantic schemas for admin-usuarios

**File**: `backend/app/schemas/admin_usuarios.py`

- [x] Define `RolRead(BaseModel)` with `id: UUID`, `codigo: str`, `nombre: str`. `from_attributes=True`.
- [x] Define `UsuarioAdminRead(BaseModel)` with `id: UUID`, `email: str`, `nombre: str`, `apellido: str`, `created_at: datetime`, `deleted_at: datetime | None`, `roles: list[RolRead]`. `from_attributes=True`. Does NOT include `password_hash`.
- [x] Add computed property `is_active: bool` (returns `self.deleted_at is None`).
- [x] Define `UsuarioAdminUpdate(BaseModel)` with `nombre: str | None = None` (max 80), `apellido: str | None = None` (max 80). `extra="ignore"` (email drops silently per D-01).
- [x] Define `UsuarioRolesUpdate(BaseModel)` with `roles: list[str]` (min 1 item). Add `@field_validator("roles")` that validates each item is in `{"ADMIN","STOCK","PEDIDOS","CLIENT"}` and deduplicates. Raises `ValueError` with invalid role names on invalid input.
- [x] Define `UsuarioEstadoUpdate(BaseModel)` with `activo: bool`.
- [x] Unit test: `UsuarioAdminUpdate(nombre="Ana", email="hack@test.com").email` raises `AttributeError` (field doesn't exist).
- [x] Unit test: `UsuarioRolesUpdate(roles=["ADMIN","INVALID"])` raises `ValidationError`.
- [x] Unit test: `UsuarioRolesUpdate(roles=["ADMIN","ADMIN"])` deduplicates to `["ADMIN"]`.

---

### Task 1.3 — AdminUsuariosRepository

**File**: `backend/app/repositories/admin_usuarios.py`

- [x] Define `AdminUsuariosRepository(BaseRepository[Usuario])`.
- [x] Implement `async def list_paginated(self, *, page, size, q, rol, activo) -> tuple[list[Usuario], int]`:
  - Base query: `SELECT usuario` with `selectinload(Usuario.usuario_roles).selectinload(UsuarioRol.rol)`.
  - If `q`: add `OR` filter `(usuario.nombre.ilike(f'%{q}%') OR usuario.apellido.ilike(f'%{q}%') OR usuario.email.ilike(f'%{q}%'))`.
  - If `rol`: join to `UsuarioRol` and `Rol` with `WHERE rol.codigo = :rol`.
  - If `activo is True`: add `WHERE usuario.deleted_at IS NULL`.
  - If `activo is False`: add `WHERE usuario.deleted_at IS NOT NULL`.
  - Count query: same filters, `SELECT COUNT(*)`.
  - Return `(items, total)` where `items` is `result[(page-1)*size : page*size]`.
  - ORDER BY: `usuario.created_at DESC` (newest first).
- [x] Implement `async def count_active_admins(self, *, exclude_user_id: UUID) -> int`:
  - Query: `SELECT COUNT(*) FROM usuario u JOIN usuario_rol ur ON ur.usuario_id = u.id JOIN rol r ON r.id = ur.rol_id WHERE r.codigo = 'ADMIN' AND u.deleted_at IS NULL AND ur.deleted_at IS NULL AND u.id != :exclude_user_id FOR UPDATE OF u`.
  - Returns integer count.
- [x] Unit test: `list_paginated` with `q="admin"` generates ILIKE filter.
- [x] Unit test: `list_paginated` with `rol="ADMIN"` includes JOIN to `Rol`.
- [x] Unit test: `count_active_admins` with all ADMINs active returns correct count.

---

### Task 1.4 — UnitOfWork: add admin_usuarios repo

**File**: `backend/app/core/uow.py`

- [x] Add `TYPE_CHECKING` import: `from app.repositories.admin_usuarios import AdminUsuariosRepository`.
- [x] Add `_admin_usuarios: AdminUsuariosRepository | None = None` attribute.
- [x] Add `@property admin_usuarios` lazy initializer: `AdminUsuariosRepository(self.session)`.
- [x] Verify: `uow.admin_usuarios` returns an `AdminUsuariosRepository` instance in tests.

---

## Phase 2 — Backend: Service Layer

### Task 2.1 — AdminUsuariosService: list and get

**File**: `backend/app/services/admin_usuarios.py`

- [x] Define `AdminUsuariosService` class with `@staticmethod` methods.
- [x] Implement `async def list_usuarios(uow, *, page, size, q, rol, activo) -> Page[UsuarioAdminRead]`:
  - Use `uow.admin_usuarios.list_paginated(...)`.
  - Build `Page[UsuarioAdminRead]` using `create_pagination_meta(total, page, size)`.
  - Map each `Usuario` to `UsuarioAdminRead.model_validate(u)`.
- [x] Implement `async def get_usuario(uow, user_id) -> UsuarioAdminRead`:
  - Use `uow.usuarios.get_with_roles(user_id)`.
  - Raise `NotFoundError(code="USER_NOT_FOUND")` if None.
- [x] Unit test: `list_usuarios` returns `Page` with correct `total`, `pages`, `items`.
- [x] Unit test: `get_usuario` with non-existent ID raises `NotFoundError`.

---

### Task 2.2 — AdminUsuariosService: update data

**File**: `backend/app/services/admin_usuarios.py`

- [x] Implement `async def update_usuario_data(uow, user_id, data: UsuarioAdminUpdate) -> UsuarioAdminRead`:
  - Fetch user via `uow.usuarios.get_with_roles(user_id)`. Raise `NotFoundError` if None.
  - Build update dict from `data.model_dump(exclude_none=True)`.
  - If empty: return current `UsuarioAdminRead` (idempotent).
  - Apply fields via `setattr`, add to session via `uow.usuarios.add(user)`.
  - Re-query via `get_with_roles` to reload relationships.
  - Return `UsuarioAdminRead.model_validate(reloaded)`.
- [x] Unit test: `update_usuario_data` with `nombre="Nuevo"` updates and returns updated read model.
- [x] Unit test: `update_usuario_data` with all-None payload returns unchanged user.
- [x] Unit test: `update_usuario_data` with non-existent ID raises `NotFoundError`.

---

### Task 2.3 — AdminUsuariosService: update roles (with last-admin guard)

**File**: `backend/app/services/admin_usuarios.py`

- [x] Implement `async def update_usuario_roles(uow, user_id, new_roles: list[str], admin_id: UUID) -> UsuarioAdminRead`:
  - Load user with `get_with_roles(user_id)`. Raise `NotFoundError` if None.
  - Extract current role codes from user's `usuario_roles`.
  - Check if ADMIN role is being removed: `"ADMIN" in current_codes and "ADMIN" not in new_roles`.
  - If so: call `count_active_admins(exclude_user_id=user_id)`. If `count == 0` → raise `ConflictError("No se puede quitar el rol ADMIN al último administrador del sistema", code="LAST_ADMIN_PROTECTED", status_code=409)`.
  - Get Rol objects for each code in `new_roles` via `uow.roles.get_by_codigo`. Raise `NotFoundError` for unknown roles.
  - Hard-delete current `UsuarioRol` records via `session.delete(ur)` for each.
  - Insert new `UsuarioRol` records with `asignado_por_id=admin_id`.
  - Call `uow.refresh_tokens.revoke_all_for_user(user_id)`.
  - Re-query with `get_with_roles` and return `UsuarioAdminRead`.
- [x] Unit test: `update_usuario_roles` removes old roles and assigns new ones.
- [x] Unit test: `update_usuario_roles` revokes all refresh tokens.
- [x] Unit test: `update_usuario_roles` when only ADMIN tries to remove own ADMIN role (last admin) → raises `ConflictError` with `code="LAST_ADMIN_PROTECTED"`.
- [x] Unit test: `update_usuario_roles` when two ADMINs exist, removing one's ADMIN role succeeds.
- [x] Integration test `@pytest.mark.integration`: concurrent transactions — two simultaneous demotions of last ADMIN → exactly one succeeds, one gets `LAST_ADMIN_PROTECTED`.

---

### Task 2.4 — AdminUsuariosService: deactivate/reactivate (with last-admin guard)

**File**: `backend/app/services/admin_usuarios.py`

- [x] Implement `async def deactivate_usuario(uow, user_id, activo: bool) -> UsuarioAdminRead`:
  - Load user. Raise `NotFoundError` if None.
  - If `activo=False` (deactivate):
    - Check if user has ADMIN role (any `ur.rol.codigo == "ADMIN"` in `usuario_roles`).
    - If ADMIN: call `count_active_admins(exclude_user_id=user_id)`. If `count == 0` → raise `ConflictError(code="LAST_ADMIN_PROTECTED")`.
    - If `user.deleted_at is not None`: already inactive → idempotent (return current state, no error).
    - Call `user.soft_delete()`.
    - Call `uow.refresh_tokens.revoke_all_for_user(user_id)`.
  - If `activo=True` (reactivate per D-05):
    - If `user.deleted_at is None`: already active → idempotent.
    - Else: `user.deleted_at = None`.
  - Re-query and return `UsuarioAdminRead`.
- [x] Unit test: deactivate sets `deleted_at` and revokes tokens.
- [x] Unit test: deactivate is idempotent (calling twice doesn't error).
- [x] Unit test: deactivate last ADMIN → `ConflictError("LAST_ADMIN_PROTECTED")`.
- [x] Unit test: reactivate inactive user clears `deleted_at`.
- [x] Integration test `@pytest.mark.integration`: deactivated user's Bearer token rejected on next authenticated request.
- [x] Integration test `@pytest.mark.integration`: deactivated user's email+password rejected at `POST /auth/login`.

---

## Phase 3 — Backend: API Layer

### Task 3.1 — Admin usuarios router

**File**: `backend/app/api/v1/admin_usuarios.py`

- [x] Define `admin_usuarios_router = APIRouter(tags=["admin-usuarios"])`.
- [x] Declare routes in this ORDER to avoid path matching ambiguity:
  1. `GET /` → `list_usuarios`
  2. `GET /{id}` → `get_usuario`
  3. `PUT /{id}/roles` → `update_usuario_roles` ← BEFORE `PUT /{id}`
  4. `PATCH /{id}/estado` → `update_usuario_estado` ← BEFORE `PUT /{id}`
  5. `PUT /{id}` → `update_usuario_data`
- [x] All endpoints use `Depends(require_role("ADMIN"))` for RBAC.
- [x] `GET /` returns `Page[UsuarioAdminRead]` with `response_model=Page[UsuarioAdminRead]`.
- [x] Router does NOT raise `HTTPException` directly — service raises `AppError`, global handler maps to RFC 7807.
- [x] Each endpoint calls `AdminUsuariosService.<method>(uow, ...)` inside a `async with uow` block — OR delegates UoW ownership to the service (service opens `async with uow`).
- [x] Integration test: `GET /api/v1/admin/usuarios` with ADMIN Bearer → HTTP 200 with `Page` response.
- [x] Integration test: `GET /api/v1/admin/usuarios` with CLIENT Bearer → HTTP 403.
- [x] Integration test: `GET /api/v1/admin/usuarios` without Bearer → HTTP 401.
- [x] Integration test: `PUT /api/v1/admin/usuarios/{id}/roles` with last ADMIN → HTTP 409 `LAST_ADMIN_PROTECTED`.
- [x] Integration test: `PATCH /api/v1/admin/usuarios/{id}/estado` with `activo=false` → revokes tokens, subsequent `GET /api/v1/auth/me` → HTTP 401.

---

### Task 3.2 — Register router in build_v1_router

**File**: `backend/app/api/v1/router.py`

- [x] Add import: `from app.api.v1.admin_usuarios import admin_usuarios_router`.
- [x] Add to `build_v1_router`: `router.include_router(admin_usuarios_router, prefix="/admin/usuarios", tags=["admin-usuarios"])`.
- [x] Verify routes with `GET /docs` or `GET /openapi.json`: all 5 endpoints appear under tag `"admin-usuarios"`.
- [x] Existing routers (`/auth/*`, `/productos/*`, `/pedidos/*`, etc.) are unaffected.

---

## Phase 4 — Frontend: Entities and Types

### Task 4.1 — TypeScript types for admin-users

**File**: `src/features/admin-users/types.ts`

- [x] Define `RolRead` interface: `{ id: string; codigo: string; nombre: string }`.
- [x] Define `UsuarioAdminRead` interface with all fields from backend schema. Include `is_active: boolean` computed from `deleted_at`.
- [x] Define `UsersQueryParams` interface: `{ page?: number; size?: number; q?: string; rol?: string; activo?: boolean }`.
- [x] Define `UsuarioAdminUpdate` interface: `{ nombre?: string; apellido?: string }`.
- [x] Define `UsuarioRolesUpdate` interface: `{ roles: string[] }`.
- [x] Define `UsuarioEstadoUpdate` interface: `{ activo: boolean }`.
- [x] TypeScript strict mode: no `any`, no implicit `undefined`.

---

## Phase 5 — Frontend: API Hooks (TanStack Query)

### Task 5.1 — useUsersQuery

**File**: `src/features/admin-users/api/useUsersQuery.ts`

- [x] Implement `useUsersQuery(params: UsersQueryParams)` using `useQuery`.
- [x] Query key: `['admin', 'users', params]`.
- [x] Calls `GET /api/v1/admin/usuarios` with `params` as query string.
- [x] Returns `Page<UsuarioAdminRead>`.
- [x] `staleTime: 30_000` (30 seconds).
- [x] On `q` param: only send if `q.length >= 3` or `q` is empty/undefined (debounce handled in UI).

---

### Task 5.2 — useUpdateUserMutation

**File**: `src/features/admin-users/api/useUpdateUserMutation.ts`

- [x] `PUT /api/v1/admin/usuarios/{id}` with `UsuarioAdminUpdate` body.
- [x] On success: invalidate `['admin', 'users']`.

---

### Task 5.3 — useUpdateUserRolesMutation

**File**: `src/features/admin-users/api/useUpdateUserRolesMutation.ts`

- [x] `PUT /api/v1/admin/usuarios/{id}/roles` with `UsuarioRolesUpdate` body.
- [x] On success: invalidate `['admin', 'users']`.
- [x] On error with `code="LAST_ADMIN_PROTECTED"`: DO NOT invalidate cache — propagate error for UI to handle.

---

### Task 5.4 — useDeactivateUserMutation

**File**: `src/features/admin-users/api/useDeactivateUserMutation.ts`

- [x] `PATCH /api/v1/admin/usuarios/{id}/estado` with `UsuarioEstadoUpdate`.
- [x] On success: invalidate `['admin', 'users']`.
- [x] On error with `code="LAST_ADMIN_PROTECTED"`: propagate for UI to show specific message.

---

## Phase 6 — Frontend: UI Components

### Task 6.1 — UsersTable component

**File**: `src/features/admin-users/ui/UsersTable.tsx`

- [x] Receives `users: UsuarioAdminRead[]`, `isLoading: boolean`, event handlers.
- [x] Columns: Nombre + Apellido, Email, Roles (badge por cada rol), Estado (badge "Activo"/"Inactivo"), Fecha registro (`created_at`), Acciones.
- [x] Acciones por fila: [Editar datos] [Editar roles] [Desactivar/Reactivar].
- [x] Estado badge: verde para Activo, rojo/gris para Inactivo.
- [x] Shows skeleton loader rows when `isLoading=true` (using `animate-pulse` Tailwind).
- [x] "Desactivar" button disabled/hidden if user is already inactive.
- [x] Responsive: horizontal scroll on mobile.

---

### Task 6.2 — UserSearchBar + UserFilters

**File**: `src/features/admin-users/ui/UserSearchBar.tsx`

- [x] Input text con debounce de 400ms via `useDebounce` de `src/shared/hooks/`.
- [x] Placeholder: "Buscar por nombre, apellido o email...".
- [x] Solo envía el valor al padre si `q.length >= 3` o `q === ""` (igual que panel de pedidos).
- [x] `onChange` callback recibe el valor debounced.

**File**: `src/features/admin-users/ui/UserFilters.tsx`

- [x] Select de rol: opciones "Todos", "ADMIN", "STOCK", "PEDIDOS", "CLIENT".
- [x] Toggle/Select de estado: "Todos", "Activos", "Inactivos".
- [x] `onChange` callbacks para cada filtro.
- [x] No debounce (selects cambian inmediatamente como en panel de pedidos).

---

### Task 6.3 — EditUserModal

**File**: `src/features/admin-users/ui/EditUserModal.tsx`

- [x] Modal con formulario TanStack Form.
- [x] Campos: `nombre` (max 80), `apellido` (max 80). Email NO editable (display-only per D-01).
- [x] Pre-populate con datos actuales del usuario.
- [x] Submit llama `useUpdateUserMutation`. Loading state en botón.
- [x] Cierra el modal en éxito. Muestra toast de éxito.
- [x] Muestra error de validación bajo cada campo si Pydantic retorna 422.

---

### Task 6.4 — EditUserRolesModal

**File**: `src/features/admin-users/ui/EditUserRolesModal.tsx`

- [x] Modal con checkboxes para los 4 roles: ADMIN, STOCK, PEDIDOS, CLIENT.
- [x] Pre-marca los roles actuales del usuario.
- [x] Requiere al menos 1 rol seleccionado (validación frontend antes de submit).
- [x] Submit llama `useUpdateUserRolesMutation`.
- [x] En error `LAST_ADMIN_PROTECTED`: muestra mensaje inline: "No es posible quitar el rol ADMIN al único administrador del sistema."
- [x] Cierra en éxito. Muestra toast de éxito.

---

### Task 6.5 — DeactivateUserModal

**File**: `src/features/admin-users/ui/DeactivateUserModal.tsx`

- [x] Modal de confirmación destructiva.
- [x] Muestra nombre y email del usuario a desactivar.
- [x] Texto de advertencia: "Esta acción cerrará todas las sesiones activas de [nombre] e impedirá su acceso al sistema. Los pedidos históricos no serán afectados."
- [x] Botones: "Cancelar" (secondary) y "Desactivar" (destructive/danger).
- [x] En error `LAST_ADMIN_PROTECTED`: muestra mensaje inline en el modal.
- [x] Cierra en éxito. Muestra toast de éxito.

---

### Task 6.6 — AdminUsersPage

**File**: `src/pages/AdminUsersPage/index.tsx`

- [x] Composición: `UserSearchBar` + `UserFilters` + `UsersTable` + paginación + modales.
- [x] Estado local: `page`, `size=20`, `q`, `rol`, `activo`, `selectedUser`, `openModal` (edit|roles|deactivate|null).
- [x] `useUsersQuery({ page, size, q: debouncedQ, rol, activo })` con debounce para `q`.
- [x] Paginación: controles Anterior/Siguiente + número de página. Usa `total`, `pages` del response.
- [x] Lazy import de modales (solo se cargan cuando se abren).
- [x] Título de página: "Gestión de Usuarios".
- [x] Estado vacío: "No se encontraron usuarios." cuando `items.length === 0 && !isLoading`.
- [x] Accessibility: `aria-label` en botones de acción, focus management en modales.

---

## Phase 7 — Frontend: Routing

### Task 7.1 — Add /admin/users subroute

**File**: `src/app/router/index.tsx` (or equivalent router file)

- [x] Within the `/admin/*` `RoleGuard roles={['ADMIN']}` subtree, add:
  ```tsx
  <Route
    path="users"
    element={
      <Suspense fallback={<PageSpinner />}>
        <AdminUsersPage />
      </Suspense>
    }
  />
  ```
- [x] `RoleGuard` is the outer element (parent route); `Suspense` is inner (child route) — guard-before-Suspense invariant.
- [x] Lazy import: `const AdminUsersPage = React.lazy(() => import('@/pages/AdminUsersPage'))`.
- [x] Test: navigating to `/admin/users` with ADMIN user renders `AdminUsersPage`.
- [x] Test: navigating to `/admin/users` with CLIENT user redirects to `/403`.

---

### Task 7.2 — Verify navigation entry

**File**: `src/shared/lib/navigation/items.ts`

- [x] Confirm entry `{ key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] }` already exists in `NAVIGATION_ITEMS` (from Change 08).
- [x] If missing: add it to `NAVIGATION_ITEMS` under ADMIN-only items section.
- [x] Test: `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` includes `/admin/users`.
- [x] Test: `filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])` excludes `/admin/users`.

---

## Phase 8 — Tests

### Task 8.1 — Unit tests: schemas

**File**: `backend/tests/unit/test_admin_usuarios_schemas.py`

- [x] `UsuarioAdminUpdate` drops `email` silently.
- [x] `UsuarioRolesUpdate` rejects unknown roles.
- [x] `UsuarioRolesUpdate` deduplicates roles.
- [x] `UsuarioRolesUpdate` with empty list raises validation error (min_length=1).
- [x] `UsuarioAdminRead` does not include `password_hash` field.

---

### Task 8.2 — Unit tests: service (mock repos)

**File**: `backend/tests/unit/test_admin_usuarios_service.py`

- [x] `list_usuarios` returns correct pagination metadata.
- [x] `update_usuario_roles` with last ADMIN → raises `ConflictError("LAST_ADMIN_PROTECTED")`.
- [x] `update_usuario_roles` with 2+ ADMINs → succeeds and revokes tokens.
- [x] `deactivate_usuario(activo=False)` → sets `deleted_at` and revokes tokens.
- [x] `deactivate_usuario(activo=False)` when already inactive → idempotent (no error).
- [x] `deactivate_usuario(activo=False)` for last ADMIN → raises `ConflictError("LAST_ADMIN_PROTECTED")`.
- [x] `deactivate_usuario(activo=True)` → clears `deleted_at`.

---

### Task 8.3 — Integration tests: API endpoints

**File**: `backend/tests/integration/test_admin_usuarios_api.py`

- [x] `@pytest.mark.integration` GET `/api/v1/admin/usuarios` → HTTP 200 with `Page` structure.
- [x] `@pytest.mark.integration` GET without auth → HTTP 401.
- [x] `@pytest.mark.integration` GET with CLIENT token → HTTP 403.
- [x] `@pytest.mark.integration` GET with `?q=admin` → filters correctly.
- [x] `@pytest.mark.integration` GET with `?activo=true` → only active users.
- [x] `@pytest.mark.integration` PUT `/roles` with last ADMIN → HTTP 409 with `code="LAST_ADMIN_PROTECTED"`.
- [x] `@pytest.mark.integration` PATCH `/estado` `activo=false` → subsequent auth request returns 401.
- [x] `@pytest.mark.integration` PATCH `/estado` `activo=false` + refresh token attempt → 401.

---

### Task 8.4 — Integration test: concurrency for last-admin guard

**File**: `backend/tests/integration/test_admin_usuarios_concurrency.py`

- [x] `@pytest.mark.integration` Two concurrent requests to degrade the last ADMIN:
  - Setup: system with exactly 1 ADMIN user (user A).
  - Simultaneously fire `PUT /api/v1/admin/usuarios/{A.id}/roles` with `{ roles: ["CLIENT"] }` from two separate connections.
  - Assert: exactly one succeeds (HTTP 200), exactly one fails (HTTP 409 `LAST_ADMIN_PROTECTED`).
  - Assert: user A still has ADMIN role (degradation was blocked by winner or loser).
  - Implementation: use `asyncio.gather` with two concurrent test client calls.

---

## Phase 9 — Delta Spec Updates

### Task 9.1 — Write new specs and update existing specs

- [x] Create `openspec/specs/backend-admin-users-management/spec.md` (new capability spec).
- [x] Create `openspec/specs/frontend-admin-users-page/spec.md` (new capability spec).
- [x] Update `openspec/specs/backend-api-v1-router/spec.md` (ADDED: admin-usuarios router registration).
- [x] Update `openspec/specs/backend-data-model/spec.md` (ADDED: pg_trgm indexes on Usuario).
- [x] Update `openspec/specs/backend-auth-register-login/spec.md` (document: login blocks `deleted_at IS NOT NULL`).
- [x] Update `openspec/specs/backend-auth-dependencies/spec.md` (document: `get_current_user` blocks soft-deleted users).
- [x] Update `openspec/specs/frontend-routing/spec.md` (ADDED: `/admin/users` subroute).

---

## Phase 10 — Validation

### Task 10.1 — Validate change artifacts

- [x] Run: `openspec validate --strict admin-users-management`
- [x] Run: `openspec status --change admin-users-management --json`
- [x] Assert: `isComplete: true`, all artifacts `done`.

---

## Task Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1.1–1.4 | Backend data layer (migration, schemas, repository, UoW) |
| 2 | 2.1–2.4 | Backend service layer (list, get, update data, update roles, deactivate) |
| 3 | 3.1–3.2 | Backend API layer (router, registration) |
| 4 | 4.1 | Frontend types |
| 5 | 5.1–5.4 | Frontend TanStack Query hooks |
| 6 | 6.1–6.6 | Frontend UI components + page |
| 7 | 7.1–7.2 | Frontend routing |
| 8 | 8.1–8.4 | Tests (unit + integration + concurrency) |
| 9 | 9.1 | Delta spec updates |
| 10 | 10.1 | Final validation |

**Total tasks**: 22 subtask groups, ~65 atomic checkboxes.
