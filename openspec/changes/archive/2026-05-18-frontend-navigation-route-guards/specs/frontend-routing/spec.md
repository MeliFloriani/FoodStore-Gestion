## MODIFIED Requirements

### Requirement: RoleGuard stub
`src/app/router/guards/RoleGuard.tsx` SHALL accept a `roles: string[]` prop and enforce role access by delegating to `useRequireRoles(roles)`. The component SHALL NOT render `<Outlet />` unconditionally. Enforcement behavior:
- When `useRequireRoles` returns `reason: 'loading'` → render a full-screen spinner.
- When `useRequireRoles` returns `reason: 'unauthenticated'` → render `<Navigate to="/login" state={{ from: location }} replace />`.
- When `useRequireRoles` returns `reason: 'forbidden'` → render `<Navigate to="/403" state={{ from: location }} replace />`.
- When `useRequireRoles` returns `reason: 'ok'` → render `<Outlet />`.

The component interface (`roles: string[]` prop) is unchanged from the stub — it is API-compatible. The RoleGuard SHALL be placed OUTSIDE (wrapping) any `React.Suspense` boundary to enforce the guard-before-Suspense invariant (see `frontend-route-guards` spec).

#### Scenario: RoleGuard enforces role — wrong role redirects to 403
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to a route with `RoleGuard roles={['ADMIN']}`
- **THEN** the user is redirected to `/403` with `state.from` set to the original location

#### Scenario: RoleGuard enforces role — correct role allows access
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to a route with `RoleGuard roles={['ADMIN']}`
- **THEN** `<Outlet />` is rendered

#### Scenario: RoleGuard redirects unauthenticated to login
- **WHEN** an unauthenticated user navigates to a route with `RoleGuard roles={['ADMIN']}`
- **THEN** the user is redirected to `/login` with `state.from` set to the original location

#### Scenario: RoleGuard shows loading on idle status
- **WHEN** `authStore.status` is `'idle'` and the user navigates to a role-guarded route
- **THEN** a full-screen spinner is rendered (no redirect)

---

## MODIFIED Requirements

### Requirement: Placeholder page routes defined for all top-level routes
The router SHALL define routes organized in three top-level branches under `RootLayout`:

**Public branch** (wrapped by `PublicLayout` — no auth required):
- `/` → redirect to `/catalog`
- `/catalog` → `CatalogPage` (lazy)
- `/401` → `UnauthorizedPage` (lazy)
- `/403` → `ForbiddenPage` (lazy)
- `/404` → `NotFoundPage` (lazy)
- `*` → redirect to `/404` (catch-all)

**Auth branch** (wrapped by `AuthLayout` — redirects authenticated users):
- `/login` → `LoginPage` (lazy)
- `/register` → `RegisterPage` (lazy)

**Private branch** (wrapped by `AppLayout → ProtectedRoute` — requires authentication):
- `/home` → `HomePage` (lazy)
- `/cart` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CartPage` (lazy)
- `/checkout` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CheckoutPage` (lazy)
- `/orders` → `RoleGuard roles={['CLIENT','ADMIN']}` → `OrdersPage` (lazy)
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → ProfilePage (placeholder, implemented in Change 13)
- `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → AddressesPage (placeholder, implemented in Change 14)
- `/stock/*` → `RoleGuard roles={['STOCK','ADMIN']}` → stock subtree placeholder (lazy)
- `/pedidos-panel/*` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → pedidos subtree placeholder (lazy)
- `/admin/*` → `RoleGuard roles={['ADMIN']}` → `AdminPage` (lazy)

`ProtectedRoute` behavior is unchanged: `status='idle'` → full-screen spinner; `status='authenticated'` → `<Outlet />`; `status='unauthenticated'` → `<Navigate to="/login" replace />`.

#### Scenario: Unauthenticated user accesses /catalog
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/catalog`
- **THEN** the `CatalogPage` placeholder renders without redirect (public route)

#### Scenario: Unauthenticated user is blocked from /stock
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/stock/products`
- **THEN** the user is redirected to `/login`

#### Scenario: CLIENT user is forbidden from /stock
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/stock/products`
- **THEN** the user is redirected to `/403`

#### Scenario: Catch-all redirects to 404
- **WHEN** a user navigates to a path that matches no registered route
- **THEN** the user is redirected to `/404`

#### Scenario: All placeholder routes render without crashing
- **WHEN** any registered route is navigated to with appropriate auth/role state
- **THEN** the page renders without a runtime error or uncaught exception

## Acceptance

- `RoleGuard` with `roles=['ADMIN']` and a CLIENT user SHALL redirect to `/403`.
- `RoleGuard` with `roles=['ADMIN']` and an ADMIN user SHALL render `<Outlet />`.
- `RoleGuard` SHALL render a spinner when `authStore.status` is `'idle'`.
- `/catalog` SHALL be accessible without authentication.
- `/stock/*` and `/pedidos-panel/*` SHALL be blocked for unauthenticated and wrong-role users.
- Error routes `/401`, `/403`, `/404` SHALL be accessible without authentication.
- The catch-all `*` route SHALL redirect to `/404`.
