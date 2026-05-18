# Changes — Roadmap Consolidado de Food Store

> **Última actualización**: 2026-05-18
> **Versión**: 1.0 (consolidada tras auditoría Descripción + Historias de Usuario + Integrador.txt v5.0)
> **Metodología**: Spec-Driven Development (SDD) sobre OpenSpec / OPSX
> **Total de changes activos**: 24
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

## Sprint 2 — Catálogo I (Categorías e Ingredientes)

### Change 09 — `catalog-categories-management`
- **Objetivo**: CRUD de categorías jerárquicas con `padre_id` autoreferencial, listado público vía CTE recursiva, validación de ciclos al editar y soft delete.
- **Historias**: US-007, US-008, US-009, US-010
- **Dependencias**: Change 04, Change 07
- **Notas críticas**: `ON DELETE SET NULL` sobre `parent_id`; el listado es público y no requiere auth.

### Change 10 — `catalog-ingredients-management`
- **Objetivo**: CRUD de ingredientes con flag `es_alergeno`, listado con filtro y soft delete que preserva ingredientes en productos existentes.
- **Historias**: US-011, US-012, US-013, US-014
- **Dependencias**: Change 04, Change 07
- **Notas críticas**: Independiente de Change 09 — pueden desarrollarse en paralelo.

---

## Sprint 3 — Catálogo II (Productos, Catálogo Público, Perfil)

### Change 11 — `catalog-products-management`
- **Objetivo**: CRUD de productos (precio NUMERIC fija, `stock_cantidad` ≥ 0, `disponible`), asociación M2M a categorías e ingredientes, `PATCH /productos/{id}/disponibilidad` y endpoints `POST/DELETE /productos/{id}/ingredientes/{ing_id}`.
- **Historias**: US-015, US-016, US-017, US-020, US-021, US-022
- **Dependencias**: Change 09, Change 10
- **Notas críticas (matriz RBAC corregida según Integrador v5.0)**:
  - **CRUD de productos** → exclusivo de **ADMIN**.
  - **`PATCH /productos/{id}/disponibilidad`** → ADMIN o STOCK.
  - **`stock_cantidad` y disponibilidad** → STOCK opera, ADMIN también.
  - Operaciones de stock con `UPDATE ... WHERE` atómicas para evitar race conditions.

### Change 12 — `catalog-public-browsing`
- **Objetivo**: Listado público paginado del catálogo con filtros por categoría, búsqueda por nombre, exclusión de alérgenos, detalle de producto, y la UI con TanStack Query (cache, paginación, debounce, **skeletons**).
- **Historias**: US-018, US-019, US-023
- **Dependencias**: Change 11, Change 08
- **Notas críticas**: Catálogo siempre filtra `disponible=true AND deleted_at IS NULL` para usuarios públicos. Paginación retorna `{ items, total, page, size, pages }`.

### Change 13 — `customer-profile-management`
- **Objetivo**: Ver y editar perfil propio (email inmutable) y cambiar contraseña verificando la actual; revoca todos los refresh tokens al cambiar password.
- **Historias**: US-061, US-062, US-063
- **Dependencias**: Change 07
- **Notas críticas**: Independiente del catálogo — puede desarrollarse en paralelo a Change 11–12.

---

## Sprint 4 — Direcciones y Carrito

### Change 14 — `delivery-addresses-management`
- **Objetivo**: CRUD de direcciones de entrega con `alias` y `es_principal` (transacción que limpia la principal anterior), validación de ownership por `userId` del JWT.
- **Historias**: US-024, US-025, US-026, US-027, US-028
- **Dependencias**: Change 07
- **Notas críticas**:
  - Endpoint dedicado `PATCH /direcciones/{id}/principal`.
  - Soportar el flujo "sin dirección" (retiro en local) en el frontend; no marcar dirección como obligatoria a nivel modelo.

### Change 15 — `shopping-cart-clientside`
- **Objetivo**: Carrito 100% client-side en `cartStore` (Zustand + localStorage): agregar (incrementa si existe), personalizar excluyendo solo ingredientes con `es_removible=true`, modificar cantidad (qty=0 elimina), eliminar ítem, vaciar carrito y resumen.
- **Historias**: US-029, US-030, US-031, US-032, US-033, US-034
- **Dependencias**: Change 12, Change 05
- **Notas críticas**: Persiste `items` completos. Selectores derivados: `subtotal`, `costoEnvio`, `total`. Suscripción por slice obligatoria.

---

## Sprint 5 — Pedidos: Validaciones y Creación

### Change 16 — `pre-checkout-validations`
- **Objetivo**: Endpoint y UX de validación previa que verifica producto vigente, disponible, stock suficiente y compara precio del carrito vs precio actual, devolviendo cambios detectados.
- **Historias**: US-069, US-070
- **Dependencias**: Change 11, Change 15

### Change 17 — `order-creation-with-snapshots`
- **Objetivo**: `POST /api/v1/pedidos` con creación atómica vía Unit of Work: validación de stock con `SELECT FOR UPDATE`, snapshot de `nombre_snapshot` + `precio_snapshot` por línea, snapshot de dirección si aplica, exclusiones como `INTEGER[]`, estado inicial PENDIENTE y primer asiento en `HistorialEstadoPedido` con `estado_desde=NULL`.
- **Historias**: US-035, US-036, US-037, US-038
- **Dependencias**: Change 14, Change 15, Change 16, Change 04
- **Notas críticas**:
  - `direccion_id` opcional → NULL = retiro en local válido.
  - `costo_envio` fijo 50.00 (excluir explícitamente si retiro en local — documentar decisión en design.md).
  - Snapshot de **nombre del producto** además del precio (RN-04 v5).
  - Validar `forma_pago_codigo` contra catálogo `habilitado=true`.

