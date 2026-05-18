# frontend-navigation Specification

## Purpose
Define the role-adaptive navigation system for the Food Store frontend. This covers the typed `NavigationItem` registry, the `filterNavItems` and `resolveDefaultRoute` pure functions, the `<Navigation>` widget contract, the multi-role UNION rule for menu rendering, and the anonymous navigation state. Navigation config is pure data — it has no React imports and is importable from any FSD layer at or above `shared/`.

## Requirements

### Requirement: NavigationItem registry
`src/shared/lib/navigation/items.ts` SHALL export a typed `NavigationItem` interface and two constants: `NAVIGATION_ITEMS` (all items with role gates) and `ANONYMOUS_NAV_ITEMS` (items for unauthenticated users). `NavigationItem` SHALL have the following shape: `key: string`, `label: string`, `path: string`, `icon?: string`, `allowedRoles: string[]` (empty array means public — no role required but still shown only when authenticated; use `ANONYMOUS_NAV_ITEMS` for unauthenticated state).
<!-- Design decision: A single enforcement mechanism. Items restricted to ADMIN use allowedRoles: ['ADMIN']. The adminOnly field was removed to prevent tiebreak ambiguity. -->

`NAVIGATION_ITEMS` SHALL cover these items grouped by role ownership:
- CLIENT items: Catálogo (`/catalog`), Mi Carrito (`/cart`), Mis Pedidos (`/orders`), Mi Perfil (`/profile`), Mis Direcciones (`/addresses`); `allowedRoles: ['CLIENT','ADMIN']`.
- STOCK items: Productos (`/stock/products`), Categorías (`/stock/categories`), Ingredientes (`/stock/ingredients`), Stock (`/stock/inventory`); `allowedRoles: ['STOCK','ADMIN']`.
- PEDIDOS items: Panel de Pedidos (`/pedidos-panel`); `allowedRoles: ['PEDIDOS','ADMIN']`.
- ADMIN-only items: Usuarios (`/admin/users`), Métricas (`/admin/metrics`); `allowedRoles: ['ADMIN']`.
<!-- OUT OF SCOPE for Change 08 (foundation only): Configuración (/admin/config) will be added in the admin module change when the route and page exist -->

`ANONYMOUS_NAV_ITEMS` SHALL contain: Catálogo (`/catalog`), Login (`/login`), Registrarse (`/register`).

#### Scenario: Registry contains all required items
- **WHEN** `NAVIGATION_ITEMS` is imported
- **THEN** it contains exactly the items specified above with correct `path` and `allowedRoles` values

#### Scenario: Anonymous registry is distinct
- **WHEN** `ANONYMOUS_NAV_ITEMS` is imported
- **THEN** it contains exactly 3 items: Catálogo, Login, Registrarse

---

### Requirement: filterNavItems pure function
`src/shared/lib/navigation/helpers.ts` SHALL export `filterNavItems(items: NavigationItem[], userRoles: string[]): NavigationItem[]`. The function SHALL:
1. Include an item if `item.allowedRoles` is empty (public item — show to authenticated users).
2. Include an item if `item.allowedRoles` has at least one entry that is present in `userRoles`.
3. De-duplicate the result by `item.path` — if two items have the same path, the first occurrence wins.
4. Return items in stable order (same order as input `items` array).
5. Return an empty array if `userRoles` is empty.

#### Scenario: CLIENT role filters correctly
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])` is called
- **THEN** result contains exactly the CLIENT items (Catálogo, Mi Carrito, Mis Pedidos, Mi Perfil, Mis Direcciones)
- **THEN** result does NOT contain any STOCK, PEDIDOS, or ADMIN-only items

#### Scenario: ADMIN role sees all items
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** result contains all items from all role groups including ADMIN-only items (those with `allowedRoles: ['ADMIN']`)

#### Scenario: Multi-role UNION de-duplicates by path
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['CLIENT','ADMIN'])` is called
- **THEN** result contains the union of CLIENT and ADMIN items
- **THEN** no path appears more than once in the result

