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
