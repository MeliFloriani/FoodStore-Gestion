# frontend-admin-users-page Specification

## Purpose
Frontend ADMIN users management page. Provides `AdminUsersPage` at `/admin/users` for ADMIN role only. Includes paginated table with server-side search and filters, modals for data editing, role editing, and logical deactivation. Introduced in Change 21 (admin-users-management).

## ADDED Requirements

### Requirement: Feature admin-users — TanStack Query hooks

`src/features/admin-users/api/` SHALL provide:

- `useUsersQuery(params: UsersQueryParams): QueryResult<Page<UsuarioAdminRead>>` — `GET /api/v1/admin/usuarios`. Query key: `['admin', 'users', params]`. `staleTime: 30_000`.
- `useUpdateUserMutation(): MutationResult` — `PUT /api/v1/admin/usuarios/{id}`. Invalidates `['admin', 'users']` on success.
- `useUpdateUserRolesMutation(): MutationResult` — `PUT /api/v1/admin/usuarios/{id}/roles`. Invalidates `['admin', 'users']` on success. Does NOT invalidate on `LAST_ADMIN_PROTECTED` error.
- `useDeactivateUserMutation(): MutationResult` — `PATCH /api/v1/admin/usuarios/{id}/estado`. Invalidates `['admin', 'users']` on success.

#### Scenario: useUsersQuery fetches paginated users
- **WHEN** `useUsersQuery({ page: 1, size: 20 })` is called from an ADMIN context
- **THEN** `GET /api/v1/admin/usuarios?page=1&size=20` is requested
- **THEN** returns `Page<UsuarioAdminRead>` with `items`, `total`, `page`, `size`, `pages`

#### Scenario: useUsersQuery with search and filters
- **WHEN** `useUsersQuery({ q: "juan", rol: "ADMIN", activo: true })` is called
- **THEN** request includes `?q=juan&rol=ADMIN&activo=true`

#### Scenario: useUpdateUserRolesMutation propagates LAST_ADMIN_PROTECTED error
- **WHEN** mutation is called and server returns HTTP 409 with `code="LAST_ADMIN_PROTECTED"`
- **THEN** the error is propagated to `onError` callback
- **THEN** the query cache is NOT invalidated (user list remains unchanged)

---

### Requirement: Feature admin-users — TypeScript types

`src/features/admin-users/types.ts` SHALL define:

- `RolRead`: `{ id: string; codigo: string; nombre: string }`
- `UsuarioAdminRead`: `{ id: string; email: string; nombre: string; apellido: string; created_at: string; deleted_at: string | null; roles: RolRead[] }`
- `UsersQueryParams`: `{ page?: number; size?: number; q?: string; rol?: string; activo?: boolean }`
- `UsuarioAdminUpdate`: `{ nombre?: string; apellido?: string }`
- `UsuarioRolesUpdate`: `{ roles: string[] }`
- `UsuarioEstadoUpdate`: `{ activo: boolean }`

No `any` types. Strict TypeScript.

---

### Requirement: UsersTable component

`src/features/admin-users/ui/UsersTable.tsx` SHALL:

- Accept `users: UsuarioAdminRead[]`, `isLoading: boolean`, and action handlers as props.
- Render a `<table>` with columns: Nombre + Apellido, Email, Roles, Estado, Fecha de registro, Acciones.
- Roles column: render one badge per role code (colored by role type).
- Estado column: green badge "Activo" when `deleted_at === null`, red/gray badge "Inactivo" otherwise.
- Acciones column: "Editar datos" button, "Editar roles" button, "Desactivar" button per row.
- "Desactivar" button is disabled/hidden when user is already inactive (`deleted_at IS NOT NULL`).
- When `isLoading=true`: render skeleton rows with `animate-pulse` (Tailwind).
- Horizontally scrollable on mobile.

