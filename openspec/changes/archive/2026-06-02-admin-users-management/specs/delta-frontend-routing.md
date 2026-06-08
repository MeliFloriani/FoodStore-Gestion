# DELTA: frontend-routing

**Change**: admin-users-management (Change 21)  
**Base spec**: `openspec/specs/frontend-routing/spec.md`  

---

## ADDED Requirements

### Requirement: /admin/users subroute within /admin/* tree

The React router SHALL add a subroute `users` inside the existing `/admin/*` `RoleGuard roles={['ADMIN']}` tree.

The `RoleGuard roles={['ADMIN']}` from the parent `/admin/*` route already provides role enforcement. The subroute MUST NOT add a redundant inner `RoleGuard`. Instead, the `Suspense` boundary is placed directly inside the existing guard-protected subtree, following the guard-before-Suspense invariant from `frontend-route-guards`.

Route definition to add within the `/admin/*` subtree:
```tsx
<Route
  path="users"
  element={
    <Suspense fallback={<PageSpinner />}>
      <AdminUsersPage />
    </Suspense>
  }
/>
```

Where:
- `AdminUsersPage` is React.lazy: `const AdminUsersPage = React.lazy(() => import('@/pages/AdminUsersPage'))`.
- The outer `RoleGuard roles={['ADMIN']}` is inherited from the `/admin/*` parent route.

#### Scenario: ADMIN user can access /admin/users
- **WHEN** an authenticated user with `roles: ['ADMIN']` navigates to `/admin/users`
- **THEN** the `RoleGuard` from the parent `/admin/*` route passes (reason: 'ok')
- **THEN** `AdminUsersPage` is rendered after the lazy import resolves

#### Scenario: CLIENT user is blocked from /admin/users (inherited guard)
- **WHEN** an authenticated user with `roles: ['CLIENT']` navigates to `/admin/users`
- **THEN** the parent `RoleGuard roles={['ADMIN']}` fires first
- **THEN** user is redirected to `/403` (reason: 'forbidden')
- **THEN** the `AdminUsersPage` lazy chunk is NOT downloaded

#### Scenario: Existing /admin/* subtree routes are unaffected
- **WHEN** `/admin/users` is added to the router
- **THEN** any other routes in the `/admin/*` subtree remain operational
- **THEN** no path matching conflicts arise

#### Scenario: /admin/users redirects unauthenticated user to login
- **WHEN** an unauthenticated user navigates to `/admin/users`
- **THEN** `ProtectedRoute` (wrapping all private routes) redirects to `/login`
- **THEN** the parent `RoleGuard` is not reached
