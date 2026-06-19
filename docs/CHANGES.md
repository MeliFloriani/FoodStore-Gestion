# Changes — Roadmap Consolidado de Food Store

> **Última actualización**: 2026-06-18 (archivado ui-ux-design-system + quality-assurance-tests-and-coverage)
> **Versión**: 1.0 (consolidada tras auditoría Descripción + Historias de Usuario + Integrador.txt v5.0)
> **Metodología**: Spec-Driven Development (SDD) sobre OpenSpec / OPSX
> **Total de changes activos**: 1
> **Sprints estimados**: 8

---

## 1. ¿Qué es un change?

Un **change** es la unidad mínima de trabajo en el flujo SDD. No es un ticket suelto: es un conjunto de tres artefactos que juntos describen, diseñan e implementan una funcionalidad de forma completa y trazable.

```
openspec/changes/<nombre-del-change>/
├── proposal.md   ← QUÉ se va a construir y POR QUÉ
├── design.md     ← CÓMO técnicamente (arquitectura, modelos, endpoints)
└── tasks.md      ← CHECKLIST atómica de implementación
```

Cuando el change está implementado y verificado, se **archiva**: las specs delta se sincronizan a `openspec/specs/` y la carpeta del change se mueve al historial.

## 2. Flujo de trabajo

```
/opsx:explore  (opcional — pensar antes de comprometerse)
       ▼
/opsx:propose  (crear change + artefactos)
       ▼
/opsx:apply    (implementar tareas)
       ▼
/opsx:archive  (sincronizar specs + cerrar change)
```

## 3. Reglas

- Nunca implementar sin `proposal.md` + `design.md` aprobados.
- Si el Change B necesita código del Change A, A debe estar **archivado** antes de proponer B.
- Un change = uno o varios commits atómicos. Nunca mezclar dos changes en el mismo commit.
- Las specs son código: se versionan en git, evolucionan con el proyecto.
- Toda decisión que contradiga este roadmap debe documentarse explícitamente en el `proposal.md` del change correspondiente.

---

## 4. Convenciones del Roadmap

| Campo | Significado |
|---|---|
| **Nombre** | kebab-case, único, semántico |
| **Objetivo** | 1–3 oraciones que describen qué entrega el change y por qué importa |
| **Historias de usuario** | Lista de US cubiertas (referencia a `Historias_de_usuario.txt`) |
| **Dependencias** | Changes previos que deben estar archivados antes de proponer este |
| **Notas críticas** | Restricciones técnicas, RBAC o decisiones de diseño no obvias derivadas de `Integrador.txt` v5.0 |

**Fuente de verdad**: ante conflicto entre documentos, prevalece `Integrador.txt` v5.0 (especificación técnica oficial del TPI).

---

# Roadmap Consolidado

---

## Sprint 8 — Calidad y Entrega

### Change 26 — `deploy-and-delivery-artifacts`
- **Objetivo**: Deploy del backend en Railway/Render/Fly.io (necesario para webhook MP público), deploy del frontend, configuración de `MP_NOTIFICATION_URL` apuntando a producción, generación de screenshots de ≥10 pantallas, grabación del video demo (5–10 min) y actualización del README con URLs y links.
- **Historias**: criterio bonus +10 pts deploy + obligatorios CE-09, CE-12, CE-13, CE-14
- **Dependencias**: todos los changes anteriores
- **Notas críticas**: Sin URL pública, **CE-09 (pago end-to-end con MP) no es evaluable** — esto convierte a Change 26 en obligatorio aunque su bonus sea opcional.

---

# Out of Scope del TPI

| Item | Estado | Razón |
|---|---|---|
| US-060 — Configuración del sistema | ❌ Fuera de scope | No figura en `Integrador.txt` v5.0 ni en su rúbrica; consume tiempo que debe ir a tests/deploy/UI-UX. Si en el futuro se agrega, sería un change post-entrega. |

---

# Mapa de Dependencias (resumen)

Leyenda: ✅ archivado · ⬜ pendiente

```
✅01 ── ✅02 ── ✅03 ── ✅04
               │
               ├─ ✅06 ── ✅07 ── ✅08
               │               │
✅01 ── ✅05 ──┘               │
                                ├─ ✅09 ┐
                                ├─ ✅10 ┤
                                │       ├─ ✅11 ── ✅12
                                │       │
                                ├─ ✅13 │
                                ├─ ✅14 │
                                │       ├─ ✅15 ── ✅16 ── ✅17 ── ✅18 ── ✅19 ── ✅20
                                │       │                                           │
                                │       │                                           ├─ ✅21
                                │       │                                           ├─ ✅22
                                │       │                                           ├─ ✅23
✅05 ──────────────────────────────────────────────────────────── ✅24 (transversal)
✅07+18+19 ──────────────────────────────────────────────────────── ✅25
todos ──────────────────────────────────────────────────────────── ⬜26
```

**Progreso:** Sprint 8 en curso. Changes 01–25 archivados. ⬜26 habilitable. Change 24–25 archivados 2026-06-18.

# Plan de Sprints

| Sprint | Changes | Foco |
|---|---|---|
| 0 | 01–05 | Fundaciones (monorepo, backend, BD+seed, patrones, frontend) |
| 1 | 06–08 | Auth + RBAC + navegación |
| 2 | 09, 10 | Catálogo I (categorías, ingredientes) |
| 3 | 11, 12, 13 | Catálogo II + perfil |
| 4 | 14, 15 | Direcciones + carrito |
| 5 | 16, 17 | Pre-checkout + creación atómica de pedido |
| 6 | 18, 19 | FSM completa + pagos MercadoPago |
| 7 | 20 | Visualización end-to-end de pedidos |
| 8 | 21, 22, 23, 24, 25, 26 | Admin + UI/UX + tests + deploy + entrega |

