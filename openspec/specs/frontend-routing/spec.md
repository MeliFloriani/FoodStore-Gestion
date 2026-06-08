# frontend-routing Specification

## Purpose
Defines the client-side route tree for the Food Store frontend application, covering public, auth, and private branches with role guards. All authenticated routes use `ProtectedRoute`; role-restricted routes use `RoleGuard`.
## Requirements
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

### Requirement: /admin route subtree expanded with nested metrics and management routes
The router SHALL expand the existing `/admin/*` catch-all under `RoleGuard roles={['ADMIN']}` to define the following nested routes:

```
/admin                  → redirect to /admin/metricas
/admin/metricas         → AdminDashboardPage (MetricasTab) (lazy)
/admin/pedidos          → AdminDashboardPage (PedidosTab) (lazy) — embeds OrdersManagementPanel
/admin/usuarios         → AdminUsersPage (lazy) — existing, from Change 21
/admin/productos        → AdminDashboardPage (ProductosTab) (lazy)
/admin/stock            → AdminDashboardPage (StockTab) (lazy)
```

All routes inherit the `RoleGuard roles={['ADMIN']}` from the parent `/admin` route defined in Change 08. No additional guard is needed for sub-routes.

#### Scenario: /admin redirects to /admin/metricas
- **GIVEN** an authenticated ADMIN user navigates to `/admin`
- **WHEN** the route resolves
- **THEN** the user is redirected to `/admin/metricas`

#### Scenario: /admin/metricas renders AdminDashboardPage MetricasTab
- **GIVEN** an authenticated ADMIN user
- **WHEN** the user navigates to `/admin/metricas`
- **THEN** `AdminDashboardPage` is rendered with the Métricas tab active

#### Scenario: /admin/pedidos renders PedidosTab
- **GIVEN** an authenticated ADMIN user
- **WHEN** the user navigates to `/admin/pedidos`
- **THEN** `OrdersManagementPanel` is rendered within the admin layout

#### Scenario: Non-ADMIN user cannot access /admin/* routes
- **GIVEN** an authenticated CLIENT user
- **WHEN** the user navigates to `/admin/metricas`
- **THEN** the user is redirected to `/403`

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
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → `ProfilePage` (lazy, from `src/pages/ProfilePage/` — composes `EditProfileForm` and `ChangePasswordForm` from `src/features/profile/`)
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

#### Scenario: CLIENT navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders (not a placeholder)
- **THEN** the page shows the user's profile data and the two profile management forms (`EditProfileForm`, `ChangePasswordForm`)

#### Scenario: ADMIN navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders
- **THEN** both profile management forms are visible