#### Scenario: Table shows skeleton during loading
- **WHEN** `isLoading={true}` is passed
- **THEN** skeleton placeholder rows are rendered
- **THEN** no actual user data rows are visible

#### Scenario: Inactive user shows correct badge and disabled action
- **WHEN** a user with `deleted_at !== null` is in `users`
- **THEN** Estado badge shows "Inactivo"
- **THEN** "Desactivar" button is disabled or hidden

---

### Requirement: UserSearchBar component with debounce

`src/features/admin-users/ui/UserSearchBar.tsx` SHALL:

- Render a text input with placeholder "Buscar por nombre, apellido o email...".
- Apply 400ms debounce via `useDebounce` from `src/shared/hooks/`.
- Call `onChange` callback only when debounced value has 3+ characters OR is empty string.
- NOT call `onChange` for values with 1-2 characters.

#### Scenario: Search debounce fires after 400ms
- **WHEN** user types "juan" quickly
- **THEN** `onChange` is called ONCE after 400ms idle time (not on each keystroke)
- **THEN** `onChange` is called with `"juan"`

#### Scenario: Short query is not sent
- **WHEN** user types "ju" (2 characters)
- **THEN** `onChange` is NOT called

---

### Requirement: UserFilters component

`src/features/admin-users/ui/UserFilters.tsx` SHALL:

- Render a role select with options: "Todos los roles", "ADMIN", "STOCK", "PEDIDOS", "CLIENT".
- Render a status select with options: "Todos", "Activos", "Inactivos".
- Call respective `onChange` callbacks immediately on change (no debounce).

---

### Requirement: EditUserModal — data editing

`src/features/admin-users/ui/EditUserModal.tsx` SHALL:

- Render a modal with TanStack Form fields: `nombre` (max 80) and `apellido` (max 80).
- Show email as read-only text (not an editable input) with a note: "El email no es editable".
- Pre-populate form with current user values.
- Submit calls `useUpdateUserMutation`. Button shows loading state during mutation.
- On success: close modal, show success toast.
- On 422 validation error: show inline field error messages.

#### Scenario: Email shown as read-only in edit modal
- **WHEN** `EditUserModal` opens for a user
- **THEN** the email is displayed (not in an `<input>`) and cannot be changed
- **THEN** the form only submits `nombre` and/or `apellido`

---

### Requirement: EditUserRolesModal — role assignment

`src/features/admin-users/ui/EditUserRolesModal.tsx` SHALL:

- Render a modal with a checkbox group for 4 roles: ADMIN, STOCK, PEDIDOS, CLIENT.
- Pre-check currently assigned roles.
- Require at least 1 role selected (client-side validation).
- Submit calls `useUpdateUserRolesMutation`.
- On HTTP 409 `LAST_ADMIN_PROTECTED`: show inline error message "No es posible quitar el rol ADMIN al único administrador del sistema." Do NOT close modal.
- On success: close modal, show success toast.

#### Scenario: LAST_ADMIN_PROTECTED error shown inline
- **WHEN** mutation returns HTTP 409 `code="LAST_ADMIN_PROTECTED"`
- **THEN** modal remains open
- **THEN** error message "No es posible quitar el rol ADMIN al único administrador del sistema." is visible

#### Scenario: At least one role required
- **WHEN** user unchecks all roles and attempts to submit
- **THEN** form shows validation error "Debe seleccionar al menos un rol"
- **THEN** mutation is NOT called

---

### Requirement: DeactivateUserModal — destructive confirmation

`src/features/admin-users/ui/DeactivateUserModal.tsx` SHALL:

- Render a destructive confirmation modal.
- Show the target user's name and email.
- Show warning text: "Esta acción cerrará todas las sesiones activas de [nombre] e impedirá su acceso al sistema. Los pedidos históricos no serán afectados."
- Render "Cancelar" (secondary) and "Desactivar" (danger/destructive) buttons.
- On confirm: call `useDeactivateUserMutation({ id, activo: false })`.
- On HTTP 409 `LAST_ADMIN_PROTECTED`: show error inline — "No se puede desactivar al último administrador del sistema."
- On success: close modal, show success toast.