# Decisiones Arquitectónicas Clave

1. **FSM partida en dos changes**: las transiciones manuales (Change 18) se implementan antes de pagos (Change 19) para poder testear toda la máquina sin depender de MercadoPago. La transición automática PENDIENTE → CONFIRMADO se incorpora donde nace su gatillo: el webhook (Change 19).
2. **`auth-me` desde Sprint 1**: el `partialize` del `authStore` persiste solo el `accessToken`; sin `/auth/me` el frontend no puede reconstruir el usuario al recargar (criterio de rúbrica Zustand).
3. **STOCK no hace CRUD de productos**: solo modifica disponibilidad y stock_cantidad. CRUD completo es ADMIN exclusivo. Decisión derivada de la matriz oficial de roles (Integrador §4.2 + §5.2).
4. **Tests escritos junto a cada dominio crítico**, no solo al final: `test_auth` con Change 06–07, `test_pedidos` con Change 17–18, `test_pagos` con Change 19. El Change 25 cierra cobertura.
5. **Sistema de diseño transversal**: tokens base sembrados en Change 05 para evitar retrabajo; consolidación en Change 24.
6. **Deploy obligatorio aunque sea bonus**: webhook MP requiere URL pública para que el flujo end-to-end (CE-09) sea evaluable.
7. **Pivote a Checkout Pro durante apply de Change 19**: el flujo inicial embebido con `<CardPayment>` y `@mercadopago/sdk-react` se reemplazó por **MercadoPago Checkout Pro (redirect)** tras recibir `Unauthorized use of live credentials` en sandbox MP al usar tokenización browser. La decisión mantiene la frontera PCI SAQ-A (MP hostea el formulario de pago; PAN/CVV nunca llegan a Food Store), elimina la dependencia `@mercadopago/sdk-react` del frontend y agrega la página `/checkout/return` como punto de retorno con polling. Deuda documentada: se pierde el valor educativo de la tokenización embebida; evaluar regreso si MP habilita tokens TEST estables.

# Riesgos a Vigilar

| ID | Riesgo | Mitigación |
|---|---|---|
| R-01 | Webhook MP no funciona en localhost | Change 26 obligatorio; ngrok como alternativa de desarrollo |
| R-02 | Confusión RBAC STOCK/ADMIN sobre productos | Validar en design.md de Change 11 y respetar matriz §5.2 |
| R-03 | Divergencia `EN_PREPARACIÓN` vs `EN_PREP` | Seed y FSM usan `EN_PREP` (Integrador §3.4) |
| R-04 | `partialize` mal configurado en authStore | Solo `accessToken` + `/auth/me` al rehidratar |
| R-05 | Tests/deploy postergados al final | Changes 25 y 26 formales; tests por dominio en cada sprint |
| R-06 | UI/UX inconsistente | Change 24 transversal, tokens desde Change 05 |
| R-07 | Snapshots incompletos en DetallePedido | Snapshot también de `nombre_snapshot`, no solo `precio_snapshot` |
| R-08 | Schemas Pydantic no separados Read/Create/Update | Verificar la triple separación en cada change que toque schemas |
| R-09 | Pivote a Checkout Pro reduce control fino de UX y deja deuda vs criterio educativo de tokenización embebida | Documentado en archive de Change 19; evaluar regreso a embedded si MP permite tokens TEST estables en sandbox; Change 20 debe contemplar impacto de la nueva página `/checkout/return` en routing |

---

---

## Ya realizado (archivado en OPSX)

## Sprint 0 — Fundaciones

### Change 01 — `bootstrap-monorepo-structure`
- **Objetivo**: Inicializar el monorepo con la estructura de carpetas backend (feature-first) y frontend (Feature-Sliced Design), `.gitignore`, `README.md` raíz y `.env.example` en ambos proyectos.
- **Historias**: US-000
- **Dependencias**: ninguna
- **Notas críticas**: Convención **Conventional Commits**. CE-01, CE-02, CE-03 del checklist de entrega arrancan acá.

### Change 02 — `backend-core-foundation`
- **Objetivo**: Configurar FastAPI con dependencias core, módulo `core/` (config, database, security), middlewares (CORS con `CORSMiddleware`, slowapi, errores RFC 7807) y validación/sanitización global de inputs.
- **Historias**: US-000a, US-068, US-074
- **Dependencias**: Change 01
- **Notas críticas**: Prefijo de routers `/api/v1`. Errores RFC 7807 con `{ detail, code, field? }`. Swagger en `/docs` y ReDoc en `/redoc` (CE-08).


### Change 03 — `database-migrations-and-seed`
- **Objetivo**: Definir el ERD v5 completo en SQLModel, generar migraciones Alembic reproducibles y reversibles e implementar el seed idempotente.
- **Historias**: US-000b
- **Dependencias**: Change 02
- **Notas críticas (alineadas a Integrador v5.0)**:
  - `RefreshToken.token_hash CHAR(64)` — **SHA-256** del token (no UUID en claro).
  - `DireccionEntrega`: campos `alias` y `es_principal` (no `es_predeterminada`).
  - `Pedido.direccion_id` nullable con `ON DELETE SET NULL` (NULL = retiro en local válido).
  - `Pedido.costo_envio DECIMAL default 50.00` (valor fijo v1).
  - `Pedido.forma_pago_codigo VARCHAR(20)` FK semántica.
  - `Categoria.parent_id` FK self-ref con `ON DELETE SET NULL`.
  - `ProductoIngrediente.es_removible BOOLEAN NOT NULL` — habilita personalización.
  - `Pago` con `mp_payment_id`, `mp_status`, `external_reference`, `idempotency_key` (todos `UQ`).
  - `EstadoPedido`: códigos `PENDIENTE | CONFIRMADO | EN_PREP | EN_CAMINO | ENTREGADO | CANCELADO` + `es_terminal`.
  - `FormaPago` seed: `MERCADOPAGO`, `EFECTIVO`, `TRANSFERENCIA` (códigos semánticos).
  - Usuario admin seed: `admin@foodstore.com` / `Admin1234!`.
