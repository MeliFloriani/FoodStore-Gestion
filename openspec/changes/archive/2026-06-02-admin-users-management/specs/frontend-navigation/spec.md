## MODIFIED Requirements

### Requirement: ADMIN-only navigation item /admin/users SHALL be present and functional

The `frontend-navigation` spec (Change 08) already declares the "Usuarios" navigation item in `NAVIGATION_ITEMS`. Change 21 activates the real implementation at `/admin/users`. The `NAVIGATION_ITEMS` array in `src/shared/lib/navigation/items.ts` MUST contain exactly one entry with `path: '/admin/users'` and `allowedRoles: ['ADMIN']`.

The item SHALL be listed under ADMIN-only items:
```typescript
{ key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] }
```

No modification to `src/shared/lib/navigation/items.ts` is required for Change 21 — this requirement documents the existing invariant that Change 21 relies upon. If the item is missing, it MUST be added.

#### Scenario: ADMIN user sees Usuarios in navigation
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** result includes `{ path: '/admin/users', label: 'Usuarios' }`

#### Scenario: Non-ADMIN user does not see Usuarios in navigation
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])` is called
- **THEN** result does NOT include any item with `path: '/admin/users'`
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['STOCK'])` is called
- **THEN** result does NOT include any item with `path: '/admin/users'`

#### Scenario: Navigation entry is already present — no duplicate needed
- **WHEN** `NAVIGATION_ITEMS` is imported after Change 08 and Change 21 are both applied
- **THEN** exactly one entry with `path: '/admin/users'` exists (no duplicates)
