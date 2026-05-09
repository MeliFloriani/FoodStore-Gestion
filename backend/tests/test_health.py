"""
Smoke test del bootstrap — verifica que el servidor FastAPI arranca
y que el health check responde correctamente.

Tests de negocio se agregan en changes posteriores (Change 02+).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """GET /health debe devolver {"status": "ok"} con HTTP 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