- **Estado**: ✅ Hecho (archivado 2026-05-12)
- **Evidencia**: `openspec/changes/archive/2026-05-12-database-migrations-and-seed/`

### Change 04 — `backend-base-patterns`
- **Objetivo**: Implementar `BaseRepository[T]` genérico con CRUD + soft delete, `UnitOfWork` como context manager async (commit/rollback automático) y dependencias FastAPI `get_current_user` y `require_role(roles)`.
- **Historias**: US-000d
- **Dependencias**: Change 03
- **Notas críticas**: Ningún `Service` debe ejecutar `session.commit()` directo (criterio rúbrica UoW). Repositorios reciben sesión por inyección desde el UoW.
- **Estado**: ✅ Hecho (archivado 2026-05-13)
- **Evidencia**: `openspec/changes/archive/2026-05-13-backend-base-patterns/`

### Change 05 — `frontend-core-foundation`
- **Objetivo**: React 19 + Vite + TypeScript estricto + FSD + Tailwind tokens enterprise + instancia Axios con refresh queue (401→refresh+retry con cola de concurrentes) + stores Zustand (authStore/cartStore/paymentStore/uiStore) + TanStack Query 5 + react-router con guards de estado + AuthSync rehydration + ErrorBoundary global. Cierra el Sprint 0 de fundaciones frontend.
- **Historias**: US-000c, US-000e, US-067
- **Dependencias**: Change 01
- **Notas críticas**:
  - `authStore` `partialize` persiste **solo `accessToken` + `refreshToken`**; `user` se reconstruye con `GET /api/v1/auth/me` al rehidratar (vía AuthSync en `app/`).
  - Estructura del `cartStore.items[*]`: `{ producto_id, nombre, precio, cantidad, imagen_url, personalizacion: number[] }`.
  - `paymentStore` y todos los campos de `uiStore` excepto `theme` **sin persistencia**.
  - Tokens base de Tailwind (dos niveles: primitivo + semántico via CSS variables) sembrados para alimentar el Design System (Change 27).
  - FSD boundary rules enforced via `eslint-plugin-boundaries`.
- **Estado**: ✅ Hecho (archivado 2026-05-14)
- **Evidencia**: `openspec/changes/archive/2026-05-14-frontend-core-foundation/`
- **Specs sincronizadas**: 1 modificada (`frontend-scaffold`) + 9 nuevas (`frontend-build-tooling`, `frontend-tailwind-tokens`, `frontend-routing`, `frontend-query-client`, `frontend-http-client`, `frontend-auth-store`, `frontend-cart-store`, `frontend-ui-payment-stores`, `frontend-error-handling`)
- **Commits**: 13 (rango: c2a1897..d807904)
- **Score post-auditoría**: ~8.5/10 (GO WITH NOTES — todos los HIGH cerrados)

### Change 06 — `auth-register-login`
- **Objetivo**: Registro de cliente (rol CLIENT auto, hash bcrypt **cost ≥ 12**, validación de email único), login con emisión de access (30 min) + refresh (7 días) y rate limiting de 5 intentos / 15 min por IP.
- **Historias**: US-001, US-002, US-073
- **Dependencias**: Change 03, Change 04
- **Notas críticas**:
  - `RegisterRequest`: `nombre`, `apellido`, `email: EmailStr`, `password ≥ 8` (separar nombre y apellido).
  - `TokenResponse` incluye `expires_in` en segundos y `token_type='bearer'`.
  - Respuesta uniforme ante credenciales inválidas (no revelar si el email existe).
- **Estado**: ✅ Hecho (archivado 2026-05-14)
- **Evidencia**: `openspec/changes/archive/2026-05-14-auth-register-login/`
- **Specs sincronizadas**: 2 nuevas (`backend-auth-register-login`, `backend-auth-token-issuance`) + 5 actualizadas (`backend-api-v1-router`, `backend-auth-dependencies`, `frontend-auth-store`, `frontend-error-handling`, `frontend-routing`)
- **Commits**: 4 (b9296cf, 6bc2d5d, 1f7e109, 459c4bb)

## Sprint 1 — Identidad, Autorización y Navegación

### Change 07 — `auth-refresh-logout-rbac-me`
- **Objetivo**: Cerrar el ciclo de sesión: rotación de refresh tokens con detección de replay, logout que revoca el refresh, RBAC (`require_role` aplicado a endpoints), `GET /api/v1/auth/me`, e interceptor frontend de renovación transparente con cola de requests concurrentes.
- **Historias**: US-003, US-004, US-005, US-006, US-066
- **Dependencias**: Change 06, Change 05
- **Notas críticas**:
  - Persistir **SHA-256** del refresh token, no el valor en claro.
  - Detección de replay → revocar familia completa (DEV-01 documentada: family-scoped en vez de all-tokens; RFC 6749 + multi-device UX).
  - Patrón Opción A (D-07-C): router captura `TokenReplayError` → segundo `UnitOfWork()` independiente commitea `revoke_family` ANTES del rollback del UoW del service.
  - `TokenReplayError` hereda directo de `Exception` (no de `AppError` ni `HTTPException`); prohibido registrar `@app.exception_handler` global.
  - `/auth/me` es indispensable para que el `authStore` reconstruya el usuario al recargar (depende del `partialize` de Change 05).
  - `AuthSync` usa `setUser()` atómico (no `login()`); `logout()` sync void.
  - Interceptor con `refreshPromise` singleton + `failedQueue`; AUTH_LOGOUT en skip-list.
  - Multi-tab sync vía native `storage` event con guard `isRefreshing()`.
