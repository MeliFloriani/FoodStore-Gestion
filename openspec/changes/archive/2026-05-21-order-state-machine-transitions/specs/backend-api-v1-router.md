# backend-api-v1-router Specification — delta

## ADDED Requirements (Change 18: order-state-machine-transitions)

### Requirement: Tres nuevos endpoints pedidos registrados en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL exponer tres nuevos endpoints bajo el prefijo `/pedidos` (ya registrado por Change 17):

1. `PATCH /api/v1/pedidos/{id}/estado` — transición de estado (staff)
2. `DELETE /api/v1/pedidos/{id}` — cancelación propia (CLIENT)
3. `GET /api/v1/pedidos/{id}/historial` — historial de estados

Estos endpoints SHALL registrarse en el mismo `pedidos_router` de `backend/app/api/v1/pedidos.py` que ya contiene `POST /` (Change 17). No se crea un router adicional.

> IMPORTANTE: `PATCH /{id}/estado` y `GET /{id}/historial` deben declararse ANTES de cualquier ruta `/{id}` genérica (si existe) para evitar ambigüedad de path matching en FastAPI. FastAPI evalúa rutas en orden de declaración.

#### Scenario: Endpoint PATCH /api/v1/pedidos/{id}/estado es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `PATCH /api/v1/pedidos/{id}/estado` con tag `"pedidos"`
- **THEN** la ruta requiere roles `PEDIDOS` o `ADMIN` (dependency `require_role`)

#### Scenario: Endpoint DELETE /api/v1/pedidos/{id} es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `DELETE /api/v1/pedidos/{id}` con tag `"pedidos"`
- **THEN** la ruta requiere rol `CLIENT` (dependency `require_role`)

#### Scenario: Endpoint GET /api/v1/pedidos/{id}/historial es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos/{id}/historial` con tag `"pedidos"`
- **THEN** la ruta requiere roles `CLIENT`, `PEDIDOS` o `ADMIN` (STOCK excluido)

#### Scenario: Nuevos endpoints no duplican el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de transición queda exactamente en `/api/v1/pedidos/{id}/estado`
- **THEN** ningún path duplica el prefijo `/api/v1/api/v1/`

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agregan los tres nuevos endpoints al pedidos_router
- **THEN** `POST /api/v1/pedidos` (Change 17) sigue operativo
- **THEN** `POST /api/v1/pedidos/validar` (Change 16) sigue operativo
- **THEN** todos los demás routers (`/auth/*`, `/productos/*`, `/catalog/*`, `/profile`, `/direcciones/*`) siguen operativos
