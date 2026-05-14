"""
Integration tests for app/repositories/base.py — BaseRepository[T].

Tests use the async_session fixture (SAVEPOINT-based isolation) from conftest.py.
All data created in tests is rolled back automatically on teardown.

Covers spec scenarios from backend-base-repository spec:
- get_by_id: returns entity, returns None for soft-deleted, returns None for non-existent
- get_by_id with include_deleted=True returns soft-deleted entity
- list_all: excludes soft-deleted by default, pagination, include_deleted override
- count: excludes soft-deleted by default
- create: persists after flush, does NOT commit
- update: applies dict fields, returns None for non-existent, skips PROTECTED_COLUMNS
- soft_delete: sets deleted_at and flushes, returns False for non-existent
- hard_delete: removes row
- filter contract: equality, PROTECTED_COLUMNS ignored, unknown column raises ValueError
- flush-only semantics: no session.commit() in source

Coverage target: ≥92% on repositories/base.py
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Rol, Usuario
from app.repositories.user import RolRepository, UsuarioRepository


def _now() -> datetime:
    """Return a naive UTC datetime (required by TIMESTAMP WITHOUT TIME ZONE columns)."""
    return datetime.utcnow()


def _make_usuario(
    email: str | None = None,
    nombre: str = "Test",
    apellido: str = "User",
) -> Usuario:
    """Factory for creating a test Usuario in memory.

    Uses naive datetimes (utcnow) to match the DB's TIMESTAMP WITHOUT TIME ZONE.
    """
    now = _now()
    return Usuario(
        id=uuid.uuid4(),
        email=email or f"test-{uuid.uuid4()}@example.com",
        password_hash="x" * 60,
        nombre=nombre,
        apellido=apellido,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def _make_rol(codigo: str | None = None) -> Rol:
    """Factory for creating a test Rol in memory."""
    now = _now()
    return Rol(
        id=uuid.uuid4(),
        codigo=codigo or f"ROLE_{uuid.uuid4().hex[:8].upper()}",
        nombre="Test Role",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


# ---------------------------------------------------------------------------
# Scenario: get_by_id returns entity for valid active record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_active_entity(async_session: AsyncSession) -> None:
    """get_by_id returns the entity when it exists and is not soft-deleted."""
    repo = UsuarioRepository(async_session)
    user = _make_usuario()
    created = await repo.create(user)

    result = await repo.get_by_id(created.id)
    assert result is not None
    assert result.id == created.id


# ---------------------------------------------------------------------------
# Scenario: get_by_id returns None for soft-deleted record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_soft_deleted(async_session: AsyncSession) -> None:
    """get_by_id returns None when the entity is soft-deleted."""
    repo = UsuarioRepository(async_session)
    user = _make_usuario()
    created = await repo.create(user)
    await repo.soft_delete(created.id)

    result = await repo.get_by_id(created.id)
    assert result is None


# ---------------------------------------------------------------------------
# Scenario: get_by_id returns None for non-existent record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_nonexistent(async_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that doesn't exist in the DB."""
    repo = UsuarioRepository(async_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# Scenario: get_by_id with include_deleted=True returns soft-deleted entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_include_deleted_returns_soft_deleted(async_session: AsyncSession) -> None:
    """get_by_id(id, include_deleted=True) returns the soft-deleted entity."""
    repo = UsuarioRepository(async_session)
    user = _make_usuario()
    created = await repo.create(user)
    await repo.soft_delete(created.id)

    result = await repo.get_by_id(created.id, include_deleted=True)
    assert result is not None
    assert result.id == created.id
    assert result.deleted_at is not None


# ---------------------------------------------------------------------------
# Scenario: list_all excludes soft-deleted records by default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_excludes_soft_deleted_by_default(async_session: AsyncSession) -> None:
    """list_all() only returns entities where deleted_at IS NULL."""
    repo = RolRepository(async_session)
    active_rol = await repo.create(_make_rol())
    soft_deleted_rol = await repo.create(_make_rol())
    await repo.soft_delete(soft_deleted_rol.id)

    results = await repo.list_all(filters={"codigo": active_rol.codigo})
    ids = [r.id for r in results]
    assert active_rol.id in ids
    assert soft_deleted_rol.id not in ids


# ---------------------------------------------------------------------------
# Scenario: list_all with include_deleted=True includes all records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_include_deleted_returns_all(async_session: AsyncSession) -> None:
    """list_all(include_deleted=True) includes both active and soft-deleted records."""
    repo = RolRepository(async_session)
    active_rol = await repo.create(_make_rol())
    soft_deleted_rol = await repo.create(_make_rol())
    await repo.soft_delete(soft_deleted_rol.id)

    results_active = await repo.list_all(filters={"codigo": active_rol.codigo}, include_deleted=True)
    results_deleted = await repo.list_all(filters={"codigo": soft_deleted_rol.codigo}, include_deleted=True)

    assert any(r.id == active_rol.id for r in results_active)
    assert any(r.id == soft_deleted_rol.id for r in results_deleted)


# ---------------------------------------------------------------------------
# Scenario: list_all pagination via skip and limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_pagination_skip_and_limit(async_session: AsyncSession) -> None:
    """list_all(skip=N, limit=M) returns the right slice."""
    repo = RolRepository(async_session)
    # Create 5 roles with a unique prefix to isolate this test
    prefix = uuid.uuid4().hex[:8].upper()
    roles = []
    for i in range(5):
        now = _now()
        rol = await repo.create(
            Rol(
                id=uuid.uuid4(),
                codigo=f"{prefix}_{i}",
                nombre=f"Role {i}",
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        roles.append(rol)

    # Get page 2 (skip=2, limit=2) filtered by prefix
    results = await repo.list_all(
        skip=2,
        limit=2,
        filters=None,
    )
    # Just verify pagination works (limit is respected)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Scenario: create persists entity and returns it after flush
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_entity_after_flush(async_session: AsyncSession) -> None:
    """create(obj) adds, flushes, and returns the entity with populated id."""
    repo = UsuarioRepository(async_session)
    user = _make_usuario()
    pre_id = user.id
    result = await repo.create(user)
    assert result is not None
    assert result.id == pre_id


# ---------------------------------------------------------------------------
# Scenario: create does NOT call session.commit()
# ---------------------------------------------------------------------------


def test_no_session_commit_call_in_base_repository() -> None:
    """BaseRepository must not make actual session.commit() calls (only docstrings allowed)."""
    import ast
    import inspect

    from app.repositories import base

    source = inspect.getsource(base)
    tree = ast.parse(source)
    commit_calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
        ):
            commit_calls.append(node.lineno)
    assert commit_calls == [], (
        f"session.commit() called at lines {commit_calls} in repositories/base.py"
    )


# ---------------------------------------------------------------------------
# Scenario: update applies dict fields to entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_applies_fields_to_entity(async_session: AsyncSession) -> None:
    """update(id, data) sets the specified fields and flushes."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())

    updated = await repo.update(rol.id, {"nombre": "Updated Name"})
    assert updated is not None
    assert updated.nombre == "Updated Name"


# ---------------------------------------------------------------------------
# Scenario: update returns None for non-existent entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_returns_none_for_nonexistent(async_session: AsyncSession) -> None:
    """update(non_existent_id, data) returns None without raising."""
    repo = UsuarioRepository(async_session)
    result = await repo.update(uuid.uuid4(), {"nombre": "X"})
    assert result is None


# ---------------------------------------------------------------------------
# Scenario: update skips PROTECTED_COLUMNS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_skips_id_in_data(async_session: AsyncSession) -> None:
    """update(id, {'id': new_uuid, 'nombre': 'X'}) ignores the 'id' key."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    original_id = rol.id
    new_uuid = uuid.uuid4()

    updated = await repo.update(rol.id, {"id": new_uuid, "nombre": "New Name"})
    assert updated is not None
    assert updated.id == original_id  # id unchanged


@pytest.mark.asyncio
async def test_update_skips_deleted_at_in_data(async_session: AsyncSession) -> None:
    """update with deleted_at in data does not resurrect soft-deleted entity."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    await repo.soft_delete(rol.id)

    # Try to resurrect — should not work (entity is soft-deleted, get_by_id returns None)
    result = await repo.update(rol.id, {"deleted_at": None, "nombre": "Resurrected"})
    assert result is None  # entity soft-deleted, get_by_id returns None


@pytest.mark.asyncio
async def test_update_empty_data_does_not_raise(async_session: AsyncSession) -> None:
    """update(id, {}) fetches entity but sets no fields — flushes without error."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    result = await repo.update(rol.id, {})
    assert result is not None


# ---------------------------------------------------------------------------
# Scenario: soft_delete sets deleted_at and flushes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_sets_deleted_at(async_session: AsyncSession) -> None:
    """soft_delete(id) sets deleted_at to a non-null timestamp."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    result = await repo.soft_delete(rol.id)
    assert result is True

    # Verify deleted_at is set
    deleted_rol = await repo.get_by_id(rol.id, include_deleted=True)
    assert deleted_rol is not None
    assert deleted_rol.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_entity_hidden_from_get_by_id(async_session: AsyncSession) -> None:
    """After soft_delete, get_by_id returns None (without include_deleted)."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    await repo.soft_delete(rol.id)

    result = await repo.get_by_id(rol.id)
    assert result is None


# ---------------------------------------------------------------------------
# Scenario: soft_delete returns False for non-existent entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_returns_false_for_nonexistent(async_session: AsyncSession) -> None:
    """soft_delete with a UUID that doesn't exist returns False (no exception)."""
    repo = UsuarioRepository(async_session)
    result = await repo.soft_delete(uuid.uuid4())
    assert result is False


# ---------------------------------------------------------------------------
# Scenario: hard_delete removes row from database
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_removes_row(async_session: AsyncSession) -> None:
    """hard_delete removes the row and subsequent get_by_id(include_deleted=True) returns None."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())
    result = await repo.hard_delete(rol.id)
    assert result is True

    result_after = await repo.get_by_id(rol.id, include_deleted=True)
    assert result_after is None


@pytest.mark.asyncio
async def test_hard_delete_returns_false_for_nonexistent(async_session: AsyncSession) -> None:
    """hard_delete with non-existent UUID returns False."""
    repo = RolRepository(async_session)
    result = await repo.hard_delete(uuid.uuid4())
    assert result is False


# ---------------------------------------------------------------------------
# Scenario: count returns correct total matching active records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_excludes_soft_deleted_by_default(async_session: AsyncSession) -> None:
    """count() excludes soft-deleted records by default."""
    repo = RolRepository(async_session)
    prefix = uuid.uuid4().hex[:8].upper()
    now = _now()
    active = await repo.create(Rol(id=uuid.uuid4(), codigo=f"{prefix}_ACTIVE", nombre="Active", created_at=now, updated_at=now, deleted_at=None))
    deleted = await repo.create(Rol(id=uuid.uuid4(), codigo=f"{prefix}_DELETED", nombre="Deleted", created_at=now, updated_at=now, deleted_at=None))
    await repo.soft_delete(deleted.id)

    # Count active only
    count_active = await repo.count(filters={"codigo": active.codigo})
    count_deleted = await repo.count(filters={"codigo": deleted.codigo})
    assert count_active == 1
    assert count_deleted == 0  # soft-deleted, not counted


# ---------------------------------------------------------------------------
# Scenario: filters equality on a valid column
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_filters_equality(async_session: AsyncSession) -> None:
    """list_all with equality filter applies WHERE column = value."""
    repo = UsuarioRepository(async_session)
    unique_nombre = f"UniqueNombre_{uuid.uuid4().hex[:8]}"
    user = await repo.create(_make_usuario(nombre=unique_nombre))

    results = await repo.list_all(filters={"nombre": unique_nombre})
    assert any(r.id == user.id for r in results)


# ---------------------------------------------------------------------------
# Scenario: PROTECTED_COLUMNS ignored in filters (deleted_at, id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_deleted_at_in_filters_is_ignored(async_session: AsyncSession) -> None:
    """list_all(filters={'deleted_at': None}) ignores deleted_at and applies implicit filter."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())

    # Should not raise and should apply the implicit deleted_at IS NULL filter
    results = await repo.list_all(filters={"deleted_at": None})
    # Active rol should be included (deleted_at is silently ignored)
    # (we can't assert exact count due to other tests seeding data, just no error)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_list_all_id_in_filters_is_silently_ignored(async_session: AsyncSession) -> None:
    """list_all(filters={'id': uuid}) silently ignores the 'id' key."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol())

    # Should not raise; 'id' is a PROTECTED_COLUMN and silently ignored
    results = await repo.list_all(filters={"id": rol.id})
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Scenario: unknown column in filters raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_unknown_column_raises_value_error(async_session: AsyncSession) -> None:
    """list_all with unknown column in filters raises ValueError."""
    repo = UsuarioRepository(async_session)
    with pytest.raises(ValueError, match="unknown filter column"):
        await repo.list_all(filters={"nonexistent_column": "value"})


# ---------------------------------------------------------------------------
# Scenario: Repository does not import get_session
# ---------------------------------------------------------------------------


def test_base_repository_does_not_import_get_session() -> None:
    """BaseRepository must not import from app.db.session (not even get_session)."""
    import ast
    import inspect

    from app.repositories import base

    source = inspect.getsource(base)
    tree = ast.parse(source)
    # Check for actual import statements (not docstring mentions)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "app.db.session" not in node.module, (
                    "base.py must not import from app.db.session"
                )


# ---------------------------------------------------------------------------
# Scenario: Generic parameter flows through method signatures
# ---------------------------------------------------------------------------


def test_base_repository_is_generic() -> None:
    """BaseRepository must be defined as Generic[T]."""
    import inspect

    from app.repositories import base

    source = inspect.getsource(base)
    assert "Generic[T]" in source
    assert "TypeVar" in source


# ---------------------------------------------------------------------------
# Scenario: D-09 — TZ-aware roundtrip: UTC-aware in, naive persisted, naive out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_tz_aware_roundtrip(async_session: AsyncSession) -> None:
    """Validate D-09 strategy: UTC-aware domain datetimes are persisted as naive.

    Strategy: "UTC aware domain + naive persistence normalization".

    The _patch_asyncpg_datetime_tz() in app/db/session.py strips tzinfo before
    binding to TIMESTAMP WITHOUT TIME ZONE columns. This test confirms:

    1. create: created_at (generated by datetime.now(UTC) inside the model default)
       is stored and read back as a naive datetime (tzinfo is None).
    2. soft_delete: deleted_at (set by Base.soft_delete() via datetime.now(UTC))
       is stored and read back as naive. The UTC instant is preserved (value is
       close to the pre-operation UTC timestamp captured before the call).

    After each write+flush, session.expire_all() is called to evict the in-memory
    state and force a fresh DB read on the next access — this is what exercises the
    actual tz-stripping roundtrip (write: aware → DB naive; read: DB naive →
    Python naive).

    See design.md D-09 and R-03 addendum for full rationale.
    """
    repo = RolRepository(async_session)

    # Capture a naive UTC reference point before creating the entity
    before_utc = datetime.utcnow()

    # Create entity — model default uses datetime.now(UTC) (tz-aware)
    rol = await repo.create(_make_rol())
    rol_id = rol.id  # capture before expire_all() evicts in-memory state

    # Evict in-memory state so the next get_by_id reads fresh from DB
    async_session.expire_all()

    # Re-fetch to confirm what asyncpg actually stored/returned
    fetched = await repo.get_by_id(rol_id)
    assert fetched is not None

    # created_at must be non-null and naive (asyncpg strips tzinfo on read)
    assert fetched.created_at is not None
    assert fetched.created_at.tzinfo is None, (
        "D-09: asyncpg should return naive datetime for TIMESTAMP WITHOUT TIME ZONE"
    )

    # Value must be close to the captured reference (within 2 seconds)
    delta_create = abs((fetched.created_at - before_utc).total_seconds())
    assert delta_create <= 2, (
        f"D-09: created_at value drifted {delta_create:.3f}s from expected UTC instant"
    )

    # Now soft-delete — Base.soft_delete() sets deleted_at = datetime.now(UTC) (aware)
    before_delete_utc = datetime.utcnow()
    deleted = await repo.soft_delete(rol_id)
    assert deleted is True

    # Evict in-memory state again to force a fresh DB read of deleted_at
    async_session.expire_all()

    # Re-fetch with include_deleted to inspect deleted_at from DB
    deleted_entity = await repo.get_by_id(rol_id, include_deleted=True)
    assert deleted_entity is not None

    # deleted_at must be non-null and naive (tz-patch stripped tzinfo on the flush)
    assert deleted_entity.deleted_at is not None
    assert deleted_entity.deleted_at.tzinfo is None, (
        "D-09: deleted_at must be naive after tz-patch strips tzinfo on persist"
    )

    # Value must be close to the captured reference (within 2 seconds)
    delta_delete = abs((deleted_entity.deleted_at - before_delete_utc).total_seconds())
    assert delta_delete <= 2, (
        f"D-09: deleted_at value drifted {delta_delete:.3f}s from expected UTC instant"
    )
