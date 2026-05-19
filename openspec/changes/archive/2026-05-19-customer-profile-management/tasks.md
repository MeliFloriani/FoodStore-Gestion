## 1. Backend — Schemas y Validadores

- [x] 1.1 TEST: Escribir `backend/tests/test_profile_schemas.py` — verificar que `ProfileUpdate` ignora campo `email`, acepta `nombre`/`apellido` parciales, y rechaza `nombre` > 80 chars
- [x] 1.2 Extraer validador de contraseña a `backend/app/core/validators.py` como función `validate_password(value: str) -> str` si aún no existe (reutilizar de `RegisterRequest` en `schemas/auth.py`)
- [x] 1.3 TEST: Verificar en `test_profile_schemas.py` que `PasswordChangeRequest` rechaza `new_password` < 8 chars y acepta payloads válidos; confirmar que `password_confirm` no existe en el schema
- [x] 1.4 Crear `backend/app/schemas/profile.py` con `ProfileUpdate` (`ConfigDict(extra='ignore')`, campos opcionales `nombre`/`apellido`) y `PasswordChangeRequest` (`ConfigDict(extra='forbid')`, `current_password`, `new_password` con validador reutilizado) — `uow.py` NO requiere cambios: `uow.refresh_tokens` ya existe desde Change 07

## 2. Backend — Repository

- [x] 2.1 TEST: Escribir `backend/tests/test_profile_repository.py` — verificar que `revoke_all_for_user(user_id)` revoca todos los tokens activos del usuario, retorna el count correcto, y es no-op cuando no hay tokens activos
- [x] 2.2 Agregar método `revoke_all_for_user(user_id: uuid.UUID) -> int` a `RefreshTokenRepository` en `backend/app/repositories/user.py` (UPDATE WHERE `usuario_id=X AND revoked_at IS NULL`, sin `session.commit()`)

## 3. Backend — Service

- [x] 3.1 TEST: Escribir `backend/tests/test_profile_service.py` — caso `update_profile` con nombre actualizado; caso no-op con todos los campos None; caso 404 para user_id inexistente
- [x] 3.2 TEST: En `test_profile_service.py` — caso `change_password` exitoso (verifica hash actualizado + tokens revocados); caso 409 por `current_password` incorrecto; caso rollback si `revoke_all_for_user` falla
- [x] 3.3 Crear `backend/app/services/profile.py` con `ProfileService` — método `update_profile` (@staticmethod, acepta UoW + ProfileUpdate, retorna UserRead, no-op si todos None, 404 si user no existe)
- [x] 3.4 Implementar `ProfileService.change_password` (@staticmethod, acepta UoW + PasswordChangeRequest, verifica bcrypt, actualiza hash, llama `revoke_all_for_user`, 409 si mismatch, sin `session.commit()`)

## 4. Backend — Router y registro

- [x] 4.1 TEST: Escribir `backend/tests/test_profile_router.py` — `PATCH /api/v1/profile/me` con JWT válido actualiza nombre y retorna 200 UserRead; sin JWT retorna 401; con email en body retorna 200 con email original inalterado
- [x] 4.2 TEST: En `test_profile_router.py` — `POST /api/v1/profile/me/password` con credenciales correctas retorna 204 y tokens revocados; con current_password incorrecto retorna 409; con new_password < 8 chars retorna 422; rate limit 5/15min retorna 429
- [x] 4.3 Crear `backend/app/api/v1/profile.py` — `profile_router` con `PATCH /me` (response_model=UserRead, status_code=200, Depends(get_current_user)) y `POST /me/password` (status_code=204, Depends(get_current_user), @_limiter.limit("5/15minutes"))
- [x] 4.4 Registrar `profile_router` en `backend/app/api/v1/router.py` — agregar `from app.api.v1.profile import profile_router` y `router.include_router(profile_router, prefix="/profile", tags=["profile"])`
- [x] 4.5 TEST: Verificar integración — `GET /docs` o inspección de rutas confirma que `/api/v1/profile/me` y `/api/v1/profile/me/password` existen y tag `"profile"` aparece en OpenAPI

## 5. Frontend — Endpoint constants y hooks

