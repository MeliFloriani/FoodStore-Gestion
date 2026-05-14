## Context

Change 03 left us with a complete database schema (ERD v5), Alembic migrations, and an idempotent seed. `app/models/base.py` provides `Base` (UUID PK, `created_at`, `updated_at`, `deleted_at`) with an in-memory `soft_delete()` method — **persistence is explicitly delegated to the caller**. `app/db/session.py` exposes a lazy `get_session_factory()` and a bare `get_session()` FastAPI dependency intended for tests.

This change adds the three-layer plumbing that all functional features depend on:

1. `BaseRepository[T]` — typed, generic data-access layer
2. `UnitOfWork` — transactional envelope that owns commit/rollback
3. FastAPI auth dependencies (`get_current_user`, `require_role`) + supporting JWT decode helper

No endpoints, no business logic, no migrations. This is infrastructure only.

---

## Goals / Non-Goals

**Goals:**

- Enforce the "Regla de Oro" import chain: Router → Service → UoW → Repository → Model
- Ensure **no Service ever calls `session.commit()` directly** (Integrador §2.1, rúbrica criterio UoW)
- Provide a single, reusable, type-safe data access API for all future repositories
- Establish the auth dependency chain (`get_current_user`, `require_role`) so routers can protect endpoints from Change 06 onwards
- Add JWT decode capability (decode-only) without introducing token issuance complexity

**Non-Goals:**

- Token issuance helpers (`create_access_token`, `create_refresh_token`) — deferred to Change 09
- Login / register / logout endpoints — deferred to Change 06
- Password hashing utilities (`verify_password`, `hash_password`) — deferred to Change 06
- Concrete repositories for specific entities beyond typed accessor stubs on UoW
- Business services for any domain
- Modifications to `app/models/base.py` or `app/db/session.py`
- Any DB migrations (schema is complete from Change 03)
- Frontend changes

---

## Decisions

### D-01 — Layered Boundaries: Router → Service → UoW → Repository → Model

```
┌─────────────────────────────────────────────────────────────┐
│ router.py       HTTP puro — parsea request, delega Service  │
│       │                                                      │
│       ▼  (solo conoce Service y Depends())                   │
│ service.py      Lógica de negocio stateless, orquesta UoW   │
│       │                                                      │
│       ▼  (async with get_uow() as uow:)                     │
│ core/uow.py     Gestión transacción, abre session, provee   │
│       │         repos, commit/rollback                       │
│       ▼  (uow.session inyectada en constructor)             │
│ repositories/   Acceso BD, hereda BaseRepository[T]         │
│       │                                                      │
│       ▼                                                      │
│ models/         SQLModel tables, sin imports superiores      │
└─────────────────────────────────────────────────────────────┘
```

**Import direction rule**: Each layer MAY import from the layer(s) below it. NO layer may import from a layer above it. Violations are a build-time error (mypy/pyright configured to enforce this via module boundaries).

**Rationale**: Keeps concerns separated, enables testing each layer in isolation, and aligns with the rúbrica requirement for UoW-managed commits.

---

### D-02 — Transactional Ownership: Only UoW Commits

`UnitOfWork.__aexit__` is the **single point** where `session.commit()` is called (on clean exit) or `session.rollback()` + re-raise (on any exception). Repositories use `session.flush()` only to obtain DB-generated values (e.g., server-side defaults) without committing.

**Why this prevents partial writes**: If a Service orchestrates multiple repository operations and any raises mid-way, the UoW `__aexit__` catches the exception, rolls back everything since the last `__aenter__`, then re-raises. Without this pattern, a Service calling `commit()` after each operation would leave partial state in the DB if the second operation fails.

**Implementation pattern**:
```python
async def __aexit__(self, exc_type, exc_val, exc_tb):
    try:
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
    finally:
        await self.session.close()
    # Re-raise by returning None (do not return True)
```

**Enforcement**: A linter rule (or ruff custom check) will flag any `session.commit()` call outside `core/uow.py`. Documented in tasks as a verification step.

---

### D-03 — Session Injection: Repositories Receive AsyncSession from UoW Constructor

Repositories are instantiated inside `UnitOfWork.__aenter__` and receive `self.session` as a constructor argument:

```python
class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session
```

**Why not `Depends(get_session)` in repositories?** FastAPI's `Depends()` is for router-level injection only. Repositories are not FastAPI route handlers — they are plain Python classes. Using `Depends(get_session)` inside a repository would bypass the UoW entirely, create a second independent session, and break transactional atomicity.

