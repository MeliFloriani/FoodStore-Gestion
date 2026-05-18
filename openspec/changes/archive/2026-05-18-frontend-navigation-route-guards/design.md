## Context

Change 07 (`auth-refresh-logout-rbac-me`, archived 2026-05-17) completed the authStore: `status` lifecycle, `hasRole(role: string): boolean`, `user.roles: string[]` (multi-role M2M from backend), token refresh queue, and `GET /auth/me` rehydration via `AuthSync`. The routing layer from Change 06 left `RoleGuard` as a deliberate stub and `AppLayout` with a static navbar.

**Current state of interest:**
- `app/router/guards/RoleGuard.tsx` — renders `<Outlet />` unconditionally regardless of `roles` prop.
- `app/layouts/AppLayout.tsx` — renders a hard-coded "Food Store" text, no dynamic navigation.
- `/catalog` is behind `ProtectedRoute` — per US-075, it must be public.
- No STOCK (`/stock/*`) or PEDIDOS (`/pedidos-panel/*`) route subtrees exist.
- No `ForbiddenPage`, `NotFoundPage`, `UnauthorizedPage`.
- No `withAuth` HOC.
- `features/` directory is empty.

**Canonical role codes** (case-sensitive): `'ADMIN' | 'STOCK' | 'PEDIDOS' | 'CLIENT'`

**Constraints:**
- FSD strict — imports flow only downward: `app/ → widgets/ → features/ → entities/ → shared/`.
- `app/` is the legitimate home for router, guards, layouts, providers.
- `shared/lib/` is accessible from all layers; navigation config may live there.
- `user.roles` is `string[]` (not a single role); multi-role users exist.
- React 19, TypeScript strict, Vitest + RTL for tests.
- 401 token-expiry flow is already owned by Change 07's `auth:expired` event + `RootLayout` listener. Guards here only handle "not authenticated" and "wrong role."

---

## Goals / Non-Goals

**Goals:**
- Replace `RoleGuard` stub with real enforcement.
- Create `useRequireRoles` hook as the single enforcement primitive.
- Provide `withAuth(Component, requiredRoles)` HOC for imperative page wrapping.
- Restructure route tree into 3 branches (public / auth / private).
- Move `/catalog` to the public branch.
- Add `/stock/*`, `/pedidos-panel/*` as gated placeholder subtrees.
- Add `/401`, `/403`, `/404` error routes.
- Deliver a role-adaptive navigation registry and `<Navigation>` widget.
- Define `resolveDefaultRoute(roles)` for post-login redirect.
- Document all architectural decisions D-01..D-08 with rationale and rejected alternatives.
- Enforce the guard-before-Suspense invariant so unauthorized users do not download forbidden chunks.

**Non-Goals:**
- No business logic in any page placeholder.
- No real catalog, cart, stock, pedidos, admin UI.
- No toast or notification UI.
- No auth flow changes (login, register, refresh, rehydration).
- No backend changes.

---

## 1. Layouts Architecture

The three existing layout tiers are preserved. A new `PublicLayout` is added for the public branch.

| Layout | File | Responsibility |
|---|---|---|
| `RootLayout` | `app/layouts/RootLayout.tsx` | Outermost shell. Listens for `auth:expired` event → `/login`. No change. |
| `PublicLayout` | `app/layouts/PublicLayout.tsx` | NEW. Wraps public routes (`/`, `/catalog`, `/403`, `/404`, `/401`). Renders `<Navigation>` in public-aware mode (login/register CTAs when unauthenticated, full nav when authenticated). |
| `AuthLayout` | `app/layouts/AuthLayout.tsx` | Wraps `/login`, `/register`. Handles `status='idle'/'authenticating'` spinner. Extended: adds post-login redirect via resolveDefaultRoute(user.roles) + deep-link preservation (location.state?.from). Spinner and unauthenticated redirect behavior unchanged. |
| `AppLayout` | `app/layouts/AppLayout.tsx` | Wraps all private routes. Imports `<Navigation>` widget. Renders `<Outlet />`. |

**Why a new `PublicLayout` instead of reusing `RootLayout`?**
`RootLayout` is structurally the outermost shell — it must remain minimal (just the `auth:expired` listener and `<Outlet />`). Adding navigation rendering into it would make it aware of auth state in an uncontrolled way. `PublicLayout` is a thin layout that renders the nav component in "public mode" and then `<Outlet />`. An authenticated user visiting `/catalog` sees the private nav through `PublicLayout`'s conditional rendering without being blocked.

