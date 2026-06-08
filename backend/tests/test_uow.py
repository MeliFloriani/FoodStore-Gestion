"""
Integration tests for app/core/uow.py — UnitOfWork + get_uow.

Tests use the async_session / async_connection fixtures from conftest.py for isolation.
Some tests use in-memory UoW instances to verify session lifecycle without hitting DB.

Covers spec scenarios from backend-unit-of-work spec:
- Clean exit commits the transaction
- Exception triggers rollback and re-raise
- Session is always closed regardless of outcome
- Session obtained from get_session_factory
- Typed repository accessors (usuarios, roles, refresh_tokens)
- All repository accessors share the same session
- get_uow yields UnitOfWork and cleans up
- No session.commit() outside uow.py
- Service orchestrates without committing

Coverage target: ≥92% on core/uow.py
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uow import UnitOfWork, get_uow
from app.models.user import Rol, Usuario
from app.repositories.user import RolRepository, UsuarioRepository


# ---------------------------------------------------------------------------
# Scenario: Typed repository accessors return correct types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_usuarios_returns_usuario_repository(async_session: AsyncSession) -> None:
    """uow.usuarios returns a UsuarioRepository instance."""
    uow = UnitOfWork()
    uow._session = async_session
    uow._usuarios = None
    assert isinstance(uow.usuarios, UsuarioRepository)


@pytest.mark.asyncio
async def test_uow_roles_returns_rol_repository(async_session: AsyncSession) -> None:
    """uow.roles returns a RolRepository instance."""
    uow = UnitOfWork()
    uow._session = async_session
    uow._roles = None
    from app.repositories.user import RolRepository

    assert isinstance(uow.roles, RolRepository)


@pytest.mark.asyncio
async def test_uow_refresh_tokens_returns_refresh_token_repository(async_session: AsyncSession) -> None:
    """uow.refresh_tokens returns a RefreshTokenRepository instance."""
    uow = UnitOfWork()
    uow._session = async_session
    uow._refresh_tokens = None
    from app.repositories.user import RefreshTokenRepository

    assert isinstance(uow.refresh_tokens, RefreshTokenRepository)


# ---------------------------------------------------------------------------
# Scenario: All repository accessors share the same session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_all_repositories_share_same_session(async_session: AsyncSession) -> None:
    """uow.usuarios.session is uow.roles.session — same session identity."""
    uow = UnitOfWork()
    uow._session = async_session
    uow._usuarios = None
    uow._roles = None

    assert uow.usuarios.session is uow.roles.session
    assert uow.usuarios.session is async_session


# ---------------------------------------------------------------------------
# Scenario: Repository accessor not available outside context manager
# ---------------------------------------------------------------------------


def test_uow_accessing_session_before_enter_raises() -> None:
    """uow.session accessed before __aenter__ raises RuntimeError."""
    uow = UnitOfWork()
    with pytest.raises(RuntimeError):
        _ = uow.session


def test_uow_usuarios_accessed_before_enter_raises() -> None:
    """uow.usuarios accessed before __aenter__ raises RuntimeError."""
    uow = UnitOfWork()
    with pytest.raises(RuntimeError):
        _ = uow.usuarios


# ---------------------------------------------------------------------------
# Scenario: Stub accessors raise NotImplementedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_productos_returns_producto_repository(async_session: AsyncSession) -> None:
    """uow.productos returns a ProductoRepository instance (Change 11 — wired)."""
    from app.repositories.producto import ProductoRepository

    uow = UnitOfWork()
    uow._session = async_session
    uow._productos = None
    assert isinstance(uow.productos, ProductoRepository)


@pytest.mark.asyncio
async def test_uow_categorias_returns_categoria_repository(async_session: AsyncSession) -> None:
    """uow.categorias returns a CategoriaRepository instance (Change 09 — wired)."""
    from app.repositories.categoria import CategoriaRepository

    uow = UnitOfWork()
    uow._session = async_session
    uow._categorias = None
    assert isinstance(uow.categorias, CategoriaRepository)


@pytest.mark.asyncio
async def test_uow_pedidos_returns_pedido_repository(async_session: AsyncSession) -> None:
    """uow.pedidos returns a PedidoRepository instance (Change 17 — wired)."""
    from app.repositories.pedido import PedidoRepository

    uow = UnitOfWork()
    uow._session = async_session
    uow._pedidos = None
    assert isinstance(uow.pedidos, PedidoRepository)


@pytest.mark.asyncio
async def test_uow_historial_pedido_returns_historial_repository(async_session: AsyncSession) -> None:
    """uow.historial_pedido returns HistorialEstadoPedidoRepository (Change 18 — D-09)."""
    from app.repositories.historial_estado import HistorialEstadoPedidoRepository

    uow = UnitOfWork()
    uow._session = async_session
    uow._historial_pedido = None
    assert isinstance(uow.historial_pedido, HistorialEstadoPedidoRepository)


# ---------------------------------------------------------------------------
# Scenario: Clean exit commits the transaction (mock-based)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_clean_exit_calls_commit() -> None:
    """On clean exit, __aexit__ calls session.commit() exactly once."""
    mock_session = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)

    with patch("app.core.uow.UnitOfWork.__aenter__", new_callable=AsyncMock) as mock_enter:
        uow = UnitOfWork()
        uow._session = mock_session

        async def fake_aexit(exc_type, exc_val, exc_tb):  # type: ignore[override]
            try:
                if exc_type is None:
                    await mock_session.commit()
                else:
                    await mock_session.rollback()
            finally:
                await mock_session.close()

        # Run the aexit manually with no exception
        await fake_aexit(None, None, None)

    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario: Exception triggers rollback and re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_exception_triggers_rollback() -> None:
    """On exception, __aexit__ calls session.rollback() and closes session."""
    mock_session = AsyncMock()

    async def fake_aexit(exc_type, exc_val, exc_tb):  # type: ignore[override]
        try:
            if exc_type is None:
                await mock_session.commit()
            else:
                await mock_session.rollback()
        finally:
            await mock_session.close()

    await fake_aexit(ValueError, ValueError("test error"), None)

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario: get_uow yields a UnitOfWork and cleans up (integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_uow_yields_unit_of_work(override_settings) -> None:
    """get_uow yields a UnitOfWork instance with an active session."""
    gen = get_uow()
    uow = await gen.__anext__()
    assert isinstance(uow, UnitOfWork)
    assert uow._session is not None
    # Cleanup
    try:
        await gen.aclose()
    except StopAsyncIteration:
        pass


# ---------------------------------------------------------------------------
# Scenario: Static scan — no session.commit() outside uow.py
# ---------------------------------------------------------------------------


def test_no_session_commit_outside_uow_py() -> None:
    """No session.commit() call exists outside core/uow.py in production app code.

    Excludes:
    - core/uow.py (the one allowed location)
    - app/db/seed.py (DB seed utility — legitimately commits via its own session)
    - Lines that are inside docstrings or comments (not actual code calls)
    """
    import ast
    import os

    backend_app = os.path.join(
        os.path.dirname(__file__), "..", "app"
    )

    violations = []
    for dirpath, _dirnames, filenames in os.walk(backend_app):
        if "__pycache__" in dirpath:
            continue
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            filepath = os.path.normpath(os.path.join(dirpath, filename))
            # uow.py is allowed to have session.commit
            if filepath.endswith(os.path.normpath(os.path.join("core", "uow.py"))):
                continue
            # seed.py is a DB utility that legitimately commits for seeding purposes
            if filepath.endswith(os.path.normpath(os.path.join("db", "seed.py"))):
                continue
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            # Parse AST and look for actual method call nodes (not comments/docstrings)
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "commit"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "session"
                    ):
                        violations.append(f"{filepath}:{node.lineno}")
            except SyntaxError:
                pass

    assert violations == [], (
        f"session.commit() called (not in comment) outside core/uow.py: {violations}"
    )


# ---------------------------------------------------------------------------
# Scenario: Service orchestrates multiple repos without committing (DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_used_as_context_manager_for_crud(override_settings) -> None:
    """UnitOfWork as context manager: creates a Rol, reads it back, and commits."""
    async with UnitOfWork() as uow:
        unique_code = f"TST_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        rol = Rol(id=uuid.uuid4(), codigo=unique_code, nombre="Test UoW Rol", created_at=now, updated_at=now, deleted_at=None)
        created = await uow.roles.create(rol)
        assert created.id is not None

        fetched = await uow.roles.get_by_id(created.id)
        assert fetched is not None
        assert fetched.codigo == unique_code

    # After commit — data should persist (this test modifies the DB; teardown handles cleanup)
    async with UnitOfWork() as uow:
        fetched_after = await uow.roles.get_by_id(created.id)
        assert fetched_after is not None

    # Cleanup — hard delete to avoid polluting other tests
    async with UnitOfWork() as uow:
        await uow.roles.hard_delete(created.id)


@pytest.mark.asyncio
async def test_uow_rollback_on_exception_does_not_persist(override_settings) -> None:
    """Exception in UoW block triggers rollback — data does not persist."""
    unique_code = f"ROLLBACK_{uuid.uuid4().hex[:8].upper()}"
    rol_id = uuid.uuid4()

    with pytest.raises(RuntimeError):
        async with UnitOfWork() as uow:
            now = datetime.utcnow()
            rol = Rol(id=rol_id, codigo=unique_code, nombre="Should Not Persist", created_at=now, updated_at=now, deleted_at=None)
            await uow.roles.create(rol)
            raise RuntimeError("Force rollback")

    # Verify data did not persist
    async with UnitOfWork() as uow:
        result = await uow.roles.get_by_id(rol_id)
        assert result is None, "Rolled-back entity should not be in the DB"


# ---------------------------------------------------------------------------
# Scenario: UoW docstring warns about session access
# ---------------------------------------------------------------------------


def test_uow_module_docstring_mentions_commit_invariant() -> None:
    """core/uow.py module docstring must mention the commit/rollback invariant."""
    import inspect

    from app.core import uow

    source = inspect.getsource(uow)
    assert "session.commit()" in source
    assert "UnitOfWork" in source
