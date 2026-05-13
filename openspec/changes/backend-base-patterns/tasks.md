## 1. Dependencies & Configuration

- [x] 1.1 Add `python-jose[cryptography]` to `backend/pyproject.toml` under `[project.dependencies]` (implements D-07: decode-only JWT capability)
- [x] 1.2 Regenerate `backend/requirements.txt` via `pip freeze` after installing the new dependency in the virtual environment
- [x] 1.3 Add `SECRET_KEY: SecretStr` (required, no default) to `Settings` in `backend/app/core/config.py` (implements `backend-auth-dependencies` Requirement: JWT-related Settings additions)
- [x] 1.4 Add `JWT_ALGORITHM: str = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES: int = 30`, `REFRESH_TOKEN_EXPIRE_DAYS: int = 7` to `Settings` in `backend/app/core/config.py`
- [x] 1.5 Update `backend/.env.example` with placeholder entries for `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` (implements spec scenario: `.env.example` contains JWT entries)

---

## 2. `core/security.py` — JWT Decode Helper

- [x] 2.1 Create `backend/app/core/security.py` with `decode_access_token(token: str) -> dict` using `jose.jwt.decode` (implements D-07; spec: `backend-auth-dependencies` Requirement: `core/security.py`)
- [x] 2.2 Import `get_settings` inside the function (lazy import to respect D-05 lazy singleton pattern) — do NOT instantiate settings at module level
- [x] 2.3 Wrap `JWTError` (and `ExpiredSignatureError`) in `UnauthorizedError("Token inválido o expirado", code="invalid_token")` from `app.core.exceptions` (implements spec scenarios: expired token, wrong signature)
- [x] 2.4 Verify that `security.py` does NOT contain `create_access_token`, `create_refresh_token`, `verify_password`, or any `passlib`/`bcrypt` imports (implements D-07 decode-only scope and spec: security.py does not contain issuance functions)

---

## 3. `repositories/base.py` — `BaseRepository[T]`

- [x] 3.1 Create `backend/app/repositories/__init__.py` (empty, marks package)
- [x] 3.2 Create `backend/app/repositories/base.py` with `T = TypeVar("T", bound=Base)` and `class BaseRepository(Generic[T])` (implements D-05; spec: `backend-base-repository` Requirement: Generic CRUD contract)
- [x] 3.3 Implement `__init__(self, model: type[T], session: AsyncSession) -> None` storing both as instance attributes (implements D-03: session injection invariant)
- [x] 3.4 Implement `get_by_id(self, id: UUID, include_deleted: bool = False) -> T | None` using `session.get()` or `select()` with soft-delete filter (implements D-04; spec scenarios: returns entity, returns None for soft-deleted, returns None for non-existent)
- [x] 3.5 Add `_active_filter()` helper method returning the SQLAlchemy column expression `Model.deleted_at == None` — reusable in custom queries to prevent R-04 (implements R-04 mitigation)
- [x] 3.6 Implement `list_all(self, skip, limit, filters, include_deleted) -> list[T]` applying soft-delete filter by default, skip/limit pagination (implements spec scenarios: excludes soft-deleted, pagination, include_deleted override)
- [x] 3.7 Implement `count(self, filters, include_deleted) -> int` using `select(func.count())` with same filter logic (implements spec: count returns correct total)
- [x] 3.8 Implement `create(self, obj: T) -> T` calling `session.add(obj)` then `await session.flush()` — NO `session.commit()` (implements spec scenario: create persists after flush; implements Requirement: flush-only semantics)
- [x] 3.9 Implement `update(self, id: UUID, data: dict) -> T | None`: fetch by id with active filter; if not found return None; iterate `data` skipping keys in `{'id','created_at','updated_at','deleted_at'}`; apply `setattr` for remaining keys; `await session.flush()`; return refreshed entity. Implements R-04 mitigation and HIGH-04 protected-field invariant.
- [x] 3.10 Implement `soft_delete(self, id: UUID) -> bool` — get entity (bypassing soft-delete filter to check if exists), call `entity.soft_delete()`, `await session.flush()`, return True/False (implements D-04; spec scenarios: sets deleted_at and flushes, returns False for non-existent)
- [x] 3.11 Implement `hard_delete(self, id: UUID) -> bool` — get entity with `include_deleted=True`, call `await session.delete(entity)`, `await session.flush()`, return True/False (implements spec: hard_delete removes row)
- [x] 3.12 Add full type annotations to all methods; verify no `Any` type in signatures (implements D-05: Pyright strict compliance)

