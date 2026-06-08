# Tasks: order-state-machine-transitions (Change 18)

Implementation checklist. All tasks reference specs in `openspec/changes/order-state-machine-transitions/specs/`. Group ordering follows the dependency chain: schemas → constants → repository → service → router → tests → frontend.

---

## Group 1 — Backend Schemas

- [x] **1.1** Create `backend/app/modules/pedidos/schemas/pedido_estado_update.py`
  - Define `PedidoEstadoUpdate(BaseModel)` with `nuevo_estado: str` and `motivo: str | None = None`.
  - Do NOT add a Pydantic validator for the "motivo required when CANCELADO" rule. That rule is contextual (depends on `nuevo_estado`) and must produce `{ "detail": "motivo es obligatorio al cancelar", "code": "MOTIVO_REQUIRED" }` — a format Pydantic standard validation cannot produce. The enforcement belongs exclusively in the service (Task 4.3).
  - Define `CancelBody(BaseModel)` with `motivo: str | None = None` (optional body for CLIENT DELETE).

- [x] **1.2** Create `backend/app/modules/pedidos/schemas/historial_read.py`
  - Define `HistorialRead(BaseModel)` with fields: `id: UUID`, `pedido_id: UUID`, `estado_desde: str | None`, `estado_hacia: str`, `motivo: str | None`, `actor_user_id: UUID | None`, `created_at: datetime`.
  - Add `model_config = ConfigDict(from_attributes=True)`.
  - Export from `app/modules/pedidos/schemas/__init__.py` if applicable.

---

## Group 2 — FSM Constants

- [x] **2.1** Create `backend/app/modules/pedidos/services/state_transition.py` — constants section
  - Define `EstadoPedido(StrEnum)` with all 6 states.
  - Define `TERMINAL_STATES: frozenset[str]`.
  - Define `ALLOWED_TRANSITIONS: dict[str, dict[str, set[str]]]` as specified in design.md.
  - Add a module-level docstring referencing RN-FS01, RN-RB08, and noting PENDIENTE→CONFIRMADO is excluded (Change 19 only).

---

## Group 3 — Repository

- [x] **3.1** Create `backend/app/modules/pedidos/repositories/historial_estado_repository.py`
  - Define `HistorialEstadoPedidoRepository` — does NOT inherit `BaseRepository[T]`.
  - Implement `async def append(self, row: HistorialEstadoPedido) -> HistorialEstadoPedido` — `self._session.add(row)`, `await self._session.flush()`, return row.
  - Implement `async def list_by_pedido(self, pedido_id: UUID) -> list[HistorialEstadoPedido]` — SELECT ORDER BY `created_at ASC`.
  - No `update()` or `delete()` methods. Add class-level docstring: "Append-only — RN-FS07 / RN-03. No UPDATE or DELETE operations are permitted at any layer."
  - Store `self._session: AsyncSession` in `__init__` (PRIVATE attribute — never expose a public `session` property).

- [x] **3.2** Add `uow.historial_pedido` lazy property accessor to `backend/app/core/uow.py`
  - Import `HistorialEstadoPedidoRepository` from the new module.
  - Add `@property historial_pedido` with private cache `self._historial_pedido` following existing pattern (see `uow.pedidos`).

---

## Group 4 — Service

- [x] **4.1** Add `validate_transition_allowed` function to `state_transition.py`
  - Signature: `def validate_transition_allowed(current_state: str, nuevo_estado: str, actor_role: str) -> None`
  - Raises `HTTPException(409, code="TERMINAL_STATE")` if `current_state` in `TERMINAL_STATES`.
  - Raises `HTTPException(409, code="INVALID_TRANSITION")` if `nuevo_estado` not in `ALLOWED_TRANSITIONS.get(current_state, {})`.
  - Raises `HTTPException(403, code="CANCEL_NOT_ALLOWED_FOR_ROLE")` if `actor_role` not in `ALLOWED_TRANSITIONS[current_state][nuevo_estado]`.

- [x] **4.2** Add `_restore_stock` helper function to `state_transition.py`
  - Signature: `async def _restore_stock(uow: UnitOfWork, pedido_id: UUID) -> None`
  - Fetches all `DetallePedido` rows for `pedido_id`.
  - For each row: executes `UPDATE producto SET stock_cantidad = stock_cantidad + :qty WHERE id = :id RETURNING stock_cantidad` (via `uow.productos` or raw SQL statement — keep it within UoW session).
  - Does NOT commit — that is UoW's responsibility.

