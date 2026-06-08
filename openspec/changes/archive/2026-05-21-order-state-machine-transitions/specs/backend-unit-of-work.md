# backend-unit-of-work Specification — delta

## MODIFIED Requirements (Change 18: order-state-machine-transitions)

### Supersession Notice

Change 17 (`order-creation-with-snapshots`) established the following restriction in the `backend-unit-of-work` spec:

> Note: `DetallePedido` and `HistorialEstadoPedido` operations are consolidated in `PedidoRepository` — no separate `uow.detalles_pedido` or `uow.historial_pedido` accessors are added.

**Change 18 revokes this restriction** for `uow.historial_pedido`. The restriction for `uow.detalles_pedido` remains in effect.

**Rationale**: `HistorialEstadoPedidoRepository` must NOT inherit `BaseRepository[T]`. Inheriting `BaseRepository[T]` would expose `update()` and `delete()` methods on the repository class, which directly violates the append-only invariant (RN-FS07 / RN-03). To enforce the append-only contract at the class level — not merely by convention — `HistorialEstadoPedidoRepository` must be a standalone class that defines only `append()` and `list_by_pedido()`. Because it is a distinct repository class (not consolidated into `PedidoRepository`), it requires its own dedicated typed accessor on `UnitOfWork`.

---

### Requirement: `uow.historial_pedido` accessor — HistorialEstadoPedidoRepository

`UnitOfWork` SHALL expose a typed `historial_pedido` lazy `@property` accessor that returns a `HistorialEstadoPedidoRepository` instance. The instance SHALL be created on first access and cached in a private `_historial_pedido` attribute, following the same lazy property pattern as all other UoW accessors (`uow.pedidos`, `uow.productos`, etc.).

The `HistorialEstadoPedidoRepository` instance SHALL receive `self._session` in its constructor and SHALL use that session for all database operations. This guarantees the append-only repository participates in the same transaction as all other repositories in the UoW.

**Import path**: `from app.modules.pedidos.repositories.historial_estado_repository import HistorialEstadoPedidoRepository`

**Accessor contract**:
```python
@property
def historial_pedido(self) -> HistorialEstadoPedidoRepository:
    if self._historial_pedido is None:
        self._historial_pedido = HistorialEstadoPedidoRepository(self._session)
    return self._historial_pedido
```

#### Scenario: uow.historial_pedido returns HistorialEstadoPedidoRepository
- **WHEN** `uow.historial_pedido` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `HistorialEstadoPedidoRepository`
- **THEN** the repository has no `update()` or `delete()` methods accessible

#### Scenario: historial_pedido shares the UoW session (atomicity)
- **WHEN** a state transition uses both `uow.pedidos.update_estado(...)` and `uow.historial_pedido.append(...)` within the same `async with UnitOfWork()` block
- **THEN** both operations are committed together when the UoW exits cleanly
- **THEN** if an exception occurs after `update_estado` but before `append`, both writes are rolled back atomically
- **NOTE**: Session sharing is verified indirectly via atomicity behavior, not by inspecting private `_session` attributes from test code.

#### Scenario: Existing UoW accessors unaffected
- **WHEN** `uow.historial_pedido` is added to `UnitOfWork`
- **THEN** all pre-existing accessors (`uow.pedidos`, `uow.productos`, `uow.usuarios`, `uow.categorias`, `uow.ingredientes`, `uow.direcciones`, `uow.refresh_tokens`) continue to function correctly
- **THEN** no existing test breaks due to the addition of `uow.historial_pedido`
