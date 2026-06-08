## ADDED Requirements

### Requirement: Pedidos listing y detail endpoints registrados en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL exponer dos nuevos endpoints bajo el prefijo `/pedidos` (ya registrado por Changes 17 y 18):

1. `GET /api/v1/pedidos` — listado paginado con discriminación RBAC (CLIENT/PEDIDOS/ADMIN)
2. `GET /api/v1/pedidos/{id}` — detalle completo del pedido (CLIENT propietario/PEDIDOS/ADMIN)

Estos endpoints SHALL registrarse en el mismo `pedidos_router` de `backend/app/api/v1/pedidos.py` que ya contiene `POST /`, `PATCH /{id}/estado`, `DELETE /{id}`, y `GET /{id}/historial`. No se crea un router adicional.

> IMPORTANTE: `GET /{id}/historial` (Change 18) y `GET /` (listado, este change) deben declararse con paths estáticos o raíz ANTES de `GET /{id}` (detalle dinámico) para evitar ambigüedad de path matching en FastAPI. Orden recomendado: `POST /` → `GET /` → `PATCH /{id}/estado` → `GET /{id}/historial` → `GET /{id}` → `DELETE /{id}`.

#### Scenario: Endpoint GET /api/v1/pedidos es accesible con rol CLIENT
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos` con tag `"pedidos"`
- **THEN** la ruta requiere roles `CLIENT`, `PEDIDOS` o `ADMIN` (STOCK excluido)

#### Scenario: Endpoint GET /api/v1/pedidos/{id} es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos/{id}` con tag `"pedidos"`
- **THEN** la ruta requiere autenticación Bearer

#### Scenario: GET /api/v1/pedidos no colisiona con GET /api/v1/pedidos/{id}
- **WHEN** la app arranca con ambas rutas registradas
- **THEN** `GET /api/v1/pedidos` devuelve el listado paginado
- **THEN** `GET /api/v1/pedidos/some-uuid` devuelve el detalle de ese pedido
- **THEN** no hay ambigüedad de path matching

#### Scenario: Rutas existentes no se ven afectadas
- **WHEN** se agregan los dos nuevos endpoints GET al pedidos_router
- **THEN** `POST /api/v1/pedidos` (Change 17) sigue operativo
- **THEN** `PATCH /api/v1/pedidos/{id}/estado` (Change 18) sigue operativo
- **THEN** `DELETE /api/v1/pedidos/{id}` (Change 18) sigue operativo
- **THEN** `GET /api/v1/pedidos/{id}/historial` (Change 18) sigue operativo
- **THEN** todos los demás routers (`/auth/*`, `/productos/*`, `/catalog/*`, `/profile`, `/direcciones/*`, `/pedidos/validar`, `/pagos/*`) siguen operativos

#### Scenario: Nuevos endpoints no duplican el prefijo v1
- **WHEN** se resuelven los paths finales
- **THEN** el listado queda exactamente en `GET /api/v1/pedidos`
- **THEN** el detalle queda exactamente en `GET /api/v1/pedidos/{id}`
- **THEN** ningún path duplica el prefijo `/api/v1/api/v1/`

#### Scenario: Tag pedidos contiene los nuevos endpoints en OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** `GET /api/v1/pedidos` aparece bajo el tag `"pedidos"`
- **THEN** `GET /api/v1/pedidos/{id}` aparece bajo el tag `"pedidos"`
