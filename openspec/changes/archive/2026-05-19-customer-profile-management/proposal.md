## Why

Food Store users (rol CLIENT) can register and log in but have no way to view or modify their own profile data or change their password after the fact. This gap blocks a core self-service expectation and leaves active sessions un-revocable from the user side when credentials must be rotated. Change 13 closes that gap by delivering the full customer profile self-management capability — read, edit, and password change — all built on top of the auth infrastructure that Change 07 already shipped.

**Historias de usuario cubiertas**: US-061, US-062, US-063.

**Sprint**: Sprint 3 — Catálogo II + Perfil (Change 13 of the consolidated roadmap).

**Dependencias upstream** (archivadas):
- Change 07 — `auth-refresh-logout-rbac-me` (archivado 2026-05-17): provee `GET /api/v1/auth/me`, `get_current_user`, `require_role`, `RefreshToken.revoke_family`, rotación con replay detection, interceptor frontend de refresh, `authStore.logout()` síncrono. Este change construye sobre todo ello; no lo rediseña.

---

## What Changes

### Backend — Nuevo módulo `profile/`

- **NEW** `PATCH /api/v1/profile/me` — actualiza campos editables del usuario autenticado (`nombre`, `apellido`). El `email` es inmutable: si aparece en el body se descarta silenciosamente (campo ignorado, no error). Devuelve `UserRead` actualizado. HTTP 200.
- **NEW** `POST /api/v1/profile/me/password` — cambia la contraseña del usuario autenticado. Body: `{ current_password, new_password }`. Verifica `current_password` con bcrypt antes de hashear la nueva. En éxito: actualiza el hash + revoca **todos** los `RefreshToken` del usuario atómicamente en una sola transacción (single `UnitOfWork`). Devuelve HTTP 204 No Content. Rate limit: 5/15min por usuario.
- **NEW** `backend/app/schemas/profile.py` — schemas Pydantic v2: `ProfileUpdate`, `PasswordChangeRequest`, `UserRead` (reutilizado de auth si ya existe, o definido aquí).
- **NEW** `backend/app/services/profile.py` — `ProfileService` con métodos `update_profile` y `change_password` como `@staticmethod`.
- **NEW** `backend/app/api/v1/profile.py` — `profile_router` con los dos endpoints.
- **MODIFIED** `backend/app/api/v1/router.py` — registra `profile_router` bajo `/profile`.
- ~~**MODIFIED** `backend/app/core/uow.py`~~ — `uow.refresh_tokens` ya existe desde Change 07; `uow.py` NO requiere cambios en este change. El método `revoke_all_for_user(user_id)` se agrega únicamente al `RefreshTokenRepository` en `backend/app/repositories/user.py`.
- **NEW** `backend/app/repositories/user.py` — agrega método `revoke_all_for_user(user_id)` a `RefreshTokenRepository` (revoca todos los tokens activos del usuario con `revoked_at = now()`).

### Frontend — Página `/profile`

- **MODIFIED** `frontend/src/pages/ProfilePage/` — reemplaza el placeholder creado en Change 08 con la página real. Compone dos forms independientes.
- **NEW** `frontend/src/features/profile/EditProfileForm.tsx` — formulario TanStack Form que llama `PATCH /api/v1/profile/me`. Estado: loading, success, error.
- **NEW** `frontend/src/features/profile/ChangePasswordForm.tsx` — formulario TanStack Form que llama `POST /api/v1/profile/me/password`. Campo `password_confirm` solo existe en el cliente, nunca se envía al backend.
- **NEW** `frontend/src/features/profile/hooks/useUpdateProfile.ts` — TanStack Query mutation hook.
- **NEW** `frontend/src/features/profile/hooks/useChangePassword.ts` — TanStack Query mutation hook; en éxito, llama `authStore.logout()` y redirige a `/login`.
- **MODIFIED** `frontend/src/shared/api/endpoints.ts` — agrega constantes `PROFILE_ME` y `PROFILE_ME_PASSWORD`.

---

## Capabilities

### New Capabilities

- `backend-profile-management`: Módulo de gestión del perfil del cliente en el backend. Cubre schemas (`ProfileUpdate`, `PasswordChangeRequest`), método de repositorio `revoke_all_for_user`, `ProfileService` con `update_profile` y `change_password`, `profile_router` con los dos endpoints, rate limiting en password change.
- `frontend-profile-page`: Página `/profile` con dos formularios desacoplados (`EditProfileForm`, `ChangePasswordForm`), hooks TanStack Query, manejo de estados (loading/success/error/session-expired) y flujo de logout post-cambio de contraseña.

### Modified Capabilities