#### Scenario: Empty roles returns empty result
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, [])` is called
- **THEN** result is an empty array

---

### Requirement: resolveDefaultRoute pure function
`src/shared/lib/navigation/helpers.ts` SHALL export `resolveDefaultRoute(roles: string[]): string`. The function SHALL return the canonical landing route for the user's highest-privilege role. Priority order (descending): `'ADMIN'` → `/admin`; `'PEDIDOS'` → `/pedidos-panel`; `'STOCK'` → `/stock/products`; `'CLIENT'` → `/catalog`; fallback (unknown roles or empty) → `/catalog`.

#### Scenario: ADMIN role lands on /admin
- **WHEN** `resolveDefaultRoute(['ADMIN'])` is called
- **THEN** result is `/admin`

#### Scenario: Multi-role ADMIN+CLIENT lands on /admin
- **WHEN** `resolveDefaultRoute(['ADMIN','CLIENT'])` is called
- **THEN** result is `/admin` (ADMIN has highest priority)

#### Scenario: CLIENT role lands on /catalog
- **WHEN** `resolveDefaultRoute(['CLIENT'])` is called
- **THEN** result is `/catalog`

#### Scenario: Unknown role uses fallback
- **WHEN** `resolveDefaultRoute(['SUPERVISOR'])` is called
- **THEN** result is `/catalog`

---

### Requirement: Navigation widget contract
`src/widgets/navigation/Navigation.tsx` SHALL be a React component that:
1. Reads `useAuthStore(s => s.status)` and `useAuthStore(s => s.user?.roles)`.
2. When `status` is `'unauthenticated'` or `'idle'`, renders `ANONYMOUS_NAV_ITEMS`.
3. When `status` is `'authenticated'`, calls `filterNavItems(NAVIGATION_ITEMS, user.roles)` and renders the filtered items.
4. Renders each item as a `<NavLink>` from `react-router-dom`.
5. Accepts an optional `isPublic?: boolean` prop with no behavioral difference in this change (reserved for future styling variants).
6. SHALL NOT import from any `features/` module.
7. SHALL NOT contain any business logic (no API calls, no cart operations, no form handling).

#### Scenario: Unauthenticated user sees anonymous navigation
- **WHEN** `<Navigation>` is rendered with `authStore.status = 'unauthenticated'`
- **THEN** the navigation shows Catálogo, Login, and Registrarse links

#### Scenario: CLIENT user sees CLIENT navigation
- **WHEN** `<Navigation>` is rendered with `authStore.status = 'authenticated'` and `user.roles = ['CLIENT']`
- **THEN** the navigation shows Mi Carrito, Mis Pedidos, Mi Perfil, Mis Direcciones, and Catálogo
- **THEN** no STOCK, PEDIDOS, or ADMIN items are visible

#### Scenario: ADMIN user sees all navigation
- **WHEN** `<Navigation>` is rendered with `authStore.status = 'authenticated'` and `user.roles = ['ADMIN']`
- **THEN** all items are visible including Usuarios and Métricas

---

### Requirement: Multi-role UNION rendering rule
The navigation system SHALL use the UNION strategy for multi-role users: a user holding multiple roles sees the union of all navigation items granted by all their roles, de-duplicated by path. No role "supersedes" another by hiding the other role's items. ADMIN-only items (`allowedRoles: ['ADMIN']`) are included only when `'ADMIN'` is present in `user.roles`, which is handled naturally by the `filterNavItems` allowedRoles check.

#### Scenario: ADMIN+CLIENT user sees union
- **WHEN** `<Navigation>` is rendered with `user.roles = ['ADMIN','CLIENT']`
- **THEN** navigation contains both CLIENT items and ADMIN-only items
- **THEN** no path is duplicated

## Acceptance

- `NAVIGATION_ITEMS` SHALL contain all items specified in the registry requirement.
- `filterNavItems(items, [])` SHALL return `[]`.
- `filterNavItems(items, ['CLIENT'])` SHALL exclude STOCK, PEDIDOS, and ADMIN-only items.
- `filterNavItems(items, ['ADMIN'])` SHALL include all items.
- `resolveDefaultRoute(['ADMIN'])` SHALL return `/admin`.
- `resolveDefaultRoute([])` SHALL return `/catalog`.
- `<Navigation>` with unauthenticated store state SHALL render anonymous items only.
- `<Navigation>` SHALL NOT import from `features/`.
- All items rendered by `<Navigation>` SHALL use `<NavLink>` from `react-router-dom`.
