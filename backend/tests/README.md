# Backend Test Suite — Patterns & Conventions

Added in Change 04 (`backend-base-patterns`).

## SAVEPOINT Isolation Pattern

Every integration test that touches the database runs inside a SAVEPOINT, ensuring
**no data persists** after the test completes — no per-test table truncation required.

### Fixture chain

```
async_engine (function-scoped)
    └── async_connection (engine.begin() — outer transaction)
            └── async_session (begin_nested() — SAVEPOINT)
                    └── test code runs here
```

1. `async_engine`: creates a new `AsyncEngine` per test (disposed on teardown).
2. `async_connection`: opens an outermost transaction via `engine.begin()`.
3. `async_session`: creates an `AsyncSession` bound to the connection, then calls
   `session.begin_nested()` to start a SAVEPOINT.
4. The test runs — `session.flush()` calls work inside the SAVEPOINT.
5. At teardown: `session.rollback()` rolls back the SAVEPOINT, then
   `async_connection` rolls back the outer transaction. Nothing hits the DB.

### Why not truncate tables?

Truncation is slow and requires knowing which tables were touched. The SAVEPOINT
pattern is zero-cost and fully automatic.

## Overriding `get_uow` in endpoint tests

Use `make_uow_override` from `tests/fixtures/uow.py` to inject the test session
into the application's UoW dependency:

```python
from tests.fixtures.uow import make_uow_override
from app.core.uow import get_uow
from app.main import app

async def test_some_endpoint(async_session, async_client):
    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        response = await async_client.get("/api/v1/some-endpoint")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_uow, None)
```

The override reuses the test session so all reads/writes happen inside the SAVEPOINT.

## Overriding `get_current_user` in tests that don't need auth

For endpoint tests that test auth-agnostic behavior, override `get_current_user`
directly to skip token validation:

```python
from app.api.deps import get_current_user

def make_user_override(user: Usuario):
    async def _override():
        return user
    return _override

app.dependency_overrides[get_current_user] = make_user_override(test_user)
```

## Seeding test data without hitting global state

Always seed data through the repository layer, never via raw SQL in tests:

```python
async def test_with_user(async_session):
    repo = UsuarioRepository(async_session)
    user = Usuario(
        email="test@example.com",
        password_hash="x" * 60,
        nombre="Test",
        apellido="User",
    )
    user = await repo.create(user)
    await async_session.flush()
    # user.id is now populated with the server-side UUID
    ...
```

Because the test runs inside a SAVEPOINT, the created user disappears after the test.

## lru_cache pollution guard

The `cache_clear` autouse fixture (in `conftest.py`) calls
`get_settings.cache_clear()`, `get_engine.cache_clear()`,
`get_session_factory.cache_clear()`, and `get_limiter.cache_clear()` before
and after **every** test. This prevents cached singleton instances (created with
test settings in one test) from leaking into the next test.
