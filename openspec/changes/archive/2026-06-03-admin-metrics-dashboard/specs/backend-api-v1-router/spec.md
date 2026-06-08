## ADDED Requirements

### Requirement: Admin metricas router mounted in build_v1_router
The `build_v1_router` factory in `backend/app/api/v1/router.py` SHALL include the admin metricas router from `backend/app/modules/admin/metricas/router.py` via `router.include_router(metricas_router, prefix="/admin/metricas", tags=["admin-metricas"])`. The final mounted paths SHALL be:
- `GET /api/v1/admin/metricas/resumen`
- `GET /api/v1/admin/metricas/ventas`
- `GET /api/v1/admin/metricas/productos-top`
- `GET /api/v1/admin/metricas/pedidos-por-estado`

#### Scenario: Metricas endpoints reachable under /api/v1/admin/metricas
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/admin/metricas/resumen` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/ventas` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/productos-top` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/pedidos-por-estado` exists as a registered route

#### Scenario: Metricas router prefix does not duplicate
- **WHEN** the final route paths are resolved
- **THEN** the path is exactly `/api/v1/admin/metricas/resumen` (not `/api/v1/api/v1/admin/metricas/resumen`)
