## MODIFIED Requirements

### Requirement: Typed repository accessor — uow.pedidos

`UnitOfWork` SHALL expose a typed repository instance for the order domain as a lazy `@property` accessor, following the same pattern as existing accessors (`uow.usuarios`, `uow.productos`, etc.). The accessor returns a new repository instance on first access and caches it in a private attribute. It shares the same `AsyncSession` as all other accessors.

> Note: `DetallePedido` and `HistorialEstadoPedido` operations are consolidated in `PedidoRepository` — no separate `uow.detalles_pedido` or `uow.historial_pedido` accessors are added.

New accessors added by Change 17 (`order-creation-with-snapshots`):

- `uow.pedidos` → `PedidoRepository(self._session)`

The import SHALL use `from app.repositories.pedido import PedidoRepository` (layer-first path). The accessor SHALL be implemented as a `@property` with cache `self._pedidos` following the existing lazy property pattern in `backend/app/core/uow.py`.

#### Scenario: uow.pedidos returns PedidoRepository
- **WHEN** `uow.pedidos` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `PedidoRepository`
- **THEN** `uow.pedidos.session` is the same object as `uow.session` (shared session)

#### Scenario: uow.pedidos shares session with uow.productos
- **WHEN** both `uow.pedidos` and `uow.productos` are accessed in the same `async with` block
- **THEN** `uow.pedidos.session is uow.productos.session` evaluates to `True`
- **THEN** changes made through both repositories are part of the same transaction

#### Scenario: Existing accessors unaffected by addition of uow.pedidos
- **WHEN** `uow.usuarios`, `uow.productos`, `uow.categorias`, `uow.ingredientes`, `uow.direcciones` are accessed
- **THEN** all return their correct typed instances as before
- **THEN** no existing test breaks due to the addition of `uow.pedidos`
