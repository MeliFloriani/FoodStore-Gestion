## 1. Types and Shared Navigation Registry

- [x] 1.1 Create `frontend/src/shared/lib/navigation/items.ts` — define `NavigationItem` interface (`key`, `label`, `path`, `icon?`, `allowedRoles: string[]`); do NOT include `adminOnly` field (ADMIN-only items use `allowedRoles: ['ADMIN']` instead); export `NAVIGATION_ITEMS: NavigationItem[]` covering all role-menu items per US-075; export `ANONYMOUS_NAV_ITEMS: NavigationItem[]` (Catálogo, Login, Registrarse)
- [x] 1.2 Create `frontend/src/shared/lib/navigation/helpers.ts` — export `filterNavItems(items: NavigationItem[], userRoles: string[]): NavigationItem[]` (UNION rule, de-duplicate by `path`; ADMIN-only items are handled via `allowedRoles: ['ADMIN']` — no separate adminOnly gate); export `resolveDefaultRoute(roles: string[]): string` (priority: ADMIN→`/admin`, PEDIDOS→`/pedidos-panel`, STOCK→`/stock/products`, CLIENT→`/catalog`, fallback `/catalog`)
- [x] 1.3 Create `frontend/src/shared/lib/navigation/index.ts` — barrel re-export of `NavigationItem`, `NAVIGATION_ITEMS`, `ANONYMOUS_NAV_ITEMS`, `filterNavItems`, `resolveDefaultRoute`

## 2. Core Guard Hook

- [x] 2.1 Create `frontend/src/app/router/guards/useRequireRoles.ts` — implement hook with signature `useRequireRoles(requiredRoles: string[]): { allowed: boolean; reason: 'loading' | 'unauthenticated' | 'forbidden' | 'ok' }`; reads `status` and `user?.roles` from `useAuthStore`; logic: idle/authenticating → loading, unauthenticated → unauthenticated, empty requiredRoles → ok, role match → ok, else → forbidden
- [x] 2.2 Write unit tests for `useRequireRoles` in `frontend/src/app/router/guards/__tests__/useRequireRoles.test.ts` — test all 5 reason branches with mocked authStore states; use `renderHook` from RTL. Required test cases:
  - Test: status='idle' → returns `{ state: 'loading' }`
  - Test: status='authenticating' → returns `{ state: 'loading' }` (must pass even though this branch is unreachable from private tree; it IS reachable from withAuth HOC context)
  - Test: status='authenticated', roles=['CLIENT'], requiredRoles=['ADMIN'] → returns `{ state: 'forbidden' }`
  - Test: status='authenticated', roles=['ADMIN','CLIENT'], requiredRoles=['ADMIN'] → returns `{ state: 'authorized' }`
  - Test: status='authenticated', roles=[], requiredRoles=['ADMIN'] → returns `{ state: 'forbidden' }`
  - Test: status='unauthenticated' → returns `{ state: 'unauthenticated' }`

## 3. Error Pages

- [x] 3.1 Create `frontend/src/pages/errors/ForbiddenPage.tsx` — renders a `<div>403 Forbidden</div>` placeholder; optionally reads `location.state?.from` and renders a "go back" link; no business logic; lazy-exportable
- [x] 3.2 Create `frontend/src/pages/errors/UnauthorizedPage.tsx` — renders `<div>401 Unauthorized - Session expired</div>` placeholder; no business logic; lazy-exportable
- [x] 3.3 Create `frontend/src/pages/errors/NotFoundPage.tsx` — renders `<div>404 Not Found</div>` placeholder; no business logic; lazy-exportable

### Phase 3b — Placeholder pages: profile and addresses

- [x] 3.4 — Create `frontend/src/pages/profile/ui/ProfilePage.tsx`
  - Minimal placeholder: `export default function ProfilePage() { return <div>Placeholder: Mi Perfil</div> }`
  - No data fetching, no forms, no imports from features/
  - This page will be implemented in Change 13 (customer-profile-management)

- [x] 3.5 — Create `frontend/src/pages/addresses/ui/AddressesPage.tsx`
  - Minimal placeholder: `export default function AddressesPage() { return <div>Placeholder: Mis Direcciones</div> }`
  - No data fetching, no forms, no imports from features/
  - This page will be implemented in Change 14 (delivery-addresses-management)

## 4. Guards: RoleGuard and withAuth HOC