**Why not a global session?** A module-level or global session is not safe for async concurrent requests. Each request needs its own session and transaction.

**`get_session()` vs `get_uow()`**: `get_session()` from `app/db/session.py` **continues to exist** for test isolation (e.g., test fixtures that need direct session access) and ad-hoc scripting. In production code (routers, services, repositories), `get_session` MUST NOT be injected via `Depends`. Production code MUST inject `get_uow` instead. Verification is mechanical (`tasks.md` §8.9 and §8.11): any `Depends(get_session)` in `backend/app/` (excluding `backend/app/db/` itself) or any `from app.db.session import get_session` in `backend/app/api/` or `backend/app/services/` is a build-time violation.

---

### D-04 — Soft Delete Contract

`BaseRepository` enforces the following soft-delete contract:

| Method | `deleted_at IS NULL` filter | Can override? |
|---|---|---|
| `get_by_id(id)` | Yes (default) | `include_deleted=True` |
| `list_all(...)` | Yes (default) | `include_deleted=True` |
| `count(...)` | Yes (default) | `include_deleted=True` |
| `soft_delete(id)` | N/A — sets `deleted_at = now(UTC)` | — |
| `hard_delete(id)` | No filter — deletes unconditionally | — |

`BaseRepository.soft_delete(id)` calls `Base.soft_delete()` (which mutates in-memory) then calls `session.flush()`. It does NOT call `session.commit()` — that is the UoW's job.

`hard_delete` is reserved for admin paths and test cleanup. In production business logic, only `soft_delete` should be used.

**Custom query risk**: Any custom query written in a concrete repository that bypasses `BaseRepository.list_all()` must manually add `WHERE deleted_at IS NULL`. This is documented as R-04 and flagged as a lint-rule-note in the tasks.

**PROTECTED COLUMNS in `update(id, data)`**: PROTECTED COLUMNS (`id`, `created_at`, `updated_at`, `deleted_at`) are managed exclusively by the ORM (PK), `Base` defaults (`created_at`), the SQLAlchemy `onupdate` hook (`updated_at`), and `soft_delete()`/`hard_delete()` (`deleted_at`). Never by `update(data)`. The `update` method SHALL silently skip any key in `data` that belongs to PROTECTED COLUMNS — preventing resurrection of soft-deleted entities via `data={'deleted_at': None}`, PK reassignment via `data={'id': ...}`, and timestamp tampering.

---

### D-05 — Generic Typing: `BaseRepository(Generic[T])`

```python
from typing import Generic, TypeVar
from app.models.base import Base

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    model: type[T]
    session: AsyncSession
    ...
```

All methods return `T`, `T | None`, `list[T]`, or `bool`. No `Any` in method signatures. Pyright in strict mode passes with zero errors.

Concrete repositories:
```python
class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Usuario, session)
```

**Rationale**: Strong static typing catches type mismatches at development time, not runtime. Generic parameter ensures the model type flows through all method signatures without casts.

**Filter contract note**: Filter contract is intentionally narrow. The `filters` parameter in `list_all` and `count` supports only equality comparisons (`{column_name: exact_value}`). Concrete repositories add typed methods (e.g. `ProductoRepository.list_by_price_range(min, max)`) instead of overloading `filters`. PROTECTED COLUMNS (`id`, `created_at`, `updated_at`, `deleted_at`) are silently ignored in `filters` to prevent bypass of soft-delete semantics or PK tampering. Columns not present on the model raise `ValueError`.

---

### D-06 — Auth Dependency Chain: `get_current_user` / `require_role`

**File location decision**: `backend/app/api/deps.py` (not `core/deps.py`).

**Rationale**: `deps.py` is a FastAPI-specific concept (it only makes sense in the context of an API router). The `core/` package contains framework-agnostic infrastructure (`config.py`, `uow.py`, `security.py`, `exceptions.py`). Placing `deps.py` in `api/` aligns with the principle that FastAPI-specific wiring (Depends, OAuth2 schemes) belongs to the API layer, not the core domain.

**Dependency chain**:
```
require_role("ADMIN", "PEDIDOS")
        │
        ▼ Depends(get_current_user)
get_current_user(token, uow)
        │
        ├── security.decode_access_token(token)  → dict | UnauthorizedError
        └── uow.usuarios.get_by_id(sub)          → Usuario | UnauthorizedError
```