- **Estado**: ✅ Hecho (archivado 2026-05-17)
- **Evidencia**: `openspec/changes/archive/2026-05-17-auth-refresh-logout-rbac-me/`
- **Specs sincronizadas**: 4 nuevas (`backend-auth-logout`, `backend-auth-me`, `backend-auth-refresh-rotation`, `frontend-auth-rehydration`) + 4 actualizadas (`frontend-auth-store`, `frontend-http-client`, `backend-auth-register-login`, `backend-auth-token-issuance`)
- **Tests**: 277 passing (188 backend + 89 frontend), coverage 93%
- **Auditoría post-apply**: blind audit READY TO ARCHIVE (8/8 constraints críticos PASS, 0 violations)

### Change 08 — `frontend-navigation-route-guards`
- **Objetivo**: Layout base, navegación adaptada al rol (CLIENT, STOCK, PEDIDOS, ADMIN, anónimo) y guards de ruta basados en `authStore`.
- **Historias**: US-075, US-076
- **Dependencias**: Change 07
- **Notas críticas**:
  - Route tree 3 ramas: public (PublicLayout) / auth (AuthLayout) / private (ProtectedRoute→AppLayout).
  - `RoleGuard` real (reemplazó stub) vía `useRequireRoles(roles)` hook.
  - `withAuth(Component, requiredRoles)` HOC desacoplado del route tree.
  - Invariante D-08: guard-before-Suspense — `RoleGuard` fuera del boundary de `React.Suspense` (chunks restringidos no se descargan).
  - `/catalog` movido a rama pública (accesible sin auth — Integrador §5.2).
  - URLs role-namespaced: `/stock/*` (STOCK+ADMIN), `/pedidos-panel/*` (PEDIDOS+ADMIN).
  - `resolveDefaultRoute(roles)` centralizado: ADMIN→`/admin`, PEDIDOS→`/pedidos-panel`, STOCK→`/stock/products`, CLIENT→`/catalog`.
  - Regla multi-rol: menú = UNIÓN de items de todos los roles del usuario (de-duplicado por path).
  - `adminOnly` eliminado — único mecanismo: `allowedRoles: ['ADMIN']`.
  - Placeholder pages: `/profile` (Change 13), `/addresses` (Change 14), `/stock/*` (Change 11), `/pedidos-panel/*` (Change 18).
  - Error pages: `/401` UnauthorizedPage, `/403` ForbiddenPage, `/404` NotFoundPage.
  - Gotcha crítico: `useAuthStore(s => s.user?.roles ?? [])` causa infinite re-renders en Vitest — solución: leer `user` entero y derivar `roles` fuera del selector.
- **Estado**: ✅ Hecho (archivado 2026-05-18)
- **Evidencia**: `openspec/changes/archive/2026-05-18-frontend-navigation-route-guards/`
- **Specs sincronizadas**: 1 actualizada (`frontend-routing`) + 4 nuevas (`frontend-navigation`, `frontend-route-guards`, `frontend-layouts`, `frontend-error-pages`)
- **Tests**: 141 passing (52 nuevos + 89 pre-existentes), 19 test files, 0 TypeScript errors
- **Auditoría**: 2 rondas blind audit → READY WITH FIXES → micro-fixes → GO. 3 BLOCKERs + 3 HIGH resueltos.

### Change 09 — `catalog-categories-management`
- **Objetivo**: CRUD de categorías jerárquicas con `padre_id` autoreferencial, listado público vía CTE recursiva, validación de ciclos al editar y soft delete.
- **Historias**: US-007, US-008, US-009, US-010
- **Dependencias**: Change 04, Change 07
- **Notas críticas**: `ON DELETE SET NULL` sobre `parent_id`; el listado es público y no requiere auth. `CategoriaUpdate` pasa como modelo Pydantic al service (no como dict) para preservar `model_fields_set`. Migración `0002` corrige unicidad de `nombre` de global a per-parent usando dos partial indexes.
- **Estado**: ✅ Hecho (archivado 2026-05-18)
- **Evidencia**: `openspec/changes/archive/2026-05-18-catalog-categories-management/`
- **Specs sincronizadas**: 3 actualizadas (`backend-api-v1-router`, `backend-migrations`, `backend-unit-of-work`) + 2 nuevas (`backend-categorias-management`, `frontend-categories-entity`)

### Change 10 — `catalog-ingredients-management`
- **Objetivo**: CRUD de ingredientes con flag `es_alergeno`, listado con filtro y soft delete que preserva ingredientes en productos existentes.
- **Historias**: US-011, US-012, US-013, US-014
- **Dependencias**: Change 04, Change 07
- **Notas críticas**: Independiente de Change 09 — pueden desarrollarse en paralelo. Migración 0004 es un ALTER sobre tabla existente: drop `uq_ingrediente_nombre` + dos partial indexes. `IngredienteUpdate` pasa como modelo Pydantic al service para preservar `model_fields_set`.
- **Estado**: ✅ Hecho (archivado 2026-05-18)
- **Evidencia**: `openspec/changes/archive/2026-05-18-catalog-ingredients-management/`
- **Specs sincronizadas**: 2 actualizadas (`backend-api-v1-router`, `backend-migrations`) + 2 nuevas (`backend-ingredientes-management`, `frontend-ingredientes-entity`)

## Sprint 3 — Catálogo II (Productos, Catálogo Público, Perfil)