- [x] **4.3** Implement module-level function `transition_state` in `state_transition.py` (NOT a class method)
  - Signature: `async def transition_state(uow: UnitOfWork, pedido_id: UUID, nuevo_estado: str, motivo: str | None, actor_role: str, actor_user_id: UUID) -> Pedido`
  - Step 1: `pedido = await uow.pedidos.get_for_update(pedido_id)` — raise `HTTPException(404, detail="El pedido no fue encontrado.", code="ORDER_NOT_FOUND")` if None. (get_for_update created in Task 4.6)
  - Step 2: Call `validate_transition_allowed(current_state, nuevo_estado, actor_role)`.
  - Step 3: If `nuevo_estado == "CANCELADO"` and not motivo: `raise HTTPException(status_code=422, detail="motivo es obligatorio al cancelar", code="MOTIVO_REQUIRED")`. This is the SOLE enforcement of the motivo rule — NOT in the schema.
  - Step 4: If `nuevo_estado == "CANCELADO"` and `current_state in {"CONFIRMADO", "EN_PREP"}`: call `await _restore_stock(uow, pedido_id)`.
  - Step 5: `await uow.pedidos.update_estado(pedido_id, nuevo_estado)`.
  - Step 6: `await uow.historial_pedido.append(HistorialEstadoPedido(pedido_id=pedido_id, estado_desde=current_state, estado_hacia=nuevo_estado, motivo=motivo, actor_user_id=actor_user_id))`.
  - Return updated `Pedido`.