**Why sub-dependencies instead of middleware?** FastAPI `Depends()` sub-dependencies:
1. Are testable — can be overridden with `app.dependency_overrides` in tests
2. Are scoped per-request and per-route — middleware runs for every request including health checks, docs, etc.
3. Compose cleanly — `require_role` is built on top of `get_current_user` without code duplication
4. Integrate with OpenAPI schema — FastAPI auto-generates the security scheme in `/docs`

**`oauth2_scheme` placeholder**: `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)` is defined now so OpenAPI shows the correct `securitySchemes`. `auto_error=False` means unprotected routes don't get a 401 from the scheme itself — only `get_current_user` raises 401 when needed. The `/api/v1/auth/login` endpoint is built in Change 06.

#### UoW deduplication per request

FastAPI deduplicates `Depends(get_uow)` across `get_current_user` and `require_role` based on callable identity. Only one `UnitOfWork` instance (and therefore one `AsyncSession`) is created per request. CONSEQUENCE: do NOT alias or wrap `get_uow` (e.g. `get_uow_v2 = get_uow` or `partial(get_uow, ...)`). Wrappers break identity equality and silently produce two transactions per request.

---

### D-07 — JWT Decode-Only Scope

This change introduces **only** `decode_access_token(token: str) → dict` in `core/security.py`:

```python
from jose import JWTError, jwt
from app.core.exceptions import UnauthorizedError

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": False,  # NON-GOAL: audience policy deferred to Change 09
                "verify_iss": False,  # NON-GOAL: issuer policy deferred to Change 09
            },
        )
        return payload
    except JWTError as exc:
        raise UnauthorizedError("Token inválido o expirado", code="invalid_token") from exc
```

Audience (`aud`) and issuer (`iss`) policies are NON-GOALS of this change. Token issuance lives in Change 09 (auth-jwt-issuance) which will define `JWT_AUDIENCE`/`JWT_ISSUER` settings and turn on `verify_aud`/`verify_iss`. Until then, `decode_access_token` validates only signature, expiration, not-before and issued-at.

**What is NOT in this change**: `create_access_token`, `create_refresh_token`, `verify_password`, `hash_password`. These live in Change 09 (`auth-register-login`) because they require the auth domain model logic (rate-limiting, bcrypt cost, refresh token rotation semantics) that belongs there.

**Cross-change contract**: Change 09 WILL add issuance helpers to `core/security.py` (or a new `core/tokens.py`). The `SECRET_KEY` and `JWT_ALGORITHM` settings added here are the shared contract between decode (this change) and issuance (Change 09). Change 09 must not introduce a second, incompatible key source.

**Security note**: `core/security.py` is an internal backend module. It is not exposed via any HTTP endpoint in this change. The only consumer is `api/deps.py::get_current_user`.

---

### D-08 — Future Extensibility

**Adding a new repository to UoW**:
1. Create `app/repositories/<domain>.py` with `class <Domain>Repository(BaseRepository[<Model>])`
2. Add a lazy attribute to `UnitOfWork`:
   ```python
   @property
   def <domain>s(self) -> <Domain>Repository:
       if self._<domain>s is None:
           self._<domain>s = <Domain>Repository(self.session)
       return self._<domain>s
   ```
3. Initialize `self._<domain>s: <Domain>Repository | None = None` in `__aenter__`

**Services consuming UoW**:
```python
class UsuarioService:
    async def get_by_id(self, uow: UnitOfWork, id: UUID) -> Usuario:
        usuario = await uow.usuarios.get_by_id(id)
        if usuario is None:
            raise NotFoundError("Usuario no encontrado")
        return usuario
```

Services are stateless and receive `uow` as a parameter (injected from the router via `Depends(get_uow)`). They never instantiate `UnitOfWork` themselves.

**Use Cases (if introduced later)**: Would sit between Service and UoW, orchestrating multi-domain operations. A Use Case would receive a `UnitOfWork` from the router and call multiple Services within the same transaction. This design makes room for that layer without requiring any changes to UoW or BaseRepository.

---

### D-09 — TZ Compatibility Patch (Persistence Boundary Normalization)

**Strategy adopted:** "UTC aware domain + naive persistence normalization" (Change 04 apply-time discovery, ratified by user).

