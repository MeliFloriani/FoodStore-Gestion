"""
API v1 router factory.

Design decisions:
- P-02: build_v1_router(settings) is a factory function, NOT a module-level instance.
  The APIRouter prefix depends on settings.API_V1_PREFIX, which must be overridable
  in tests. A module-level router would capture the default settings at import time.
- D-13: The GET /health readiness endpoint accesses Depends(get_session) directly,
  bypassing the Router → Service → UoW → Repo layered pattern. This is an explicit
  documented exception for infrastructure health probes (not domain logic).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_app_version
from app.db.session import get_session


def build_v1_router(settings: Settings) -> APIRouter:
    """Build and return the v1 APIRouter with all v1 endpoints registered.

    Args:
        settings: Injected Settings instance (allows prefix override in tests).

    Returns:
        Configured APIRouter with prefix=settings.API_V1_PREFIX.
    """
    router = APIRouter(prefix=settings.API_V1_PREFIX)

    @router.get("/health", tags=["health"], summary="Readiness probe")
    async def health_readiness(
        session: AsyncSession = Depends(get_session),  # D-13: health probe exception
    ) -> dict[str, str]:
        """Readiness probe: verifies database connectivity.

        Exception D-13: this endpoint accesses the DB session directly, skipping
        the Router → Service → UoW → Repository pattern. Justified because this is
        an infrastructure readiness probe, not domain logic.
        """
        try:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="Database connection failed",
            )
        return {
            "status": "ok",
            "database": db_status,
            "version": get_app_version(),
        }

    # --- Auth endpoints (Change auth-register-login) ---
    from app.api.v1.auth import auth_router  # noqa: PLC0415 — lazy import inside factory

    router.include_router(auth_router)

    # --- Catalog: Categories (Change 09 — catalog-categories-management) ---
    from app.api.v1.categorias import categorias_router  # noqa: PLC0415 — lazy import inside factory

    router.include_router(categorias_router, prefix="/categorias", tags=["categorias"])

    # --- Catalog: Ingredients (Change 10 — catalog-ingredients-management) ---
    from app.api.v1.ingredientes import ingredientes_router  # noqa: PLC0415 — lazy import inside factory

    router.include_router(ingredientes_router, prefix="/ingredientes", tags=["ingredientes"])

    # --- Catalog: Products (Change 11 — catalog-products-management) ---
    from app.api.v1.productos import productos_router  # noqa: PLC0415 — lazy import inside factory

    router.include_router(productos_router, prefix="/productos", tags=["productos"])

    return router
