# backend-admin-aggregated-permissions Specification

## Purpose
TBD - created by archiving change admin-catalog-orders-aggregated-permissions. Update Purpose after archive.
## Requirements
### Requirement: ADMIN aggregated RBAC rule for catalog management
The system SHALL enforce that any catalog management endpoint that accepts role STOCK MUST also accept role ADMIN. This is the ADMIN ⊇ STOCK aggregation principle.

The canonical require_role tuples for catalog management SHALL be:
- `POST /api/v1/categorias/` → `require_role("ADMIN", "STOCK")`
- `PUT /api/v1/categorias/{id}` → `require_role("ADMIN", "STOCK")`
- `DELETE /api/v1/categorias/{id}` → `require_role("ADMIN", "STOCK")`
- `GET /api/v1/ingredientes/` → `require_role("ADMIN", "STOCK")`
- `GET /api/v1/ingredientes/{id}` → `require_role("ADMIN", "STOCK")`
- `POST /api/v1/ingredientes/` → `require_role("ADMIN", "STOCK")`
- `PUT /api/v1/ingredientes/{id}` → `require_role("ADMIN", "STOCK")`
- `DELETE /api/v1/ingredientes/{id}` → `require_role("ADMIN", "STOCK")`
- `PATCH /api/v1/productos/{id}/disponibilidad` → `require_role("ADMIN", "STOCK")`
- `POST /api/v1/productos/` → `require_role("ADMIN")` (ADMIN-exclusive; STOCK has no full product CRUD — see D-01)
- `PATCH /api/v1/productos/{id}` → `require_role("ADMIN")`
- `DELETE /api/v1/productos/{id}` → `require_role("ADMIN")`
- `POST /api/v1/productos/{id}/ingredientes` → `require_role("ADMIN")`
- `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` → `require_role("ADMIN")`

Read endpoints for public catalog (`GET /api/v1/categorias/`, `GET /api/v1/categorias/{id}`, `GET /api/v1/productos/`, `GET /api/v1/productos/{id}`, `GET /api/v1/productos/{id}/ingredientes`) are public — no authentication required.

#### Scenario: ADMIN can create a category
- **WHEN** `POST /api/v1/categorias/` is called with a valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `CategoriaRead`

#### Scenario: ADMIN can create an ingredient
- **WHEN** `POST /api/v1/ingredientes/` is called with a valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `IngredienteRead`

#### Scenario: ADMIN can create a product
- **WHEN** `POST /api/v1/productos/` is called with a valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `ProductoRead`

#### Scenario: ADMIN can update product availability
- **WHEN** `PATCH /api/v1/productos/{id}/disponibilidad` is called with a valid ADMIN JWT and `{"disponible": false}`
- **THEN** response is HTTP 200 with updated `ProductoRead`

#### Scenario: ADMIN can delete a category
- **WHEN** `DELETE /api/v1/categorias/{id}` is called with a valid ADMIN JWT for a leaf category with no active products
- **THEN** response is HTTP 204 No Content

#### Scenario: ADMIN can delete an ingredient
- **WHEN** `DELETE /api/v1/ingredientes/{id}` is called with a valid ADMIN JWT
- **THEN** response is HTTP 204 No Content

---

### Requirement: ADMIN aggregated RBAC rule for order management
The system SHALL enforce that any order management endpoint that accepts role PEDIDOS MUST also accept role ADMIN. This is the ADMIN ⊇ PEDIDOS aggregation principle.

The canonical require_role tuples for order management SHALL be:
- `POST /api/v1/pedidos/` → `require_role("CLIENT", "ADMIN")` (order creation — CLIENT initiates, ADMIN can create on behalf)
- `GET /api/v1/pedidos/` → `require_role("CLIENT", "PEDIDOS", "ADMIN")` (CLIENT sees own; PEDIDOS/ADMIN see all)
- `GET /api/v1/pedidos/{id}` → authenticated via `get_current_user`; RBAC enforced in service (CLIENT: ownership check; PEDIDOS/ADMIN: any order; STOCK: 403)
- `PATCH /api/v1/pedidos/{id}/estado` → `require_role("PEDIDOS", "ADMIN")`
- `GET /api/v1/pedidos/{id}/historial` → `require_role("CLIENT", "PEDIDOS", "ADMIN")` (CLIENT: ownership check; PEDIDOS/ADMIN: any)
- `DELETE /api/v1/pedidos/{id}` → `require_role("CLIENT")` ONLY — CLIENT self-cancellation path; administrative cancellation MUST use PATCH /estado with `nuevo_estado=CANCELADO`
- `POST /api/v1/pedidos/validar` → `require_role("CLIENT", "ADMIN")`
- `GET /api/v1/pagos/{pedido_id}/latest` → `require_role("CLIENT", "PEDIDOS", "ADMIN")`