### Change 11 — `catalog-products-management`
- **Objetivo**: CRUD de productos (precio NUMERIC fija, `stock_cantidad` ≥ 0, `disponible`), asociación M2M a categorías e ingredientes, `PATCH /productos/{id}/disponibilidad` y endpoints `POST/DELETE /productos/{id}/ingredientes/{ing_id}`.
- **Historias**: US-015, US-016, US-017, US-020, US-021, US-022
- **Dependencias**: Change 09, Change 10
- **Notas críticas (RBAC corregida según Integrador v5.0)**:
  - **CRUD de productos** → exclusivo de **ADMIN**.
  - **`PATCH /productos/{id}/disponibilidad`** → ADMIN o STOCK.
  - Operaciones de stock con `UPDATE ... WHERE` atómicas para evitar race conditions.
  - `precio_base`: DECIMAL(10,2) en BD → `float` en SQLModel → `Decimal` en Pydantic → `string` en JSON vía `@field_serializer`.
  - `lazy="noload"` en `Producto.producto_categorias/ingredientes`; pivots back-refs `selectin`. Máximo 5 queries en `get_with_relations`.
- **Estado**: ✅ Hecho (archivado 2026-05-19)
- **Evidencia**: `openspec/changes/archive/2026-05-19-catalog-products-management/`
- **Specs sincronizadas**: 4 actualizadas (`backend-api-v1-router`, `backend-categorias-management`, `backend-ingredientes-management`, `backend-migrations`) + 2 nuevas (`backend-products-management`, `frontend-products-entity`)
- **Tests**: 370 passing (backend), 0 TypeScript errors (frontend)
- **Auditoría**: blind audit → 3 BLOCKERs + 6 HIGH resueltos → re-audit GO FOR APPLY

## Sprint 3 — Catálogo II

### Change 12 — `catalog-public-browsing`
- **Objetivo**: Listado público paginado del catálogo con filtros por categoría, búsqueda por nombre, exclusión de alérgenos, detalle de producto, y la UI con TanStack Query (cache, paginación, debounce, skeletons).
- **Historias**: US-018, US-019, US-023
- **Dependencias**: Change 11, Change 08
- **Notas críticas**: Catálogo siempre filtra `disponible=true AND deleted_at IS NULL` para usuarios públicos. Paginación retorna `{ items, total, page, size, pages }`.
- **Estado**: ✅ Hecho (archivado 2026-05-19)
- **Evidencia**: `openspec/changes/archive/2026-05-19-catalog-public-browsing/`
- **Specs sincronizadas**: 2 nuevas (`backend-catalog-public-browsing`, `frontend-catalog-public`) + 2 actualizadas (`backend-api-v1-router`, `frontend-products-entity`)
- **Tests**: 445 passing (backend, 76 nuevos), 234 passing (frontend)

### Change 13 — `customer-profile-management`
- **Objetivo**: Ver y editar perfil propio (email inmutable) y cambiar contraseña verificando la actual; revoca todos los refresh tokens al cambiar password.
- **Historias**: US-061, US-062, US-063
- **Dependencias**: Change 07
- **Notas críticas**: Independiente del catálogo — puede desarrollarse en paralelo a Change 11–12. Módulo `profile/` desacoplado de `auth/`. Revocación global de refresh tokens atómica en un único UoW.
- **Estado**: ✅ Hecho (archivado 2026-05-19)
- **Evidencia**: `openspec/changes/archive/2026-05-19-customer-profile-management/`
- **Specs sincronizadas**: 2 nuevas (`backend-profile-management`, `frontend-profile-page`) + 2 actualizadas (`backend-api-v1-router`, `frontend-routing`)
- **Tests**: 209 passing (backend, 34 nuevos), 251 passing (frontend, 20 nuevos). 1 skipped (rate limit 429 — requiere env real).
- **Auditoría**: blind audit READY WITH NOTES (7.5/10) → correcciones quirúrgicas → READY FOR APPLY

---

## Sprint 4 — Direcciones y Carrito

### Change 14 — `delivery-addresses-management`
- **Objetivo**: CRUD de direcciones de entrega con `alias` y `es_principal` (transacción que limpia la principal anterior), validación de ownership por `userId` del JWT.
- **Historias**: US-024, US-025, US-026, US-027, US-028
- **Dependencias**: Change 07
- **Notas críticas**:
  - Endpoint dedicado `PATCH /direcciones/{id}/principal`.
  - Soportar el flujo "sin dirección" (retiro en local) en el frontend; no marcar dirección como obligatoria a nivel modelo.
- **Estado**: ✅ Hecho (archivado 2026-05-20)
- **Evidencia**: `openspec/changes/archive/2026-05-20-delivery-addresses-management/`
- **Specs sincronizadas**: 3 nuevas (`backend-direcciones-management`, `frontend-direcciones-entity`, `frontend-direcciones-page`) + 3 actualizadas (`backend-api-v1-router`, `backend-migrations`, `frontend-routing`)

### Change 15 — `shopping-cart-clientside`
- **Objetivo**: Carrito 100% client-side en `cartStore` (Zustand + localStorage): agregar (incrementa si existe), personalizar excluyendo solo ingredientes con `es_removible=true`, modificar cantidad (qty=0 elimina), eliminar ítem, vaciar carrito y resumen.
- **Historias**: US-029, US-030, US-031, US-032, US-033, US-034
- **Dependencias**: Change 12, Change 05
- **Notas críticas**: Persiste `items` completos. Selectores derivados: `subtotal`, `costoEnvio`, `total`. Suscripción por slice obligatoria. Breaking Change: `CartItem.producto_id: number → string`, `personalizacion: number[] → string[]` (UUID alignment). Migración v1→v2 vía `onRehydrateStorage`.
- **Estado**: ✅ Hecho (archivado 2026-05-20)
- **Evidencia**: `openspec/changes/archive/2026-05-20-shopping-cart-clientside/`
- **Specs sincronizadas**: 1 actualizada (`frontend-cart-store`) — Breaking Change + `buildItemKey`/`es_removible`/slice subscription requirements
- **Tests**: 47 passing (17 cartUtils + 24 store + 6 persist), 0 TypeScript errors, 0 ESLint violations