**Decoupling rules:**
- Layouts do NOT import any feature module.
- Layouts do NOT know which page is rendered behind `<Outlet />`.
- `AppLayout` imports `<Navigation>` widget only — no direct store reads in the layout.
- `PublicLayout` imports `<Navigation>` widget only.

---

## 2. Role-Adaptive Navigation System

Navigation items are defined in a pure typed registry at `shared/lib/navigation/items.ts`.

```
NavigationItem {
  key: string             // unique identifier
  label: string           // display text
  path: string            // route path
  icon?: string           // icon key (resolved by Navigation widget)
  allowedRoles: string[]  // empty array = public (no auth required)
                          // non-empty = at least one of these roles required
                          // ADMIN-only items use allowedRoles: ['ADMIN'] — no separate adminOnly field
}
```
<!-- Design decision: A single enforcement mechanism. The adminOnly field was removed to prevent tiebreak ambiguity. Items restricted to ADMIN use allowedRoles: ['ADMIN']. -->

**Menu per role (D-07 UNION rule):**

| Role | Menu items |
|---|---|
| Anonymous (unauthenticated) | Catálogo, Login, Registrarse |
| CLIENT | Catálogo, Mi Carrito, Mis Pedidos, Mi Perfil, Mis Direcciones |
| STOCK | Productos, Categorías, Ingredientes, Stock |
| PEDIDOS | Panel de Pedidos |
| ADMIN | All CLIENT items + All STOCK items + Panel de Pedidos + Usuarios + Métricas *(Configuración: out of scope — agrega en change del módulo admin)* |

Multi-role users (e.g., ADMIN + CLIENT) receive the **UNION** of all items allowed by their roles, de-duplicated by `path` (D-07).

**`NAVIGATION_ITEMS` constant** — exported from `shared/lib/navigation/items.ts`. The `<Navigation>` widget in `widgets/navigation/Navigation.tsx` calls `filterNavItems(items, user?.roles ?? [])` to get the visible set. `filterNavItems` is a pure function exported from `shared/lib/navigation/index.ts`.

**Anonymous menu** — a separate constant `ANONYMOUS_NAV_ITEMS` for items shown when `user` is `null`. This avoids conditional logic inside the widget.

---

## 3. Centralized Route Guards

**`ProtectedRoute`** (`app/router/guards/ProtectedRoute.tsx`) — NO changes to behavior or API. Reads `status` from `authStore`. Handles `'idle'` with a loading spinner (no redirect), `'authenticated'` with `<Outlet />`, `'unauthenticated'` with `<Navigate to="/login" replace />`.

**`useRequireRoles(requiredRoles: string[])`** (`app/router/guards/useRequireRoles.ts`) — NEW internal hook. Reads `status` and `user?.roles` from `authStore`. Returns `{ allowed: boolean; reason: 'loading' | 'unauthenticated' | 'forbidden' | 'ok' }`. Logic:
1. If `status === 'idle' || status === 'authenticating'` → `{ allowed: false, reason: 'loading' }`.
2. If `status === 'unauthenticated'` → `{ allowed: false, reason: 'unauthenticated' }`.
3. If `requiredRoles.length === 0` → `{ allowed: true, reason: 'ok' }` (public route — always allowed for authenticated user).
4. If `requiredRoles.some(r => user.roles.includes(r))` → `{ allowed: true, reason: 'ok' }`.
5. Else → `{ allowed: false, reason: 'forbidden' }`.

**`RoleGuard`** (`app/router/guards/RoleGuard.tsx`) — REAL enforcement. Wraps `useRequireRoles`. Props: `roles: string[]` (required roles, at least one must match). Behavior:
- `reason === 'loading'` → renders full-screen spinner.
- `reason === 'unauthenticated'` → `<Navigate to="/login" state={{ from: location }} replace />` (preserves deep-link).
- `reason === 'forbidden'` → `<Navigate to="/403" state={{ from: location }} replace />`.
- `reason === 'ok'` → `<Outlet />`.

**Guard-before-Suspense invariant (D-08):** `RoleGuard` is placed OUTSIDE (wrapping) the lazy `React.Suspense` boundary. This means unauthorized users never trigger the chunk download. Route definition pattern:
```
RoleGuard roles={['ADMIN']}
  └─ Suspense fallback={<PageSpinner />}
       └─ lazy AdminPage
```

