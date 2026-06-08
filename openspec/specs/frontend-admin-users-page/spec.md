# frontend-admin-users-page Specification

## Purpose
Frontend capability for the admin users management panel. Provides a paginated, filterable table of all users with search, role editing (with last-admin guard feedback), and logical deactivation. Introduced in Change 21 (admin-users-management).

## Files

| File | Description |
|------|-------------|
| `frontend/src/features/admin-users/types.ts` | TypeScript types: RolRead, UsuarioAdminRead, UsersQueryParams, UsuarioAdminUpdate, UsuarioRolesUpdate, UsuarioEstadoUpdate, isUserActive helper, VALID_ROLES const |
| `frontend/src/features/admin-users/api/useUsersQuery.ts` | TanStack Query hook: GET /api/v1/admin/usuarios with pagination + filters |
| `frontend/src/features/admin-users/api/useUpdateUserMutation.ts` | TanStack Mutation: PUT /api/v1/admin/usuarios/{id} |
| `frontend/src/features/admin-users/api/useUpdateUserRolesMutation.ts` | TanStack Mutation: PUT /api/v1/admin/usuarios/{id}/roles |
| `frontend/src/features/admin-users/api/useDeactivateUserMutation.ts` | TanStack Mutation: PATCH /api/v1/admin/usuarios/{id}/estado |
| `frontend/src/features/admin-users/ui/UsersTable.tsx` | Table component with skeleton loader, role badges, action buttons |
| `frontend/src/features/admin-users/ui/UserSearchBar.tsx` | Debounced search input (400ms, min 3 chars) |
| `frontend/src/features/admin-users/ui/UserFilters.tsx` | Rol and estado filter selects |
| `frontend/src/features/admin-users/ui/EditUserModal.tsx` | TanStack Form modal for nombre/apellido editing (email read-only per D-01) |
| `frontend/src/features/admin-users/ui/EditUserRolesModal.tsx` | Checkbox modal for role assignment with last-admin guard feedback |
| `frontend/src/features/admin-users/ui/DeactivateUserModal.tsx` | Confirmation modal for user deactivation (no Reactivar button per OQ-02) |
| `frontend/src/pages/AdminUsersPage/index.tsx` | Page composition: search + filters + table + pagination + modals |
| `frontend/src/app/router/routes.tsx` | Route /admin/users registered under RoleGuard roles={['ADMIN']} |

## Requirements

### Requirement: TypeScript types for admin user operations

`frontend/src/features/admin-users/types.ts` SHALL define:

- `RolRead` interface: `{ id: string; codigo: string; nombre: string }`.
- `UsuarioAdminRead` interface: `{ id: string; email: string; nombre: string; apellido: string; created_at: string; deleted_at: string | null; roles: RolRead[] }`. **SHALL NOT** include `password_hash`.
- `UsersQueryParams` interface: `{ page?: number; size?: number; q?: string; rol?: string; activo?: boolean }`.
- `UsuarioAdminUpdate` interface: `{ nombre?: string; apellido?: string }`. **No `email` field** (D-01).
- `UsuarioRolesUpdate` interface: `{ roles: string[] }`.
- `UsuarioEstadoUpdate` interface: `{ activo: boolean }`.
- `isUserActive(user: UsuarioAdminRead): boolean` helper — returns `user.deleted_at === null`.
- `VALID_ROLES: readonly string[]` const — `["ADMIN", "STOCK", "PEDIDOS", "CLIENT"]`.

#### Scenario: isUserActive returns true for active user
- **WHEN** `isUserActive({ deleted_at: null, ...rest })` is called
- **THEN** it returns `true`

#### Scenario: isUserActive returns false for inactive user
- **WHEN** `isUserActive({ deleted_at: "2024-01-01T00:00:00Z", ...rest })` is called
- **THEN** it returns `false`

---

### Requirement: useUsersQuery hook

`frontend/src/features/admin-users/api/useUsersQuery.ts` SHALL implement `useUsersQuery(params: UsersQueryParams)`:

- Query key: `['admin', 'users', effectiveParams]`.
- Calls `GET /api/v1/admin/usuarios` with params as query string.
- Returns `Page<UsuarioAdminRead>` (paginated result).
- `staleTime: 30_000` (30 seconds).
- On `q` param: only sends if `q.length >= 3` or `q === ""` (debounce handled in UI).

#### Scenario: Query key includes params
- **WHEN** `useUsersQuery({ page: 2, rol: 'ADMIN' })` is called
- **THEN** the query key is `['admin', 'users', { page: 2, rol: 'ADMIN' }]`

---

### Requirement: useUpdateUserMutation hook

`frontend/src/features/admin-users/api/useUpdateUserMutation.ts` SHALL call `PUT /api/v1/admin/usuarios/{id}` with `UsuarioAdminUpdate` body and invalidate `['admin', 'users']` on success.

#### Scenario: Invalidates users cache on success
- **WHEN** the mutation completes successfully for `PUT /api/v1/admin/usuarios/{id}`
- **THEN** the query key `['admin', 'users']` is invalidated

---

### Requirement: useUpdateUserRolesMutation hook