---

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

### Change 19 — `payments-mercadopago-integration`
- **Objetivo**: Integración MercadoPago end-to-end con SDK React embebido (`<CardPayment>`), backend con `idempotency_key` UUID y `external_reference`, webhook IPN que verifica firma, consulta API real de MP, procesa idempotentemente, dispara la transición automática PENDIENTE → CONFIRMADO con decremento atómico de stock cuando el pago es `approved`, soporta reintento y polling de estado en frontend.
- **Historias**: US-045, US-046, US-047, US-048, US-039, US-072
- **Dependencias**: Change 17, Change 18
- **Notas críticas**:
  - SDK frontend: **`@mercadopago/sdk-react`** (no redirect — checkout embebido).
  - Tokenización en browser (PCI SAQ-A): los datos de tarjeta nunca tocan el backend.
  - Variable `MP_NOTIFICATION_URL` configurada al webhook público (depende de Change 26 para entorno real).
  - **Polling cada 30s** desde el frontend sobre el estado del pedido para `PaymentStatus`.
  - Webhook responde HTTP 200 inmediatamente y procesa idempotentemente con `idempotency_key`.

---

## Sprint 7 — Visualización de Pedidos

### Change 20 — `orders-visualization`
- **Objetivo**: Listado y detalle de pedidos para CLIENT (filtrado por su `userId`), panel de gestión para PEDIDOS/ADMIN con filtros por estado/fecha/cliente, página de confirmación de pedido creado (`OrderConfirmation`) y **timeline visual del historial** con polling de `PaymentStatus`.
- **Historias**: US-049, US-050, US-051, US-052, US-071
- **Dependencias**: Change 17, Change 18, Change 19
- **Notas críticas**: Paginación obligatoria. CLIENT solo ve sus propios pedidos (403 si intenta ver otros). Detalle incluye snapshots, historial completo y pagos asociados.

---

## Sprint 8 — Administración, Calidad y Entrega

### Change 21 — `admin-users-management`
- **Objetivo**: Panel ADMIN de usuarios con listado paginado y búsqueda, edición de datos y roles con guarda "último ADMIN", desactivación lógica que invalida todos los refresh tokens y bloquea login.
- **Historias**: US-053, US-054, US-055
- **Dependencias**: Change 07

### Change 22 — `admin-catalog-orders-aggregated-permissions`
- **Objetivo**: Habilitar acceso del rol ADMIN a todos los endpoints de gestión de catálogo y pedidos vía `require_role(["ADMIN", ...])` y exponer las vistas correspondientes en el menú ADMIN.
- **Historias**: US-064, US-065
- **Dependencias**: Change 11, Change 18, Change 19, Change 20
- **Notas críticas**: Cambio "ligero pero crítico" — solo ajusta dependencias `require_role` en routers existentes; no duplica endpoints.

### Change 23 — `admin-metrics-dashboard`
- **Objetivo**: Dashboard ADMIN con KPI cards (ventas totales, pedidos por estado, usuarios), evolución de ventas por período (`DATE_TRUNC` día/semana/mes), top productos más vendidos, distribución de pedidos por estado, y gestión de pedidos/stock embebidas en el panel.
- **Historias**: US-056, US-057, US-058, US-059
- **Dependencias**: Change 20, Change 21, Change 19
- **Notas críticas**: Gráficos con recharts (`LineChart`, `BarChart`, `PieChart`). Filtros por rango de fechas. Crear índices en `creado_en` y `estado_codigo` si los queries lo requieren.

### Change 24 — `ui-ux-design-system` *(transversal)*
- **Objetivo**: Sistema de diseño consistente: tokens Tailwind, paleta, tipografía, sistema de toasts, skeleton loaders, modales de confirmación, estados vacíos, layout mobile-first y aplicación a todas las features.
- **Historias**: criterio de rúbrica "UI/UX y Diseño" (10 pts) — sin US específica
- **Dependencias**: Change 05 (puede arrancarse ahí en paralelo); cierre en Sprint 8 cuando todas las features estén disponibles para refinamiento visual.
- **Notas críticas**: Tokens base sembrados en Change 05 para no retrabajar componentes; este change consolida la coherencia visual del sistema completo.

### Change 25 — `quality-assurance-tests-and-coverage`
- **Objetivo**: Suite de tests con `pytest` cubriendo `test_auth` (registro, login, refresh rotation, RBAC), `test_pedidos` (FSM, snapshots, atomicidad UoW, restauración de stock) y `test_pagos` (idempotency, webhook, transición automática). Cobertura ≥ 60%.
- **Historias**: criterio de bonus +10 pts (Integrador §12)
- **Dependencias**: Change 07 (auth), Change 18 (FSM), Change 19 (pagos). Tests por dominio se escriben junto a cada change correspondiente; este change cierra cobertura global y CI.
- **Notas críticas**: Sin Change 25, se pierde el bonus +10 y la lógica crítica queda sin red de seguridad.

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

```
01 ── 02 ── 03 ── 04
            │
            ├─ 06 ── 07 ── 08
            │              │
01 ── 05 ───┘              │
                           ├─ 09 ┐
                           ├─ 10 ┤
                           │     ├─ 11 ── 12
                           │     │
                           ├─ 13 │
                           ├─ 14 │
                           │     ├─ 15 ── 16 ── 17 ── 18 ── 19 ── 20
                           │     │                                    │
                           │     │                                    ├─ 21
                           │     │                                    ├─ 22
                           │     │                                    ├─ 23
05 ─────────────────────────────────────────────────────── 24 (transversal)
07,18,19 ─────────────────────────────────────────────────── 25
todos ───────────────────────────────────────────────────── 26
```

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

---

— Roadmap consolidado · Food Store · OPSX/SDD —