---

## Sprint 5 — Pedidos: Validaciones y Creación

### Change 16 — `pre-checkout-validations`
- **Objetivo**: Endpoint y UX de validación previa que verifica producto vigente, disponible, stock suficiente y compara precio del carrito vs precio actual, devolviendo cambios detectados.
- **Historias**: US-069, US-070
- **Dependencias**: Change 11, Change 15
- **Estado**: ✅ Hecho (archivado 2026-05-20)
- **Evidencia**: `openspec/changes/archive/2026-05-20-pre-checkout-validations/`
- **Specs sincronizadas**: 2 nuevas (`backend-pre-checkout-validations`, `frontend-pre-checkout-validation`) + 2 actualizadas (`backend-api-v1-router`, `frontend-routing`)
- **Tests**: 21 backend passing (16 service + 5 router), 14 frontend passing (4 hook + 10 componente), 0 TypeScript errors

### Change 17 — `order-creation-with-snapshots`
- **Objetivo**: `POST /api/v1/pedidos` con creación atómica vía Unit of Work: validación de stock con `SELECT FOR UPDATE`, snapshot de `nombre_snapshot` + `precio_snapshot` por línea, FK de dirección si aplica, exclusiones como `UUID[]`, estado inicial PENDIENTE y primer asiento en `HistorialEstadoPedido` con `estado_desde=NULL`.
- **Historias**: US-035, US-036, US-037, US-038
- **Dependencias**: Change 14, Change 15, Change 16, Change 04
- **Estado**: ✅ Hecho (archivado 2026-05-21)
- **Evidencia**: `openspec/changes/archive/2026-05-21-order-creation-with-snapshots/`
- **Specs sincronizadas**: 2 nuevas (`backend-order-creation`, `frontend-checkout`) + 2 actualizadas (`backend-api-v1-router`, `backend-unit-of-work`)
- **Tests**: 19 backend unit tests passing, 9 frontend tests passing. Tests de concurrencia marcados `@pytest.mark.integration` (requieren PostgreSQL real).
- **Decisiones clave**: `exclusiones` como `UUID[]` (migración 0008 convierte de `INTEGER[]`); `costo_envio` 50.00/0.00 server-side; dirección solo FK nullable (snapshot completo = deuda OQ-01 → Change 20).

## Sprint 6 — FSM y Pagos

### Change 18 — `order-state-machine-transitions`
- **Objetivo**: FSM completa de transiciones manuales: avance CONFIRMADO → EN_PREP → EN_CAMINO → ENTREGADO, cancelación con restauración atómica de stock cuando proceda, audit trail append-only y endpoint `GET /pedidos/{id}/historial`.
- **Historias**: US-040, US-041, US-042, US-043, US-044
- **Dependencias**: Change 17
- **Notas críticas (RBAC v5.0)**:
  - Avance de estados → ADMIN o PEDIDOS.
  - **CANCELADO desde PENDIENTE**: CLIENT (sus propios), PEDIDOS o ADMIN — `DELETE /api/v1/pedidos/{id}` para el cliente.
  - **CANCELADO desde CONFIRMADO**: PEDIDOS o ADMIN; restaurar stock atómicamente.
  - **CANCELADO desde EN_PREP**: solo ADMIN.
  - `motivo` **obligatorio** si `nuevo_estado = CANCELADO` (RN-05).
  - `HistorialEstadoPedido` es append-only: prohibido `UPDATE`/`DELETE` desde cualquier capa.
- **Estado**: ✅ Hecho (archivado 2026-05-21)
- **Evidencia**: `openspec/changes/archive/2026-05-21-order-state-machine-transitions/`
- **Specs sincronizadas**: 3 nuevas (`backend-order-state-machine`, `backend-order-history`, `frontend-pedido-state-actions`) + 3 actualizadas (`backend-api-v1-router`, `backend-order-creation`, `backend-unit-of-work`)
- **Tests**: 37 unit tests passing (state_transition), @pytest.mark.integration para FSM router. Frontend: 3 test files.
- **Auditoría**: blind audit → 5 BLOCKERs (F-01..F-05) + 12 HIGH/MEDIUM/LOW resueltos → re-audit PASS → apply → archive.
- **Decisiones clave**: `uow.historial_pedido` accessor D-09 (supersede restricción Change 17 NF-01); pessimistic lock `SELECT FOR UPDATE` vía `get_for_update()`; `HistorialEstadoPedidoRepository` no hereda `BaseRepository[T]` (append-only invariante); `actor_user_id` alias de `cambiado_por_id` vía `Field(alias=...)`.

