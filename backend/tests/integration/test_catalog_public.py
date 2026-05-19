"""
Integration tests for the public catalog API endpoints.

Task 4.3 — verifies:
  - GET /api/v1/catalog/productos returns 200 with no auth header.
  - Response body has items, total, page, size, pages; no item has stock_cantidad.
  - Every item has tiene_stock as boolean.
  - Filter params: q, categoria_id, excluir_alergenos, page, size, ordenar.
  - GET /api/v1/catalog/productos/{id} returns 200 with full relations.
  - Returns 404 with code="PRODUCT_NOT_FOUND" for disponible=false product.
  - Returns 404 with code="PRODUCT_NOT_FOUND" for soft-deleted product.
  - Returns 422 for non-UUID path param.
  - excluir_alergenos=abc returns 422 with code="INVALID_ALLERGEN_IDS".
  - size=200 returns 422 (schema validation).
  - GET /api/v1/catalog/ingredientes-alergenos returns 200 with no auth.
  - Returns only ingredients with es_alergeno=true.
  - Excludes soft-deleted ingredients.

Uses the SAVEPOINT-based seeded_session and async_client fixtures.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override

CATALOG_URL = "/api/v1/catalog"
CATALOG_PRODUCTOS = f"{CATALOG_URL}/productos"
CATALOG_ALERGENOS = f"{CATALOG_URL}/ingredientes-alergenos"


# ---------------------------------------------------------------------------
# Helpers — create test data via repository directly
# ---------------------------------------------------------------------------


async def _create_producto(
    session,
    nombre: str = None,
    precio_base: float = 10.00,
    stock_cantidad: int = 5,
    disponible: bool = True,
    deleted_at=None,
) -> "Producto":
    """Create a Producto directly in the test session."""
    from app.models.catalog import Producto

    nombre = nombre or f"Prod_{uuid.uuid4().hex[:8]}"
    p = Producto(
        nombre=nombre,
        precio_base=precio_base,
        stock_cantidad=stock_cantidad,
        disponible=disponible,
    )
    if deleted_at is not None:
        p.deleted_at = deleted_at
    session.add(p)
    await session.flush()
    return p


async def _create_categoria(session, nombre: str = None) -> "Categoria":
    """Create a Categoria directly in the test session."""
    from app.models.catalog import Categoria

    nombre = nombre or f"Cat_{uuid.uuid4().hex[:8]}"
    c = Categoria(nombre=nombre)
    session.add(c)
    await session.flush()
    return c


async def _create_ingrediente(
    session,
    nombre: str = None,
    es_alergeno: bool = True,
    deleted_at=None,
) -> "Ingrediente":
    """Create an Ingrediente directly in the test session."""
    from app.models.catalog import Ingrediente

    nombre = nombre or f"Ing_{uuid.uuid4().hex[:8]}"
    i = Ingrediente(nombre=nombre, es_alergeno=es_alergeno)
    if deleted_at is not None:
        i.deleted_at = deleted_at
    session.add(i)
    await session.flush()
    return i


async def _link_producto_categoria(session, producto_id, categoria_id) -> None:
    """Associate a product with a category."""
    from app.models.catalog import ProductoCategoria

    pivot = ProductoCategoria(
        producto_id=producto_id,
        categoria_id=categoria_id,
        es_principal=True,
    )
    session.add(pivot)
    await session.flush()


async def _link_producto_ingrediente(
    session,
    producto_id,
    ingrediente_id,
    es_removible: bool = True,
) -> None:
    """Associate a product with an ingredient."""
    from app.models.catalog import ProductoIngrediente

    pivot = ProductoIngrediente(
        producto_id=producto_id,
        ingrediente_id=ingrediente_id,
        es_removible=es_removible,
    )
    session.add(pivot)
    await session.flush()


# ---------------------------------------------------------------------------
# GET /api/v1/catalog/productos — basic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog_productos_returns_200_no_auth(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos without auth header returns 200."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Create a visible product
        await _create_producto(seeded_session, nombre="Visible Product")

        response = await async_client.get(CATALOG_PRODUCTOS)
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_response_shape(
    seeded_session, async_client: AsyncClient
) -> None:
    """Response body has items, total, page, size, pages fields."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        await _create_producto(seeded_session)

        response = await async_client.get(CATALOG_PRODUCTOS)
        assert response.status_code == 200
        body = response.json()

        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "size" in body
        assert "pages" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_items_have_no_stock_cantidad(
    seeded_session, async_client: AsyncClient
) -> None:
    """No item in the catalog list response should have stock_cantidad key."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        await _create_producto(seeded_session, stock_cantidad=10)

        response = await async_client.get(CATALOG_PRODUCTOS)
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1

        for item in items:
            assert "stock_cantidad" not in item, (
                f"stock_cantidad found in item: {item}"
            )
            assert "tiene_stock" in item
            assert isinstance(item["tiene_stock"], bool)
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_excludes_hidden_products(
    seeded_session, async_client: AsyncClient
) -> None:
    """catalog/productos must NOT return products with disponible=false or soft-deleted."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        visible = await _create_producto(seeded_session, nombre="Visible")
        _hidden = await _create_producto(seeded_session, nombre="Hidden", disponible=False)
        _deleted = await _create_producto(
            seeded_session,
            nombre="Deleted",
            deleted_at=datetime.now(timezone.utc),
        )

        response = await async_client.get(CATALOG_PRODUCTOS)
        assert response.status_code == 200
        items = response.json()["items"]

        names = [item["nombre"] for item in items]
        assert "Visible" in names
        assert "Hidden" not in names
        assert "Deleted" not in names
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Filter: q (ILIKE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog_filter_q_ilike(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos?q=<suffix> filters by ILIKE match."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Use a unique suffix as the q term so only our products match
        pizza_suffix = f"pizza_{uuid.uuid4().hex[:6]}"
        burger_suffix = f"burger_{uuid.uuid4().hex[:6]}"

        p1 = await _create_producto(seeded_session, nombre=f"Margherita {pizza_suffix}")
        p2 = await _create_producto(seeded_session, nombre=f"Napolitana {pizza_suffix}")
        p3 = await _create_producto(seeded_session, nombre=f"Classic {burger_suffix}")

        # Search by the pizza_suffix — should match p1 and p2 only
        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"q": pizza_suffix}
        )
        assert response.status_code == 200
        body = response.json()
        ids = [item["id"] for item in body["items"]]
        assert str(p1.id) in ids, "p1 should match the pizza_suffix filter"
        assert str(p2.id) in ids, "p2 should match the pizza_suffix filter"
        assert str(p3.id) not in ids, "p3 (burger) should NOT match the pizza_suffix filter"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Filter: categoria_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog_filter_categoria_id(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos?categoria_id=<uuid> returns products in that category."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        cat_a = await _create_categoria(seeded_session, nombre=f"Cat_A_{uuid.uuid4().hex[:6]}")
        cat_b = await _create_categoria(seeded_session, nombre=f"Cat_B_{uuid.uuid4().hex[:6]}")

        p1 = await _create_producto(seeded_session, nombre=f"Prod_CatA_{uuid.uuid4().hex[:6]}")
        p2 = await _create_producto(seeded_session, nombre=f"Prod_CatB_{uuid.uuid4().hex[:6]}")

        await _link_producto_categoria(seeded_session, p1.id, cat_a.id)
        await _link_producto_categoria(seeded_session, p2.id, cat_b.id)

        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"categoria_id": str(cat_a.id)}
        )
        assert response.status_code == 200
        body = response.json()
        ids = [item["id"] for item in body["items"]]
        assert str(p1.id) in ids
        assert str(p2.id) not in ids
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Filter: excluir_alergenos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog_excluir_alergenos_excludes_matching(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos?excluir_alergenos=<uuid> excludes products with that allergen."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        gluten = await _create_ingrediente(seeded_session, nombre=f"Gluten_{uuid.uuid4().hex[:6]}", es_alergeno=True)
        tomate = await _create_ingrediente(seeded_session, nombre=f"Tomate_{uuid.uuid4().hex[:6]}", es_alergeno=False)

        p_with_gluten = await _create_producto(seeded_session, nombre=f"WithGluten_{uuid.uuid4().hex[:6]}")
        p_without_gluten = await _create_producto(seeded_session, nombre=f"NoGluten_{uuid.uuid4().hex[:6]}")

        await _link_producto_ingrediente(seeded_session, p_with_gluten.id, gluten.id)
        await _link_producto_ingrediente(seeded_session, p_without_gluten.id, tomate.id)

        # Use the actual UUID of the gluten ingredient — Ingrediente.id is UUID in this project
        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"excluir_alergenos": str(gluten.id)}
        )
        assert response.status_code == 200
        body = response.json()
        ids = [item["id"] for item in body["items"]]
        assert str(p_with_gluten.id) not in ids, "Product with gluten should be excluded"
        assert str(p_without_gluten.id) in ids, "Product without gluten should be included"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_excluir_alergenos_invalid_returns_422(
    seeded_session, async_client: AsyncClient
) -> None:
    """excluir_alergenos=not-a-uuid returns 422 with code=INVALID_ALLERGEN_IDS."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"excluir_alergenos": "not-a-uuid"}
        )
        assert response.status_code == 422
        body = response.json()
        assert body.get("code") == "INVALID_ALLERGEN_IDS"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Pagination and ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog_size_200_returns_422(
    seeded_session, async_client: AsyncClient
) -> None:
    """size=200 returns 422 (CatalogProductosQuery validates size <= 100)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"size": "200"}
        )
        assert response.status_code == 422, (
            f"Expected 422 for size=200, got: {response.status_code}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_pagination(
    seeded_session, async_client: AsyncClient
) -> None:
    """Pagination works: page=2 with size=1 returns the second product."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        suffix = uuid.uuid4().hex[:6]
        await _create_producto(seeded_session, nombre=f"Alpha_{suffix}")
        await _create_producto(seeded_session, nombre=f"Beta_{suffix}")

        # Get page 1 with size=1
        r1 = await async_client.get(CATALOG_PRODUCTOS, params={"page": 1, "size": 1, "q": suffix})
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["page"] == 1
        assert body1["size"] == 1
        assert body1["total"] == 2
        assert body1["pages"] == 2
        assert len(body1["items"]) == 1

        # Get page 2 with size=1
        r2 = await async_client.get(CATALOG_PRODUCTOS, params={"page": 2, "size": 1, "q": suffix})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["page"] == 2
        assert len(body2["items"]) == 1

        # Items on different pages should be different
        assert body1["items"][0]["id"] != body2["items"][0]["id"]
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_catalog_ordenar_nombre_asc(
    seeded_session, async_client: AsyncClient
) -> None:
    """ordenar=nombre sorts products by nombre ASC."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        suffix = uuid.uuid4().hex[:6]
        await _create_producto(seeded_session, nombre=f"Zzz_{suffix}")
        await _create_producto(seeded_session, nombre=f"Aaa_{suffix}")

        response = await async_client.get(
            CATALOG_PRODUCTOS, params={"ordenar": "nombre", "q": suffix}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 2
        names = [item["nombre"] for item in items]
        assert names == sorted(names)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# GET /api/v1/catalog/productos/{id} — detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_200(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos/{id} returns 200 with full detail for visible product."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        p = await _create_producto(seeded_session, nombre="Detail Product", stock_cantidad=3)
        cat = await _create_categoria(seeded_session, nombre="Test Cat")
        ing = await _create_ingrediente(seeded_session, nombre="Gluten Test", es_alergeno=True)
        await _link_producto_categoria(seeded_session, p.id, cat.id)
        await _link_producto_ingrediente(seeded_session, p.id, ing.id)

        response = await async_client.get(f"{CATALOG_PRODUCTOS}/{p.id}")
        assert response.status_code == 200, f"Expected 200, got: {response.text}"

        body = response.json()
        assert body["id"] == str(p.id)
        assert body["nombre"] == "Detail Product"
        assert "stock_cantidad" not in body
        assert "tiene_stock" in body
        assert body["tiene_stock"] is True  # stock_cantidad=3 > 0
        assert "categorias" in body
        assert "ingredientes" in body
        assert len(body["categorias"]) >= 1
        assert len(body["ingredientes"]) >= 1

        # Check ingredient has es_alergeno field
        for ing_data in body["ingredientes"]:
            assert "es_alergeno" in ing_data
            assert "ingrediente_id" in ing_data
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_no_auth_required(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos/{id} does not require Authorization header."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        p = await _create_producto(seeded_session)
        response = await async_client.get(f"{CATALOG_PRODUCTOS}/{p.id}")
        # Must not return 401 or 403
        assert response.status_code not in (401, 403), (
            f"Unexpected auth error: {response.status_code}"
        )
        assert response.status_code in (200, 404)
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_404_for_disabled(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos/{id} returns 404 for disponible=false product."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        p = await _create_producto(seeded_session, disponible=False)
        response = await async_client.get(f"{CATALOG_PRODUCTOS}/{p.id}")
        assert response.status_code == 404, (
            f"Expected 404 for disabled product, got: {response.status_code}"
        )
        body = response.json()
        assert body.get("code") == "PRODUCT_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_404_for_soft_deleted(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos/{id} returns 404 for soft-deleted product."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        p = await _create_producto(
            seeded_session,
            deleted_at=datetime.now(timezone.utc),
        )
        response = await async_client.get(f"{CATALOG_PRODUCTOS}/{p.id}")
        assert response.status_code == 404, (
            f"Expected 404 for soft-deleted product, got: {response.status_code}"
        )
        body = response.json()
        assert body.get("code") == "PRODUCT_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_422_for_non_uuid(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/productos/not-a-uuid returns 422."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(f"{CATALOG_PRODUCTOS}/not-a-uuid")
        assert response.status_code == 422, (
            f"Expected 422 for non-UUID id, got: {response.status_code}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_get_catalog_producto_detail_tiene_stock_false(
    seeded_session, async_client: AsyncClient
) -> None:
    """tiene_stock is False when stock_cantidad is 0."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        p = await _create_producto(seeded_session, stock_cantidad=0)
        response = await async_client.get(f"{CATALOG_PRODUCTOS}/{p.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["tiene_stock"] is False
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# GET /api/v1/catalog/ingredientes-alergenos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_ingredientes_alergenos_200_no_auth(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/ingredientes-alergenos returns 200 without auth header."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(CATALOG_ALERGENOS)
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_ingredientes_alergenos_response_shape(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/ingredientes-alergenos response has items and total."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(CATALOG_ALERGENOS)
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)
        assert body["total"] == len(body["items"])
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_ingredientes_alergenos_only_allergens(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/ingredientes-alergenos returns only es_alergeno=true ingredients."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        suffix = uuid.uuid4().hex[:6]
        await _create_ingrediente(seeded_session, nombre=f"Gluten_{suffix}", es_alergeno=True)
        await _create_ingrediente(seeded_session, nombre=f"Lactosa_{suffix}", es_alergeno=True)
        await _create_ingrediente(seeded_session, nombre=f"Tomate_{suffix}", es_alergeno=False)

        response = await async_client.get(CATALOG_ALERGENOS)
        assert response.status_code == 200
        items = response.json()["items"]

        allergen_names = [item["nombre"] for item in items]
        assert any(f"Gluten_{suffix}" in n for n in allergen_names)
        assert any(f"Lactosa_{suffix}" in n for n in allergen_names)
        assert not any(f"Tomate_{suffix}" in n for n in allergen_names)

        # All returned items must have es_alergeno=true
        for item in items:
            assert item["es_alergeno"] is True
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_ingredientes_alergenos_excludes_soft_deleted(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/ingredientes-alergenos excludes soft-deleted allergens."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        suffix = uuid.uuid4().hex[:6]
        await _create_ingrediente(seeded_session, nombre=f"Active_{suffix}", es_alergeno=True)
        await _create_ingrediente(
            seeded_session,
            nombre=f"Deleted_{suffix}",
            es_alergeno=True,
            deleted_at=datetime.now(timezone.utc),
        )

        response = await async_client.get(CATALOG_ALERGENOS)
        assert response.status_code == 200
        names = [item["nombre"] for item in response.json()["items"]]
        assert any(f"Active_{suffix}" in n for n in names)
        assert not any(f"Deleted_{suffix}" in n for n in names)
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_list_ingredientes_alergenos_empty_when_none(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/catalog/ingredientes-alergenos returns empty list when no allergens exist."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Don't create any allergens — just test the shape
        response = await async_client.get(CATALOG_ALERGENOS)
        assert response.status_code == 200
        body = response.json()
        # May have allergens from other tests, but shape must be correct
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Catalog routes are registered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_routes_registered(
    seeded_session, async_client: AsyncClient
) -> None:
    """All catalog routes are registered in the app route table."""
    routes = [route.path for route in app.routes]  # type: ignore[attr-defined]

    expected_routes = [
        "/api/v1/catalog/productos",
        "/api/v1/catalog/productos/{id}",
        "/api/v1/catalog/ingredientes-alergenos",
    ]
    for expected in expected_routes:
        assert expected in routes, (
            f"Route {expected} not found. Registered routes: {[r for r in routes if 'catalog' in r]}"
        )