#### Scenario: Unauthenticated user is still blocked from /profile
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/profile`
- **THEN** `ProtectedRoute` redirects to `/login` (behavior unchanged from Change 08)

## Acceptance

- `RoleGuard` with `roles=['ADMIN']` and a CLIENT user SHALL redirect to `/403`.
- `RoleGuard` with `roles=['ADMIN']` and an ADMIN user SHALL render `<Outlet />`.
- `RoleGuard` SHALL render a spinner when `authStore.status` is `'idle'`.
- `/catalog` SHALL be accessible without authentication.
- `/stock/*` and `/pedidos-panel/*` SHALL be blocked for unauthenticated and wrong-role users.
- Error routes `/401`, `/403`, `/404` SHALL be accessible without authentication.
- The catch-all `*` route SHALL redirect to `/404`.

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
- `/checkout/review` → `RoleGuard roles={['CLIENT','ADMIN']}` → `PreCheckoutReviewPage` (lazy, from `src/pages/PreCheckoutReviewPage/` — composes `PreCheckoutReview` from `src/features/pre-checkout-validation/`)
- `/orders` → `RoleGuard roles={['CLIENT','ADMIN']}` → `OrdersPage` (lazy)
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → `ProfilePage` (lazy, from `src/pages/ProfilePage/` — composes `EditProfileForm` and `ChangePasswordForm` from `src/features/profile/`)
- `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → `AddressesPage` (lazy, implemented in Change 14 — real page, not placeholder)
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

#### Scenario: CLIENT navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders (not a placeholder)
- **THEN** the page shows the user's profile data and the two profile management forms (`EditProfileForm`, `ChangePasswordForm`)

#### Scenario: ADMIN navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders
- **THEN** both profile management forms are visible

#### Scenario: CLIENT navigates to /addresses and sees AddressesPage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/addresses`
- **THEN** the real `AddressesPage` component renders (not a placeholder)
- **THEN** the page displays the user's address list (or empty state if no addresses)

#### Scenario: Unauthenticated user is blocked from /addresses
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/addresses`
- **THEN** the user is redirected to `/login`

#### Scenario: STOCK user is forbidden from /addresses
- **WHEN** an authenticated user with roles `['STOCK']` (without CLIENT or ADMIN) navigates to `/addresses`
- **THEN** the user is redirected to `/403`

#### Scenario: CLIENT navigates to /checkout/review and sees PreCheckoutReviewPage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/checkout/review`
- **THEN** the real `PreCheckoutReviewPage` component renders
- **THEN** the page triggers the pre-checkout validation and shows the review UI

#### Scenario: Unauthenticated user is blocked from /checkout/review
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/checkout/review`
- **THEN** `ProtectedRoute` redirects to `/login` with `state.from` preserved

#### Scenario: STOCK user is forbidden from /checkout/review
- **WHEN** an authenticated user with roles `['STOCK']` (without CLIENT or ADMIN) navigates to `/checkout/review`
- **THEN** `RoleGuard` redirects to `/403`

#### Scenario: /checkout/review does not conflict with /checkout
- **WHEN** routes are resolved
- **THEN** `/checkout/review` routes to `PreCheckoutReviewPage` (not `CheckoutPage`)
- **THEN** `/checkout` still routes to `CheckoutPage`

## ADDED Requirements (Change 20: orders-visualization)

### Requirement: Rutas de visualización de pedidos en la rama privada

El router de la aplicación SHALL agregar las siguientes rutas dentro de la rama privada (bajo `AppLayout → ProtectedRoute`):

```
/orders          → RoleGuard roles={['CLIENT']} → OrdersPage (lazy)
/orders/:id      → RoleGuard roles={['CLIENT']} → OrderDetailPage (lazy)
/order-confirmation/:id → RoleGuard roles={['CLIENT']} → OrderConfirmationPage (lazy)
```

Estas rutas coexisten con `/orders` ya registrado como placeholder en Changes 08/13 (mismo path, se reemplaza el componente placeholder con la implementación real).

> IMPORTANTE: `/orders/:id` debe declararse DESPUÉS de `/orders` para evitar conflictos. React Router 6+ resuelve correctamente rutas estáticas antes de dinámicas dentro del mismo padre.

#### Scenario: CLIENT navega a /orders y ve su lista de pedidos
- **WHEN** un usuario CLIENT navega a `/orders`
- **THEN** `OrdersPage` real renderiza (no el placeholder)
- **THEN** `GET /api/v1/pedidos` es llamado con el token del CLIENT

#### Scenario: CLIENT navega a /orders/:id y ve el detalle
- **WHEN** un usuario CLIENT navega a `/orders/some-uuid`
- **THEN** `OrderDetailPage` renderiza con `pedidoId = "some-uuid"`
- **THEN** `GET /api/v1/pedidos/some-uuid` es llamado

#### Scenario: /orders/:id no colisiona con /orders
- **WHEN** se resuelven las rutas
- **THEN** `/orders` route to `OrdersPage`
- **THEN** `/orders/some-uuid` routes to `OrderDetailPage`
- **THEN** no hay ambigüedad

#### Scenario: /order-confirmation/:id es accesible post-creación de pedido
- **WHEN** `useCreateOrder` navega a `/order-confirmation/{pedidoId}` tras HTTP 201
- **THEN** `OrderConfirmationPage` renderiza
- **THEN** el `:id` está disponible via `useParams`

#### Scenario: Roles no-CLIENT rechazados en /orders
- **WHEN** un usuario con rol STOCK navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`
- **WHEN** un usuario con rol PEDIDOS navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`
- **WHEN** un usuario con rol ADMIN (sin rol CLIENT) navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`

---

## MODIFIED Requirements (Change 20: orders-visualization)

### Requirement: Placeholder page routes defined for all top-level routes

El router SHALL actualizar la configuración de la rama privada para conectar `/pedidos-panel/*` con el panel real. El árbol de rutas privadas es ahora:

**Private branch** (wrapped by `AppLayout → ProtectedRoute` — requires authentication):
- `/home` → `HomePage` (lazy)
- `/cart` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CartPage` (lazy)
- `/checkout` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CheckoutPage` (lazy)
- `/checkout/review` → `RoleGuard roles={['CLIENT','ADMIN']}` → `PreCheckoutReviewPage` (lazy)
- `/checkout/return` → `CheckoutReturnPage` (lazy — Change 19, sin RoleGuard adicional, auth via ProtectedRoute)
- `/orders` → `RoleGuard roles={['CLIENT']}` → `OrdersPage` (lazy — **implementación real, Change 20**)
- `/orders/:id` → `RoleGuard roles={['CLIENT']}` → `OrderDetailPage` (lazy — **Change 20**)
- `/order-confirmation/:id` → `RoleGuard roles={['CLIENT']}` → `OrderConfirmationPage` (lazy — **Change 20**)
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → `ProfilePage` (lazy)
- `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → `AddressesPage` (lazy)
- `/stock/*` → `RoleGuard roles={['STOCK','ADMIN']}` → stock subtree placeholder (lazy)
- `/pedidos-panel` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → `PedidosPanelPage` (lazy — **implementación real, Change 20**)
- `/pedidos-panel/:id` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → `PedidosPanelDetailPage` (lazy — **Change 20**)
- `/admin/*` → `RoleGuard roles={['ADMIN']}` → `AdminPage` (lazy)

#### Scenario: PEDIDOS navega a /pedidos-panel y ve el panel real
- **WHEN** un usuario PEDIDOS navega a `/pedidos-panel`
- **THEN** `PedidosPanelPage` real renderiza (no el placeholder)
- **THEN** `GET /api/v1/pedidos` es llamado con el token del PEDIDOS

#### Scenario: PEDIDOS navega a /pedidos-panel/:id y ve el detalle de gestión
- **WHEN** un usuario PEDIDOS navega a `/pedidos-panel/some-uuid`
- **THEN** `PedidosPanelDetailPage` renderiza con el `pedidoId` correcto

#### Scenario: /pedidos-panel/:id no colisiona con /pedidos-panel
- **WHEN** se resuelven las rutas
- **THEN** `/pedidos-panel` routes to `PedidosPanelPage`
- **THEN** `/pedidos-panel/some-uuid` routes to `PedidosPanelDetailPage`

#### Scenario: Rutas previas no afectadas
- **WHEN** se agregan las nuevas rutas
- **THEN** `/checkout/return` (Change 19) sigue operativo
- **THEN** `/checkout/review` (Change 16) sigue operativo
- **THEN** `/addresses` (Change 14) sigue operativo
- **THEN** todas las rutas auth y públicas permanecen sin cambios

## ADDED Requirements (Change 21: admin-users-management)

### Requirement: /admin/users subroute for admin users management panel

The router SHALL add `/admin/users` as a subroute within the ADMIN-guarded subtree (`/admin/*` branch):

```
/admin/users  →  RoleGuard roles={['ADMIN']}  →  Suspense  →  AdminUsersPage (lazy)
```

- Lazy import: `const AdminUsersPage = React.lazy(() => import('@/pages/AdminUsersPage'))`.
- `RoleGuard roles={['ADMIN']}` is the outer element — guard-before-Suspense invariant is maintained.
- `<Suspense fallback={<PageLoader />}>` wraps `<AdminUsersPage />` as the inner element.
- Route is registered at path `users` (or `/admin/users` absolute) inside the existing `/admin/*` `RoleGuard` parent.

The updated private branch includes:
- `/admin/users` → `RoleGuard roles={['ADMIN']}` → `AdminUsersPage` (lazy — **Change 21**)

All other routes are unchanged from Change 20.

#### Scenario: ADMIN navigates to /admin/users and sees AdminUsersPage
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/admin/users`
- **THEN** `AdminUsersPage` renders (not a placeholder)
- **THEN** `GET /api/v1/admin/usuarios` is called

#### Scenario: CLIENT is forbidden from /admin/users
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/admin/users`
- **THEN** `RoleGuard` redirects to `/403`

#### Scenario: Unauthenticated user is blocked from /admin/users
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/admin/users`
- **THEN** `ProtectedRoute` redirects to `/login`

#### Scenario: /admin/users does not conflict with other /admin/* routes
- **WHEN** routes are resolved
- **THEN** `/admin/users` routes to `AdminUsersPage`
- **THEN** all other `/admin/*` routes are unaffected

#### Scenario: Guard-before-Suspense invariant holds for /admin/users
- **WHEN** the route tree is inspected
- **THEN** `RoleGuard` is the parent element (outer)
- **THEN** `React.Suspense` is the child element (inner, wrapping the lazy page)
- **THEN** role enforcement occurs before any async chunk load
