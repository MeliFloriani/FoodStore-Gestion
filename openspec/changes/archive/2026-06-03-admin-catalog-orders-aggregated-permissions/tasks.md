## 1. Auditoría de routers — catálogo

- [x] 1.1 Auditar `backend/app/api/v1/categorias.py` — confirmar que POST `/`, PUT `/{id}`, DELETE `/{id}` usan `require_role("ADMIN", "STOCK")` en sus `dependencies`
- [x] 1.2 Auditar `backend/app/api/v1/ingredientes.py` — confirmar que GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}` usan `require_role("ADMIN", "STOCK")`
- [x] 1.3 Auditar `backend/app/api/v1/productos.py` — confirmar que POST `/`, PATCH `/{id}`, DELETE `/{id}`, POST `/{id}/ingredientes`, DELETE `/{id}/ingredientes/{ing_id}` usan `require_role("ADMIN")`; y que PATCH `/{id}/disponibilidad` usa `require_role("ADMIN", "STOCK")`
- [x] 1.4 Documentar resultado de auditoría de catálogo: todos los `require_role` están correctos (sin modificaciones necesarias)

## 2. Auditoría de routers — pedidos y pagos

- [x] 2.1 Auditar `backend/app/api/v1/pedidos.py` — confirmar: POST `/` tiene `require_role("CLIENT","ADMIN")`; GET `/` tiene `require_role("CLIENT","PEDIDOS","ADMIN")`; PATCH `/{id}/estado` tiene `require_role("PEDIDOS","ADMIN")`; GET `/{id}/historial` tiene `require_role("CLIENT","PEDIDOS","ADMIN")`
- [x] 2.2 Auditar `backend/app/api/v1/pedidos.py` — confirmar: DELETE `/{id}` tiene `require_role("CLIENT")` exclusivamente (CLIENT-only por Change 18 D-12); GET `/{id}` usa `get_current_user` con RBAC en service
- [x] 2.3 Auditar `backend/app/api/v1/pedidos_validar.py` — confirmar `require_role("CLIENT","ADMIN")`
- [x] 2.4 Auditar `backend/app/pagos/router.py` — confirmar GET `/{pedido_id}/latest` tiene `require_role("CLIENT","PEDIDOS","ADMIN")`
- [x] 2.5 Documentar resultado de auditoría de pedidos: todos los `require_role` están correctos (sin modificaciones necesarias)

## 3. Auditoría de frontend navigation

- [x] 3.1 Auditar `frontend/src/shared/lib/navigation/items.ts` — confirmar que `stock-products`, `stock-categories`, `stock-ingredients`, `stock-inventory` tienen `allowedRoles: ['STOCK','ADMIN']`
- [x] 3.2 Auditar `frontend/src/shared/lib/navigation/items.ts` — confirmar que `pedidos-panel` tiene `allowedRoles: ['PEDIDOS','ADMIN']`
- [x] 3.3 Auditar `frontend/src/shared/lib/navigation/items.ts` — confirmar que `admin-users`, `admin-metrics` tienen `allowedRoles: ['ADMIN']`
- [x] 3.4 Documentar resultado de auditoría de navegación: todos los `allowedRoles` están correctos (sin modificaciones necesarias)

## 4. Tests RBAC backend — catálogo

- [x] 4.1 Crear `backend/tests/rbac/test_admin_access_catalog.py` con fixtures de usuario ADMIN
- [x] 4.2 Agregar smoke test: ADMIN → 201 en POST `/api/v1/categorias/`
- [x] 4.3 Agregar smoke test: ADMIN → 201 en POST `/api/v1/ingredientes/`
- [x] 4.4 Agregar smoke test: ADMIN → 201 en POST `/api/v1/productos/`
- [x] 4.5 Agregar smoke test: ADMIN → 200 en PATCH `/api/v1/productos/{id}/disponibilidad`
- [x] 4.6 Agregar smoke test: ADMIN → 204 en DELETE `/api/v1/categorias/{id}` (leaf, sin productos activos)
- [x] 4.7 Agregar smoke test: ADMIN → 204 en DELETE `/api/v1/ingredientes/{id}`
- [x] 4.8 Agregar smoke test: STOCK → 403 en POST `/api/v1/productos/` (verificar que STOCK no tiene CRUD completo de productos)

## 5. Tests RBAC backend — pedidos

- [x] 5.1 Crear `backend/tests/rbac/test_admin_access_pedidos.py` con fixtures de usuario ADMIN y pedidos de prueba
- [x] 5.2 Agregar smoke test: ADMIN → 200 en GET `/api/v1/pedidos/` (lista todos, no solo propios)
- [x] 5.3 Agregar smoke test: ADMIN → 200 en GET `/api/v1/pedidos/{id}` (cualquier pedido)
- [x] 5.4 Agregar smoke test: ADMIN → 200 en GET `/api/v1/pedidos/{id}/historial` (cualquier pedido)
- [x] 5.5 Agregar smoke test: ADMIN → 200 en PATCH `/api/v1/pedidos/{id}/estado` con transición válida
- [x] 5.6 Agregar smoke test: ADMIN → 403 en DELETE `/api/v1/pedidos/{id}` (CLIENT-only path)
- [x] 5.7 Agregar smoke test: STOCK → 403 en GET `/api/v1/pedidos/`

## 6. Tests frontend — navegación ADMIN

- [x] 6.1 Crear `frontend/src/shared/lib/navigation/__tests__/navigation.admin.test.ts`
- [x] 6.2 Test: `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` retorna exactamente 12 items
- [x] 6.3 Test: resultado incluye paths `/stock/products`, `/stock/categories`, `/stock/ingredients`, `/stock/inventory`
- [x] 6.4 Test: resultado incluye path `/pedidos-panel`
- [x] 6.5 Test: resultado incluye paths `/admin/users`, `/admin/metrics`
- [x] 6.6 Test: ningún path está duplicado en el resultado
- [x] 6.7 Test: render de `<Navigation>` con `user.roles = ['ADMIN']` muestra links a todos los items de gestión

## 7. Validación final

- [x] 7.1 Ejecutar `openspec validate "admin-catalog-orders-aggregated-permissions" --strict` y confirmar PASS con `isComplete: true`
- [x] 7.2 Ejecutar `openspec status --change "admin-catalog-orders-aggregated-permissions" --json` y confirmar todos los artifacts en estado `done`
- [x] 7.3 Confirmar que ningún archivo fuera de `openspec/changes/admin-catalog-orders-aggregated-permissions/` fue modificado
- [x] 7.4 Ejecutar suite de tests RBAC backend (`pytest backend/tests/rbac/ -v`) y confirmar todos PASS
- [x] 7.5 Ejecutar tests frontend de navegación ADMIN (`npm test -- navigation.admin`) y confirmar PASS
