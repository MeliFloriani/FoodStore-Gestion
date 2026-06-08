# Design: order-state-machine-transitions (Change 18)

## Architecture Overview

```
HTTP Request
    │
    ▼
app/api/v1/pedidos.py  (pedidos_router)
    │  require_role(...)  ← FastAPI Depends — coarse-grained RBAC by endpoint
    │  validate schema    ← PedidoEstadoUpdate / optional CancelBody
    │
    ▼
app/modules/pedidos/services/state_transition.py
    │  PedidoStateService.transition_state(uow, pedido_id, nuevo_estado, motivo, actor)
    │  PedidoStateService.cancel_own_client(uow, pedido_id, motivo, actor)
    │    ├─ validate_transition_allowed(current_state, nuevo_estado, actor_role)  ← FSM + fine-grained RBAC
    │    ├─ validate_motivo_if_cancel(nuevo_estado, motivo)
    │    └─ (if cancel from CONFIRMADO or EN_PREP) restore_stock(uow, pedido_id)
    │
    ▼
app/core/uow.py  (UnitOfWork)
    │  async with UnitOfWork() as uow:
    ├─ uow.pedidos           → PedidoRepository          (get + update_estado)
    ├─ uow.historial_pedido  → HistorialEstadoPedidoRepository  (append ONLY)
    └─ uow.productos         → ProductoRepository         (restore_stock)
    │
    ▼
PostgreSQL
    ├─ SELECT pedido FOR UPDATE   (pessimistic lock — prevents concurrent transitions)
    ├─ UPDATE pedido SET estado_codigo = :nuevo
    ├─ INSERT historial_estado_pedido (append-only)
    └─ UPDATE producto SET stock_cantidad = stock_cantidad + :qty  (conditional)
```

## Separation of Concerns

Six responsibilities are explicitly separated into distinct functions/modules:

| Responsibility | Module / Function |
|---|---|
| (a) FSM transition validation | `state_transition.py` → `validate_transition_allowed()` (module-level function) |
| (b) RBAC authorization | Router `require_role` (coarse) + `validate_transition_allowed` role check (fine) |
| (c) Transactional state mutation | `state_transition.py` → `transition_state(uow, ...)` via `uow.pedidos.update_estado()` |
| (d) Stock restoration | `state_transition.py` → `_restore_stock(uow, pedido_id)` (module-level private function) |
| (e) Append-only history write | `HistorialEstadoPedidoRepository.append()` — no update/delete methods |
| (f) API exposure | `app/api/v1/pedidos.py` — HTTP only, no business logic |

## Module Additions

All new files are added to the existing `app/modules/pedidos/` structure (created by Change 17):

```
backend/app/
├── api/v1/
│   └── pedidos.py                          ← MODIFIED: add 3 new endpoints
├── core/
│   └── uow.py                              ← MODIFIED: add uow.historial_pedido accessor
└── modules/pedidos/
    ├── model.py                            ← unchanged (tables exist from Ch03/17)
    ├── schemas/
    │   ├── pedido_estado_update.py         ← NEW: PedidoEstadoUpdate, CancelBody
    │   └── historial_read.py              ← NEW: HistorialRead
    ├── repositories/
    │   └── historial_estado_repository.py ← NEW: append-only, no update/delete
    └── services/
        └── state_transition.py            ← NEW: module-level functions (not a class)

frontend/src/features/
└── pedido-state-actions/                  ← NEW feature slice
    ├── api/
    │   └── pedidoEstadoApi.ts             ← Axios calls
    ├── hooks/
    │   ├── useTransitionEstado.ts         ← useMutation PATCH
    │   ├── useCancelarPedidoCliente.ts    ← useMutation DELETE
    │   └── useHistorialPedido.ts          ← useQuery GET historial
    ├── components/
    │   ├── EstadoActionBar.tsx            ← button group per current state
    │   └── CancelReasonModal.tsx          ← modal with mandatory reason input
    └── index.ts                           ← barrel export
```

## FSM Constants