- `backend-api-v1-router`: Registrar `profile_router` bajo prefijo `/profile` en `build_v1_router`.
- `backend-auth-refresh-rotation`: Documentar el escenario aditivo: cuando `change_password` revoca TODOS los tokens del usuario vía `revoke_all_for_user`, los intentos de refresh posteriores encuentran sus tokens con `revoked_at IS NOT NULL` → el router trata esto como un caso normal de "token inválido/revocado" (HTTP 401 `invalid_token`), NO como replay (la revocación es voluntaria, no por ataque detectado). No hay cambio de comportamiento en el algoritmo de rotación — solo se documenta este camino adicional.
- `frontend-routing`: Reemplazar el placeholder `ProfilePage` en la entrada `/profile` del router por el componente real importado desde `features/profile` o `pages/ProfilePage`.

---

## Impact

- **Backend** — Archivos nuevos: `backend/app/schemas/profile.py`, `backend/app/services/profile.py`, `backend/app/api/v1/profile.py`. Archivos modificados: `backend/app/repositories/user.py` (nuevo método `revoke_all_for_user`), `backend/app/api/v1/router.py` (registro del router). `backend/app/core/uow.py` NO se modifica — `uow.refresh_tokens` ya existe desde Change 07.
- **Frontend** — Archivos nuevos: `frontend/src/features/profile/EditProfileForm.tsx`, `frontend/src/features/profile/ChangePasswordForm.tsx`, `frontend/src/features/profile/hooks/useUpdateProfile.ts`, `frontend/src/features/profile/hooks/useChangePassword.ts`, `frontend/src/features/profile/index.ts`, `frontend/src/pages/ProfilePage/index.tsx`. Archivos modificados: `frontend/src/shared/api/endpoints.ts`.
- **Database** — Sin migraciones: no se agrega ninguna columna al modelo `Usuario`. Los campos `nombre` y `apellido` ya existen (verificado en `backend/app/models/user.py`). El campo `telefono` NO existe en el modelo actual; se excluye del scope.
- **Auth** — `POST /api/v1/profile/me/password` invalida todas las sesiones activas del usuario. El access token vigente en el cliente sigue siendo válido hasta su expiración natural (30 min) — ventana residual aceptada y documentada (ver design.md § Decisions).
- **No migraciones Alembic en este change.**
- **No nuevas dependencias de paquetes** más allá de lo ya instalado en Changes 06 y 07 (bcrypt, python-jose, slowapi).

---

## Restricciones críticas

1. **Email inmutable** — el campo `email` no figura en `ProfileUpdate`. Si aparece en el PATCH body, el servidor lo ignora silenciosamente (Pydantic `model_config = ConfigDict(extra='ignore')`). No se devuelve error para evitar enumeración.
2. **Auto-operación únicamente** — no existe endpoint `/profile/{id}`. El `user_id` se extrae siempre del JWT vía `get_current_user`. Ningún parámetro de path o body puede sobreescribirlo.
3. **Atomicidad en password change** — la actualización del `password_hash` y la revocación de todos los `RefreshToken` del usuario ocurren en la MISMA transacción (single `UnitOfWork`). Estado parcial es imposible por diseño.
4. **Ventana residual de access token** — el access token del cliente sigue siendo válido hasta 30 min post-cambio de contraseña. Decisión: Opción (a) — aceptada y documentada. No se introduce `password_changed_at` claim en este change.
5. **Sin nuevas dependencias de paquetes.**
6. **Sin acoplamiento con catálogo (Changes 11/12), direcciones (Change 14), carrito (Change 15) ni admin usuarios (Change 21).**
7. **Formularios frontend desacoplados** — dos componentes, dos hooks, dos mutaciones TanStack Query.
8. **Campo `telefono`** — no existe en el modelo `Usuario` actual (verificado). Excluido del scope de este change. La arquitectura queda abierta para agregarlo en un change futuro con migración.

---

## Notas / Decisiones

- **Discrepancia de sprint**: el brief del usuario menciona "Sprint 2"; el roadmap (`docs/CHANGES.md`) posiciona este change en **Sprint 3** (junto a Changes 11 y 12). Se sigue el roadmap como fuente de verdad.
- **Namespace `profile/` en lugar de ampliar `auth/`**: los endpoints de auth gestionan sesiones y tokens; los endpoints de perfil gestionan datos del usuario. Mantener namespaces separados mejora la legibilidad del contrato de API y el ownership del código. Decisión definitiva en design.md § Decisions D-01.
- **`GET /api/v1/auth/me` no se modifica**: ya entrega el perfil completo. La página `/profile` lo consume directamente como endpoint de lectura. No se crea un endpoint de lectura duplicado en `/profile`.
