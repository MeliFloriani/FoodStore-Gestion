## Why

Change 07 (`auth-refresh-logout-rbac-me`) delivered a working `authStore` with `hasRole(role)`, token refresh, and rehydration via `GET /auth/me`. The frontend routing layer from Change 06 (`frontend-core-foundation`) wired `ProtectedRoute` and `RoleGuard` as stubs — `RoleGuard` renders `<Outlet />` unconditionally and there is no role-based navigation at all. Users with any role can reach any route; the navigation bar is a static "Food Store" text with no adaptability. Sprint 1 Stories US-075 and US-076 both require real RBAC enforcement in the UI: a role-adaptive menu and real route guards. Without this change the frontend has no access control.

## What Changes

- **RoleGuard enforcement**: replace the unconditional `<Outlet />` stub with real role-checking logic against `authStore.user?.roles`. Unauthenticated ≠ wrong-role — they are handled separately.
- **`useRequireRoles(roles)` hook**: shared internal hook used by both the `RoleGuard` component and the `withAuth` HOC to centralize enforcement logic.
- **`withAuth(Component, requiredRoles)` HOC**: thin wrapper over `useRequireRoles`; for imperative wrapping of standalone pages that cannot use the route tree.
- **PublicLayout**: new lightweight layout for catalog (and future public pages); renders navigation that shows login/register CTAs when unauthenticated, full navigation when authenticated.
- **3-branch route tree restructure**: public branch (`/catalog`, `/` home redirect), auth branch (`/login`, `/register`), private branch (all role-gated routes). `/catalog` moves OUT of `ProtectedRoute`.
- **Role-namespaced routes**: `/stock/*` (STOCK + ADMIN) and `/pedidos-panel/*` (PEDIDOS + ADMIN) route subtrees created as gated placeholders. `/admin/*` remains.
- **Error pages**: `ForbiddenPage` (`/403`), `UnauthorizedPage` (`/401`), `NotFoundPage` (`/404`) in `pages/errors/`.
- **Navigation registry**: `NAVIGATION_ITEMS` typed registry in `shared/lib/navigation/items.ts`; items carry `allowedRoles` filters; anonymous menu is a distinct constant. `resolveDefaultRoute(roles)` pure function for post-login redirect.
- **`<Navigation>` widget**: `widgets/navigation/` consumes the registry, filters by user roles, renders the adaptive nav.
- **AppLayout refactor**: imports and renders `<Navigation>` widget instead of static text.
- **Post-login redirect**: `AuthLayout` reads `resolveDefaultRoute(user.roles)` after successful auth to send each role to their home.
- **Guard-before-Suspense invariant**: `RoleGuard` evaluates roles before the `React.lazy` Suspense boundary so unauthorized users never download forbidden chunks.

## Capabilities

### New Capabilities

- `frontend-navigation`: role-adaptive navigation registry, `NavigationItem` type, `<Navigation>` widget contract, multi-role union rule, anonymous menu rendering.
- `frontend-route-guards`: `RoleGuard` real enforcement, `useRequireRoles` hook, `withAuth` HOC, guard-before-Suspense invariant.
- `frontend-layouts`: `PublicLayout` (new), `AppLayout` responsibilities with navigation widget integration; `RootLayout` and `AuthLayout` remain unchanged in behavior.
- `frontend-error-pages`: `UnauthorizedPage` (/401), `ForbiddenPage` (/403), `NotFoundPage` (/404) page contracts.

### Modified Capabilities

- `frontend-routing`: Replace "RoleGuard is a stub" clause with real enforcement contract; add 3-branch route tree (public/auth/private); add role-namespaced subtrees (`/stock/*`, `/pedidos-panel/*`); add error-route paths `/401`, `/403`, `/404`; document `/catalog` as a public route.

## Impact

- **Files created**: `shared/lib/navigation/items.ts`, `shared/lib/navigation/index.ts`, `app/router/guards/` (RoleGuard updated, useRequireRoles new), `app/router/guards/withAuth.tsx`, `app/layouts/PublicLayout.tsx`, `pages/errors/ForbiddenPage.tsx`, `pages/errors/UnauthorizedPage.tsx`, `pages/errors/NotFoundPage.tsx`, `widgets/navigation/Navigation.tsx`.
- **Files modified**: `app/router/guards/RoleGuard.tsx` (stub → real enforcement), `app/router/routes.tsx` (route tree restructure), `app/layouts/AppLayout.tsx` (consume Navigation widget).
- **Backend coupling**: read-only. `user.roles: string[]` comes from `GET /api/v1/auth/me` (Change 07). No backend changes required.
- **Downstream unlocked**: Sprint 1 functional features (catalog, cart, orders, admin, stock, pedidos) can now be placed behind proper guards.
- **Testing**: new Vitest + RTL test files for `resolveDefaultRoute`, `useRequireRoles`, navigation filter, and guard redirect scenarios.

## Acceptance Criteria

### US-075 — Menú adaptado al rol del usuario

> **Historia**: Como usuario del sistema, quiero ver solo las opciones de menú correspondientes a mi rol, para tener una interfaz limpia y enfocada en mis tareas.

