# backend-unit-of-work Specification

## Purpose
Async context manager that owns all transaction lifecycle: session creation, commit on success, rollback on error. Introduced in Change 04 (`backend-base-patterns`). Every Service MUST use `UnitOfWork` — no Service may call `session.commit()` directly (Integrador §2.1, criterio rúbrica UoW).

## Requirements

### Requirement: Async context manager lifecycle
`UnitOfWork` SHALL be an async context manager implementing `__aenter__` and `__aexit__`. `__aenter__` SHALL open a new `AsyncSession` via `get_session_factory()()`. `__aexit__` SHALL commit the session if no exception was raised, or rollback and re-raise if any exception occurred, and SHALL always close the session in a `finally` block.

#### Scenario: Clean exit commits the transaction
- **WHEN** code runs `async with UnitOfWork() as uow:` and no exception is raised inside the block
- **THEN** `uow.session.commit()` is called exactly once on exit
- **THEN** the session is closed after commit
- **THEN** changes made via repository flush operations are persisted to the database

#### Scenario: Exception triggers rollback and re-raise
- **WHEN** code runs `async with UnitOfWork() as uow:` and an exception is raised inside the block
- **THEN** `uow.session.rollback()` is called
- **THEN** the session is closed after rollback
- **THEN** the exception is re-raised (not swallowed)
- **THEN** no data written during the block is persisted to the database

#### Scenario: Session is always closed regardless of outcome
- **WHEN** `UnitOfWork.__aexit__` is called with or without an exception
- **THEN** `uow.session.close()` is called in a `finally` block
- **THEN** the database connection is returned to the pool

#### Scenario: Session obtained from get_session_factory
- **WHEN** `UnitOfWork.__aenter__` runs
- **THEN** the session is created via `get_session_factory()()` (lazy singleton from `app.db.session`)
- **THEN** `expire_on_commit=False` is applied (inherited from factory configuration)

---

### Requirement: Typed repository accessors
`UnitOfWork` SHALL expose typed repository instances as attributes (e.g., `uow.usuarios`, `uow.roles`, `uow.refresh_tokens`, `uow.productos`, `uow.categorias`, `uow.ingredientes`, `uow.pedidos`, `uow.direcciones`). Repositories SHALL be instantiated lazily inside `__aenter__` and SHALL all share the same `AsyncSession` instance.

#### Scenario: Repository accessor returns correctly typed instance
- **WHEN** `uow.usuarios` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `UsuarioRepository`
- **THEN** `uow.usuarios.session` is the same object as `uow.session` (shared session)

#### Scenario: All repository accessors share the same session
- **WHEN** both `uow.usuarios` and `uow.roles` are accessed in the same `async with` block
- **THEN** `uow.usuarios.session is uow.roles.session` evaluates to `True`
- **THEN** changes made through both repositories are part of the same transaction

#### Scenario: Repository accessor not available outside context manager
- **WHEN** `uow.usuarios` is accessed outside an `async with UnitOfWork() as uow:` block (i.e., after `__aexit__`)
- **THEN** accessing the attribute raises `RuntimeError` or returns `None` (undefined state)

---

### Requirement: `get_uow` FastAPI dependency
`UnitOfWork` SHALL be accompanied by a `get_uow()` async generator function that yields a `UnitOfWork` instance for use with FastAPI `Depends()`.

#### Scenario: get_uow yields a UnitOfWork and cleans up
- **WHEN** a FastAPI route declares `uow: UnitOfWork = Depends(get_uow)`
- **THEN** `uow` is a live `UnitOfWork` instance with an active session during the request
- **THEN** after the route handler returns, the UoW's `__aexit__` is called (commit or rollback)
- **THEN** the session is closed before the response is sent

#### Scenario: get_uow is injectable via Depends in router
- **WHEN** a route handler function is defined as `async def handler(uow: UnitOfWork = Depends(get_uow))`
- **THEN** FastAPI resolves the dependency correctly
- **THEN** the route receives a UoW with `uow.session` ready to use

---

### Requirement: "No Service commits directly" invariant
NO Service, Router, or Repository SHALL call `session.commit()` directly. `session.commit()` is exclusively the responsibility of `UnitOfWork.__aexit__`. This is a hard architectural invariant enforced by code review and lint verification.

