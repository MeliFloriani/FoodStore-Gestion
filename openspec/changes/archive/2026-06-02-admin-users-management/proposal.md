# Proposal: admin-users-management

**Change**: 21 of Food Store Roadmap  
**Sprint**: 8 — Administración, Calidad y Entrega  
**Status**: Proposed  
**Date**: 2026-06-02  

---

## Why Now

Sprint 8 opens the ADMIN capabilities layer. Users management is a foundational admin function: it unblocks the metrics dashboard (Change 23, which shows user counts) and establishes the security invariant that ADMIN accounts can never be left without at least one active administrator. The auth infrastructure (JWT, refresh rotation, soft delete, RBAC) was completed in Change 07 and is fully production-ready. No blockers remain.

---

## What

Panel ADMIN de usuarios con tres capacidades:

1. **US-053 — Listado paginado y búsqueda** (Alta): tabla paginada de todos los usuarios del sistema con búsqueda por nombre/apellido/email, filtro por rol y filtro por estado activo/inactivo.

2. **US-054 — Edición de datos y roles** (Media): editar nombre/apellido de un usuario y reemplazar su conjunto de roles, con guarda que impide degradar al último ADMIN del sistema. Invalida todos los refresh tokens del usuario modificado para forzar re-login con el nuevo set de roles.

3. **US-055 — Desactivación lógica** (Media): soft delete del usuario (`deleted_at = now()`), revocación global de todos sus refresh tokens activos, y bloqueo automático de login y acceso con token (ya implementado vía `deleted_at IS NULL` en `get_by_email` y `get_by_id`). La guarda "último ADMIN" aplica también aquí.

---

## Acceptance Criteria (literal de las Historias de Usuario)

### US-053 — Listar usuarios del sistema

- [ ] GIVEN un Admin autenticado, WHEN accede al listado de usuarios, THEN ve: nombre, email, rol, fecha de registro, estado (activo/inactivo).
- [ ] Soporta búsqueda por nombre o email.
- [ ] Soporta filtro por rol.
- [ ] Paginación obligatoria.

### US-054 — Editar usuario (Admin)

- [ ] GIVEN un Admin, WHEN edita el rol de un usuario, THEN el cambio se aplica inmediatamente (el próximo token que obtenga ese usuario tendrá el nuevo rol).
- [ ] Un Admin no puede degradar al último ADMIN del sistema.
- [ ] Se puede activar/desactivar usuarios (nota: cubierto en US-055).

### US-055 — Desactivar usuario

- [ ] GIVEN un usuario activo, WHEN el Admin lo desactiva, THEN no puede loguearse más.
- [ ] Los pedidos históricos del usuario se mantienen intactos.
- [ ] Se invalidan todos los refresh tokens del usuario desactivado.

---

## Scope In

| Area | Description |
|------|-------------|
| Backend | Nuevo router `GET /api/v1/admin/usuarios`, `GET /api/v1/admin/usuarios/{id}`, `PUT /api/v1/admin/usuarios/{id}`, `PUT /api/v1/admin/usuarios/{id}/roles`, `PATCH /api/v1/admin/usuarios/{id}/estado` |
| Backend | Nuevo `AdminUsuariosService` con lógica de guarda "último ADMIN" |
| Backend | Nuevo `AdminUsuariosRepository` con queries paginadas + búsqueda ILIKE + filtros |
| Backend | Delta en `backend-auth-register-login` y `backend-auth-dependencies`: documentar que login y `get_current_user` ya bloquean `deleted_at IS NOT NULL` (no requiere cambio de código, solo spec) |
| Backend | Delta en `backend-api-v1-router`: registrar el nuevo router bajo `/admin/usuarios` |
| Backend | Delta en `backend-data-model`: índices GIN/ILIKE sobre `nombre`, `apellido`, `email` para la búsqueda |
| Frontend | Nueva página `AdminUsersPage` en `src/pages/AdminUsersPage/` accesible desde `/admin/users` |
| Frontend | Feature `admin-users`: hooks TanStack Query, formularios TanStack Form, modales de edición y confirmación |
| Frontend | Delta en `frontend-routing`: subrouta `/admin/users` dentro del árbol `/admin/*` |
| Frontend | Delta en `frontend-navigation`: confirmar que la entrada "Usuarios → /admin/users" ya está declarada en `NAVIGATION_ITEMS` (existe desde Change 08) |
| Tests | `pytest` unit tests para `AdminUsuariosService` (guarda último ADMIN, desactivación, edición de roles) |
| Tests | Tests de integración `@pytest.mark.integration` para concurrencia en guarda "último ADMIN" |

---

## Scope Out (explícitamente excluido)

| Feature | Reason |
|---------|--------|
| Reactivación de usuario (PATCH estado activo → inactivo) | US-055 no la menciona; Integrador v5.0 no la requiere. Documentada como decisión abierta D-05. |
| Cambio de contraseña por ADMIN | No figura en US-053/054/055. Fuera de scope. |
| Creación de nuevos usuarios por ADMIN | No figura en el roadmap Change 21. Registro solo por /auth/register. |
| Eliminación física (hard delete) de usuarios | Contrario a RN-CA09 y política de soft delete del proyecto. |
| Gestión de catálogo o pedidos desde el panel ADMIN | Scope de Change 22 y 23. |
| Dashboard de métricas ADMIN | Scope de Change 23. |