- [x] 4.1 Modify `frontend/src/app/router/guards/RoleGuard.tsx` — replace unconditional `<Outlet />` stub with `useRequireRoles(roles)` call; implement: loading → `<FullScreenSpinner />`; unauthenticated → `<Navigate to="/login" state={{ from: location }} replace />`; forbidden → `<Navigate to="/403" state={{ from: location }} replace />`; ok → `<Outlet />`; props remain `{ roles: string[] }` (API unchanged)
- [x] 4.2 Create `frontend/src/app/router/guards/withAuth.tsx` — implement `withAuth<P>(Component: React.ComponentType<P>, requiredRoles: string[]): React.FC<P>`; uses `useRequireRoles` internally; same redirect logic as `RoleGuard`; forwards all props to `Component` on `ok`
- [x] 4.3 Write integration tests for `RoleGuard` in `frontend/src/app/router/guards/__tests__/RoleGuard.test.tsx` — test: (a) unauthenticated user → redirected to `/login`; (b) authenticated user wrong role → redirected to `/403`; (c) authenticated user correct role → renders `<Outlet />`; (d) status=idle → renders spinner; mock `useAuthStore` and `react-router-dom`
- [x] 4.4 Write unit tests for `withAuth` HOC in `frontend/src/app/router/guards/__tests__/withAuth.test.tsx` — mirror RoleGuard test scenarios; verify props are forwarded on `ok`
- [x] 4.5 — Security test: unauthorized users do NOT download role-guarded lazy chunks
  - Framework: Vitest
  - Setup: spy on the dynamic `import()` for at least one role-guarded lazy page (e.g., AdminPage chunk)
  - Test: Mount a MemoryRouter with initialEntry `/admin` and a CLIENT user (roles=['CLIENT']) in the auth store
  - Assert: (a) `RoleGuard` redirects to `/403`, AND (b) the lazy AdminPage import spy was NOT called (chunk not downloaded)
  - Why: This is the mechanistic verification of invariant D-08 (guard-before-Suspense). Without it, accidental inversion of Suspense/Guard order is silent.
  - Note: Vitest supports `vi.mock()` on dynamic imports; the exact spy mechanism depends on the router test setup established in task 9.x
  - Depends on: tasks 4.3 (guard setup), 7.0 (two-node pattern in place)

## 5. Layouts

- [x] 5.1 Create `frontend/src/app/layouts/PublicLayout.tsx` — renders `<Navigation>` widget (imported from `widgets/navigation/Navigation`) + `<Outlet />`; passes `isPublic={true}` or equivalent prop to `Navigation` so it renders anonymous vs authenticated nav based on authStore status
- [x] 5.2 Modify `frontend/src/app/layouts/AppLayout.tsx` — import `Navigation` from `widgets/navigation/Navigation`; replace static "Food Store" text with `<Navigation />`; keep `<Outlet />` and structural shell unchanged

## 6. Navigation Widget

- [x] 6.1 Create `frontend/src/widgets/navigation/Navigation.tsx` — reads `useAuthStore(s => s.status)` and `useAuthStore(s => s.user?.roles)`; calls `filterNavItems(NAVIGATION_ITEMS, roles)` when authenticated, renders `ANONYMOUS_NAV_ITEMS` when unauthenticated; renders a `<nav>` with list of links using `react-router-dom` `<NavLink>`; accepts optional `isPublic?: boolean` prop
- [x] 6.2 Write rendering tests for `Navigation` in `frontend/src/widgets/navigation/__tests__/Navigation.test.tsx` — test: (a) unauthenticated → shows anonymous items (Catálogo, Login, Registrarse); (b) CLIENT → shows CLIENT items only; (c) STOCK → shows STOCK items only; (d) PEDIDOS → shows PEDIDOS item only; (e) ADMIN → shows all items; (f) ADMIN+CLIENT multi-role → union de-duplicated; mock `useAuthStore`

## 7. Router Refactor — 3-Branch Route Tree

- [x] 7.0 — Refactor `withSuspense` helper
  - File: `frontend/src/app/router/routes.tsx`
  - Remove or rename the existing `withSuspense(Page)` helper that wraps pages as `<Suspense><Page/></Suspense>` in route `element` props
  - Replace all non-guarded public/auth routes that used `withSuspense` with inline `<Suspense fallback={<RouteLoading/>}><LazyPage/></Suspense>` as the route element (this is fine for non-guarded routes)
  - For ALL role-guarded routes, enforce the two-node pattern:
    ```
    // CORRECT — guard evaluated BEFORE Suspense resolves
    <Route element={<RoleGuard roles={['ADMIN']}/>}>
      <Route path="/admin" element={<Suspense fallback={<RouteLoading/>}><AdminPage/></Suspense>}/>
    </Route>

    // FORBIDDEN — Suspense fires before RoleGuard evaluates
    <Route element={<RoleGuard roles={['ADMIN']}/>}>
      <Route path="/admin" element={withSuspense(AdminPage)}/>
    </Route>
    ```
  - Depends on: none (this is prerequisite for tasks 7.1–7.5)