### Change 19 — `payments-mercadopago-integration`
- **Objetivo**: Integración MercadoPago Checkout Pro end-to-end: `POST /api/v1/pagos` crea una preferencia de pago con `Preference.create`, devuelve `init_point` / `sandbox_init_point`, redirige el browser a la página hosteada de MP; webhook IPN con HMAC-SHA256 + freshness check de 5 min (`abs(now-ts)>300 → 400 WEBHOOK_EXPIRED`), re-query obligatoria de la API MP (`GET /v1/payments/{id}` — el payload del webhook nunca es fuente de verdad), transición automática PENDIENTE→CONFIRMADO con `actor_user_id=NULL, motivo="Pago aprobado MP"`, decremento atómico de stock en un único UoW (Pago + FSM + stock). Alias `POST /api/v1/pagos/crear` para compatibilidad §5.4. Página nueva `/checkout/return` maneja `back_urls` con polling `usePaymentStatus` cada 30s.
- **Historias**: US-045, US-046, US-047, US-048, US-039, US-072
- **Dependencias**: Change 17, Change 18
- **Notas críticas**:
  - **Pivote durante apply**: el flujo inicial `<CardPayment>` embebido se reemplazó por **Checkout Pro (redirect)** tras `Unauthorized use of live credentials` en sandbox MP. PCI SAQ-A se mantiene (MP hostea el formulario de pago; PAN/CVV nunca llegan a Food Store).
  - **Deuda técnica**: se pierde objetivo educativo de tokenización browser; `@mercadopago/sdk-react` removido del frontend.
  - Webhook IPN HMAC-SHA256 con freshness check: `abs(time.time()-int(ts))>300 → HTTP 400 WEBHOOK_EXPIRED`. Verificación ANTES del cómputo HMAC para rechazar replays temprano.
  - Re-query MP API obligatoria — el payload del webhook nunca es fuente de verdad (RN-PA04).
  - Single UoW: Pago + `state_transition(SYSTEM actor)` + `decrement_stock` atómico.
  - Alias `POST /api/v1/pagos/crear` apunta al mismo handler que `POST /api/v1/pagos` (compatibilidad Integrador §5.4).
  - Página nueva `/checkout/return` maneja `back_urls` de MP (afecta routing del frontend; revisar impacto en Change 20).
  - `pedidoId` en `paymentStore` corregido de `number` a `string` (UUID).
  - `external_reference` en tabla `pago` ya no es UNIQUE (migración 0010); soporta 1:N Pago por Pedido (reintento RN-PA08).
  - `mp_preference_id VARCHAR(100) UNIQUE NULL` agregado (migración 0011).
- **Estado**: ✅ Hecho (archivado 2026-06-01)
- **Evidencia**: `openspec/changes/archive/2026-06-01-payments-mercadopago-integration/`
- **Specs sincronizadas**:
  - **4 nuevas**: `backend-pagos-management`, `backend-pagos-webhook`, `frontend-checkout-payment`, `frontend-payment-polling`
  - **5 modificadas**: `backend-data-model` (drop `uq_pago_external_reference`, add `mp_status_detail` + `mp_preference_id`), `backend-order-state-machine` (add automatic PENDIENTE→CONFIRMADO scenario), `backend-api-v1-router` (register `pagos_router`), `frontend-checkout` (add PayWithMercadoPagoButton step), `frontend-ui-payment-stores` (`pedidoId: number → string`)
- **Tests**: 29/29 unit tests `test_pagos.py` passing; `tsc --noEmit` 0 errors. E2E sandbox opt-in (requiere ngrok + Change 26).
- **Decisiones clave**: D-01 1:N Pago/Pedido via drop external_reference UQ; D-02 inline processing webhook (no BackgroundTasks); D-03 always re-query MP API; D-08 HMAC-SHA256 con freshness 5 min; D-09 create_preference() Checkout Pro; D-10 PayWithMercadoPagoButton + browser redirect; D-11 alias /crear.

## Sprint 7 — Visualización de Pedidos

### Change 20 — `orders-visualization`
- **Objetivo**: Listado y detalle de pedidos para CLIENT (filtrado por su `userId`), panel de gestión para PEDIDOS/ADMIN con filtros por estado/fecha/cliente, página de confirmación de pedido creado (`OrderConfirmation`) y **timeline visual del historial** con polling de `PaymentStatus`.
- **Historias**: US-049, US-050, US-051, US-052, US-071
- **Dependencias**: Change 17, Change 18, Change 19
- **Notas críticas**: Paginación obligatoria. CLIENT solo ve sus propios pedidos (403 si intenta ver otros). Detalle incluye snapshots, historial completo y pagos asociados. D-15 strict role separation: CLIENT→`/orders*`, PEDIDOS/ADMIN→`/pedidos-panel*`. BUG-01 (timeline `estado_hacia` undefined) corregido con fix backend contract-faithful: `Field(alias=)` → `Field(validation_alias=)` en `HistorialEstadoPedidoRead`; la especificación Change 18 mandaba `estado_hacia`/`actor_user_id` y el frontend ya era correcto — el backend serializaba erróneamente el alias por defecto de FastAPI `by_alias=True`.
- **Estado**: ✅ Hecho (archivado 2026-06-02)
- **Evidencia**: `openspec/changes/archive/2026-06-02-orders-visualization/`
- **Specs sincronizadas**: 3 actualizadas (`backend-api-v1-router`, `frontend-checkout`, `frontend-routing`) + 7 nuevas (`backend-orders-detail`, `backend-orders-listing`, `frontend-order-confirmation`, `frontend-order-history-timeline`, `frontend-orders-detail`, `frontend-orders-history`, `frontend-orders-management-panel`)
- **Tests**: 20/20 backend `test_orders_visualization.py` + 2 nuevos de regresión `by_alias`; 3 frontend test files passing + 1 nuevo test anti-undefined en `OrderHistoryTimeline`. `openspec validate --strict` PASS. 101/101 tasks completas.