---

## 4. `withAuth` HOC (D-01)

`withAuth<P>(Component: React.ComponentType<P>, requiredRoles: string[]): React.FC<P>`

The HOC is a thin wrapper over `useRequireRoles`. It provides the same enforcement logic as `RoleGuard` but for cases where a component cannot be placed in the route tree (e.g., imperative wrapping of a standalone page outside the router config, or feature-level page components that need to self-declare their access requirements).

**Semantics:**
- Calls `useRequireRoles(requiredRoles)` internally.
- On `loading` → renders `<PageSpinner />`.
- On `unauthenticated` → renders `<Navigate to="/login" />`.
- On `forbidden` → renders `<Navigate to="/403" />`.
- On `ok` → renders `<Component {...props} />`.

**When to use HOC vs layout-guard:**
| Pattern | Use when |
|---|---|
| `RoleGuard` in route tree | Preferred — declarative, co-located with route definition. Use for all route-level access control. |
| `withAuth` HOC | Use when a page component must enforce its own access (e.g., standalone feature page outside the main router config, feature team owns access requirements). |

Both patterns call the same `useRequireRoles` hook → identical semantics, no divergence.

---

## 5. Lazy Loading Strategy (D-08)

All routes are registered in the route tree regardless of user role. `React.lazy` is used per route. This gives predictable route matching and avoids conditional route registration which causes router re-initialization.

The `RoleGuard` is placed BEFORE the `Suspense` boundary (closer to the root in the tree). When `RoleGuard` returns `<Navigate to="/403" />`, the lazy component's chunk is never imported. Unauthorized users do not download forbidden JS chunks.

**Fallback hierarchy:**
1. `ProtectedRoute` renders `<FullScreenSpinner />` on `status='idle'`.
2. `RoleGuard` renders `<FullScreenSpinner />` on `reason='loading'`.
3. `React.Suspense fallback={<PageSpinner />}` handles the lazy-load itself once guards pass.

Route definition example:
```tsx
{
  path: 'admin',
  element: <RoleGuard roles={['ADMIN']} />,
  children: [{
    index: true,
    element: (
      <Suspense fallback={<PageSpinner />}>
        <AdminPage />
      </Suspense>
    ),
  }],
}
```

---

## 6. React-Router Integration

Route tree restructure — three top-level branches under `RootLayout`:

```
RootLayout
├── [public branch]   PublicLayout
│   ├── /             → redirect to /catalog (or role-aware home if authenticated)
│   ├── /catalog      → CatalogPage (lazy, public)
│   ├── /401          → UnauthorizedPage
│   ├── /403          → ForbiddenPage
│   └── /404          → NotFoundPage
│
├── [auth branch]     AuthLayout
│   ├── /login        → LoginPage
│   └── /register     → RegisterPage
│
├── [private branch]  AppLayout → ProtectedRoute
│   ├── /home         → HomePage
│   ├── /cart         → RoleGuard roles={['CLIENT']}  → CartPage
│   ├── /checkout     → RoleGuard roles={['CLIENT']}  → CheckoutPage
│   ├── /orders       → RoleGuard roles={['CLIENT']}  → OrdersPage
│   ├── /profile      → RoleGuard roles={['CLIENT','ADMIN']} → ProfilePage (placeholder)
│   ├── /stock/*      → RoleGuard roles={['STOCK','ADMIN']}  → stock subtree (placeholder)
│   ├── /pedidos-panel/* → RoleGuard roles={['PEDIDOS','ADMIN']} → pedidos subtree (placeholder)
│   └── /admin/*      → RoleGuard roles={['ADMIN']}   → AdminPage (placeholder)
│
└── * → redirect /404
```

**`/` root redirect**: authenticated users are redirected by `resolveDefaultRoute`. Unauthenticated users are redirected to `/catalog` (public).

All layouts are `<Outlet />` parents — they provide structure but do not own page content.

---

## 7. Navigation States and Visual Fallbacks

| State | `authStore.status` | Guard behavior | Visual |
|---|---|---|---|
| Rehydrating | `'idle'` | `ProtectedRoute` → spinner; `RoleGuard` → spinner | `<FullScreenSpinner />` |
| Login/register in flight | `'authenticating'` | `AuthLayout` → spinner | `<FullScreenSpinner />` |
| Authenticated, correct role | `'authenticated'` + role match | `RoleGuard` → `<Outlet />` | Page content |
| Authenticated, wrong role | `'authenticated'` + no role match | `RoleGuard` → `/403` | `ForbiddenPage` |
| Unauthenticated on protected route | `'unauthenticated'` | `ProtectedRoute` → `/login` | `LoginPage` |
| Public route | any | No guard | Page content |

