## ADDED Requirements

### Requirement: Pedidos-validacion router montado en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL incluir el router de validación pre-checkout importado desde `backend/app/api/v1/pedidos_validar.py` mediante `from app.api.v1.pedidos_validar import pedidos_validar_router` seguido de `router.include_router(pedidos_validar_router, prefix="/pedidos", tags=["pedidos-validacion"])`. El endpoint resultante SHALL quedar montado en `{settings.API_V1_PREFIX}/pedidos/validar` (ej: `/api/v1/pedidos/validar`).

El router de pedidos-validación SHALL NOT incluirse en `app/main.py` directamente — siempre se registra a través de `build_v1_router`.

El router SHALL declarar su propio path `/validar` (sin prefijo `/pedidos` — ese lo aporta `build_v1_router`).

#### Scenario: Endpoint POST /api/v1/pedidos/validar es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `POST /api/v1/pedidos/validar` con tag `"pedidos-validacion"`

#### Scenario: Router pedidos-validacion no duplica el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de validación queda exactamente en `/api/v1/pedidos/validar` (no `/api/v1/api/v1/pedidos/validar`)

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agrega el router de pedidos-validación en `build_v1_router`
- **THEN** los endpoints pre-existentes (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`) siguen operativos sin cambios

#### Scenario: Tag pedidos-validacion aparece en schema OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** existe una sección con tag `"pedidos-validacion"` en el schema OpenAPI
- **THEN** el endpoint `POST /api/v1/pedidos/validar` aparece bajo ese tag
