# frontend-profile-page Specification

## Purpose
Frontend profile page capability. Introduced in Change 13 (customer-profile-management). Provides the real ProfilePage implementation replacing the Change 08 placeholder, along with EditProfileForm, ChangePasswordForm, and supporting hooks.

## Requirements

### Requirement: ProfilePage composes two decoupled forms
`frontend/src/pages/ProfilePage/index.tsx` SHALL render the real profile page (replacing the Change 08 placeholder). It SHALL:
- Load the current user profile by consuming `GET /api/v1/auth/me` via TanStack Query (the existing `useCurrentUser` hook or equivalent).
- Render an `EditProfileForm` component (feature layer).
- Render a `ChangePasswordForm` component (feature layer), visually separated.
- The two forms SHALL be fully decoupled — different components, different TanStack Query mutations, different submission handlers.
- Show a loading skeleton while the profile data is loading.
- Require authentication (route is already protected by `RoleGuard roles={['CLIENT','ADMIN']}` from Change 08).

#### Scenario: ProfilePage renders both forms for an authenticated user
- **WHEN** an authenticated CLIENT navigates to `/profile`
- **THEN** both `EditProfileForm` and `ChangePasswordForm` are visible on the page
- **THEN** the `EditProfileForm` fields are pre-filled with the current user's `nombre` and `apellido`
- **THEN** the email field is visible but disabled/read-only

#### Scenario: ProfilePage shows loading skeleton while fetching
- **WHEN** the profile data is in loading state
- **THEN** a loading skeleton or spinner is shown instead of the form fields

---

### Requirement: EditProfileForm — profile data mutation
`frontend/src/features/profile/EditProfileForm.tsx` SHALL:
- Use TanStack Form to manage form state.
- Fields: `nombre` (text, required, max 80), `apellido` (text, required, max 80), `email` (text, disabled, read-only — never in the submit payload).
- On submit, call the `useUpdateProfile` mutation hook with `{ nombre, apellido }` only. `email` SHALL NOT appear in the request body.
- Display loading state on the submit button during the mutation.
- On success: show a success toast notification; invalidate the `useCurrentUser` query cache.
- On error: map HTTP error codes to user-friendly messages inline.
- Frontend validation rules (replicated from backend, for instant UX feedback): `nombre` and `apellido` non-empty, max 80 chars.

#### Scenario: EditProfileForm submits without email field
- **WHEN** user submits the EditProfileForm
- **THEN** the HTTP request body contains `nombre` and `apellido` only
- **THEN** the body does NOT contain an `email` field

#### Scenario: EditProfileForm shows success toast on 200 response
- **WHEN** `PATCH /api/v1/profile/me` returns HTTP 200
- **THEN** a success toast notification is displayed
- **THEN** the form remains on the page (no redirect)

#### Scenario: EditProfileForm shows loading state on submit
- **WHEN** the form is submitted and the mutation is pending
- **THEN** the submit button is disabled and shows a loading indicator

#### Scenario: EditProfileForm shows validation error for empty nombre
- **WHEN** user clears the `nombre` field and submits
- **THEN** an inline validation error is displayed on the `nombre` field
- **THEN** no HTTP request is made

---

### Requirement: useUpdateProfile hook
`frontend/src/features/profile/hooks/useUpdateProfile.ts` SHALL define a TanStack Query `useMutation` hook that:
- Calls `PATCH /api/v1/profile/me` via Axios with the `ProfileUpdate` payload.
- Returns the standard mutation state (`isLoading`, `isError`, `isSuccess`, `error`, `mutate`/`mutateAsync`).
- On success, invalidates the query key associated with `GET /api/v1/auth/me` so the `authStore` user data can be refreshed if needed.

#### Scenario: useUpdateProfile sends PATCH to correct endpoint
- **WHEN** `mutate({ nombre: "Test", apellido: "User" })` is called
- **THEN** an HTTP PATCH request is sent to `/api/v1/profile/me` with body `{ "nombre": "Test", "apellido": "User" }`

