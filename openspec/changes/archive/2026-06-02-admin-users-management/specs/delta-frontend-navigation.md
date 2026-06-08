# DELTA: frontend-navigation

**Change**: admin-users-management (Change 21)  
**Base spec**: `openspec/specs/frontend-navigation/spec.md`  

---

## CLARIFICATION (No code change required)

### Requirement: ADMIN-only navigation item /admin/users already declared

The `frontend-navigation` spec (Change 08) already declares the "Usuarios" navigation item in `NAVIGATION_ITEMS`:
```typescript
{ key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] }
```

This item is listed under ADMIN-only items and correctly uses `allowedRoles: ['ADMIN']`.

**No modification to `src/shared/lib/navigation/items.ts` is required for Change 21.**

This delta spec documents that:
1. The `/admin/users` route now has a real implementation (previously the `/admin/*` subtree used a placeholder `AdminPage`).
2. The navigation item was always in place — it is now functional.
3. The item correctly restricts to `['ADMIN']` — `filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])` excludes it.

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