#### Scenario: Warning text clearly explains consequences
- **WHEN** `DeactivateUserModal` renders
- **THEN** warning text about session invalidation and data preservation is visible
- **THEN** the target user's name is included in the warning

#### Scenario: LAST_ADMIN_PROTECTED blocks deactivation
- **WHEN** mutation returns HTTP 409 `code="LAST_ADMIN_PROTECTED"`
- **THEN** modal remains open
- **THEN** error message about last ADMIN is displayed

---

### Requirement: AdminUsersPage

`src/pages/AdminUsersPage/index.tsx` SHALL:

- Compose: page title "Gestión de Usuarios", `UserSearchBar`, `UserFilters`, `UsersTable`, pagination controls, and the 3 modals.
- Manage local state: `page`, `size=20`, `q` (raw), `rol`, `activo`, `selectedUser: UsuarioAdminRead | null`, `openModal: 'edit' | 'roles' | 'deactivate' | null`.
- Pass debounced `q` (≥3 chars or empty) to `useUsersQuery`.
- Pagination controls: Previous / Next buttons and current page indicator. Disable "Previous" on page 1, disable "Next" on last page.
- Empty state when `items.length === 0 && !isLoading`: "No se encontraron usuarios con los filtros actuales."
- All 3 modals lazy-imported via `React.lazy` for code splitting.
- RoleGuard enforcement inherited from parent `/admin/*` route (no additional guard in page).

#### Scenario: Search updates user list
- **WHEN** user types "garcia" in search bar and 400ms pass
- **THEN** `useUsersQuery` is called with `q="garcia"`
- **THEN** `UsersTable` re-renders with filtered results

#### Scenario: Pagination controls work
- **WHEN** `total=45`, `size=20`, `page=1`
- **THEN** "Next" button is enabled
- **THEN** `pages=3` is displayed
- **WHEN** user clicks "Next"
- **THEN** `page` becomes 2 and `useUsersQuery` is called with `page=2`

#### Scenario: Empty state displayed
- **WHEN** `useUsersQuery` returns `items: []` and `isLoading: false`
- **THEN** empty state message "No se encontraron usuarios..." is visible

#### Scenario: ADMIN access only
- **WHEN** a CLIENT user navigates to `/admin/users`
- **THEN** `RoleGuard roles={['ADMIN']}` from parent route redirects to `/403`
- **THEN** `AdminUsersPage` component is NOT rendered (lazy chunk not downloaded)

---

### Requirement: Route /admin/users registered in router

`src/app/router/index.tsx` (or equivalent) SHALL:

- Within the `/admin/*` `RoleGuard roles={['ADMIN']}` subtree, add a subroute:
  ```
  Route path="users"
    element=Suspense(fallback=<PageSpinner />)
      AdminUsersPage (React.lazy)
  ```
- `RoleGuard` is the outer element (parent); `Suspense` is inner (child) — guard-before-Suspense invariant from `frontend-route-guards` spec.
- `AdminUsersPage` is lazy-loaded: `React.lazy(() => import('@/pages/AdminUsersPage'))`.

#### Scenario: Authorized ADMIN reaches /admin/users
- **WHEN** authenticated ADMIN navigates to `/admin/users`
- **THEN** `RoleGuard` passes (reason: 'ok')
- **THEN** `Suspense` triggers lazy import of `AdminUsersPage`
- **THEN** page renders with user management UI

#### Scenario: CLIENT user cannot access /admin/users chunk
- **WHEN** CLIENT user navigates to `/admin/users`
- **THEN** `RoleGuard` redirects to `/403` before `Suspense` evaluates
- **THEN** `AdminUsersPage` lazy chunk is NOT downloaded