---

## 4. `core/uow.py` — `UnitOfWork` + `get_uow`

- [x] 4.1 Create `backend/app/core/uow.py` with `class UnitOfWork` implementing `__aenter__` and `__aexit__` (implements spec: `backend-unit-of-work` Requirement: Async context manager lifecycle)
- [x] 4.2 In `__aenter__`: open `AsyncSession` via `get_session_factory()()`, assign to `self.session`, initialize all repository stub attributes to `None`, return `self` (implements D-03; spec scenario: session obtained from get_session_factory)
- [x] 4.3 In `__aexit__`: if no exception → `await self.session.commit()`; if exception → `await self.session.rollback()`; in `finally` block → `await self.session.close()` and re-raise if exception (implements D-02; spec scenarios: clean exit commits, exception triggers rollback, session always closed)
- [x] 4.4 Add typed repository accessor properties for: `usuarios` → `UsuarioRepository`, `roles` → `RolRepository`, `refresh_tokens` → `RefreshTokenRepository` (core auth path — needed by `get_current_user` in this change) using lazy init pattern from D-08 (implements spec: typed repository accessors)
- [x] 4.5 Add stub accessor properties for future repositories: `productos`, `categorias`, `ingredientes`, `pedidos`, `direcciones` — each raises `NotImplementedError` or returns a typed stub, marked with `# TODO: implement in Change <N>` (documents extension points, implements D-08 future extensibility)
- [x] 4.6 Define `async def get_uow() -> AsyncGenerator[UnitOfWork, None]` as a module-level function using `async with UnitOfWork() as uow: yield uow` (implements spec: `get_uow` FastAPI dependency)
- [x] 4.7 Ensure `uow.session` is not part of the public type signature exposed to consumers — add a docstring warning that only test fixtures should access `session` directly (implements spec: Raw session not exposed outside UoW)

---

## 5. `api/deps.py` — FastAPI Auth Dependencies

- [x] 5.1 Create `backend/app/api/deps.py` with `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)` (implements D-06; spec: oauth2_scheme placeholder)
- [x] 5.2 Implement `get_current_user(token: str | None = Depends(oauth2_scheme), uow: UnitOfWork = Depends(get_uow)) -> Usuario` (implements D-06; spec: `get_current_user` dependency)
  - Raise `UnauthorizedError("Token requerido", code="missing_token")` if `token` is None/empty
  - Call `security.decode_access_token(token)` (propagates `UnauthorizedError` on failure)
  - Extract `sub` from payload; raise `UnauthorizedError` if `sub` is missing or not a valid UUID
  - Call `await uow.usuarios.get_by_id(UUID(sub))` — returns `None` if user not found or soft-deleted
  - Raise `UnauthorizedError("Usuario no encontrado o inactivo", code="user_not_found")` if result is None
  - Return the `Usuario` instance
- [x] 5.3 Implement `require_role(*roles: str)` factory that returns a dependency callable (implements D-06; spec: `require_role` dependency factory)
  - Inner dependency: `async def _check(usuario: Usuario = Depends(get_current_user), uow: UnitOfWork = Depends(get_uow)) -> Usuario`
  - Query active `UsuarioRol` records for the user; check if any `rol.codigo` is in `roles`
  - Raise `ForbiddenError("Permisos insuficientes", code="forbidden")` if no match
  - Return `usuario` on success
- [x] 5.4 Import `UnauthorizedError` and `ForbiddenError` from `app.core.exceptions` — do NOT raise raw `HTTPException` (ensures RFC 7807 formatting via existing error handlers from Change 02)

---

## 6. Concrete Repositories for Auth Path

- [x] 6.1 Create `backend/app/repositories/user.py` with `class UsuarioRepository(BaseRepository[Usuario])` — constructor calls `super().__init__(Usuario, session)` (needed by `uow.usuarios` in this change)
- [x] 6.2 Create `class RolRepository(BaseRepository[Rol])` in the same file (needed by `require_role` via `uow.roles`)
- [x] 6.3 Create `class RefreshTokenRepository(BaseRepository[RefreshToken])` in the same file (needed by UoW accessor — no methods called in this change, but accessor must type-check)
- [x] 6.4 Wire all three repositories into `UnitOfWork` lazy accessor properties (`uow.usuarios`, `uow.roles`, `uow.refresh_tokens`) — import from `app.repositories.user` (implements task 4.4)

---

## 7. Documentation Hooks (Docstrings Only)

