## Context

Food Store tiene 4 roles: CLIENT, ADMIN, STOCK y PEDIDOS. La decisión D-15 (Change 20) establece que ADMIN es exclusivamente rol de gestión — no CLIENT. El principio de agregación define ADMIN ⊇ STOCK (catálogo) y ADMIN ⊇ PEDIDOS (pedidos): cualquier recurso de gestión accesible por STOCK o PEDIDOS debe ser también accesible por ADMIN.

La auditoría de los routers confirma el siguiente estado actual:

**Catálogo — routers:**
- `categorias.py`: POST `/`, PUT `/{id}`, DELETE `/{id}` → `require_role("ADMIN", "STOCK")` ✅
- `ingredientes.py`: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}` → `require_role("ADMIN", "STOCK")` ✅
- `productos.py`: POST `/`, PATCH `/{id}`, DELETE `/{id}`, POST `/{id}/ingredientes`, DELETE `/{id}/ingredientes/{ing_id}` → `require_role("ADMIN")` ✅; PATCH `/{id}/disponibilidad` → `require_role("ADMIN", "STOCK")` ✅

**Pedidos — routers:**
- `pedidos.py` POST `/`: `require_role("CLIENT", "ADMIN")` ✅
- `pedidos.py` GET `/`: `require_role("CLIENT", "PEDIDOS", "ADMIN")` ✅
- `pedidos.py` GET `/{id}`: `get_current_user` + RBAC en service (STOCK → 403, CLIENT → ownership check, PEDIDOS/ADMIN → any) ✅
- `pedidos.py` PATCH `/{id}/estado`: `require_role("PEDIDOS", "ADMIN")` ✅
- `pedidos.py` GET `/{id}/historial`: `require_role("CLIENT", "PEDIDOS", "ADMIN")` ✅
- `pedidos.py` DELETE `/{id}`: `require_role("CLIENT")` — CLIENT-only por diseño (Change 18 D-12) ✅
- `pedidos_validar.py` POST `/validar`: `require_role("CLIENT", "ADMIN")` ✅
- `pagos/router.py` GET `/{pedido_id}/latest`: `require_role("CLIENT", "PEDIDOS", "ADMIN")` ✅

**Frontend navigation:**
- `NAVIGATION_ITEMS`: `stock-products`, `stock-categories`, `stock-ingredients`, `stock-inventory` → `allowedRoles: ['STOCK','ADMIN']` ✅; `pedidos-panel` → `allowedRoles: ['PEDIDOS','ADMIN']` ✅; `admin-users`, `admin-metrics` → `allowedRoles: ['ADMIN']` ✅

**Conclusión de la auditoría**: No se requiere ningún cambio de código. El cambio es de documentación, ratificación formal y cobertura de tests.

## Goals / Non-Goals

**Goals:**
- Documentar formalmente la matriz RBAC ADMIN sobre catálogo y pedidos en un spec canónico.
- Ratificar el invariante del menú ADMIN en un spec canónico de navegación.
- Agregar tests de humo RBAC que verifiquen el acceso ADMIN a cada endpoint de gestión.
- Cerrar US-064 y US-065 con evidencia verificable.

**Non-Goals:**
- No se crean endpoints nuevos (`/admin/...`).
- No se modifica lógica de negocio (FSM, snapshots, stock, pagos).
- No se altera `DELETE /pedidos/{id}` (CLIENT-only por Change 18 D-12).
- No se da a ADMIN acceso a rutas CLIENT (carrito, checkout). Decisión D-15 prevalece.
- No se introduce parámetro `incluir_eliminados` (RN-CA10 de US-064 nota — postergado).
- No se implementan métricas ni funcionalidades post-entrega.

## Decisions

### D-01: ADMIN se agrega a tuplas existentes; no se crean endpoints `/admin/...` paralelos
**Decisión**: Usar `require_role("ADMIN", "STOCK")` / `require_role("PEDIDOS", "ADMIN")` en los routers existentes. No duplicar endpoints bajo un prefijo `/admin/`.

**Alternativa descartada**: Crear un router `/api/v1/admin/` con aliases de cada endpoint de catálogo y pedidos. Descartado porque: (1) duplica surface de API sin agregar valor, (2) crea dos fuentes de verdad para la misma operación, (3) duplica tests, (4) rompe el principio DRY en el dominio de seguridad.

**Justificación**: Un único punto de validación por recurso es más seguro (sin riesgo de discrepancia de permisos entre el endpoint original y su alias) y más simple de mantener.

### D-02: Matriz RBAC se documenta en un spec nuevo `backend-admin-aggregated-permissions`
**Decisión**: Crear un spec de referencia cruzada que sirva como fuente canónica de la matriz RBAC de ADMIN sobre catálogo y pedidos. Los specs de dominio (categorias, productos, pedidos, etc.) referencian este spec con una nota de ratificación.

**Alternativa descartada**: Actualizar cada spec de dominio individualmente con la matriz completa. Descartado porque: duplica información y crea riesgo de inconsistencia futura.

### D-03: `DELETE /pedidos/{id}` se mantiene CLIENT-only; cancelación administrativa = PATCH /estado
**Decisión**: El endpoint `DELETE /pedidos/{id}` acepta únicamente `require_role("CLIENT")`. La cancelación de un pedido por ADMIN o PEDIDOS se realiza exclusivamente via `PATCH /pedidos/{id}/estado` con `{"nuevo_estado": "CANCELADO", "motivo": "..."}`.

**Justificación**: Change 18 D-12 establece esta separación explícitamente. DELETE está semánticamente asociado a auto-cancelación del propietario. La FSM (PATCH /estado) es el mecanismo correcto para operaciones administrativas sobre el ciclo de vida del pedido. Cambiar esto requeriría un change propio con análisis de impacto.

### D-04: Menú ADMIN no agrega items nuevos; se ratifica la unión existente
**Decisión**: `NAVIGATION_ITEMS` ya expone correctamente todos los items de gestión con `allowedRoles` que incluyen `'ADMIN'`. No se agregan items nuevos. Se crea un spec `frontend-admin-menu-exposure` que formaliza el invariante: ningún item de gestión puede agregarse sin incluir `'ADMIN'` en `allowedRoles`.

**Justificación**: La regla de unión de `filterNavItems` (Change 08, D-08) garantiza que ADMIN ve la unión de todos los items de todos sus roles. No se introduce un mecanismo especial para ADMIN — la regla general ya lo cubre.

## Matriz de permisos consolidada

### Catálogo (US-064)

| Endpoint | Método | Roles | Spec de respaldo |
|---|---|---|---|
| `/api/v1/categorias/` | GET (tree) | Público | backend-categorias-management |
| `/api/v1/categorias/{id}` | GET | Público | backend-categorias-management |
| `/api/v1/categorias/` | POST | ADMIN, STOCK | backend-categorias-management |
| `/api/v1/categorias/{id}` | PUT | ADMIN, STOCK | backend-categorias-management |
| `/api/v1/categorias/{id}` | DELETE | ADMIN, STOCK | backend-categorias-management |
| `/api/v1/ingredientes/` | GET | ADMIN, STOCK | backend-ingredientes-management |
| `/api/v1/ingredientes/{id}` | GET | ADMIN, STOCK | backend-ingredientes-management |
| `/api/v1/ingredientes/` | POST | ADMIN, STOCK | backend-ingredientes-management |
| `/api/v1/ingredientes/{id}` | PUT | ADMIN, STOCK | backend-ingredientes-management |
| `/api/v1/ingredientes/{id}` | DELETE | ADMIN, STOCK | backend-ingredientes-management |
| `/api/v1/productos/` | GET (list) | Público | backend-products-management |
| `/api/v1/productos/{id}` | GET | Público | backend-products-management |
| `/api/v1/productos/` | POST | ADMIN | backend-products-management |
| `/api/v1/productos/{id}` | PATCH | ADMIN | backend-products-management |
| `/api/v1/productos/{id}` | DELETE | ADMIN | backend-products-management |
| `/api/v1/productos/{id}/disponibilidad` | PATCH | ADMIN, STOCK | backend-products-management |
| `/api/v1/productos/{id}/ingredientes` | GET | Público | backend-products-management |
| `/api/v1/productos/{id}/ingredientes` | POST | ADMIN | backend-products-management |
| `/api/v1/productos/{id}/ingredientes/{ing_id}` | DELETE | ADMIN | backend-products-management |

### Pedidos (US-065)

| Endpoint | Método | Roles | Spec de respaldo |
|---|---|---|---|
| `/api/v1/pedidos/` | POST | CLIENT, ADMIN | backend-order-creation |
| `/api/v1/pedidos/` | GET | CLIENT, PEDIDOS, ADMIN | backend-orders-listing |
| `/api/v1/pedidos/{id}` | GET | CLIENT (own), PEDIDOS, ADMIN | backend-orders-detail |
| `/api/v1/pedidos/{id}/estado` | PATCH | PEDIDOS, ADMIN | backend-order-state-machine |
| `/api/v1/pedidos/{id}/historial` | GET | CLIENT (own), PEDIDOS, ADMIN | backend-order-history |
| `/api/v1/pedidos/{id}` | DELETE | CLIENT (own only) | backend-order-state-machine |
| `/api/v1/pedidos/validar` | POST | CLIENT, ADMIN | backend-pre-checkout-validations |
| `/api/v1/pagos/{pedido_id}/latest` | GET | CLIENT (own), PEDIDOS, ADMIN | backend-pagos-management |

### Frontend navigation — Invariante ADMIN

| Item | Key | allowedRoles |
|---|---|---|
| Catálogo | catalog | CLIENT, ADMIN |
| Mi Carrito | cart | CLIENT, ADMIN |
| Mis Pedidos | orders | CLIENT, ADMIN |
| Mi Perfil | profile | CLIENT, ADMIN |
| Mis Direcciones | addresses | CLIENT, ADMIN |
| Productos (gestión) | stock-products | STOCK, ADMIN |
| Categorías (gestión) | stock-categories | STOCK, ADMIN |
| Ingredientes (gestión) | stock-ingredients | STOCK, ADMIN |
| Stock (inventario) | stock-inventory | STOCK, ADMIN |
| Panel de Pedidos | pedidos-panel | PEDIDOS, ADMIN |
| Usuarios | admin-users | ADMIN |
| Métricas | admin-metrics | ADMIN |

## Risks / Trade-offs

- [Riesgo mínimo] La auditoría confirma que el código ya está correcto. El riesgo es que si en el futuro se agregan endpoints sin actualizar la matriz en `backend-admin-aggregated-permissions`, el spec se vuelve stale. → Mitigación: incluir en la regla del spec la obligación de mantener la matriz actualizada en cualquier change que modifique RBAC de catálogo o pedidos.
- [Trade-off: ADMIN en productos.py es `require_role("ADMIN")` sin STOCK] Los endpoints de CRUD completo de productos (`POST /`, `PATCH /{id}`, `DELETE /{id}`) usan solo `require_role("ADMIN")` — STOCK no tiene acceso a CRUD de productos, solo a disponibilidad. Esto es correcto según Integrador §5.2 y se ratifica explícitamente en el spec (no es un gap).
- [Deuda documentada] `incluir_eliminados` mencionado en US-064 nota (RN-CA10) no se implementa en este change. Se documenta como deuda para Change 23.

## Open Questions

Ninguna activa. Todas las decisiones están resueltas por la auditoría del código y las decisiones previas (D-15 Change 20, D-12 Change 18).
