## ADDED Requirements

### Requirement: Admin usuarios router mounted in build_v1_router

The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the admin usuarios router from `backend/app/api/v1/admin_usuarios.py` via:
```python
from app.api.v1.admin_usuarios import admin_usuarios_router
router.include_router(admin_usuarios_router, prefix="/admin/usuarios", tags=["admin-usuarios"])
```

The final mounted paths SHALL be:
- `GET /api/v1/admin/usuarios` — listado paginado con búsqueda y filtros
- `GET /api/v1/admin/usuarios/{id}` — detalle de un usuario
- `PUT /api/v1/admin/usuarios/{id}` — editar datos del usuario
- `PUT /api/v1/admin/usuarios/{id}/roles` — reemplazar roles del usuario
- `PATCH /api/v1/admin/usuarios/{id}/estado` — activar/desactivar usuario

The admin-usuarios router SHALL NOT be included in `app/main.py` directly — always registered through `build_v1_router`.

#### Scenario: Admin usuarios endpoints reachable under /api/v1/admin/usuarios
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/admin/usuarios` exists as a registered route
- **THEN** `PUT /api/v1/admin/usuarios/{id}/roles` exists as a registered route
- **THEN** `PATCH /api/v1/admin/usuarios/{id}/estado` exists as a registered route

#### Scenario: Admin usuarios router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint is exactly `GET /api/v1/admin/usuarios` (not `/api/v1/api/v1/admin/usuarios`)

#### Scenario: Existing routers are unaffected
- **WHEN** the admin-usuarios router is added to `build_v1_router`
- **THEN** all pre-existing endpoints (`/api/v1/auth/*`, `/api/v1/pedidos/*`, `/api/v1/productos/*`, `/api/v1/pagos/*`, etc.) remain operational

#### Scenario: admin-usuarios tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"admin-usuarios"` appears in the OpenAPI schema
- **THEN** all 5 admin-usuarios endpoints appear under that tag