- [x] 7.1 Add module-level docstring to `repositories/base.py` explaining the flush-only contract and the soft-delete two-step pattern
- [x] 7.2 Add module-level docstring to `core/uow.py` explaining the commit/rollback ownership invariant and the `get_session()` vs `get_uow()` distinction
- [x] 7.3 Add module-level docstring to `core/security.py` noting this is decode-only and that issuance is deferred to Change 09
- [x] 7.4 Add module-level docstring to `api/deps.py` explaining the dependency chain (`require_role → get_current_user → decode_access_token → uow.usuarios`)

---

## 8. Verification Checklist

- [x] 8.1 Run `mypy --strict backend/app/repositories/base.py backend/app/core/uow.py backend/app/core/security.py backend/app/api/deps.py` — zero errors expected (implements Technical Acceptance Criteria)
- [x] 8.2 Run `ruff check backend/app/repositories/ backend/app/core/uow.py backend/app/core/security.py backend/app/api/deps.py` — zero violations expected
- [x] 8.3 Scan for `session.commit()` outside `uow.py`: `grep -rn "session.commit" backend/app/ --include="*.py"` — expected: exactly one match in `core/uow.py` (implements R-03 mitigation and Technical Acceptance Criteria)
- [x] 8.4 Scan for `session.commit` in `security.py` and `deps.py` — expected: zero matches
- [x] 8.5 Verify `BaseRepository` is `Generic[T]` via static inspection — `class BaseRepository(Generic[T])` must appear in source
- [x] 8.6 Verify `SECRET_KEY` is declared as `SecretStr` in `Settings` (not `str`) — check `backend/app/core/config.py`
- [x] 8.7 Confirm no production endpoint was added: `grep -rn "@router" backend/app/ --include="*.py"` must show no new routes added in this change
- [x] 8.8 Confirm `app/models/base.py` and `app/db/session.py` are unmodified: `git diff backend/app/models/base.py backend/app/db/session.py` — expected: no changes
- [x] 8.9 Static check: `grep -rn 'Depends(get_session)' backend/app/ --include='*.py' | grep -v '__pycache__'` → expected zero matches. `get_session` is reserved for test fixtures; production code MUST inject `get_uow` instead. If this grep returns any match, the apply is incomplete.
- [x] 8.10 Static check: `grep -rn 'get_uow' backend/app/api/ --include='*.py' | grep -v 'Depends(get_uow)'` → expected zero matches outside imports (no wrappers/aliases)
- [x] 8.11 Static check: `grep -rn 'from app.db.session import get_session' backend/app/api/ backend/app/services/ --include='*.py'` → expected zero matches. Only `backend/app/db/` itself and `backend/tests/` may import `get_session`.

---

## 9. Test fixtures (prerequisite for §3, §4, §5 tests)

- [x] 9.1 Create `backend/tests/conftest.py` with: `event_loop` (session-scoped), `async_engine` fixture (function-scoped, uses test database URL from env `DATABASE_URL_TEST` or falls back to `DATABASE_URL` with schema isolation), `async_connection` fixture wrapping engine in `engine.begin()`, `async_session` fixture creating an `AsyncSession` bound to the connection with `session.begin_nested()` so every test runs inside a SAVEPOINT that rolls back on teardown.
- [x] 9.2 Create `backend/tests/fixtures/uow.py` exposing `make_uow_override(session: AsyncSession) -> Callable[..., AsyncGenerator[UnitOfWork, None]]`: returns a factory that yields a `UnitOfWork` whose `__aenter__` reuses the test session (no new session created). Used in integration tests via `app.dependency_overrides[get_uow] = make_uow_override(session)`.
- [x] 9.3 Add `cache_clear` helpers: a `pytest` autouse fixture that calls `get_settings.cache_clear()`, `get_engine.cache_clear()`, `get_session_factory.cache_clear()` before and after each test to prevent lru_cache pollution (also addresses MED-05).
- [x] 9.4 Write minimum integration tests: one test function per Scenario in `backend-base-repository` spec, one per Scenario in `backend-unit-of-work` spec, one per Scenario in `backend-auth-dependencies` spec. Coverage target ≥ 92% on the new modules (`repositories/base.py`, `core/uow.py`, `core/security.py`, `api/deps.py`) — aligned with Change 02.
- [x] 9.5 Document in `backend/tests/README.md` (NEW, short): the savepoint pattern, how to override `get_uow` and `get_current_user`, and how to seed test data without hitting global state.