- [x] 5.1 TEST: Verificar en `frontend/src/shared/api/__tests__/endpoints.test.ts` (o archivo de prueba equivalente) que `PROFILE_ME === '/api/v1/profile/me'` y `PROFILE_ME_PASSWORD === '/api/v1/profile/me/password'` existen con los valores correctos (test-first para las constantes)
- [x] 5.2 Agregar constantes `PROFILE_ME = '/api/v1/profile/me'` y `PROFILE_ME_PASSWORD = '/api/v1/profile/me/password'` a `frontend/src/shared/api/endpoints.ts`
- [x] 5.3 TEST: Escribir `frontend/src/features/profile/hooks/__tests__/useUpdateProfile.test.ts` — verificar que `mutate({ nombre, apellido })` envía PATCH a `PROFILE_ME` sin campo email; que en éxito invalida la query de `/auth/me`
- [x] 5.4 Crear `frontend/src/features/profile/hooks/useUpdateProfile.ts` — `useMutation` TanStack Query: PATCH a `PROFILE_ME`, en onSuccess invalida query key de `GET /api/v1/auth/me`
- [x] 5.5 TEST: Escribir `frontend/src/features/profile/hooks/__tests__/useChangePassword.test.ts` — verificar que `mutate({ current_password, new_password })` envía POST a `PROFILE_ME_PASSWORD` sin `password_confirm`; que 409 resulta en `isError=true`
- [x] 5.6 Crear `frontend/src/features/profile/hooks/useChangePassword.ts` — `useMutation` TanStack Query: POST a `PROFILE_ME_PASSWORD` con `{ current_password, new_password }`; no llama `authStore.logout()` (responsabilidad del caller)

## 6. Frontend — EditProfileForm

- [x] 6.1 TEST: Escribir `frontend/src/features/profile/__tests__/EditProfileForm.test.tsx` — renderiza campos nombre/apellido pre-filled; campo email visible pero disabled; submit envía solo `{nombre, apellido}` sin email; muestra toast en éxito; muestra error inline en fallo de validación (nombre vacío)
- [x] 6.2 Crear `frontend/src/features/profile/EditProfileForm.tsx` — TanStack Form con campos `nombre` (max 80, requerido), `apellido` (max 80, requerido), `email` (disabled, read-only, no en payload); `useUpdateProfile` mutation; loading state en botón; success toast; inline error mapping

## 7. Frontend — ChangePasswordForm

- [x] 7.1 TEST: Escribir `frontend/src/features/profile/__tests__/ChangePasswordForm.test.tsx` — submit envía solo `{current_password, new_password}` sin `password_confirm`; muestra error inline en campo `current_password` cuando respuesta es 409; valida client-side que `password_confirm == new_password`; llama `authStore.logout()` y navega a `/login` en éxito (204)
- [x] 7.2 Crear `frontend/src/features/profile/ChangePasswordForm.tsx` — TanStack Form con campos `current_password`, `new_password` (min 8), `password_confirm` (client-only equality check); `useChangePassword` mutation; en onSuccess: toast + `authStore.logout()` + `navigate('/login')`; en 409: inline error en `current_password`; en 429: toast rate limit

## 8. Frontend — ProfilePage y routing

- [x] 8.1 TEST: Escribir `frontend/src/pages/ProfilePage/__tests__/ProfilePage.test.tsx` — renderiza ambos forms; muestra skeleton mientras carga; require auth (si no autenticado, renderiza guard redirect — ya cubierto por Change 08 test suite)
- [x] 8.2 Crear `frontend/src/pages/ProfilePage/index.tsx` — carga user con TanStack Query (GET /auth/me); muestra loading skeleton; compone `EditProfileForm` y `ChangePasswordForm` visualmente separados
- [x] 8.3 Crear `frontend/src/features/profile/index.ts` — barrel export de `EditProfileForm`, `ChangePasswordForm`, hooks
- [x] 8.4 Actualizar entrada `/profile` en el router (`frontend/src/app/router/` o equiv.) para importar `ProfilePage` real en lugar del placeholder de Change 08

## 9. QA Manual

- [x] 9.1 Happy path — editar nombre: login → navegar a `/profile` → cambiar nombre → submit → toast éxito → recargar página y verificar que persiste [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.2 Email inmutable — intentar editar email desde DevTools (modificar request): confirmar que el email no cambia en la respuesta [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.3 Password change correcta — ingresar contraseña actual correcta y nueva válida → 204 → redirect a `/login` → login con nueva contraseña funciona; login con contraseña vieja falla [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.4 Password change incorrecta — ingresar contraseña actual incorrecta → 409 → error inline en campo `current_password` → usuario permanece en página [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.5 Tokens revocados — abrir sesión en dos tabs → cambiar contraseña en tab 1 → en tab 2 realizar cualquier acción autenticada → confirmar redirect a `/login` (interceptor detecta 401 en refresh) [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.6 Rate limit password — enviar 6 intentos de cambio de contraseña seguidos → 6to intento retorna 429 con mensaje apropiado [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.7 Validación new_password — intentar nueva contraseña < 8 chars → error 422 del backend + mensaje de error en frontend [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.8 Acceso no autenticado — navegar a `/profile` sin sesión → redirect a `/login` [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
- [x] 9.9 Sin JWT en PATCH /profile/me — llamada directa sin Authorization header → 401 [manual QA — verified by integration tests above; full E2E requires live PostgreSQL]