`PublicLayout` renders `<Navigation>` in public-aware mode:
- `status='idle'` → show anonymous nav (Catálogo, Login, Registrarse).
- `status='authenticated'` → show role-filtered nav.
- `status='unauthenticated'` → show anonymous nav.

---

## 8. Decoupling Rules

Guards have no business logic. Examples of what is NOT allowed:
- `RoleGuard` importing `useCartStore` or checking cart state.
- `ProtectedRoute` importing any feature module.
- Layouts importing feature-level components directly (only widgets or shared).

Navigation does not import features. `NAVIGATION_ITEMS` contains only paths and labels — it knows nothing about component implementations.

Layouts do not know page internals:
- `AppLayout` imports `<Navigation>` widget by its public API only.
- `PublicLayout` same.

Import rule examples (concrete):
- ALLOWED: `widgets/navigation/Navigation.tsx` imports from `shared/lib/navigation/` (downward).
- ALLOWED: `app/layouts/AppLayout.tsx` imports `widgets/navigation/Navigation.tsx` (downward).
- FORBIDDEN: `shared/lib/navigation/items.ts` imports from `entities/auth/` (upward from shared is forbidden).
- FORBIDDEN: `widgets/navigation/Navigation.tsx` imports from `features/*` (widgets cannot import features going UP — but features may not exist yet; regardless, this is illegal).
- ALLOWED: `app/router/guards/RoleGuard.tsx` imports `entities/auth/model/store.ts` (app → entities is downward).

---

## 9. authStore Integration

Guards and navigation consume `authStore` via reactive selectors only. No guard ever calls `setUser`, `logout`, or any write action.

Selectors used:
- `useAuthStore(s => s.status)` — determines guard rendering path.
- `useAuthStore(s => s.user?.roles)` — determines role filtering.
- `useAuthStore(s => s.hasRole)` — available via store selector but `useRequireRoles` reads `user.roles` directly for multi-role union check.

**Rehydration handshake**: `AuthSync` (owned by Change 07) calls `GET /auth/me` when `status='authenticating'`, sets `status='authenticated'` + `user` on success. Guards observe `status='idle'` during this window and render a spinner — they do NOT redirect to `/login` during idle. This invariant is already established by `ProtectedRoute`; `RoleGuard` must respect the same contract.

**Cross-tab sync**: `authStore` uses `localStorage` + Zustand `persist` middleware. The `storage` event fires when another tab modifies `localStorage`. Zustand's persist middleware handles this automatically — guards will re-evaluate when `status` changes reactively. No additional cross-tab handling is needed for this change.

---

## 10. Folder Structure

```
frontend/src/
├── app/
│   ├── layouts/
│   │   ├── RootLayout.tsx       (no change)
│   │   ├── AuthLayout.tsx       (no change)
│   │   ├── AppLayout.tsx        (MODIFIED: add <Navigation> widget)
│   │   └── PublicLayout.tsx     (NEW)
│   ├── router/
│   │   ├── routes.tsx           (MODIFIED: 3-branch tree + new routes)
│   │   └── guards/
│   │       ├── ProtectedRoute.tsx  (no change)
│   │       ├── RoleGuard.tsx       (MODIFIED: real enforcement)
│   │       ├── useRequireRoles.ts  (NEW)
│   │       └── withAuth.tsx        (NEW)
│   └── providers/               (no change)
│
├── pages/
│   ├── errors/
│   │   ├── ForbiddenPage.tsx    (NEW: /403)
│   │   ├── UnauthorizedPage.tsx (NEW: /401)
│   │   └── NotFoundPage.tsx     (NEW: /404)
│   └── ... (existing pages unchanged)
│
├── widgets/
│   └── navigation/
│       └── Navigation.tsx       (NEW)
│
├── shared/
│   └── lib/
│       └── navigation/
│           ├── items.ts         (NEW: NAVIGATION_ITEMS, ANONYMOUS_NAV_ITEMS, NavigationItem type)
│           ├── helpers.ts       (NEW: filterNavItems, resolveDefaultRoute)
│           └── index.ts         (NEW: barrel export)
│
└── entities/
    └── auth/                    (no change — hasRole, user.roles already complete)
```