#### Scenario: Service orchestrates multiple repos without committing
- **WHEN** a Service method calls multiple repository operations within `async with get_uow() as uow:`
- **THEN** none of the Service method's code calls `session.commit()` directly
- **THEN** all writes are flushed (visible within the transaction) but not committed until UoW exits

#### Scenario: Static scan finds no commit outside uow.py
- **WHEN** `backend/app/` is scanned for `session.commit()` calls
- **THEN** the only match is within `backend/app/core/uow.py`
- **THEN** no match exists in any `service.py`, `router.py`, or `repository.py` file

#### Scenario: Mid-operation exception does not leave partial writes
- **WHEN** a Service creates entity A (flushed), then raises an exception before creating entity B
- **THEN** UoW `__aexit__` rolls back the entire transaction
- **THEN** entity A is NOT present in the database after rollback

---

### Requirement: Raw session not exposed outside UoW
`UnitOfWork` SHALL NOT expose `self.session` as part of its public API to consumers (Services and Routers). Services interact exclusively with repository accessor attributes. Only `UnitOfWork` internal code and test fixtures (via `app.db.session.get_session`) may access the session directly.

#### Scenario: Service does not access uow.session directly
- **WHEN** a Service method is implemented correctly
- **THEN** the Service code accesses only `uow.<repository_name>.<method>(...)` — not `uow.session`
- **THEN** there is no import of `AsyncSession` in `service.py` files

## MODIFIED Requirements

### Requirement: Typed repository accessors
`UnitOfWork` SHALL expose typed repository instances as attributes (e.g., `uow.usuarios`, `uow.roles`, `uow.refresh_tokens`, `uow.productos`, `uow.categorias`, `uow.ingredientes`, `uow.pedidos`, `uow.direcciones`). Repositories SHALL be instantiated lazily as `@property` accessors (NOT in `__aenter__`). Each accessor returns `RepositoryClass(self._session)` on access and caches the instance in a private `_repository_name` attribute. All repositories share the same `AsyncSession` instance.

The `uow.categorias` accessor SHALL be implemented by REPLACING the existing `NotImplementedError` stub for the `categorias` lazy property in `backend/app/core/uow.py`. The stub already defines a `categorias` property that raises `NotImplementedError`. The fix is to replace the stub body with the actual `CategoriaRepository(self._session)` instantiation, following the same lazy property pattern used by `uow.usuarios`, `uow.roles`, and other existing accessors. The import SHALL use `from app.repositories.categoria import CategoriaRepository` (layer-first path). This accessor is wired in Change 09 (`catalog-categories-management`).

#### Scenario: Repository accessor returns correctly typed instance
- **WHEN** `uow.usuarios` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `UsuarioRepository`
- **THEN** `uow.usuarios.session` is the same object as `uow.session` (shared session)

#### Scenario: uow.categorias returns CategoriaRepository
- **WHEN** `uow.categorias` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `CategoriaRepository`
- **THEN** `uow.categorias.session` is the same object as `uow.session` (shared session)

#### Scenario: All repository accessors share the same session
- **WHEN** both `uow.usuarios` and `uow.categorias` are accessed in the same `async with` block
- **THEN** `uow.usuarios.session is uow.categorias.session` evaluates to `True`
- **THEN** changes made through both repositories are part of the same transaction

#### Scenario: Repository accessor not available outside context manager
- **WHEN** `uow.usuarios` is accessed outside an `async with UnitOfWork() as uow:` block (i.e., after `__aexit__` or before `__aenter__`)
- **THEN** accessing the attribute raises `RuntimeError` (the lazy property checks `self._session is None` and raises before attempting to instantiate the repository)

## MODIFIED Requirements

### Requirement: Typed repository accessor — uow.pedidos

`UnitOfWork` SHALL expose a typed repository instance for the order domain as a lazy `@property` accessor, following the same pattern as existing accessors (`uow.usuarios`, `uow.productos`, etc.). The accessor returns a new repository instance on first access and caches it in a private attribute. It shares the same `AsyncSession` as all other accessors.

> Note: `DetallePedido` operations are consolidated in `PedidoRepository` — no separate `uow.detalles_pedido` accessor is added. The restriction on `uow.historial_pedido` that existed in Change 17 has been **superseded by Change 18** — see the MODIFIED Requirement below.

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

## MODIFIED Requirements (Change 18: order-state-machine-transitions)

### Supersession Notice

Change 17 (`order-creation-with-snapshots`) established the following restriction in this spec:

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