```python
# app/modules/pedidos/services/state_transition.py

from enum import StrEnum

class EstadoPedido(StrEnum):
    PENDIENTE  = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    EN_PREP    = "EN_PREP"
    EN_CAMINO  = "EN_CAMINO"
    ENTREGADO  = "ENTREGADO"
    CANCELADO  = "CANCELADO"

TERMINAL_STATES: frozenset[str] = frozenset({EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO})

# Structure: {current_state: {next_state: set_of_allowed_roles}}
# Roles that may perform each specific transition
ALLOWED_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    EstadoPedido.PENDIENTE: {
        # CLIENT cancela PENDIENTE exclusivamente via DELETE /pedidos/{id} — ver cancel_own_client()
        EstadoPedido.CANCELADO: {"PEDIDOS", "ADMIN"},
    },
    EstadoPedido.CONFIRMADO: {
        EstadoPedido.EN_PREP:   {"PEDIDOS", "ADMIN"},
        EstadoPedido.CANCELADO: {"PEDIDOS", "ADMIN"},
    },
    EstadoPedido.EN_PREP: {
        EstadoPedido.EN_CAMINO: {"PEDIDOS", "ADMIN"},
        EstadoPedido.CANCELADO: {"ADMIN"},           # RN-RB08: ADMIN only
    },
    EstadoPedido.EN_CAMINO: {
        EstadoPedido.ENTREGADO: {"PEDIDOS", "ADMIN"},
    },
    # ENTREGADO and CANCELADO: no outgoing transitions (terminal)
}
```

> Note: `PENDIENTE → CONFIRMADO` is NOT in `ALLOWED_TRANSITIONS` — that transition is exclusively automatic (Change 19 webhook). Any manual attempt to set `nuevo_estado = CONFIRMADO` will result in `INVALID_TRANSITION`.

## Error Catalog

| Code | HTTP | Trigger |
|------|------|---------|
| `ORDER_NOT_FOUND` | 404 | `pedido_id` does not exist — detail: "El pedido no fue encontrado." |
| `ORDER_NOT_OWNED` | 403 | CLIENT attempts DELETE on an order that is not theirs — detail: "No tiene permiso para operar sobre este pedido." |
| `TERMINAL_STATE` | 409 | Transition attempted from ENTREGADO or CANCELADO (RN-FS06 / RN-01) — detail: "El pedido está en un estado terminal y no admite más transiciones." |
| `INVALID_TRANSITION` | 409 | Transition not in `ALLOWED_TRANSITIONS` for current state (including PENDIENTE→CONFIRMADO, and CLIENT DELETE from EN_PREP/EN_CAMINO/ENTREGADO/CANCELADO) — detail: "La transición solicitada no es válida desde el estado actual." For CLIENT DELETE from non-cancellable state: "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint." |
| `CANCEL_NOT_ALLOWED_FOR_ROLE` | 403 | Role not in the allowed set for the requested transition (fine-grained, e.g. PEDIDOS trying to cancel EN_PREP) — detail: "Su rol no tiene permiso para cancelar pedidos en este estado." |
| `MOTIVO_REQUIRED` | 422 | `nuevo_estado = CANCELADO` but `motivo` is null or empty (RN-05) — detail: "motivo es obligatorio al cancelar." |

## Sequence Diagrams

### 1. PATCH transition (advance)

```
Client (PEDIDOS/ADMIN)
  │
  │  PATCH /api/v1/pedidos/{id}/estado
  │  { nuevo_estado: "EN_CAMINO", motivo: null }
  ▼
pedidos_router
  │  require_role(["PEDIDOS","ADMIN"])
  │  parse PedidoEstadoUpdate
  ▼
transition_state(uow, pedido_id, nuevo_estado, motivo, actor_role, actor_user_id)  ← module-level function
  │  uow.pedidos.get_for_update(pedido_id)  ← SELECT FOR UPDATE (pessimistic lock)
  │  check TERMINAL_STATES                  ← raise TERMINAL_STATE if applies
  │  check ALLOWED_TRANSITIONS              ← raise INVALID_TRANSITION or CANCEL_NOT_ALLOWED_FOR_ROLE
  │  validate_motivo_if_cancel              ← raise MOTIVO_REQUIRED if applies (service, not schema)
  │  uow.pedidos.update_estado(pedido_id, nuevo_estado)
  │  uow.historial_pedido.append(HistorialEstadoPedido(
  │    pedido_id, estado_desde=current, estado_hacia=nuevo,
  │    motivo, actor_user_id
  │  ))
  │  [UoW commits atomically]
  ▼
200 PedidoRead
```

### 2. Cancel from CONFIRMADO with stock restoration