---

## 11. Future Integration Prep

Route slots are registered as empty placeholders now:
- `/stock/*` → stock subtree will receive `ProductManagementPage`, `IngredientPage`, etc. in a future change. The `RoleGuard roles={['STOCK','ADMIN']}` is already in place.
- `/pedidos-panel/*` → orders management subtree for PEDIDOS role. Guard already in place.
- `/admin/*` → admin dashboard, users, metrics, config. Guard already in place.
- `/profile`, `/addresses` → CLIENT profile routes. Guard already in place.

Dynamic sidebars: `AppLayout` already imports `<Navigation>` widget. When the widget gains a sidebar variant (future Design System change), only the widget changes — layouts and guards are not affected.

Error boundaries: `ErrorBoundary` at `app/` level already wraps `RouterProvider`. Route-level error boundaries can be added per route's `errorElement` in the future without changing guard logic.

---

## 12. Unauthorized / Forbidden Strategy

**401 (token expired)**: Owned by Change 07. `RootLayout` listens for `auth:expired` DOM event and navigates to `/login`. The `ProtectedRoute` handles `status='unauthenticated'` → redirect to `/login`. Guards in this change do NOT need to handle 401 separately.

**403 (role mismatch — new in this change)**: `RoleGuard` detects `reason='forbidden'` and redirects `<Navigate to="/403" state={{ from: location }} replace />`. The `ForbiddenPage` MAY render a "Go back" or "Go to your home" CTA using `resolveDefaultRoute(user.roles)` to send the user to a route they can access.

**Deep-link preservation**: When an unauthenticated user hits a protected route, `RoleGuard` stores `{ from: location }` in router state. After login, `AuthLayout` reads `location.state?.from` and redirects there; if absent, falls back to `resolveDefaultRoute(user.roles)`.

**`/401` route**: Rendered when the backend explicitly returns 401 and the HTTP client redirects to it (future use). `UnauthorizedPage` renders a "Session expired" message. For now it is a placeholder — the `auth:expired` event flow already handles token expiry.

**`/404` route**: Rendered by the router catch-all `*` route. No auth gating needed.

---

## 13. Separation Principles

**Routing vs Auth:**
- Routing (`routes.tsx`) declares WHICH guard wraps WHICH route.
- Auth (`authStore`) owns WHAT the current authentication state is.
- Guards are the boundary — they read auth state and express routing consequences.

**Guards vs Layouts:**
- Guards express access decisions: allow, redirect-to-login, redirect-to-403.
- Layouts express visual structure: nav shell, content area, footer.
- A guard does not render ANY layout element. A layout does not make ANY access decision.

**Navigation vs Features:**
- `NAVIGATION_ITEMS` is configuration data — paths, labels, role filters.
- Features own their implementation. Navigation knows only the path to navigate to.
- Adding a new feature route requires ONE additive line in `items.ts`, no changes to guards.

**Access vs Rendering:**
- Access control is enforced at the route tree level (guard wraps the route).
- Rendering (what the page shows) is determined by the page component.
- A page component MUST NOT re-implement access control — guards are the single enforcement point.

---

## Decisions

### D-01: withAuth HOC vs Layout-Guard Component

**Problem (OQ-1)**: Should `withAuth` HOC coexist with `RoleGuard`, or should one be dropped?

**Decision**: Both coexist. `useRequireRoles` is the single enforcement primitive; both `RoleGuard` and `withAuth` call it. The HOC is provided as a thin wrapper for imperative use cases (e.g., a standalone page component that must declare its own access requirements). The layout-guard (`RoleGuard`) is the preferred declarative pattern for route-tree-level access control.

**Rationale**: The HOC adds zero implementation overhead (it calls the same hook). Having it available prevents future contributors from bypassing guards by importing page components directly in custom routes. Both patterns are self-consistent.

**Rejected alternatives**:
- HOC only (drop `RoleGuard`): loses the route-tree declarative pattern; guards and routes become harder to read.
- Layout-guard only (drop HOC): prevents feature teams from self-declaring access; increases coupling to the app router.

---

### D-02: /catalog Public Route — Route Tree Restructure

**Problem (OQ-2)**: `/catalog` is currently behind `ProtectedRoute`. US-075 says unauthenticated users see "Catálogo" in the menu. The route tree must be restructured.

