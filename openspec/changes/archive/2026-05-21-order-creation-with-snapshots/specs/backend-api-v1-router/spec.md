## MODIFIED Requirements

### Requirement: Pedidos router montado en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL incluir el router de pedidos importado desde `backend/app/api/v1/pedidos.py` mediante `from app.api.v1.pedidos import pedidos_router` seguido de `router.include_router(pedidos_router, prefix="/pedidos", tags=["pedidos"])`. El endpoint resultante SHALL quedar montado en `{settings.API_V1_PREFIX}/pedidos` (ej: `/api/v1/pedidos`).

El router de pedidos SHALL NOT incluirse en `app/main.py` directamente — siempre se registra a través de `build_v1_router`.

El router SHALL declarar sus propios paths sin prefijo `/pedidos` (ese lo aporta `build_v1_router`). El path de creación de pedido SHALL ser `POST /` (raíz del router), resultando en `POST /api/v1/pedidos`.

> IMPORTANTE: El router de pedidos (Change 17) y el router de pedidos-validacion (Change 16) comparten el mismo prefijo `/pedidos` en `build_v1_router`. El router de Change 16 define el path `/validar`; el de Change 17 define el path `/` (raíz). FastAPI resuelve correctamente ambos sin colisión.

#### Scenario: Endpoint POST /api/v1/pedidos es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `POST /api/v1/pedidos` con tag `"pedidos"`

#### Scenario: Router pedidos no duplica el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de creación queda exactamente en `POST /api/v1/pedidos` (no `/api/v1/api/v1/pedidos`)

#### Scenario: Router pedidos coexiste con router pedidos-validacion sin colisión
- **WHEN** la app arranca con ambos routers montados bajo el prefijo `/pedidos`
- **THEN** `POST /api/v1/pedidos/validar` sigue operativo (Change 16)
- **THEN** `POST /api/v1/pedidos` es el nuevo endpoint de creación (Change 17)
- **THEN** no hay ambigüedad de path matching entre los dos routers

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agrega el router de pedidos en `build_v1_router`
- **THEN** los endpoints pre-existentes (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`, `/api/v1/pedidos/validar`) siguen operativos sin cambios

#### Scenario: Tag pedidos aparece en schema OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** existe una sección con tag `"pedidos"` en el schema OpenAPI
- **THEN** el endpoint `POST /api/v1/pedidos` aparece bajo ese tag