- [x] **4.4** Implement module-level function `cancel_own_client` in `state_transition.py` (NOT a class method)
  - Signature: `async def cancel_own_client(uow: UnitOfWork, pedido_id: UUID, motivo: str | None, actor_user_id: UUID, requesting_user_id: UUID) -> Pedido`
  - Step 1: `pedido = await uow.pedidos.get_for_update(pedido_id)` — raise `HTTPException(404, detail="El pedido no fue encontrado.", code="ORDER_NOT_FOUND")` if None.
  - Step 2: Check `pedido.usuario_id == requesting_user_id` — raise `HTTPException(403, detail="No tiene permiso para operar sobre este pedido.", code="ORDER_NOT_OWNED")` if not.
  - Step 3: Check `pedido.estado_codigo in {"PENDIENTE", "CONFIRMADO"}` — raise `HTTPException(409, detail="Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint.", code="INVALID_TRANSITION")` if not. This handles EN_PREP, EN_CAMINO, ENTREGADO, and CANCELADO.
  - Step 4: If `pedido.estado_codigo == "CONFIRMADO"`: call `await _restore_stock(uow, pedido_id)`. If `pedido.estado_codigo == "PENDIENTE"`: skip (stock was not decremented — Change 19 hasn't run).
  - Step 5: Resolve `motivo = motivo or "Cancelado por el cliente"`.
  - Step 6: `await uow.pedidos.update_estado(pedido_id, "CANCELADO")`.
  - Step 7: `await uow.historial_pedido.append(...)`.
  - Return updated `Pedido`.

- [x] **4.5** Add `update_estado` method to `PedidoRepository` in `backend/app/modules/pedidos/repositories/pedido_repository.py` (or equivalent path established by Change 17)
  - Signature: `async def update_estado(self, pedido_id: UUID, nuevo_estado: str) -> Pedido`
  - Executes `UPDATE pedido SET estado_codigo = :nuevo_estado WHERE id = :pedido_id RETURNING *`, flushes, returns updated row.
  - The FOR UPDATE lock is acquired by `get_for_update` (Task 4.6) before calling this method.

- [x] **4.6** Add `get_for_update` method to `PedidoRepository`
  - Signature: `async def get_for_update(self, pedido_id: UUID) -> Pedido | None`
  - Executes `SELECT * FROM pedido WHERE id = :pedido_id FOR UPDATE` (pessimistic row lock).
  - Returns the `Pedido` instance if found, `None` otherwise.
  - This method MUST be called before reading `pedido.estado_codigo` in any transition service function.

---

## Group 5 — Router

- [x] **5.1** Add `PATCH /{id}/estado` endpoint to `backend/app/api/v1/pedidos.py`
  - Dependencies: `require_role(["PEDIDOS", "ADMIN"])`, `uow: UnitOfWork = Depends(get_uow)`, `current_user = Depends(get_current_user)`.
  - Body: `body: PedidoEstadoUpdate`.
  - Calls `transition_state(uow, id, body.nuevo_estado, body.motivo, actor_role=current_user.role, actor_user_id=current_user.id)` — module-level function imported from `state_transition.py`.
  - Returns `response_model=PedidoRead`, HTTP 200.
  - Place this route BEFORE any generic `/{id}` route to avoid path conflict.

- [x] **5.2** Add `DELETE /{id}` endpoint to `backend/app/api/v1/pedidos.py`
  - Dependencies: `require_role(["CLIENT"])`, `uow: UnitOfWork = Depends(get_uow)`, `current_user = Depends(get_current_user)`.
  - Body: `body: CancelBody = Body(default=None)` (optional).
  - Calls `cancel_own_client(uow, id, body.motivo if body else None, actor_user_id=current_user.id, requesting_user_id=current_user.id)` — module-level function from `state_transition.py`. Accepts PENDIENTE and CONFIRMADO states (see Task 4.4); returns 409 for all other states.
  - Returns `response_model=PedidoRead`, HTTP 200.

- [x] **5.3** Add `GET /{id}/historial` endpoint to `backend/app/api/v1/pedidos.py`
  - Dependencies: `require_role(["CLIENT", "PEDIDOS", "ADMIN"])`, `uow: UnitOfWork = Depends(get_uow)`, `current_user = Depends(get_current_user)`.
  - If `current_user.role == "CLIENT"`: verify `pedido.usuario_id == current_user.id` — raise `HTTPException(403, code="ORDER_NOT_OWNED")` if not.
  - Calls `uow.historial_pedido.list_by_pedido(id)`.
  - Returns `response_model=list[HistorialRead]`, HTTP 200.

---

## Group 6 — Backend Unit Tests

- [x] **6.1** Unit tests for `validate_transition_allowed`
  - `tests/unit/test_state_transition_validator.py`
  - Happy: all valid advance transitions (CONFIRMADO→EN_PREP with PEDIDOS, EN_PREP→EN_CAMINO with ADMIN, EN_CAMINO→ENTREGADO with PEDIDOS).
  - Error: skip state (CONFIRMADO→EN_CAMINO) → `INVALID_TRANSITION`.
  - Error: manual PENDIENTE→CONFIRMADO → `INVALID_TRANSITION`.
  - Error: ENTREGADO→anything → `TERMINAL_STATE`.
  - Error: CANCELADO→anything → `TERMINAL_STATE`.
  - Error: PEDIDOS tries to cancel EN_PREP → `CANCEL_NOT_ALLOWED_FOR_ROLE`.
  - Happy: ADMIN cancels EN_PREP → passes.

- [x] **6.2** Unit tests for module-level `transition_state` function (mocked UoW)
  - `tests/unit/test_pedido_state_service.py`
  - Mock `uow.pedidos.get_for_update` (# get_for_update implementado en Tarea 4.6), `uow.pedidos.update_estado`, `uow.historial_pedido.append`, `uow.productos`.
  - Happy: advance CONFIRMADO→EN_PREP — verifies `update_estado` called with "EN_PREP", `append` called once, `_restore_stock` NOT called.
  - Happy: cancel CONFIRMADO with PEDIDOS — verifies `_restore_stock` IS called, then `update_estado("CANCELADO")`.
  - Happy: cancel EN_PREP with ADMIN — verifies `_restore_stock` called.
  - Error: order not found → 404.
  - Error: MOTIVO_REQUIRED on cancel without motivo → 422 with `code="MOTIVO_REQUIRED"` (raised by service, not schema).
  - Error: INVALID_TRANSITION for wrong state → 409.

- [x] **6.3** Unit tests for module-level `cancel_own_client` function (mocked UoW)
  - Mock `uow.pedidos.get_for_update` (# get_for_update implementado en Tarea 4.6).
  - Happy: CLIENT cancels own PENDIENTE → `update_estado("CANCELADO")` called, default motivo substituted, `_restore_stock` NOT called.
  - Happy: CLIENT cancels own CONFIRMADO → `_restore_stock` IS called, then `update_estado("CANCELADO")`.
  - Error: ORDER_NOT_OWNED when different user.
  - Error: INVALID_TRANSITION (409) when state is EN_PREP (CLIENT cannot cancel via DELETE from EN_PREP). Verify error detail: "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint."
  - Error: INVALID_TRANSITION (409) when state is EN_CAMINO.

- [x] **6.4** Unit tests for `HistorialEstadoPedidoRepository`
  - Verify `append()` calls `session.add` and `session.flush`.
  - Verify `list_by_pedido()` builds correct query with ORDER BY.
  - Verify no `update()` or `delete()` method exists on the class.

- [x] **6.5** Unit tests for router endpoints (TestClient, mocked service)
  - `tests/unit/test_pedidos_router_state.py`
  - PATCH happy paths (mock `transition_state` to return a valid `Pedido`):
    - `CONFIRMADO → EN_PREP` with rol PEDIDOS → 200
    - `EN_PREP → EN_CAMINO` with rol PEDIDOS → 200
    - `EN_CAMINO → ENTREGADO` with rol PEDIDOS → 200
    - `EN_PREP → CANCELADO` with rol ADMIN (with motivo) → 200
    - `CONFIRMADO → CANCELADO` with rol PEDIDOS (with motivo) → 200
  - PATCH error paths: CLIENT token → 403; missing body → 422.
  - DELETE happy paths: CLIENT own PENDIENTE → 200; CLIENT own CONFIRMADO → 200 (with stock restore mocked).
  - DELETE error paths: PEDIDOS token → 403; missing order → 404; EN_PREP state → 409 INVALID_TRANSITION.
  - GET historial: STOCK token → 403; CLIENT own order → 200; CLIENT other's order → 403.

---

## Group 7 — Backend Integration Tests

- [x] **7.1** Integration test: stock restored on cancel from CONFIRMADO
  - `tests/integration/test_stock_restore_on_cancel.py`
  - **TEST MARKER**: `@pytest.mark.integration`
  - Setup (explicit — do NOT use vague "set known stock values"):
    1. Create a product with `stock_cantidad = 10` (known baseline).
    2. Create an order with 3 units of that product. Set `estado_codigo = "CONFIRMADO"` directly in the test DB.
    3. Set `producto.stock_cantidad = 7` directly in the test DB — simulating the state post-Change-19 where stock was decremented upon confirmation. # Nota: simula estado post-Change-19 donde stock fue decrementado al confirmar. Change 19 es propietario de ese decremento.
  - Execute: `PATCH /api/v1/pedidos/{id}/estado` with `{ nuevo_estado: "CANCELADO", motivo: "test" }` using a valid PEDIDOS staff token.
  - Assert:
    1. Response HTTP 200.
    2. `producto.stock_cantidad == 10` (restored exactly by `detalle.cantidad = 3`).
    3. `pedido.estado_codigo == "CANCELADO"`.
    4. One new `HistorialEstadoPedido` row with `estado_desde = "CONFIRMADO"`, `estado_hasta = "CANCELADO"`.
    5. Rollback test: if `historial_pedido.append()` raises an exception, verify `stock_cantidad` is NOT changed (transaction atomicity — still 7, not 10).

- [x] **7.2** Integration test: concurrent transition requests — only one succeeds
  - `tests/integration/test_concurrent_transition.py`
  - **TEST MARKER**: `@pytest.mark.integration`
  - Use `asyncio.gather` to fire two simultaneous PATCH `CONFIRMADO→EN_PREP` requests.
  - Assert: exactly one HTTP 200, one HTTP 409 `INVALID_TRANSITION`.
  - Assert: exactly one `HistorialEstadoPedido` row written.

---

## Group 8 — Frontend: Hooks and API

- [x] **8.1** Create `frontend/src/features/pedido-state-actions/api/pedidoEstadoApi.ts`
  - Export `patchEstadoPedido(pedidoId, payload)`, `deletePedido(pedidoId, motivo?)`, `getHistorialPedido(pedidoId)` using the shared Axios client.
  - Export error code → toast message map `ESTADO_ERROR_MESSAGES`.
  - Define and export `FRONTEND_ALLOWED_TRANSITIONS` TypeScript constant that mirrors exactly the backend `ALLOWED_TRANSITIONS` map (including the corrected PENDIENTE→CANCELADO = ["PEDIDOS","ADMIN"] and CLIENT PENDIENTE/CONFIRMADO via DELETE). Include the following comment:
    ```typescript
    // Fuente normativa: backend ALLOWED_TRANSITIONS en state_transition.py.
    // El backend es la única fuente de verdad para permisos de transición;
    // este mapa se usa SOLO para optimización de UI (ocultar botones).
    // La autorización real ocurre en el backend.
    ```

- [x] **8.2** Create `frontend/src/features/pedido-state-actions/hooks/useTransitionEstado.ts`
  - `useMutation` calling `patchEstadoPedido`.
  - `onSuccess`: invalidate `pedidoEstadoKeys.detail` and `pedidoEstadoKeys.historial`.
  - `onError`: call toast with `ESTADO_ERROR_MESSAGES[error.code] ?? fallback`.

- [x] **8.3** Create `frontend/src/features/pedido-state-actions/hooks/useCancelarPedidoCliente.ts`
  - `useMutation` calling `deletePedido`.
  - `onSuccess`: invalidate `pedidoEstadoKeys.detail` and `pedidoEstadoKeys.list`.

- [x] **8.4** Create `frontend/src/features/pedido-state-actions/hooks/useHistorialPedido.ts`
  - `useQuery` with key `pedidoEstadoKeys.historial(pedidoId)` calling `getHistorialPedido`.

- [x] **8.5** Create `frontend/src/features/pedido-state-actions/index.ts`
  - Barrel export: all hooks, `pedidoEstadoKeys`, `EstadoActionBar`, `CancelReasonModal`.

---

## Group 9 — Frontend: Components

- [x] **9.1** Create `frontend/src/features/pedido-state-actions/components/CancelReasonModal.tsx`
  - Controlled modal (`isOpen`, `onClose`, `onConfirm`, `isPending` props).
  - Textarea for `motivo` (required, `minLength=1` after trim).
  - Confirm button disabled when `motivo.trim().length === 0` or `isPending`.
  - Calls `onConfirm(motivo.trim())` on submit.

- [x] **9.2** Create `frontend/src/features/pedido-state-actions/components/EstadoActionBar.tsx`
  - Props: `{ pedidoId, currentEstado, userRole, onCancelClick }`.
  - Mirror FSM map as a TypeScript constant `FRONTEND_ALLOWED_TRANSITIONS` defined in `pedidoEstadoApi.ts` (see Task 8.1). Import it here for client-side filtering of available actions.
  - Renders advance buttons calling `useTransitionEstado().mutateAsync`.
  - Renders cancel button calling `onCancelClick` (delegates to modal).
  - Renders nothing (or status badge) for terminal states.
  - IMPORTANT: the `FRONTEND_ALLOWED_TRANSITIONS` map is UI-only. Authorization is always validated on the backend. Never use this map as a security gate.

---

## Group 10 — Frontend Tests

- [x] **10.1** Vitest unit tests for hooks (`tests/features/pedido-state-actions/hooks.test.ts`)
  - Mock `pedidoEstadoApi` with `vi.mock`.
  - `useTransitionEstado`: verify mutation calls correct API function; verify `onSuccess` calls `queryClient.invalidateQueries` with correct keys.
  - `useCancelarPedidoCliente`: same pattern for DELETE.
  - `useHistorialPedido`: verify `useQuery` is called with `pedidoEstadoKeys.historial(id)`.

- [x] **10.2** Vitest component tests for `CancelReasonModal`
  - Confirm button disabled initially and with empty/whitespace input.
  - `onConfirm` called with trimmed value when text present and button clicked.
  - `isPending` disables button.

- [x] **10.3** Vitest component tests for `EstadoActionBar`
  - CONFIRMADO + PEDIDOS: shows EN_PREP and cancel buttons, not ENTREGADO.
  - EN_PREP + PEDIDOS: shows EN_CAMINO button, no cancel button.
  - EN_PREP + ADMIN: shows EN_CAMINO AND cancel button.
  - ENTREGADO + ADMIN: no action buttons rendered.
  - CANCELADO + ADMIN: no action buttons rendered.
  - PENDIENTE + CLIENT: only cancel button rendered.

---

## Group 11 — Wiring

- [x] **11.1** Verify `backend/app/api/v1/pedidos.py` imports are complete: `transition_state`, `cancel_own_client` (module-level functions from `state_transition.py`), `PedidoEstadoUpdate`, `CancelBody`, `HistorialRead`, `get_uow`, `require_role`, `get_current_user`.

- [x] **11.2** Verify `backend/app/core/uow.py` has `historial_pedido` property and import is correct (as documented in Task 3.2 and delta spec `specs/backend-unit-of-work.md`).

---

## Post-Implementation Verification

> These items are not implementation tasks — they are post-apply verification steps to confirm the change is complete.

- [x] **V-01** Confirm `openspec status --change order-state-machine-transitions --json` returns `isComplete: true` after all groups above are complete.