```
Staff (PEDIDOS/ADMIN)
  │
  │  PATCH /api/v1/pedidos/{id}/estado
  │  { nuevo_estado: "CANCELADO", motivo: "Cliente solicitó cancelación" }
  ▼
transition_state(uow, pedido_id, "CANCELADO", motivo, actor_role, actor_user_id)  ← module-level function
  │  uow.pedidos.get_for_update(pedido_id)
  │  current_state = "CONFIRMADO"
  │  check ALLOWED_TRANSITIONS["CONFIRMADO"]["CANCELADO"] → {"PEDIDOS","ADMIN"} ✓
  │  validate_motivo → present ✓
  │  _restore_stock(uow, pedido_id)
  │    └─ SELECT detalle_pedido WHERE pedido_id = :id
  │       UPDATE producto SET stock_cantidad = stock_cantidad + :qty
  │         WHERE id = :producto_id RETURNING stock_cantidad   (per product)
  │  uow.pedidos.update_estado(pedido_id, "CANCELADO")
  │  uow.historial_pedido.append(...)
  │  [UoW commits atomically — all or nothing]
  ▼
200 PedidoRead
```

### 3. CLIENT DELETE flow (cancel own PENDIENTE or CONFIRMADO)

```
Client (CLIENT role)
  │
  │  DELETE /api/v1/pedidos/{id}
  │  body: { motivo: "Ya no lo necesito" }  ← optional
  ▼
pedidos_router
  │  require_role(["CLIENT"])
  │  extract current_user from JWT
  ▼
cancel_own_client(uow, pedido_id, motivo, actor_user_id)
  │  SELECT pedido FOR UPDATE
  │  check pedido.usuario_id == current_user.id  ← raise ORDER_NOT_OWNED if not
  │  check current_state in {"PENDIENTE", "CONFIRMADO"}
  │    ← raise INVALID_TRANSITION (409) if state is EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO
  │    detail: "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint."
  │  if current_state == "CONFIRMADO": call _restore_stock(uow, pedido_id)  ← atomic stock restore
  │  if current_state == "PENDIENTE": skip stock restore (Change 19 hasn't decremented yet)
  │  motivo defaults to "Cancelado por el cliente" if None
  │  uow.pedidos.update_estado(pedido_id, "CANCELADO")
  │  uow.historial_pedido.append(...)
  │  [UoW commits atomically — stock restore + state + history, or full rollback]
  ▼
200 PedidoRead
```

> For states EN_PREP, EN_CAMINO, ENTREGADO, and CANCELADO: CLIENT DELETE returns 409 `INVALID_TRANSITION` with detail "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint."

### 4. GET historial

```
Any authenticated user
  │
  │  GET /api/v1/pedidos/{id}/historial
  ▼
pedidos_router
  │  require_role(["CLIENT","PEDIDOS","ADMIN"])  ← STOCK excluded at dependency level
  │  fetch pedido to check ownership if CLIENT
  ▼
200 List[HistorialRead] ORDER BY created_at ASC
```

## Concurrency Control