`frontend/src/features/admin-users/api/useUpdateUserRolesMutation.ts` SHALL call `PUT /api/v1/admin/usuarios/{id}/roles` with `UsuarioRolesUpdate` body.

- On success: invalidate `['admin', 'users']`.
- On error with `code="LAST_ADMIN_PROTECTED"`: **do NOT** invalidate cache — propagate error for UI to handle inline.
- Exports `getErrorCode(error: unknown): string | undefined` helper.

#### Scenario: Invalidates users cache on success
- **WHEN** the roles mutation completes successfully
- **THEN** the query key `['admin', 'users']` is invalidated

#### Scenario: Does not invalidate cache on LAST_ADMIN_PROTECTED
- **WHEN** the roles mutation fails with an error whose `code` equals `"LAST_ADMIN_PROTECTED"`
- **THEN** the query key `['admin', 'users']` is NOT invalidated
- **THEN** the error is propagated to the caller for inline UI handling

---

### Requirement: useDeactivateUserMutation hook

`frontend/src/features/admin-users/api/useDeactivateUserMutation.ts` SHALL call `PATCH /api/v1/admin/usuarios/{id}/estado` with `UsuarioEstadoUpdate`.

- On success: invalidate `['admin', 'users']`.
- On error with `code="LAST_ADMIN_PROTECTED"`: propagate error for UI to show specific inline message.

#### Scenario: Invalidates users cache on success
- **WHEN** the deactivate mutation completes successfully
- **THEN** the query key `['admin', 'users']` is invalidated

#### Scenario: Propagates LAST_ADMIN_PROTECTED error
- **WHEN** the deactivate mutation fails with an error whose `code` equals `"LAST_ADMIN_PROTECTED"`
- **THEN** the error is propagated to the caller (not swallowed) so the UI can show the inline message

---

### Requirement: UsersTable component

`frontend/src/features/admin-users/ui/UsersTable.tsx` SHALL:

- Accept props: `users: UsuarioAdminRead[]`, `isLoading: boolean`, and action callbacks (`onEdit`, `onEditRoles`, `onDeactivate`).
- Render columns: Nombre + Apellido, Email, Roles (badge per role), Estado (badge), Fecha registro, Acciones.
- Show skeleton rows with `animate-pulse` when `isLoading=true`.
- Role badges: colored by type (ADMIN = red/dark, STOCK = blue, PEDIDOS = yellow/orange, CLIENT = green).
- Estado badge: green for Activo, red/gray for Inactivo.
- Actions per row: "Editar datos", "Editar roles", "Desactivar" (hidden for already-inactive users — OQ-02 compliant, no Reactivar button).
- Responsive: horizontal scroll on mobile.

#### Scenario: Desactivar button hidden for inactive user
- **WHEN** a user row has `deleted_at` not null (inactive user)
- **THEN** no "Desactivar" button is rendered for that row
- **THEN** no "Reactivar" button is rendered for that row (OQ-02 CLOSED)

---

### Requirement: UserSearchBar component

`frontend/src/features/admin-users/ui/UserSearchBar.tsx` SHALL:

- Render an input with placeholder `"Buscar por nombre, apellido o email..."`.
- Debounce `onChange` callback by 400ms using `useDebounce` from `src/shared/hooks/`.
- Only fire `onChange` if debounced value has `length >= 3` or is empty string `""`.
- Accept `onChange: (value: string) => void` prop.

#### Scenario: Fires onChange only on 3+ chars or empty
- **WHEN** value is `"ab"` and 400ms passes
- **THEN** `onChange` is NOT called with `"ab"`
- **WHEN** value is `"abc"` and 400ms passes
- **THEN** `onChange` IS called with `"abc"`
- **WHEN** value is `""` and 400ms passes
- **THEN** `onChange` IS called with `""`

---

### Requirement: UserFilters component

`frontend/src/features/admin-users/ui/UserFilters.tsx` SHALL:

- Render a role select: options `"Todos"`, `"ADMIN"`, `"STOCK"`, `"PEDIDOS"`, `"CLIENT"`.
- Render an estado select: options `"Todos"`, `"Activos"`, `"Inactivos"`.
- Fire onChange callbacks immediately (no debounce).

#### Scenario: Role select exposes all valid roles plus Todos
- **WHEN** `UserFilters` is rendered
- **THEN** the role select contains the options `"Todos"`, `"ADMIN"`, `"STOCK"`, `"PEDIDOS"`, `"CLIENT"`
- **THEN** the estado select contains the options `"Todos"`, `"Activos"`, `"Inactivos"`

#### Scenario: onChange fires immediately without debounce
- **WHEN** the user selects `"Inactivos"` in the estado select
- **THEN** the `onChange` callback is invoked synchronously with the new value (no debounce delay)

---

### Requirement: EditUserModal component

`frontend/src/features/admin-users/ui/EditUserModal.tsx` SHALL:

- Use TanStack Form for form state management.
- Expose fields: `nombre` (max 80 chars), `apellido` (max 80 chars).
- Show `email` as a disabled read-only input (D-01 — email is immutable).
- Pre-populate all fields with the current user's data.
- Call `useUpdateUserMutation` on submit. Show loading state on submit button.
- Close modal on success.
- Render as accessible `role="dialog"`.

