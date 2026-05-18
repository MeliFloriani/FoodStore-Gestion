"""
UnitOfWork override factory for integration tests.

Pattern:
  Instead of letting UnitOfWork create its own AsyncSession (which would commit
  and persist data), we inject the test session (which runs inside a SAVEPOINT
  that is rolled back at teardown).

Usage in a test:
    from tests.fixtures.uow import make_uow_override
    from app.core.uow import get_uow

    async def test_something(async_session, async_client):
        app.dependency_overrides[get_uow] = make_uow_override(async_session)
        response = await async_client.get("/api/v1/some-endpoint")
        assert response.status_code == 200
        # SAVEPOINT rolls back automatically — no data persists after the test.

See also: backend/tests/README.md for the full pattern explanation.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uow import UnitOfWork


def make_uow_override(
    session: AsyncSession,
) -> Callable[[], AsyncGenerator[UnitOfWork, None]]:
    """Return a FastAPI dependency override that yields a UnitOfWork using the test session.

    The returned UnitOfWork reuses the provided AsyncSession directly, bypassing
    get_session_factory(). This means __aenter__ / __aexit__ still run (providing
    the right interface) but the session is never committed — the SAVEPOINT wrapping
    the test transaction handles rollback at teardown.

    The override's __aexit__ is patched to skip commit/rollback (those are handled
    by the test fixture's SAVEPOINT), while still running logger calls and cleanup.

    Args:
        session: The test AsyncSession created by the async_session fixture.

    Returns:
        An async generator function suitable for use with app.dependency_overrides.
    """

    async def _override() -> AsyncGenerator[UnitOfWork, None]:
        uow = UnitOfWork()
        # Inject the test session directly — bypasses get_session_factory().
        uow._session = session  # noqa: SLF001 — fixture needs direct access (R-05)
        # Reset lazy repos so they bind to this session.
        uow._usuarios = None  # noqa: SLF001
        uow._roles = None  # noqa: SLF001
        uow._usuario_roles = None  # noqa: SLF001
        uow._refresh_tokens = None  # noqa: SLF001
        uow._categorias = None  # noqa: SLF001 — Change 09
        try:
            yield uow
        finally:
            # Do NOT commit or rollback here — the SAVEPOINT in conftest.py handles it.
            # Also do NOT close the session — the async_connection fixture owns it.
            pass

    return _override