- [x] 7.1 Modify `frontend/src/app/router/routes.tsx` — restructure into 3 branches under `RootLayout`: (1) public branch under `PublicLayout` with `/`, `/catalog`, `/401`, `/403`, `/404`; (2) auth branch under `AuthLayout` with `/login`, `/register`; (3) private branch under `AppLayout → ProtectedRoute` with all role-gated routes; add catch-all `*` → redirect `/404`
  - Add lazy imports at the top of the routes file:
    ```ts
    const ProfilePage = lazy(() => import('@/pages/profile/ui/ProfilePage'))
    const AddressesPage = lazy(() => import('@/pages/addresses/ui/AddressesPage'))
    ```
  - Register `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → lazy ProfilePage (two-node pattern per task 7.0)
  - Register `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → lazy AddressesPage (two-node pattern per task 7.0)
  - Depends on: tasks 3.4, 3.5, 7.0
- [x] 7.2 Add STOCK subtree to private branch: path `/stock/*` wrapped in `RoleGuard roles={['STOCK','ADMIN']}`; placeholder index route renders `<div>Stock Module - Placeholder</div>`; lazy-wrapped
  NOTE: Use the two-node route pattern (see task 7.0). Do NOT use withSuspense() for this route.
- [x] 7.3 Add PEDIDOS subtree to private branch: path `/pedidos-panel/*` wrapped in `RoleGuard roles={['PEDIDOS','ADMIN']}`; placeholder index route renders `<div>Pedidos Panel - Placeholder</div>`; lazy-wrapped
  NOTE: Use the two-node route pattern (see task 7.0). Do NOT use withSuspense() for this route.
- [x] 7.4 Wrap `CartPage`, `CheckoutPage`, `OrdersPage` in `RoleGuard roles={['CLIENT','ADMIN']}` inside the private branch (Depends on 7.1)
- [x] 7.5 Verify `AdminPage` remains wrapped in `RoleGuard roles={['ADMIN']}` (no change, just confirm)
- [x] 7.6 Write integration tests for route tree in `frontend/src/app/router/__tests__/routes.test.tsx` — test: (a) unauthenticated GET `/catalog` → renders `CatalogPage` (no redirect); (b) unauthenticated GET `/stock/products` → redirected to `/login`; (c) CLIENT role GET `/stock/products` → redirected to `/403`; (d) STOCK role GET `/stock/products` → renders placeholder; use `createMemoryRouter` + `renderWithProviders`

## 8. Post-Login Redirect

- [x] 8.1 — Implement post-login redirect logic in `AuthLayout`
  - File: `frontend/src/app/layouts/AuthLayout.tsx`
  - REPLACE the existing `return <Navigate to="/" replace />` line (currently the only redirect for authenticated users) with the following logic:
    1. If `location.state?.from` exists → redirect to `location.state.from` (deep-link preservation)
    2. Else → call `resolveDefaultRoute(user.roles)` from `shared/lib/navigation/helpers` and redirect there
  - Do NOT leave the old `<Navigate to="/" replace />` as a fallback — it must be fully replaced
  - Import `resolveDefaultRoute` from `shared/lib/navigation`
  - Import `useAuthStore` selector for `user.roles`
  - Depends on: task 1.2 (resolveDefaultRoute implemented)
- [x] 8.2 Write unit tests for post-login redirect in `frontend/src/app/layouts/__tests__/AuthLayout.test.tsx` — test: (a) CLIENT login → redirected to `/catalog`; (b) ADMIN login → redirected to `/admin`; (c) STOCK login → redirected to `/stock/products`; (d) PEDIDOS login → redirected to `/pedidos-panel`; (e) deep-link preserved: had `from=/stock/products`, STOCK login → redirected to `/stock/products`

## 9. Navigation Registry Tests

- [x] 9.1 Write unit tests for `filterNavItems` in `frontend/src/shared/lib/navigation/__tests__/helpers.test.ts` — test: (a) empty roles → empty result; (b) CLIENT roles → CLIENT items only; (c) ADMIN → all items; (d) ADMIN+CLIENT → union, no duplicate paths; (e) unknown role → no items
- [x] 9.2 Write unit tests for `resolveDefaultRoute` in same file — test all 4 roles + fallback + multi-role priority (ADMIN+CLIENT → `/admin`)

## 10. Documentation

- [x] 10.1 Check if `frontend/README.md` has a routing section; if yes, update to describe the 3-branch route tree and guard pattern; if no routing section exists, skip (no new README sections are created for this change)
