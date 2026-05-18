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
