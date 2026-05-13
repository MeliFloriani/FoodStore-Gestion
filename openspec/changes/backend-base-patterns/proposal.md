## Why

Change 03 (`database-migrations-and-seed`) established all SQLModel entities and the database schema. Before any functional feature (auth, catalog, orders) can be built, the backend needs shared infrastructure that enforces the architectural "Regla de Oro": **Router → Service → UoW → Repository → Model**. Without `BaseRepository[T]`, `UnitOfWork`, and the FastAPI auth dependencies in place, every downstream change would be forced to re-invent session management, commit semantics, and identity resolution — leading to inconsistency and violating the rúbrica requirement that no `Service` executes `session.commit()` directly (Integrador §2.1, criterio UoW).

## What Changes

- **New: `BaseRepository[T]` generic** (`backend/app/repositories/base.py`)
  - Parametrized with `TypeVar T` bound to `app.models.base.Base`
  - Provides async CRUD: `get_by_id`, `list_all`, `count`, `create`, `update`, `soft_delete`, `hard_delete`
  - Soft-delete filter (`deleted_at IS NULL`) applied by default; overridable with `include_deleted=True`
  - Uses `session.flush()` only — never `session.commit()` (commit is the UoW's exclusive responsibility)
  - Session injected by constructor from UoW; repositories MUST NOT construct sessions themselves
  - `filters` parameter supports equality-only comparisons on non-protected columns; PROTECTED COLUMNS (`id`, `created_at`, `updated_at`, `deleted_at`) silently ignored; unknown columns raise `ValueError`; `update(id, data)` also silently skips PROTECTED COLUMNS to prevent soft-delete resurrection or PK reassignment

- **New: `UnitOfWork` async context manager** (`backend/app/core/uow.py`)
  - `__aenter__` opens `AsyncSession` via `get_session_factory()`
  - `__aexit__` commits on clean exit; rolls back and re-raises on any exception; closes session
  - Exposes typed repository accessors as lazy-instantiated attributes sharing the same session
  - Provides FastAPI dependency `get_uow() → AsyncGenerator[UnitOfWork, None]`
  - Hard invariant: **no Service or Router may call `session.commit()` directly**

- **New: `core/security.py` — JWT decode helpers** (`backend/app/core/security.py`)
  - `decode_access_token(token: str) → dict` using `python-jose[cryptography]`
  - Maps `JWTError` / `ExpiredSignatureError` to `UnauthorizedError` from `app.core.exceptions`
  - **Decode only** — token issuance (`create_access_token`, `create_refresh_token`) is deferred to Change 09 (auth-register-login)

- **New: JWT-related settings additions** (`backend/app/core/config.py` + `backend/.env.example`)
  - `SECRET_KEY: SecretStr` (required, no default)
  - `JWT_ALGORITHM: str = "HS256"`
  - `ACCESS_TOKEN_EXPIRE_MINUTES: int = 30`
  - `REFRESH_TOKEN_EXPIRE_DAYS: int = 7`

- **New: FastAPI auth dependencies** (`backend/app/api/deps.py`)
  - `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)` (placeholder — login endpoint is built in Change 09)
  - `get_current_user(token, uow) → Usuario`: decodes JWT via `security.decode_access_token`, resolves `Usuario` via `uow.usuarios`, raises `UnauthorizedError` (→ HTTP 401 RFC 7807) if token invalid or user missing/soft-deleted
  - `require_role(*roles: str)` → dependency factory that composes on `get_current_user` and checks `UsuarioRol`, raises `ForbiddenError` (→ HTTP 403 RFC 7807) if no matching role

- **New: `python-jose[cryptography]`** added to `pyproject.toml` and `requirements.txt`

- **New: Test fixtures** (`backend/tests/conftest.py`, `backend/tests/fixtures/uow.py`, `backend/tests/README.md`)
  - `conftest.py`: `event_loop` (session-scoped), `async_engine`, `async_connection`, `async_session` with SAVEPOINT rollback isolation
  - `fixtures/uow.py`: `make_uow_override(session)` factory for injecting test session into UoW via `dependency_overrides`
  - `cache_clear` autouse fixture to prevent `lru_cache` pollution across tests (also addresses MED-05)
  - Prerequisites for repository/UoW/deps integration tests; coverage target ≥ 92% on new modules

## Capabilities

### New Capabilities

- `backend-base-repository`: Generic CRUD contract, soft-delete defaults, session injection invariants, flush-only semantics
- `backend-unit-of-work`: Async context manager contract, commit/rollback semantics, typed repository accessors, "no Service commits" invariant
- `backend-auth-dependencies`: `get_current_user` (401 paths), `require_role` (403 paths), `oauth2_scheme` placeholder, decode-only JWT contract

### Modified Capabilities

- `backend-config`: New required field `SECRET_KEY: SecretStr` + optional JWT fields (`JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`). Behavior of existing fields unchanged — purely additive.

## Impact

- **Files created (production)**:
  - `backend/app/repositories/base.py`
  - `backend/app/core/uow.py`
  - `backend/app/core/security.py`
  - `backend/app/api/deps.py`
- **Files modified (production)**:
  - `backend/app/core/config.py` — four new settings fields (additive, no breaking changes)
  - `backend/.env.example` — four new env var examples
  - `backend/pyproject.toml` — add `python-jose[cryptography]` dependency
  - `backend/requirements.txt` — lockfile updated
- **Files NOT modified**: `app/models/base.py`, `app/db/session.py`, all archived change artifacts, existing specs
- **Dependencies unlocked**: Change 06 (`auth-register-login`), Change 09 (`catalog-categories-management`), Change 10 (`catalog-ingredients-management`), and all downstream changes requiring `get_current_user` / `require_role`
- **No endpoints** introduced; no business services; no DB migrations
- **Non-goals**: token issuance helpers (`create_access_token`, `create_refresh_token`), login/register endpoints, password hashing utilities, concrete repositories for specific entities (only stubs on UoW), business services, modifications to existing models or migrations from Change 03, Audience/Issuer policies (`aud`/`iss` validation) and `JWT_AUDIENCE`/`JWT_ISSUER` settings — deferred to Change 09 alongside token issuance