**Context:** `app/models/base.py` produces `datetime.now(UTC)` (timezone-aware) for `created_at`, `updated_at`, `deleted_at` and inside `soft_delete()`. The Alembic migration emits `sa.DateTime()` → PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`, which requires naive datetimes. asyncpg raises `DataError` when an aware datetime is bound to such a column.

**Mechanism:** `_patch_asyncpg_datetime_tz()` in `app/db/session.py` monkey-patches `AsyncpgDateTime.bind_processor` at the class level (global within the process). The patch wraps the bind processor so that any `datetime` with `tzinfo` is normalized to naive via `.replace(tzinfo=None)`, preserving the UTC instant. The patch is idempotent (guard `_tz_patched = True` on the class) and is applied at module import — before any engine is created. Reads of `TIMESTAMP WITHOUT TIME ZONE` columns return naive datetimes to the domain.

**Side effects accepted:**
- The patch is process-global by design: it affects every async engine created in the process. Multi-worker (Uvicorn) is safe because each worker is an independent Python interpreter. Hot-reload is safe because the guard prevents re-patching.
- Reads return naive datetimes. Today this is safe — no temporal comparison exists in repositories or services (only `IS NULL` for soft-delete). **Re-evaluation condition:** any change that introduces temporal comparisons (e.g., Change 06 `expires_at` on refresh tokens, Change 11 order date-range filters) MUST explicitly normalize the read value back to UTC-aware via `dt.replace(tzinfo=UTC)` before comparing against `datetime.now(UTC)`. This contract is non-optional.

**Long-term fix (out of scope for Change 04):** Migrate all timestamp columns to `TIMESTAMPTZ` (`TIMESTAMP WITH TIME ZONE`) in a dedicated change. When that migration runs, remove `_patch_asyncpg_datetime_tz()` from `db/session.py` and remove any `replace(tzinfo=UTC)` shims added in consumer changes (Change 06, 11). Until then, the patch is the agreed boundary.

**Cross-references:** R-03 addendum (this design.md), Hallazgo #3 of tz-patch audit (covered by `test_soft_delete_tz_aware_roundtrip`).

---

## Risks / Trade-offs

### R-01 — Coupling UoW to Concrete Repositories
**Risk**: `UnitOfWork` directly instantiates concrete repository classes, creating tight coupling. Adding a new repository requires modifying `UnitOfWork`.
**Mitigation**: Typed accessor properties are the documented extension point (see D-08). All accessors are tested. If the number of repositories becomes unmanageable, a registry pattern can be introduced in a future change without breaking the interface.

### R-02 — Premature JWT Decode Without Issuance
**Risk**: `decode_access_token` is usable in this change but no token issuer exists yet. A developer could accidentally try to call `get_current_user` in a route before Change 09 ships, getting confusing 401 errors.
**Mitigation**: Clear cross-change contract documented in D-07. `api/deps.py` is an internal module — no endpoint exposes it until a router explicitly declares `Depends(get_current_user)`. The `oauth2_scheme` with `auto_error=False` ensures no accidental 401s on unprotected routes.

### R-03 — Session Lifecycle Leaks in `__aexit__`
**Risk**: If `session.commit()` raises (e.g., DB constraint violation), and the `__aexit__` does not properly handle the exception, the session remains open, leaking connections.
**Mitigation**: `__aexit__` uses a `try/finally` pattern: rollback is attempted on any exception; `session.close()` is in the `finally` block so it runs regardless of whether commit or rollback succeeded. The exception is re-raised (not swallowed) so the caller sees it as an HTTP 500 (or the appropriate domain error).

**Addendum (apply-time discovery — see D-09):** R-03 originally covered transaction lifecycle leaks in UoW `__aexit__`. Apply-time integration testing surfaced a related but distinct lifecycle concern at the persistence boundary: tz-aware datetimes produced by `models/base.py` were incompatible with the `TIMESTAMP WITHOUT TIME ZONE` columns generated by Change 03's Alembic migration. The mitigation is the TZ compatibility patch documented in D-09. The patch carries forward as **tech-debt**: when the long-term `TIMESTAMPTZ` migration lands, remove the patch and any consumer shims. Tracking owner: the change that introduces temporal comparisons first (likely Change 06 or 11) MUST either (a) add explicit `replace(tzinfo=UTC)` on read values, or (b) propose and execute the `TIMESTAMPTZ` migration. The patch is NOT a permanent architectural choice — it is a deliberate, time-boxed bridge.

### R-04 — Soft-Delete Filter Forgotten on Custom Queries
**Risk**: A concrete repository adds a custom SQLAlchemy query (e.g., JOIN, CTE) without applying `WHERE deleted_at IS NULL`. Soft-deleted records appear in results.
**Mitigation**: `BaseRepository` provides a `_active_filter()` helper method returning the standard filter expression, reusable in custom queries. A note in the tasks verification checklist flags this for review. Future Change 25 (QA) should add a test that verifies the filter is applied.

### R-05 — Test Isolation: UoW-Based Tests
**Risk**: Tests that use `get_uow` will commit data to the test database, causing test pollution between test runs.
**Mitigation**: Executable via §9 of `tasks.md` (tasks §9.1–§9.5). The savepoint pattern relies on `session.begin_nested()` + `connection.rollback()` after each test — no per-test DB recreation is required. `get_session()` from `app/db/session.py` continues to exist precisely to support direct session access in test fixtures without going through the UoW. Override `get_uow` via `app.dependency_overrides[get_uow] = make_uow_override(session)` (see `backend/tests/fixtures/uow.py` from task §9.2).

---

## Technical Acceptance Criteria

- [ ] `mypy --strict` passes on `repositories/base.py`, `core/uow.py`, `core/security.py`, `api/deps.py` with zero errors
- [ ] `ruff check` passes on all new files with zero violations
- [ ] No `session.commit()` call exists anywhere in the codebase outside `core/uow.py` (verifiable via `grep -r "session.commit" backend/app/` — expected: one hit in `uow.py`)
- [ ] `BaseRepository` is parametrized with `Generic[T]` where `T` is bound to `Base`
- [ ] `get_by_id` and `list_all` return only rows where `deleted_at IS NULL` when called without `include_deleted=True`
- [ ] `soft_delete` calls `Base.soft_delete()` and then `session.flush()` — does NOT call `session.commit()`
- [ ] `UnitOfWork.__aexit__` commits on clean exit and rolls back + re-raises on any exception
- [ ] `get_uow` is a valid FastAPI `AsyncGenerator` dependency (verified by injecting it in a test route)
- [ ] `decode_access_token` raises `UnauthorizedError` (not `JWTError`) on invalid/expired tokens
- [ ] `SECRET_KEY` is declared as `SecretStr` in `Settings` (not plain `str`)
- [ ] `backend/.env.example` contains entries for `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`

---

## Validation of Consistency (US-000d Acceptance Criteria Cross-Reference)

| US-000d Acceptance Criterion | Covered By |
|---|---|
| `BaseRepository[T]` with `get_by_id`, `list_all`, `count`, `create`, `update`, `soft_delete`, `hard_delete` | D-05 + `backend-base-repository` spec |
| `get_by_id` and `list_all` exclude `deleted_at IS NOT NULL` by default | D-04 + `backend-base-repository` spec |
| `UnitOfWork` as async context manager: opens session, exposes repos, commits on exit, rollbacks on error | D-02 + D-03 + `backend-unit-of-work` spec |
| `get_current_user`: extracts Bearer token, decodes JWT, returns `Usuario` or HTTP 401 | D-06 + `backend-auth-dependencies` spec |
| `require_role(roles)`: verifies role membership, raises HTTP 403 if missing | D-06 + `backend-auth-dependencies` spec |
| RFC 7807 error format for 401/403 (reuses Change 02 handlers) | D-06 + existing `backend-error-handling` spec |

---

## Testing Strategy (Future — Change 25 Scope)

The following test categories will be created in Change 25 or alongside each consuming feature change:

| Category | Description |
|---|---|
| `test_base_repository_crud` | create/update/get_by_id/list_all/hard_delete on a test entity |
| `test_base_repository_soft_delete` | `soft_delete` sets `deleted_at`; subsequent `get_by_id` returns None; `include_deleted=True` returns it |
| `test_base_repository_filters` | `list_all` with various filters; `count` with filters |
| `test_uow_commit` | Service-style code inside `async with uow:` commits on clean exit; data persists |
| `test_uow_rollback` | Exception inside `async with uow:` triggers rollback; data does not persist |
| `test_get_current_user_valid_token` | Valid JWT → returns correct `Usuario` |
| `test_get_current_user_expired_token` | Expired JWT → HTTP 401 with RFC 7807 body |
| `test_get_current_user_missing_token` | No Bearer header → HTTP 401 |
| `test_get_current_user_deleted_user` | Valid JWT but user is soft-deleted → HTTP 401 |
| `test_require_role_authorized` | User with correct role → request proceeds |
| `test_require_role_forbidden` | User without required role → HTTP 403 with RFC 7807 body |

---

## Open Questions

None — all decisions are resolved within this change scope. The cross-change JWT issuance contract (D-07) is explicitly deferred to Change 09 and documented.
