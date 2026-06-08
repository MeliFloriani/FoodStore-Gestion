## Why

El rol ADMIN carece de acceso formal documentado a los endpoints de gestión de catálogo y pedidos, lo que lo hace operativamente dependiente de roles STOCK y PEDIDOS para resolver incidentes de producción. Este cambio cierra las US-064 y US-065 ratificando la matriz oficial de roles (Integrador §4.2 / §5.2): ADMIN ⊇ STOCK (catálogo) y ADMIN ⊇ PEDIDOS (pedidos), sin introducir endpoints nuevos ni modificar lógica de negocio.

## What Changes

- **Auditoría y ratificación** de los `require_role` en todos los endpoints de gestión de catálogo (`categorias`, `ingredientes`, `productos`) confirmando que incluyen `"ADMIN"`.
- **Auditoría y ratificación** de los `require_role` en todos los endpoints de gestión de pedidos (`pedidos`) confirmando las tuplas `("CLIENT","PEDIDOS","ADMIN")` para listado/detalle/historial y `("PEDIDOS","ADMIN")` para transición de estado.
- **Documentación explícita** de `DELETE /pedidos/{id}` como CLIENT-only por diseño (Change 18, D-12); la cancelación administrativa se realiza vía `PATCH /pedidos/{id}/estado` con `nuevo_estado=CANCELADO`.
- **Ratificación del menú ADMIN** en `NAVIGATION_ITEMS`: los items de gestión (`stock-*`, `pedidos-panel`) ya tienen `allowedRoles` que incluyen `'ADMIN'`; este cambio confirma el invariante y agrega tests si faltan.
- **No se crean endpoints nuevos**, no se modifica lógica de negocio (FSM, snapshots, stock, pagos), no se altera el modelo de datos.

## Capabilities

### New Capabilities
- `backend-admin-aggregated-permissions`: Matriz RBAC oficial de ADMIN sobre catálogo y pedidos. Documenta la regla: cualquier endpoint de gestión que acepte STOCK también acepta ADMIN; cualquier endpoint que acepte PEDIDOS también acepta ADMIN. Casos explícitamente excluidos: `DELETE /pedidos/{id}` (CLIENT-only), creación de pedido `POST /pedidos` (CLIENT/ADMIN), validación pre-checkout `POST /pedidos/validar` (CLIENT/ADMIN).
- `frontend-admin-menu-exposure`: Invariante del menú ADMIN — el menú renderizado para un usuario con rol ADMIN expone todos los items de gestión (`stock-products`, `stock-categories`, `stock-ingredients`, `stock-inventory`, `pedidos-panel`, `admin-users`, `admin-metrics`). Regla: ningún item de gestión puede agregarse en el futuro sin incluir `'ADMIN'` en su `allowedRoles`.

### Modified Capabilities
- `backend-products-management`: Ratificación explícita de que ADMIN tiene acceso completo a todos los endpoints write de productos; PATCH `/disponibilidad` acepta `("ADMIN","STOCK")`.
- `backend-categorias-management`: Ratificación explícita de que todos los endpoints write aceptan `("ADMIN","STOCK")`.
- `backend-ingredientes-management`: Ratificación explícita de que todos los endpoints (incluidos los read de gestión interna) aceptan `("ADMIN","STOCK")`.
- `backend-order-state-machine`: Ratificación de `PATCH /{id}/estado` con `("PEDIDOS","ADMIN")` y documentación de que `DELETE /{id}` es CLIENT-only (cancelación administrativa = PATCH /estado).
- `backend-orders-listing`: Ratificación de `GET /` con `("CLIENT","PEDIDOS","ADMIN")`.
- `backend-orders-detail`: Ratificación de `GET /{id}` con acceso ADMIN vía `get_current_user` + RBAC en service.
- `backend-order-history`: Ratificación de `GET /{id}/historial` con `("CLIENT","PEDIDOS","ADMIN")`.
- `frontend-navigation`: ADDED Requirement — el menú renderiza items de gestión cuando el rol activo es ADMIN (ratifica invariante de `filterNavItems` con `['ADMIN']`).

## Impact

- **Backend**: Ninguna modificación de código necesaria si la auditoría confirma que todos los `require_role` ya son correctos. Si se detectan gaps, ajuste quirúrgico de la tupla en el router afectado.
- **Frontend**: Ninguna modificación de código necesaria; `NAVIGATION_ITEMS` ya expone items de gestión para ADMIN. Se agregan tests de cobertura.
- **Tests**: Tests de humo RBAC nuevos: `test_admin_access_catalog.py` y `test_admin_access_pedidos.py` (backend), `navigation.admin.test.ts` (frontend).
- **Specs**: Dos specs nuevas + deltas mínimos en 7 specs existentes.
- **Dependencias**: Change 11 (catalog-products-management), Change 18 (order-state-machine-transitions), Change 19 (payments-mercadopago-integration), Change 20 (orders-visualization).
- **Riesgos**: Muy bajo. Cambio "ligero pero crítico" — solo ajusta documentación y agrega tests. Decisión D-15 (ADMIN es exclusivamente rol de gestión, no CLIENT) prevalece sin cambios.
