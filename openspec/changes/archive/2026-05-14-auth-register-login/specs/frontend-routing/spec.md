## MODIFIED Requirements

### Requirement: Three layout tiers (RootLayout, AuthLayout, AppLayout)
The router SHALL define three nested layout routes:

- `RootLayout` (`src/app/layouts/RootLayout.tsx`): outermost shell, wraps all routes. Listens for `auth:expired` DOM event and navigates to `/login`. Renders `<Outlet />`.
- `AuthLayout` (`src/app/layouts/AuthLayout.tsx`): wraps public-only routes (`/login`, `/register`). SHALL check `authStore.status` (NOT `accessToken`): if `status === 'idle'` **OR** `status === 'authenticating'` (NEW — inflight login/register), render a full-screen spinner/loading state (not a redirect); if `status === 'authenticated'`, redirect to `/`; if `status === 'unauthenticated'`, render the auth content (login/register).
- `AppLayout` (`src/app/layouts/AppLayout.tsx`): wraps protected routes. Includes a structural navigation placeholder (no business UI). Renders `<Outlet />`.

**MODIFIED behavior**: `AuthLayout` previously showed the spinner guard only for `status === 'idle'`. It now also covers `status === 'authenticating'` so that login and register form submissions do not flash the auth page content while the server round-trip is in progress.

> **Constraint — no flash of auth UI during inflight requests**: The `status: 'authenticating'` state is set by `authStore` when a login or register request is in flight. `AuthLayout` MUST render the loading state during this window to prevent the auth form from being re-rendered mid-submission.

#### Scenario: AuthLayout redirects authenticated user
- **WHEN** a user with `status: 'authenticated'` navigates to `/login`
- **THEN** they are redirected to `/`

#### Scenario: AuthLayout shows loading on idle status
- **WHEN** a user navigates to `/login` with `status: 'idle'` (rehydration in progress)
- **THEN** a full-screen loading state is shown (no redirect)

#### Scenario: AuthLayout shows loading on authenticating status
- **WHEN** `authStore.status` is `'authenticating'` (login or register in flight) and the user is on `/login` or `/register`
- **THEN** a full-screen loading state (spinner) is shown instead of the auth form
- **THEN** no redirect occurs

#### Scenario: AuthLayout renders login page when unauthenticated
- **WHEN** a user navigates to `/login` with `status: 'unauthenticated'`
- **THEN** the login page is rendered

#### Scenario: RootLayout listens for auth:expired
- **WHEN** the `auth:expired` custom event is dispatched on `window`
- **THEN** the user is navigated to `/login`