- Before reading `pedido.estado_codigo` in the service, execute `SELECT * FROM pedido WHERE id = :id FOR UPDATE`. This pessimistic lock ensures that if two concurrent requests target the same order, the second waits until the first commits or rolls back. Without this lock, two concurrent PATCH requests could both read the same state and both attempt the transition, leading to an inconsistent state.
- Stock restoration uses `UPDATE producto SET stock_cantidad = stock_cantidad + :qty WHERE id = :id RETURNING stock_cantidad` — the additive expression is safe under lock because each UPDATE acquires a row-level lock on the producto row. Products are updated in ascending `id` order (same convention as Change 17's lock ordering) to prevent deadlocks when multiple products are involved.

## Migration Assessment

**No migration required.** All necessary tables and columns exist:
- `pedido` table with `estado_codigo VARCHAR(20)` — Change 03/17.
- `historial_estado_pedido` table with `id`, `pedido_id`, `estado_desde`, `estado_hacia`, `motivo`, `actor_user_id`, `created_at` — Change 03/17.
- `detalle_pedido` table with `producto_id`, `cantidad` — Change 03/17.
- `producto` table with `stock_cantidad` — Change 03/17.

## Frontend Module: `pedido-state-actions`

Located at `frontend/src/features/pedido-state-actions/`.

### TanStack Query Keys

```typescript
export const pedidoEstadoKeys = {
  historial: (pedidoId: string) => ['pedido', pedidoId, 'historial'] as const,
  // 'pedido' list key (for invalidation) aligns with Change 20's future panel
  list: () => ['pedidos'] as const,
  detail: (id: string) => ['pedido', id] as const,
}
```

### Hook Contracts

**`useTransitionEstado(pedidoId: string)`**
- `useMutation` → `PATCH /api/v1/pedidos/{pedidoId}/estado`
- Payload: `{ nuevo_estado: string, motivo?: string }`
- `onSuccess`: invalidates `pedidoEstadoKeys.detail(pedidoId)` and `pedidoEstadoKeys.historial(pedidoId)`
- Returns: `{ mutateAsync, isPending, isError, error }`

**`useCancelarPedidoCliente(pedidoId: string)`**
- `useMutation` → `DELETE /api/v1/pedidos/{pedidoId}` with optional body `{ motivo?: string }`
- `onSuccess`: invalidates `pedidoEstadoKeys.detail(pedidoId)`, `pedidoEstadoKeys.list()`
- Returns: `{ mutateAsync, isPending, isError, error }`

**`useHistorialPedido(pedidoId: string)`**
- `useQuery` → `GET /api/v1/pedidos/{pedidoId}/historial`
- Query key: `pedidoEstadoKeys.historial(pedidoId)`
- Returns: `{ data: HistorialRead[], isLoading, isError }`

### Components

**`EstadoActionBar`** — receives `currentEstado: string`, `pedidoId: string`, `userRole: string`. Renders available action buttons based on the FSM map (what transitions are possible from `currentEstado` for `userRole`). Triggers `useTransitionEstado` or opens `CancelReasonModal`.

**`CancelReasonModal`** — controlled modal with a required textarea for `motivo`. Submit is disabled until `motivo.trim().length > 0`. On confirm calls the appropriate mutation. On API error maps `MOTIVO_REQUIRED` / `CANCEL_NOT_ALLOWED_FOR_ROLE` / `INVALID_TRANSITION` to user-facing toast messages.

### Error Mapping to Toasts

| Backend code | Toast message |
|---|---|
| `INVALID_TRANSITION` | "Transición de estado no permitida desde el estado actual." |
| `TERMINAL_STATE` | "El pedido ya está en un estado terminal y no puede modificarse." |
| `MOTIVO_REQUIRED` | "Debes ingresar un motivo para cancelar el pedido." |
| `CANCEL_NOT_ALLOWED_FOR_ROLE` | "Tu rol no permite cancelar pedidos en este estado." |
| `ORDER_NOT_FOUND` | "Pedido no encontrado." |
| `ORDER_NOT_OWNED` | "No puedes cancelar un pedido que no es tuyo." |

---

## Decision Log (design-level)

**D-09 — Change 18 supersedes Change 17 restriction on separate UoW accessors**
Change 17 explicitly stated "no separate `uow.historial_pedido` accessor" to simplify the UoW interface. Change 18 revokes this restriction. Rationale: `HistorialEstadoPedidoRepository` cannot inherit `BaseRepository[T]` (that would expose `update()` and `delete()` methods, violating the append-only invariant RN-FS07 / RN-03 at the class level). Because it is a distinct repository class with a distinct contract, it requires a dedicated typed accessor `uow.historial_pedido → HistorialEstadoPedidoRepository`. The delta spec `specs/backend-unit-of-work.md` (in this change) formally supersedes the Change 17 constraint and documents the new accessor contract.

**D-10 — US-043 ambiguity resolved in favor of Integrador §3.4 + RN-FS08**
US-043 in Historias_de_usuario.txt mentions rejection of cancellation from EN_PREP, which conflicts with Integrador §3.4 and RN-FS08, which permit ADMIN to cancel from EN_PREP (with stock restoration). Change 18 follows Integrador §3.4 as the authoritative technical specification. EN_CAMINO and terminal states (ENTREGADO, CANCELADO) do NOT permit cancellation from any role. This decision is also documented normatively in `specs/backend-order-state-machine.md`.

**D-11 — `motivo` validation is the service's responsibility, not the schema's**
A Pydantic validator on `PedidoEstadoUpdate` for the "motivo required when CANCELADO" rule would produce a standard 422 without the `{ "code": "MOTIVO_REQUIRED" }` field required by the error catalog (RFC 7807-style). The only valid enforcement point is the service (`state_transition.py`), which raises `HTTPException(422, detail="motivo es obligatorio al cancelar", code="MOTIVO_REQUIRED")`. The schema defines `motivo: str | None` without contextual validation. This keeps the error format consistent across all business-rule violations.

**D-12 — Functions not class for `state_transition.py`**
`state_transition.py` defines module-level functions (`transition_state`, `cancel_own_client`, `validate_transition_allowed`, `_restore_stock`) rather than a class. All functions are stateless (all state lives in the UoW and database). Using a class (`PedidoStateService`) adds unnecessary indirection: the router would need to instantiate the class or call static methods with no benefit. Module-level functions are simpler, directly importable, and consistent with the project's existing service pattern (see `crear_pedido` in `pedidos_service.py`).
