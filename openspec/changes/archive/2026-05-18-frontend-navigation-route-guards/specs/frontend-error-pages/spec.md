# frontend-error-pages Specification

## Purpose
Define the three error page components for the Food Store frontend: `UnauthorizedPage` (/401), `ForbiddenPage` (/403), and `NotFoundPage` (/404). These pages are FSD `pages/` layer components — they may use router hooks and shared UI primitives, but contain no business logic, no API calls, and no feature-level imports. They are accessible without authentication (registered under `PublicLayout` in the route tree).

## Requirements

### Requirement: UnauthorizedPage (/401)
`src/pages/errors/UnauthorizedPage.tsx` SHALL be a React component that renders a 401 Unauthorized message. It SHALL:
1. Render a visible "401" status code and a human-readable message (e.g., "Session expired. Please log in again.").
2. Render a link or button to navigate to `/login`.
3. NOT import any `features/` module.
4. NOT perform any API call.
5. Be lazy-exportable (default export, compatible with `React.lazy`).

This page is rendered when the user has no valid session (expired or missing token). In the current change it is a placeholder — the actual 401 flow is still handled by `RootLayout`'s `auth:expired` event listener (Change 07). The `/401` route provides a fallback target for future explicit 401 redirects from the HTTP client.

#### Scenario: UnauthorizedPage renders visible 401 message
- **WHEN** a user navigates to `/401`
- **THEN** the page renders without error
- **THEN** a "401" indicator and a message about the session are visible

#### Scenario: UnauthorizedPage provides a path to login
- **WHEN** the `/401` page is rendered
- **THEN** a link to `/login` is present

---

### Requirement: ForbiddenPage (/403)
`src/pages/errors/ForbiddenPage.tsx` SHALL be a React component that renders a 403 Forbidden message. It SHALL:
1. Render a visible "403" status code and a human-readable message (e.g., "You don't have permission to access this page.").
2. Optionally read `location.state?.from` (via `useLocation()`) to display the attempted path.
3. Render a CTA to navigate to `/catalog` (hard-coded). CTA navigation target: hard-coded `/catalog` (this page is a foundation placeholder; role-aware redirect can be added in Change 24 design system or later). Rationale: ForbiddenPage must not depend on auth state — it must render correctly even in edge cases where the store is partially hydrated or roles are unavailable.
4. NOT import any `features/` module.
5. NOT perform any API call.
6. Be lazy-exportable (default export, compatible with `React.lazy`).

`RoleGuard` redirects to `/403` with `state={{ from: location }}` — `ForbiddenPage` MAY display the attempted path for user clarity, but this is not required in this change (placeholder behavior is acceptable).

#### Scenario: ForbiddenPage renders visible 403 message
- **WHEN** a user is redirected to `/403` by `RoleGuard`
- **THEN** the page renders without error
- **THEN** a "403" indicator and a permissions message are visible

#### Scenario: ForbiddenPage provides a path back
- **WHEN** the `/403` page is rendered
- **THEN** a navigation link to a valid accessible route is present (e.g., `/catalog`)

---

### Requirement: NotFoundPage (/404)
`src/pages/errors/NotFoundPage.tsx` SHALL be a React component that renders a 404 Not Found message. It SHALL:
1. Render a visible "404" status code and a human-readable message (e.g., "Page not found.").
2. Render a link to return to `/catalog` or the application home.
3. NOT import any `features/` module.
4. NOT perform any API call.
5. Be lazy-exportable (default export, compatible with `React.lazy`).

This page is the target of the router catch-all `*` route.

#### Scenario: NotFoundPage renders for unmatched routes
- **WHEN** a user navigates to a path that matches no registered route (e.g., `/nonexistent-path`)
- **THEN** the router redirects to `/404`
- **THEN** the `NotFoundPage` renders without error

#### Scenario: NotFoundPage provides a path home
- **WHEN** the `/404` page is rendered
- **THEN** a link to `/catalog` or a home route is present

---

### Requirement: Error pages are publicly accessible
All three error pages SHALL be registered under the `PublicLayout` branch in the route tree. They SHALL be accessible to unauthenticated users. This is necessary because:
- A user may be redirected to `/403` or `/401` while unauthenticated (unlikely but possible via direct URL access).
- `/404` must always be accessible.

#### Scenario: Unauthenticated user can access error pages
- **WHEN** an unauthenticated user navigates directly to `/401`, `/403`, or `/404`
- **THEN** the respective page renders without redirect to `/login`

---

### Requirement: Error pages have no business logic
All three error pages (`UnauthorizedPage`, `ForbiddenPage`, `NotFoundPage`) SHALL be minimal structural components. They SHALL NOT:
- Import from `features/`.
- Import from `entities/`.
- Call any API endpoint.
- Import or use any Zustand store directly (router hooks from `react-router-dom` are allowed).
- Contain conditional rendering based on auth state beyond what is needed for the "go to your home" CTA.

#### Scenario: Error page renders without store access
- **WHEN** any error page renders with no auth store initialized
- **THEN** the page renders without throwing or reading undefined store state

## Acceptance

- `UnauthorizedPage` SHALL render at `/401` without auth guard.
- `ForbiddenPage` SHALL render at `/403` without auth guard.
- `NotFoundPage` SHALL render at `/404` without auth guard.
- The catch-all `*` route SHALL redirect to `/404`.
- All three error pages SHALL have a default export compatible with `React.lazy`.
- No error page SHALL import from `features/`.
- `ForbiddenPage` SHALL contain a navigable link to a valid accessible route.
- All three pages SHALL render without errors when `authStore` is in any state.