#### Scenario: ADMIN can list all orders
- **WHEN** `GET /api/v1/pedidos/` is called with a valid ADMIN JWT
- **THEN** response is HTTP 200 with `Page[PedidoListItem]` containing all orders in the system (not filtered by user)

#### Scenario: ADMIN can advance order state
- **WHEN** `PATCH /api/v1/pedidos/{id}/estado` is called with a valid ADMIN JWT and `{"nuevo_estado": "EN_PREP"}`
- **WHEN** the order is in state `CONFIRMADO`
- **THEN** response is HTTP 200 with `PedidoRead` showing `estado_codigo = "EN_PREP"`

#### Scenario: ADMIN can cancel an order via PATCH estado
- **WHEN** `PATCH /api/v1/pedidos/{id}/estado` is called with a valid ADMIN JWT and `{"nuevo_estado": "CANCELADO", "motivo": "Cancelado por administración"}`
- **WHEN** the order is in a cancellable state (PENDIENTE, CONFIRMADO, or EN_PREP per RN-RB08)
- **THEN** response is HTTP 200 with `PedidoRead` showing `estado_codigo = "CANCELADO"`

#### Scenario: ADMIN cannot cancel via DELETE endpoint
- **WHEN** `DELETE /api/v1/pedidos/{id}` is called with a valid ADMIN JWT
- **THEN** response is HTTP 403 (ADMIN is not in `require_role("CLIENT")`)
- **THEN** administrative cancellation MUST be performed via `PATCH /api/v1/pedidos/{id}/estado`

#### Scenario: ADMIN can view order detail
- **WHEN** `GET /api/v1/pedidos/{id}` is called with a valid ADMIN JWT for any existing order
- **THEN** response is HTTP 200 with `PedidoDetail` regardless of order ownership

#### Scenario: ADMIN can view order history
- **WHEN** `GET /api/v1/pedidos/{id}/historial` is called with a valid ADMIN JWT
- **THEN** response is HTTP 200 with `list[HistorialEstadoPedidoRead]` for any order

#### Scenario: STOCK role is blocked from order management
- **WHEN** `GET /api/v1/pedidos/` is called with a valid STOCK JWT
- **THEN** response is HTTP 403

---

### Requirement: RBAC exclusion documentation — endpoints explicitly out of scope for ADMIN aggregation
The system SHALL document the following endpoints as intentionally NOT subject to the ADMIN ⊇ STOCK / ADMIN ⊇ PEDIDOS aggregation rule. These exclusions MUST be preserved in all future changes.

**`DELETE /api/v1/pedidos/{id}`** — CLIENT-only self-cancellation path. Rationale: this endpoint is semantically a client action (cancelling one's own order). ADMIN and PEDIDOS MUST perform administrative cancellation exclusively via `PATCH /{id}/estado` with `nuevo_estado=CANCELADO`. This separation was established in Change 18 (D-12) and SHALL remain CLIENT-only.

**`POST /api/v1/pagos/`** and **`POST /api/v1/pagos/crear`** — CLIENT-only payment initiation. ADMIN SHALL NOT initiate payments on behalf of clients.

**`POST /api/v1/pagos/webhook`** — public IPN handler, no authentication required.

#### Scenario: RBAC exclusion for DELETE /pedidos/{id} is intentional and documented
- **WHEN** a design review is performed on the RBAC matrix
- **THEN** `DELETE /api/v1/pedidos/{id}` with `require_role("CLIENT")` is confirmed as correct
- **THEN** no change to this endpoint's `require_role` is made in this change or future changes without an explicit architecture decision

#### Scenario: ADMIN cannot initiate a payment
- **WHEN** `POST /api/v1/pagos/` is called with a valid ADMIN JWT
- **THEN** response is HTTP 403 (ADMIN is not in `require_role("CLIENT")` for payment initiation)

