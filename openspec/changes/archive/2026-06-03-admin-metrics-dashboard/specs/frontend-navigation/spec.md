## MODIFIED Requirements

### Requirement: NavigationItem registry

The ADMIN-only item `Métricas` in `NAVIGATION_ITEMS` SHALL use `path: '/admin/metricas'` (not `/admin/metrics`). All other fields — `label`, `allowedRoles: ['ADMIN']`, `key` — remain unchanged.

#### MODIFIED Scenario: Registry contains all required items — Métricas path
- **WHEN** `NAVIGATION_ITEMS` is imported
- **THEN** the ADMIN-only Métricas item has `path: '/admin/metricas'` (not `/admin/metrics`)

---

### Requirement: filterNavItems renders all management items for ADMIN role

The assertion `the result includes paths /admin/users, /admin/metrics` SHALL be replaced with `/admin/metricas`.

#### MODIFIED Scenario: filterNavItems with ADMIN role returns all 12 NAVIGATION_ITEMS — corrected path
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** the result has exactly 12 items
- **THEN** the result includes paths `/stock/products`, `/stock/categories`, `/stock/ingredients`, `/stock/inventory`
- **THEN** the result includes path `/pedidos-panel`
- **THEN** the result includes paths `/admin/users`, `/admin/metricas`
- **THEN** the result includes CLIENT paths `/catalog`, `/cart`, `/orders`, `/profile`, `/addresses`

---

## ADDED Requirements

### Requirement: ADMIN dashboard Métricas navigation entry SHALL point to /admin/metricas

The system SHALL update the "Métricas" entry in `NAVIGATION_ITEMS` (`src/shared/lib/navigation/items.ts`) to use `path: '/admin/metricas'` (Spanish-language route). The `allowedRoles: ['ADMIN']` and `label: 'Métricas'` fields SHALL remain unchanged. This delta corrects the path from the placeholder `/admin/metrics` (English) established in Change 08.

The `resolveDefaultRoute` function SHALL continue to return `/admin` for the `'ADMIN'` role (unchanged). The router's redirect to `/admin/metricas` handles the final landing.

#### Scenario: ADMIN navigation includes Métricas item pointing to /admin/metricas
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** the result includes an item with `path: '/admin/metricas'` and `label: 'Métricas'`

#### Scenario: Path correction does not affect other ADMIN items
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** Usuarios item still has `path: '/admin/users'`
- **THEN** no other item paths are changed by this delta
