## ADDED Requirements

### Requirement: createBrowserRouter with lazy-loaded routes
`src/app/router/routes.tsx` SHALL configure the application router using `createBrowserRouter` from react-router-dom v6+. Each page route SHALL use `lazy` (React.lazy / route-level `lazy` function) so that page bundles are code-split by default.

#### Scenario: Router initializes without errors
- **WHEN** the application boots and `RouterProvider` mounts the router
- **THEN** no runtime errors are thrown and the root URL renders without crashing

#### Scenario: Route-level code splitting active
- **WHEN** the router is created
- **THEN** each page module is wrapped in a `lazy` call so it is not in the initial bundle

---

### Requirement: Three layout tiers (RootLayout, AuthLayout, AppLayout)
The router SHALL define three nested layout routes:

- `RootLayout` (`src/app/layouts/RootLayout.tsx`): outermost shell, wraps all routes. Listens for `auth:expired` DOM event and navigates to `/login`. Renders `<Outlet />`.
- `AuthLayout` (`src/app/layouts/AuthLayout.tsx`): wraps public-only routes (`/login`, `/register`). SHALL check `authStore.status` (NOT `accessToken`): if `status === 'idle'`, render a full-screen loading state (not a redirect); if `status === 'authenticated'`, redirect to `/`; if `status === 'unauthenticated'`, render the auth content (login/register).
- `AppLayout` (`src/app/layouts/AppLayout.tsx`): wraps protected routes. Includes a structural navigation placeholder (no business UI). Renders `<Outlet />`.

> **Note**: The `status: 'idle'` state represents the window between localStorage rehydration (synchronous) and the `GET /auth/me` call completing (asynchronous). Both `AuthLayout` and `ProtectedRoute` MUST handle this state explicitly to prevent flash of incorrect UI.

#### Scenario: AuthLayout redirects authenticated user
- **WHEN** a user with `status: 'authenticated'` navigates to `/login`
- **THEN** they are redirected to `/`

#### Scenario: AuthLayout shows loading on idle status
- **WHEN** a user navigates to `/login` with `status: 'idle'` (rehydration in progress)
- **THEN** a full-screen loading state is shown (no redirect)

#### Scenario: AuthLayout renders login page when unauthenticated
- **WHEN** a user navigates to `/login` with `status: 'unauthenticated'`
- **THEN** the login page is rendered

#### Scenario: RootLayout listens for auth:expired
- **WHEN** the `auth:expired` custom event is dispatched on `window`
- **THEN** the user is navigated to `/login`

---

### Requirement: ProtectedRoute guard
`src/app/router/guards/ProtectedRoute.tsx` SHALL be a React component that reads `status` from `authStore` (NOT `accessToken`). Guard logic: if `status === 'idle'`, render a full-screen loading state (not a redirect to login); if `status === 'authenticated'`, render `<Outlet />`; if `status === 'unauthenticated'`, render `<Navigate to="/login" replace />`.

#### Scenario: Unauthenticated user redirected from protected route
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/`
- **THEN** they are redirected to `/login`

#### Scenario: Authenticated user can access protected route
- **WHEN** a user with `status: 'authenticated'` navigates to `/`
- **THEN** the route renders without redirect

#### Scenario: ProtectedRoute shows loading on idle status
- **WHEN** a user navigates to `/dashboard` with `status: 'idle'` (rehydration in progress)
- **THEN** a full-screen loading state is shown (no redirect to `/login`)

#### Scenario: ProtectedRoute redirects unauthenticated on dashboard
- **WHEN** a user navigates to `/dashboard` with `status: 'unauthenticated'`
- **THEN** they are redirected to `/login`

---

### Requirement: RoleGuard stub
`src/app/router/guards/RoleGuard.tsx` SHALL accept a `roles: string[]` prop and render `<Outlet />` unconditionally in this change (no actual role enforcement yet). The component interface and prop contract SHALL be defined so that role enforcement can be added in a future change without changing the API.

#### Scenario: RoleGuard renders children without enforcement
- **WHEN** RoleGuard is mounted with any `roles` array
- **THEN** it renders `<Outlet />` regardless of the current user's roles

---

### Requirement: AuthSync component for rehydration fetch (MED-05)
A component `AuthSync` (or equivalent logic in `AppLayout`) in `src/app/providers/` SHALL subscribe to `authStore.status`. WHEN `status === 'authenticating'`, it SHALL call `GET /api/v1/auth/me` via `http.ts` and update the store: `setUser(user)` + set `status: 'authenticated'` on success; `logout()` on failure.

This component is a `useEffect`-based stub in the `app/` layer and does not belong to any FSD entity. It exists solely to decouple the rehydration fetch from the `entities/auth/store` module (which cannot import `shared/api/http.ts`).

#### Scenario: AuthSync triggers auth/me on authenticating status
- **WHEN** `authStore.status` transitions to `'authenticating'`
- **THEN** `AuthSync` calls `GET /api/v1/auth/me` via `http.ts`

#### Scenario: AuthSync does not double-fetch
- **WHEN** `status` is `'authenticated'` or `'unauthenticated'`
- **THEN** `AuthSync` does not trigger any fetch

---

### Requirement: Placeholder page routes defined for all top-level routes
The router SHALL define placeholder routes for: `/login`, `/register`, `/` (home), `/catalog`, `/cart`, `/checkout`, `/orders`, `/admin/*`. Each placeholder SHALL render a `<div>` with a descriptive text string (e.g., `<div>Placeholder: Catalog</div>`). No business logic, no API calls, no store reads.

Route tree:
- `/` → `AppLayout` → `ProtectedRoute` → `HomePage`
- `/catalog` → `AppLayout` → `ProtectedRoute` → `CatalogPage`
- `/cart` → `AppLayout` → `ProtectedRoute` → `CartPage`
- `/checkout` → `AppLayout` → `ProtectedRoute` → `CheckoutPage`
- `/orders` → `AppLayout` → `ProtectedRoute` → `OrdersPage`
- `/admin/*` → `AppLayout` → `ProtectedRoute` → `RoleGuard roles={['ADMIN']}` → `AdminPage`
- `/login` → `AuthLayout` → `LoginPage`
- `/register` → `AuthLayout` → `RegisterPage`

#### Scenario: Login route renders placeholder
- **WHEN** unauthenticated user navigates to `/login`
- **THEN** the page renders without error and the placeholder text is visible

#### Scenario: All placeholder routes render without crashing
- **WHEN** any registered route is navigated to (with auth state set appropriately for guards)
- **THEN** the page renders without a runtime error or uncaught exception