**Decision**: Three top-level branches under `RootLayout`: (1) public branch with `PublicLayout`, (2) auth branch with `AuthLayout`, (3) private branch with `AppLayout + ProtectedRoute`. `/catalog` moves to the public branch. An authenticated user visiting `/catalog` is not redirected — `PublicLayout` renders their full nav, and the same `CatalogPage` (placeholder) is shown.

**Rationale**: Clean separation between "routes that require auth" and "routes that are open to all." Avoids the hack of conditionally bypassing `ProtectedRoute`.

**Rejected alternatives**:
- Move `/catalog` outside `ProtectedRoute` without a dedicated `PublicLayout`: loses the ability to render the correct navigation variant for public routes.
- Two-branch tree (public + private): AuthLayout is not "private" in the same sense; keeping it as a third branch maintains the existing semantic.

---

### D-03: Canonical URLs for STOCK and PEDIDOS

**Problem (OQ-3)**: Should STOCK routes be `/stock/*` or `/admin/stock/*`? Should PEDIDOS be `/pedidos/*` or `/orders-management`?

**Decision**: Top-level role-namespaced paths: `/stock/*` for STOCK module; `/pedidos-panel/*` for PEDIDOS (avoids clash with CLIENT-owned `/orders`). ADMIN users also have access to both via `RoleGuard roles={['STOCK','ADMIN']}` and `roles={['PEDIDOS','ADMIN']}` respectively.