#### Scenario: Email shown as disabled
- **WHEN** `EditUserModal` is rendered with a user
- **THEN** the email input is `disabled` (not editable)
- **THEN** the email value is displayed

---

### Requirement: EditUserRolesModal component

`frontend/src/features/admin-users/ui/EditUserRolesModal.tsx` SHALL:

- Show checkboxes for all 4 roles: ADMIN, STOCK, PEDIDOS, CLIENT.
- Pre-check the user's currently assigned roles.
- Require at least 1 role selected (client-side validation before submit).
- Show validation error `"Debe seleccionar al menos un rol"` when submitted with no roles.
- Call `useUpdateUserRolesMutation` on submit.
- On error `LAST_ADMIN_PROTECTED`: show inline message `"No es posible quitar el rol ADMIN al único administrador del sistema."`.
- Close modal on success.
- Render as accessible `role="dialog"`.

#### Scenario: Pre-checks current roles
- **WHEN** user has roles `[ADMIN, CLIENT]`
- **THEN** ADMIN checkbox is checked
- **THEN** CLIENT checkbox is checked
- **THEN** STOCK checkbox is not checked
- **THEN** PEDIDOS checkbox is not checked

---

### Requirement: DeactivateUserModal component

`frontend/src/features/admin-users/ui/DeactivateUserModal.tsx` SHALL:

- Show the user's full name (`nombre + " " + apellido`) and email.
- Show warning text: `"Esta acción cerrará todas las sesiones activas de [nombre] e impedirá su acceso al sistema. Los pedidos históricos no serán afectados."`
- Render "Cancelar" (secondary) and "Desactivar" (destructive) buttons.
- **SHALL NOT** render a "Reactivar" button (OQ-02 CLOSED — backend supports it, frontend does not expose it in Change 21).
- Call `useDeactivateUserMutation` with `{ activo: false }` on confirm.
- On error `LAST_ADMIN_PROTECTED`: show inline message `"No se puede desactivar al último administrador del sistema."`.
- Close modal on success.
- Render as accessible `role="dialog"`.

#### Scenario: No Reactivar button (OQ-02 CLOSED)
- **WHEN** `DeactivateUserModal` is rendered
- **THEN** no button with text "Reactivar" exists in the DOM
- **THEN** no element with text matching `/reactivar/i` exists

---

### Requirement: AdminUsersPage composition

`frontend/src/pages/AdminUsersPage/index.tsx` SHALL:

- Title: `"Gestión de Usuarios"`.
- Compose: `UserSearchBar` + `UserFilters` + `UsersTable` + pagination controls + lazy-loaded modals.
- Local state: `page` (default 1), `size` (fixed 20), `q`, `rol`, `activo`, `selectedUser`, `openModal` (`'edit' | 'roles' | 'deactivate' | null`).
- Call `useUsersQuery({ page, size, q, rol, activo })`.
- Pagination: Previous/Next buttons + page indicator. Uses `total` and `pages` from response.
- Lazy import modals (only loaded when opened).
- Empty state: `"No se encontraron usuarios con los filtros actuales."` when `items.length === 0 && !isLoading`.

#### Scenario: Renders title and core child components
- **WHEN** `AdminUsersPage` is mounted for an authenticated ADMIN user
- **THEN** the heading `"Gestión de Usuarios"` is rendered
- **THEN** `UserSearchBar`, `UserFilters`, and `UsersTable` are present in the rendered tree

#### Scenario: Empty state shown when no users match filters
- **WHEN** `useUsersQuery` resolves with `items.length === 0` and `isLoading === false`
- **THEN** the text `"No se encontraron usuarios con los filtros actuales."` is rendered

---

### Requirement: Route /admin/users registered

`frontend/src/app/router/routes.tsx` SHALL register `/admin/users` under the `RoleGuard roles={['ADMIN']}` subtree:

- Lazy import: `const AdminUsersPage = React.lazy(() => import('@/pages/AdminUsersPage'))`.
- Route element wraps `AdminUsersPage` in `<Suspense fallback={<PageLoader />}>`.
- `RoleGuard` is the outer element (parent); `Suspense` is inner (child) — guard-before-Suspense invariant.

#### Scenario: ADMIN navigates to /admin/users
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/admin/users`
- **THEN** `AdminUsersPage` renders
- **THEN** the users table is visible

#### Scenario: CLIENT is forbidden from /admin/users
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/admin/users`
- **THEN** `RoleGuard` redirects to `/403`

---

## Design Decisions

| ID | Decision |
|----|----------|
| D-01 | Email immutable: email shown as disabled read-only in EditUserModal, not included in UsuarioAdminUpdate type |
| D-02 | Roles update uses PUT replace (full set semantics) |
| D-05 | Backend supports reactivation (activo=true), frontend does NOT expose it in Change 21 (OQ-02 CLOSED) |
| OQ-02 | No "Reactivar" button in DeactivateUserModal or UsersTable — CLOSED, not deferred |