### Change 24 — `ui-ux-design-system` *(transversal)*
- **Objetivo**: Sistema de diseño consistente: tokens Tailwind, paleta, tipografía, sistema de toasts, skeleton loaders, modales de confirmación, estados vacíos, layout mobile-first y aplicación a todas las features.
- **Historias**: criterio de rúbrica "UI/UX y Diseño" (10 pts) — sin US específica
- **Dependencias**: Change 05 (puede arrancarse ahí en paralelo); cierre en Sprint 8 cuando todas las features estén disponibles para refinamiento visual.
- **Notas críticas**: Tokens base sembrados en Change 05 para no retrabajar componentes; este change consolida la coherencia visual del sistema completo.
- **Estado**: ✅ Hecho (archivado 2026-06-18)
- **Evidencia**: `openspec/changes/archive/2026-06-18-ui-ux-design-system/`
- **Specs sincronizadas**: 1 modificada (`frontend-tailwind-tokens`) + 6 nuevas (`frontend-design-system-toasts`, `frontend-design-system-skeletons`, `frontend-design-system-confirm-dialog`, `frontend-design-system-empty-state`, `frontend-design-system-mobile-first-layout`, `frontend-design-system-typography`)
- **Commits**: 0 directos (implementado vía subagentes OPSX)
- **Tests**: 446+ passing, 0 TypeScript errors. 47 pre-existing test failures no relacionados.

## Sprint 8 — Administración (parcial)

### Change 21 — `admin-users-management`
- **Objetivo**: Panel ADMIN de usuarios con listado paginado y búsqueda, edición de datos y roles con guarda "último ADMIN", desactivación lógica que invalida todos los refresh tokens y bloquea login.
- **Historias**: US-053, US-054, US-055
- **Dependencias**: Change 07
- **Estado**: ✅ Hecho (archivado 2026-06-02)
- **Evidencia**: `openspec/changes/archive/2026-06-02-admin-users-management/`
- **Specs sincronizadas**: 2 nuevas (`backend-admin-users-management`, `frontend-admin-users-page`) + 1 nueva documental (`backend-auth-login-deactivation`) + 4 modificadas (`backend-api-v1-router`, `backend-data-model`, `frontend-routing`, `frontend-navigation`)
- **Tests**: 42 backend (33 unit + 9 integration) + 43 frontend (7 archivos) = 85 verdes. `tsc --noEmit` 0 errors.
- **Auditoría**: blind audit READY TO ARCHIVE (0 BLOCKER/HIGH/MEDIUM, 1 LOW F-01 corregido pre-archive).

### Change 22 — `admin-catalog-orders-aggregated-permissions`
- **Objetivo**: Habilitar acceso del rol ADMIN a todos los endpoints de gestión de catálogo y pedidos vía `require_role(["ADMIN", ...])` y exponer las vistas correspondientes en el menú ADMIN.
- **Historias**: US-064, US-065
- **Dependencias**: Change 11, Change 18, Change 19, Change 20
- **Notas críticas**: Cambio "ligero pero crítico" — solo ajusta dependencias `require_role` en routers existentes; no duplica endpoints.
- **Estado**: ✅ Hecho (archivado 2026-06-03)
- **Evidencia**: `openspec/changes/archive/2026-06-03-admin-catalog-orders-aggregated-permissions/`
- **Tests sincronizados**: 2 nuevas specs + 8 deltas. 13 backend tests RBAC + 7 frontend tests nav.
- **Deuda documentada**: F-01 (test render `<Navigation>` para ADMIN) → pendiente Change 24/navegación.

### Change 23 — `admin-metrics-dashboard`
- **Objetivo**: Dashboard ADMIN con KPI cards (ventas totales, pedidos por estado, usuarios), evolución de ventas por período (`DATE_TRUNC` día/semana/mes), top productos más vendidos, distribución de pedidos por estado, y gestión de pedidos/stock embebidas en el panel.
- **Historias**: US-056, US-057, US-058, US-059
- **Dependencias**: Change 20, Change 21, Change 19
- **Notas críticas**: Gráficos con recharts (`LineChart`, `BarChart`, `PieChart`). Índices `ix_pedido_created_at_estado_codigo` + `ix_detalle_pedido_producto_id` (migración 0014). Módulo en `app/modules/admin/metricas/`. Path `/admin/metricas` (corregido de `/admin/metrics`). `created_at` naive — pasar `datetime` sin timezone. `DATE_TRUNC` requiere string literal interpolado (no bind param). `deleted_at IS NULL` para usuarios activos.
- **Estado**: ✅ Hecho (archivado 2026-06-03)
- **Evidencia**: `openspec/changes/archive/2026-06-03-admin-metrics-dashboard/`
- **Specs sincronizadas**: 2 nuevas (`backend-admin-metrics`, `frontend-admin-metrics-dashboard`) + 5 modificadas (`backend-api-v1-router`, `backend-migrations`, `frontend-admin-menu-exposure`, `frontend-navigation`, `frontend-routing`)
- **Tests**: 16 backend `test_metricas.py` passing. Navegación 22/22 tests PASS post path-correction.

---

## Sprint 8 — Calidad y Entrega

### Change 25 — `quality-assurance-tests-and-coverage`
- **Objetivo**: Suite de tests con `pytest` cubriendo `test_auth` (registro, login, refresh rotation, RBAC), `test_pedidos` (FSM, snapshots, atomicidad UoW, restauración de stock) y `test_pagos` (idempotency, webhook, transición automática). Covertura ≥ 60%.
- **Historias**: criterio de bonus +10 pts (Integrador §12)
- **Dependencias**: Change 07 (auth), Change 18 (FSM), Change 19 (pagos). Tests por dominio se escriben junto a cada change correspondiente; este change cierra cobertura global y CI.
- **Notas críticas**: Sin Change 25, se pierde el bonus +10 y la lógica crítica queda sin red de seguridad.
- **Estado**: ✅ Hecho (archivado 2026-06-18)
- **Evidencia**: `openspec/changes/archive/2026-06-18-quality-assurance-tests-and-coverage/`
- **Specs sincronizadas**: 3 nuevas (`backend-test-coverage`, `ci-pipeline`, `frontend-test-coverage`)
- **Tests**: 87 test files frontend (666 tests) + backend coverage 65.19% / frontend lines 61.6%. CI pipeline via GitHub Actions.

---

— Roadmap consolidado · Food Store · OPSX/SDD —