- GIVEN un usuario con rol CLIENT, WHEN ve el menú, THEN ve: Catálogo, Mi Carrito, Mis Pedidos, Mi Perfil, Mis Direcciones.
- GIVEN un usuario con rol STOCK, WHEN ve el menú, THEN ve: Productos, Categorías, Ingredientes, Stock.
- GIVEN un usuario con rol PEDIDOS, WHEN ve el menú, THEN ve: Panel de Pedidos.
- GIVEN un usuario con rol ADMIN, WHEN ve el menú, THEN ve: todas las opciones de todos los roles + Usuarios + Métricas. *(Configuración: out of scope para Change 08 — se incorpora cuando exista la ruta y la página en el change del módulo admin.)*
- Un usuario no autenticado ve: Catálogo, Login, Registrarse.

### US-076 — Guards de navegación por autenticación y rol

> **Historia**: Como Sistema, quiero proteger las rutas del frontend según autenticación y rol, para evitar que usuarios accedan a vistas no autorizadas.

- GIVEN un usuario no autenticado, WHEN intenta acceder a una ruta protegida, THEN es redirigido al login.
- GIVEN un usuario autenticado sin el rol requerido, WHEN intenta acceder a una ruta restringida, THEN ve pantalla 403 o es redirigido.
- Las rutas públicas (catálogo, login, registro) son accesibles sin autenticación.

## Scope

### In Scope

- All layouts: PublicLayout (new), AppLayout refactor; RootLayout and AuthLayout contract unchanged.
- Role-adaptive navigation registry, `NavigationItem` type, anonymous/role menus.
- `<Navigation>` widget that renders the adaptive nav.
- Real `RoleGuard` enforcement (replacing stub).
- `useRequireRoles(roles)` internal hook.
- `withAuth(Component, requiredRoles)` HOC decision and implementation.
- Public/private route tree restructure (3-branch).
- `/catalog` moved to public branch.
- Role-namespaced route subtrees: `/stock/*`, `/pedidos-panel/*` as gated placeholders.
- Error pages: `ForbiddenPage`, `NotFoundPage`, `UnauthorizedPage`.
- `resolveDefaultRoute(roles)` for post-login redirect.
- Guard-before-Suspense invariant documentation and implementation.
- Unit + integration tests (Vitest + RTL).

### Out of Scope

- No business module screens — all existing pages (catalog, cart, orders, admin) remain as placeholders.
- No real catalog, cart, stock, pedidos, or admin UI content — placeholders only.
- No toast wiring or toast notification UI (deferred to Design System change).
- No auth flow changes — token refresh, login, register, rehydration are owned by Change 07.
- No backend changes.
- No `docs/CHANGES.md` update (archive time only).
- No MercadoPago integration.

## Dependencies

- **Change 07 (`auth-refresh-logout-rbac-me`)** — archived. Provides: `authStore` with `hasRole(role)`, `user.roles: string[]`, `status` lifecycle, `GET /auth/me` rehydration, and `auth:expired` event. This change reads from that store and does NOT modify it.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Auth/navigation sync race: guard reads `status='idle'` before rehydration completes, shows wrong UI | Medium | High | `ProtectedRoute` already handles `'idle'` with a loading spinner; `RoleGuard` must also gate on `status !== 'idle'` before evaluating roles |
| Router/auth coupling: guards directly depend on `authStore`; future store shape changes break guards | Low | Medium | Guards import only stable selectors (`status`, `hasRole`); do not destructure the store internals |
| Multi-role edge case: ADMIN + CLIENT user lands on wrong default route | Low | Low | `resolveDefaultRoute` priority table documents ADMIN > PEDIDOS > STOCK > CLIENT |
| Future scalability: adding new roles requires touching `NAVIGATION_ITEMS` and `resolveDefaultRoute` | Certain | Low | Both are co-located in `shared/lib/navigation/`; change is additive |
| Chunk leak: unauthorized user triggers lazy route download before `RoleGuard` evaluates | Medium | Medium | Guard-before-Suspense invariant: `RoleGuard` wraps the lazy `<Suspense>` boundary, not the other way around |

## Open Questions

| # | Question | Resolution (see design.md D-0X) |
|---|---|---|
| OQ-1 | `withAuth` HOC vs layout-guard component — implement both, discard one, or both? | D-01: HOC is a thin wrapper over `useRequireRoles`; both coexist — layout guard preferred for route tree, HOC for imperative wrapping |
| OQ-2 | `/catalog` currently behind `ProtectedRoute` — restructure route tree? | D-02: 3-branch tree; `/catalog` in public branch |
| OQ-3 | URL canonical for STOCK and PEDIDOS modules | D-03: `/stock/*` and `/pedidos-panel/*` top-level |
| OQ-4 | `ForbiddenPage` — FSD page or shared/ui; route `/403` or inline? | D-04: `pages/errors/ForbiddenPage`; route `/403`; redirect-by-default |
| OQ-5 | Default landing post-login per role | D-05: `resolveDefaultRoute` pure function; ADMIN→`/admin`, PEDIDOS→`/pedidos-panel`, STOCK→`/stock/products`, CLIENT→`/catalog` |
| OQ-6 | Navigation config location | D-06: `shared/lib/navigation/items.ts`; widget in `widgets/navigation/` |
| OQ-7 | Multi-role precedence (ADMIN+CLIENT → superset or override?) | D-07: UNION of all granted items, de-duplicated by route path |
| OQ-8 | "Lazy loading by role" — conditional route registration vs `RoleGuard` | D-08: all routes registered; `RoleGuard` gates before `Suspense`; unauthorized users never download forbidden chunks |