#### Scenario: useUpdateProfile invalidates user cache on success
- **WHEN** the mutation succeeds
- **THEN** the TanStack Query cache entry for `/api/v1/auth/me` is invalidated

---

### Requirement: ChangePasswordForm — password mutation
`frontend/src/features/profile/ChangePasswordForm.tsx` SHALL:
- Use TanStack Form to manage form state.
- Fields: `current_password` (password input), `new_password` (password input), `password_confirm` (password input).
- `password_confirm` is a client-side only field — it SHALL NEVER appear in the HTTP request body.
- On submit, call the `useChangePassword` mutation hook with `{ current_password, new_password }` only.
- Frontend validation: `new_password` min 8 chars; `password_confirm` must equal `new_password`.
- Display loading state on the submit button during the mutation.
- On success (204): show "Contraseña actualizada. Cerrando sesión..." toast, then call `authStore.logout()` and `navigate('/login')`.
- On 409 (`CURRENT_PASSWORD_MISMATCH`): show inline error on `current_password` field.
- On 429: show "Demasiados intentos. Espera 15 minutos." toast.
- On 422: map Pydantic error details to form fields.

#### Scenario: ChangePasswordForm submits without password_confirm field
- **WHEN** user submits the ChangePasswordForm
- **THEN** the HTTP request body contains `current_password` and `new_password` only
- **THEN** the body does NOT contain `password_confirm`

#### Scenario: ChangePasswordForm shows inline error on 409
- **WHEN** the mutation returns HTTP 409 with `code="CURRENT_PASSWORD_MISMATCH"`
- **THEN** an inline error message is displayed on the `current_password` field
- **THEN** the user remains on the page

#### Scenario: ChangePasswordForm logs out and redirects on success
- **WHEN** the mutation returns HTTP 204
- **THEN** `authStore.logout()` is called
- **THEN** the user is redirected to `/login`

#### Scenario: ChangePasswordForm validates password_confirm equality client-side
- **WHEN** `new_password` and `password_confirm` do not match
- **THEN** an inline error is displayed on `password_confirm`
- **THEN** no HTTP request is made

#### Scenario: ChangePasswordForm shows rate limit error on 429
- **WHEN** the mutation returns HTTP 429
- **THEN** a toast error "Demasiados intentos. Espera 15 minutos." is displayed
- **THEN** the user remains on the page

---

### Requirement: useChangePassword hook
`frontend/src/features/profile/hooks/useChangePassword.ts` SHALL define a TanStack Query `useMutation` hook that:
- Calls `POST /api/v1/profile/me/password` via Axios with `{ current_password, new_password }`.
- Returns standard mutation state.
- Does NOT call `authStore.logout()` directly — the caller (`ChangePasswordForm`) is responsible for the logout+redirect flow on `onSuccess`.

#### Scenario: useChangePassword sends POST to correct endpoint
- **WHEN** `mutate({ current_password: "OldPass1", new_password: "NewPass1" })` is called
- **THEN** an HTTP POST request is sent to `/api/v1/profile/me/password` with the correct body
- **THEN** the body does NOT contain `password_confirm`

#### Scenario: useChangePassword returns isError=true on 409
- **WHEN** the server returns HTTP 409
- **THEN** `isError` is `true`
- **THEN** `error` contains the HTTP error response

---

### Requirement: PROFILE_ME and PROFILE_ME_PASSWORD endpoint constants
`frontend/src/shared/api/endpoints.ts` SHALL add:
- `PROFILE_ME: '/api/v1/profile/me'`
- `PROFILE_ME_PASSWORD: '/api/v1/profile/me/password'`

These constants SHALL be used by `useUpdateProfile` and `useChangePassword` hooks respectively.

#### Scenario: Endpoint constants are exported from endpoints.ts
- **WHEN** `PROFILE_ME` and `PROFILE_ME_PASSWORD` are imported from `endpoints.ts`
- **THEN** they equal `'/api/v1/profile/me'` and `'/api/v1/profile/me/password'` respectively
