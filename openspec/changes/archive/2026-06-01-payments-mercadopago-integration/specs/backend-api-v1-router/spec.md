## ADDED Requirements

### Requirement: Pagos router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the pagos router from `backend/app/pagos/router.py` via `from app.pagos.router import pagos_router` followed by `router.include_router(pagos_router, prefix="/pagos", tags=["pagos"])`. The final mounted paths SHALL be:

- `POST /api/v1/pagos` — create payment (CLIENT) — canonical REST endpoint
- `POST /api/v1/pagos/crear` — **alias** pointing to the same handler as `POST /api/v1/pagos` (for Integrador §5.4 rubric compatibility — see design.md D-11). Returns identical response.
- `POST /api/v1/pagos/webhook` — IPN handler (public)
- `GET /api/v1/pagos/{pedido_id}/latest` — latest pago for a pedido (CLIENT, PEDIDOS, ADMIN)

The pagos router SHALL NOT be included in `app/main.py` directly — always registered through `build_v1_router`.

> **Alias declaration order**: `POST /pagos/crear` MUST be declared BEFORE `GET /pagos/{pedido_id}/latest` (and after `POST /pagos/webhook`) to avoid path matching ambiguity with the dynamic `{pedido_id}` segment.

> IMPORTANT: `POST /pagos/webhook` MUST be declared BEFORE `GET /pagos/{pedido_id}/latest` in the router to avoid path matching ambiguity. FastAPI evaluates routes in declaration order; the static segment `webhook` must precede the dynamic `{pedido_id}` segment.

#### Scenario: Alias POST /api/v1/pagos/crear is accessible and equivalent
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos/crear` exists as a registered route with tag `"pagos"`
- **THEN** it delegates to the same handler as `POST /api/v1/pagos`
- **THEN** it returns the same HTTP 201 `PagoResponse` on success

#### Scenario: Endpoint POST /api/v1/pagos is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos` exists as a registered route with tag `"pagos"`
- **THEN** the route requires role `CLIENT`

#### Scenario: Endpoint POST /api/v1/pagos/webhook is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos/webhook` exists as a registered route with tag `"pagos"`
- **THEN** the route has NO JWT auth dependency (public endpoint)

#### Scenario: Endpoint GET /api/v1/pagos/{pedido_id}/latest is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/pagos/{pedido_id}/latest` exists as a registered route with tag `"pagos"`
- **THEN** the route requires roles `CLIENT`, `PEDIDOS`, or `ADMIN`

#### Scenario: Pagos router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the create payment endpoint is exactly `POST /api/v1/pagos` (not `/api/v1/api/v1/pagos`)
- **THEN** the webhook endpoint is exactly `POST /api/v1/pagos/webhook`

#### Scenario: Pagos tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"pagos"` appears in the OpenAPI schema
- **THEN** all three pagos endpoints appear under that tag

#### Scenario: Existing routers are unaffected
- **WHEN** the pagos router is added to `build_v1_router`
- **THEN** all pre-existing endpoints (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`, `/api/v1/pedidos/*`) remain operational