---

## Breaking Changes

Ninguno. Este change es **estrictamente aditivo**:

- No modifica contratos de endpoints existentes.
- Los endpoints de auth (`/auth/login`, `/auth/refresh`, `/auth/me`) no cambian su código; el bloqueo de usuarios desactivados ya está implementado via `deleted_at IS NULL` en `UsuarioRepository.get_by_email` y `BaseRepository.get_by_id`.
- No modifica el modelo `Usuario` ni agrega columnas (usa `deleted_at` existente heredado de `Base`).
- No modifica `UsuarioRol` ni `RefreshToken` (reusa métodos existentes).

---

## Success Criteria

- [ ] `GET /api/v1/admin/usuarios` retorna listado paginado `Page[UsuarioAdminRead]` con roles incluidos, sin exponer `password_hash`.
- [ ] Búsqueda ILIKE por nombre/apellido/email funciona en menos de 500ms para datasets de 10k usuarios (con índice).
- [ ] `PUT /api/v1/admin/usuarios/{id}/roles` con el único ADMIN del sistema retorna HTTP 409 `LAST_ADMIN_PROTECTED`.
- [ ] `PATCH /api/v1/admin/usuarios/{id}/estado` (desactivar) invalida todos los refresh tokens del usuario.
- [ ] Usuario desactivado recibe HTTP 401 en `/auth/login` (sin mensaje diferenciado por seguridad) y en cualquier endpoint con Bearer token válido antiguo.
- [ ] Página `/admin/users` requiere rol ADMIN; CLIENT recibe 403.
- [ ] Todos los endpoints de admin retornan errores RFC 7807 con `{ detail, code, field? }`.
- [ ] Tests unitarios para AdminUsuariosService pasan (incluye escenarios de concurrencia con SELECT FOR UPDATE).

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Race condition en guarda "último ADMIN": dos ADMINs intentan degradarse mutuamente al mismo tiempo | Alta | Usar `SELECT FOR UPDATE` sobre la fila `UsuarioRol` objetivo + conteo dentro de la misma transacción. Ver D-03. |
| Modelo `Usuario` no tiene campo `activo` booleano (las Historias lo mencionan) — usa `deleted_at` del `Base` | Media | Confirmado por lectura de `backend/app/models/user.py`. El `deleted_at IS NOT NULL` = desactivado. Integrador v5.0 §3.1 usa el patrón soft delete. Las Historias están en conflicto menor: el documento de mayor jerarquía (Integrador v5.0) gana. No se agrega campo `activo`. |
| Invalidación de refresh tokens en edición de roles: ¿es necesaria si el usuario no cambió de estado? | Baja | US-054 lo indica explícitamente ("Invalidar refresh tokens del usuario modificado para forzar re-login con nuevo rol"). Se implementa igual que en `change_password` usando `revoke_all_for_user`. |
| Búsqueda ILIKE sin índice: full table scan en producción | Media | Agregar índice funcional `lower(nombre || ' ' || apellido)` y posiblemente `pg_trgm` index sobre email. Documentar en delta spec `backend-data-model`. |

---

## Open Questions / Decisions Pending

| ID | Question | Default if not resolved |
|----|----------|------------------------|
| OQ-01 | ¿Puede el ADMIN modificar el email de otro usuario? Change 13 lo dejó inmutable para el propio usuario. Integrador v5.0 no lo menciona explícitamente para ADMIN. | **CERRADA (usuario, 2026-06-02)**: email es inmutable también para ADMIN editando a otro usuario. `UsuarioAdminUpdate` NO contiene campo `email`. Consistente con Change 13. Documentado como D-01. |
| OQ-02 | ¿Existe endpoint de reactivación? US-055 no lo menciona. | **CERRADA (usuario, 2026-06-02)**: `PATCH /estado` con `activo=true` queda soportado en backend (reversibilidad operativa), pero la UI **NO** expone botón "Reactivar" en este change. Tareas frontend ofrecen únicamente la acción "Desactivar". Ver D-05. |
| OQ-03 | Payload de edición de roles: ¿PUT replace del set completo vs PATCH delta (agregar/quitar individual)? | Default: PUT replace (más simple, atómico, menos operaciones). Ver D-02. |
| OQ-04 | Concurrencia guarda "último ADMIN": ¿lock pesimista (`SELECT FOR UPDATE`) vs lock advisory de PostgreSQL? | Default: `SELECT FOR UPDATE` en la fila objetivo del usuario. Ver D-03. |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Change 07 `auth-refresh-logout-rbac-me` | Archivado | Provee: `require_role`, `revoke_all_for_user`, `get_current_user` con `deleted_at` filter, `UsuarioRolRepository` |
| Change 13 `customer-profile-management` | Archivado | Provee: patrón de edición de perfil con UoW, `revoke_all_for_user` en `change_password` |
| Change 20 `orders-visualization` | Archivado | Provee: patrón de listado paginado con server-side pagination para el frontend |
| Change 08 `frontend-auth-rbac-guards` | Archivado | Provee: `RoleGuard`, `useRequireRoles`, entrada nav ADMIN ya declarada |