**Rationale**: Top-level paths are semantically cleaner — each role has its own URL namespace. `/pedidos-panel` is distinct from `/orders` (client's order history). No nesting under `/admin/*` avoids making ADMIN the owner of STOCK/PEDIDOS UI.

**Rejected alternatives**:
- `/admin/stock/*`: conflates admin role with stock-management role; STOCK users don't navigate to `/admin/`.
- `/orders-management`: ambiguous, not role-scoped.

---

### D-04: ForbiddenPage Location and Route

**Problem (OQ-4)**: Where does `ForbiddenPage` live? Route `/403` or inline rendering?

**Decision**: FSD page layer — `pages/errors/ForbiddenPage.tsx`, `pages/errors/UnauthorizedPage.tsx`, `pages/errors/NotFoundPage.tsx`. Routes: `/403`, `/401`, `/404`. `RoleGuard` redirects to `/403` by default (redirect-by-default mode), preserving the `from` location in router state.

**Rationale**: Redirect-by-default makes the forbidden state visible in the URL (useful for debugging, browser back-button works predictably). An inline-render variant (no URL change) would hide the forbidden state and break the back-button.

**Rejected alternatives**:
- `shared/ui` location: error pages have page-level concerns (they can import route state, navigation hooks); they belong in `pages/`.
- Inline rendering without redirect: loses URL clarity, complicates back-button behavior.

---

### D-05: Default Landing Post-Login

**Problem (OQ-5)**: Where does each role land after login?

**Decision**: `resolveDefaultRoute(roles: string[]): string` pure function in `shared/lib/navigation/helpers.ts`. Priority table (highest-privilege first):
1. `'ADMIN'` → `/admin`
2. `'PEDIDOS'` → `/pedidos-panel`
3. `'STOCK'` → `/stock/products`
4. `'CLIENT'` → `/catalog`
5. fallback → `/catalog`

Multi-role: the highest-privilege role in the priority table wins.

**Rationale**: A pure function is testable in isolation (unit tests). Priority order reflects operational importance: ADMIN must reach the dashboard, PEDIDOS urgently needs the order panel, STOCK needs product management, CLIENT lands on the catalog.

**Rejected alternatives**:
- Post-login redirect hardcoded in `AuthLayout`: non-testable, couples auth UI to routing logic.
- Per-role login endpoints: requires backend changes, out of scope.

---

### D-06: Navigation Config Location

**Problem (OQ-6)**: Where does the navigation config live — `shared/lib/navigation/`, `widgets/`, or `app/` inline?

**Decision**: `frontend/src/shared/lib/navigation/items.ts` exports `NAVIGATION_ITEMS`, `ANONYMOUS_NAV_ITEMS`, and the `NavigationItem` type. Pure data, no React imports. `filterNavItems` and `resolveDefaultRoute` live in `shared/lib/navigation/helpers.ts`. The `<Navigation>` widget in `widgets/navigation/Navigation.tsx` consumes the registry and renders the nav UI. `AppLayout` and `PublicLayout` import the widget.

**Rationale**: `shared/lib/` is importable from all layers. Placing config there keeps it accessible to `widgets/`, `app/`, and any future `features/` that need to know about navigation paths. Keeping the widget in `widgets/` keeps UI rendering concerns separate from pure config.

**Rejected alternatives**:
- `widgets/navigation/items.ts`: would make nav config inaccessible from `app/` layouts without going through the widget.
- `app/` inline: couples config to the router, makes it harder to test.

---

### D-07: Multi-Role Precedence

**Problem (OQ-7)**: If a user has ADMIN + CLIENT roles, which menu is shown — ADMIN superset, CLIENT subset, or UNION?

**Decision**: UNION. The displayed menu is the union of all menu items granted by all the user's roles, de-duplicated by `path`. ADMIN-only items use `allowedRoles: ['ADMIN']` — they are included naturally by the `filterNavItems` union rule when `'ADMIN'` is present in `user.roles`.

**Rationale**: A multi-role user genuinely has the grants of all their roles. Showing only the "highest" role's menu would silently hide legitimate CLIENT features from an ADMIN+CLIENT user. The union is semantically correct.

**Rejected alternatives**:
- ADMIN supersedes all: hides legitimate CLIENT access (e.g., an admin who also places orders). Semantically wrong.
- Intersection: would show no items for most role combinations (CLIENT ∩ ADMIN = empty per current menu definitions). Obviously wrong.

---

### D-08: Lazy Loading Strategy

**Problem (OQ-8)**: Should routes be registered conditionally per role, or should all routes be registered with `RoleGuard` gating access?

**Decision**: All routes are registered in the route tree for all users. `React.lazy` is used per route. `RoleGuard` is placed OUTSIDE (wrapping) the `React.Suspense` boundary. The invariant: if `RoleGuard` returns a redirect, the lazy component's `import()` is never triggered — forbidden chunks are not downloaded.

**Rationale**: Conditional route registration causes router re-initialization when auth state changes, leading to navigation flickers and lost scroll position. Static route registration is predictable and avoids this. The guard-before-Suspense placement achieves chunk isolation without dynamic registration.

**Rejected alternatives**:
- Conditional route registration: causes router to remount on every role change; bad UX.
- Suspense wraps RoleGuard: allows the lazy import to be triggered before the guard evaluates; unauthorized users download forbidden chunks.

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `status='idle'` causes guard flash (spinner briefly shown to authenticated user) | `ProtectedRoute` already handles idle with spinner; `RoleGuard` same. Rehydration completes in milliseconds in practice. |
| `user.roles` null during `status='authenticating'` | `useRequireRoles` handles `status='authenticating'` as `reason='loading'` — never reads `user.roles` before status is `'authenticated'`. |
| Future roles (e.g., `SUPERVISOR`) break navigation | `NAVIGATION_ITEMS` is additive — new items added without modifying existing ones. `resolveDefaultRoute` has a fallback. |
| `/catalog` as public route allows unauthenticated access to the real catalog data | Catalog API endpoints may still require auth at the backend level; that is the backend's concern. This change only moves the ROUTE to public. |
| Guard-before-Suspense order is easy to accidentally reverse | Documented as an invariant in spec; integration tests verify the redirect behavior; code review checklist item. |

## Migration Plan

1. Write new files first (in order: `useRequireRoles`, `withAuth`, navigation registry, error pages, `PublicLayout`, `Navigation` widget).
2. Modify `RoleGuard` — replace unconditional `<Outlet />` with `useRequireRoles` call. Existing tests that pass `roles={['ADMIN']}` and expect `<Outlet />` must be updated to mock an authenticated ADMIN user.
3. Restructure `routes.tsx` — move `/catalog` to public branch, add error routes, add STOCK/PEDIDOS subtrees.
4. Modify `AppLayout` — add `<Navigation>` widget import and rendering.
5. Add `PublicLayout` to public branch in routes.
6. Wire `resolveDefaultRoute` into post-login redirect in `AuthLayout`.
7. Run existing test suite — update any test that relied on the stub `RoleGuard` behavior.
8. Write new tests.

**Rollback**: the guard changes are isolated to `app/router/guards/`. Reverting `RoleGuard.tsx` to the stub is a one-line change. No database or backend state is affected.

## Open Questions

All 8 open questions from the proposal have been resolved as D-01..D-08 above. No unresolved questions remain.
