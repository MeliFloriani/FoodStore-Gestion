"""
Tests unitarios para pedidos_validar_service.validar_pre_checkout.

TDD: cubre todos los escenarios del spec backend-pre-checkout-validations.
Usa unittest.mock para aislar el service de la BD real.

Tasks cubiertos: 4.1–4.10 (service tests).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.pedidos_validar import (
    ItemAValidar,
    ValidarPreCheckoutRequest,
)
from app.services.pedidos_validar_service import validar_pre_checkout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_producto(
    id: uuid.UUID | None = None,
    precio_base: float = 100.00,
    stock_cantidad: int = 10,
    disponible: bool = True,
    deleted_at=None,
) -> MagicMock:
    """Build a fake Producto ORM object."""
    p = MagicMock()
    p.id = id or uuid.uuid4()
    p.precio_base = precio_base
    p.stock_cantidad = stock_cantidad
    p.disponible = disponible
    p.deleted_at = deleted_at
    return p


def _make_pi(
    producto_id: uuid.UUID,
    ingrediente_id: uuid.UUID,
    es_removible: bool = True,
) -> MagicMock:
    """Build a fake ProductoIngrediente pivot object."""
    pi = MagicMock()
    pi.producto_id = producto_id
    pi.ingrediente_id = ingrediente_id
    pi.es_removible = es_removible
    return pi


def _make_productos_repo(productos: list[MagicMock]) -> MagicMock:
    """Build a mock ProductoRepository with get_by_ids returning given list."""
    repo = MagicMock()
    repo.get_by_ids = AsyncMock(return_value=productos)
    return repo


def _make_uow(productos_repo: MagicMock, session_execute_result=None) -> MagicMock:
    """Build a mock UnitOfWork with productos repo and mocked session.execute."""
    uow = MagicMock()
    uow.productos = productos_repo

    # Default session mock (returns empty list for ProductoIngrediente query)
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = (
        session_execute_result if session_execute_result is not None else []
    )
    mock_session.execute = AsyncMock(return_value=mock_result)
    uow.session = mock_session
    return uow


def _make_request(*items: ItemAValidar) -> ValidarPreCheckoutRequest:
    return ValidarPreCheckoutRequest(items=list(items))


def _item(
    producto_id: str | None = None,
    cantidad: int = 1,
    precio: str = "100.00",
    personalizacion: list[str] | None = None,
) -> ItemAValidar:
    return ItemAValidar(
        producto_id=producto_id or str(uuid.uuid4()),
        cantidad=cantidad,
        precio=precio,
        personalizacion=personalizacion or [],
    )


# ---------------------------------------------------------------------------
# Task 4.1 — Fixture de UoW en modo test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uow_mock_is_valid():
    """Task 4.1: El mock del UoW se configura correctamente."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    assert uow.productos is repo
    await uow.productos.get_by_ids([pid])
    repo.get_by_ids.assert_called_once_with([pid])


# ---------------------------------------------------------------------------
# Task 4.2 — Happy path: carrito válido → ok=True, cambios=[]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carrito_valido_ok_true_sin_cambios():
    """Task 4.2: Carrito con producto vigente, disponible, stock ok y precio igual → ok=True."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, precio_base=100.00, stock_cantidad=5, disponible=True)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), cantidad=2, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is True
    assert response.cambios == []
    assert len(response.items) == 1
    assert response.items[0].vigente is True
    assert response.items[0].disponible is True


# ---------------------------------------------------------------------------
# Task 4.3 — PRODUCTO_NO_VIGENTE: producto con deleted_at no nulo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_producto_eliminado_no_vigente():
    """Task 4.3: Producto con deleted_at no nulo → PRODUCTO_NO_VIGENTE, ok=False.

    get_by_ids excluye productos con deleted_at IS NOT NULL, entonces el producto
    no aparece en la lista retornada. El service infiere PRODUCTO_NO_VIGENTE.
    """
    pid = uuid.uuid4()
    # Producto eliminado NO aparece en get_by_ids (excluido por deleted_at IS NULL)
    repo = _make_productos_repo([])  # lista vacía = el producto fue excluido
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), cantidad=1, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    assert len(response.cambios) == 1
    assert response.cambios[0].tipo == "PRODUCTO_NO_VIGENTE"
    assert response.cambios[0].detalle["razon"] == "no_encontrado"
    assert response.items[0].vigente is False
    assert response.items[0].stock_disponible is None


# ---------------------------------------------------------------------------
# Task 4.4 — PRODUCTO_NO_DISPONIBLE: disponible=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_producto_no_disponible():
    """Task 4.4: Producto disponible=False → PRODUCTO_NO_DISPONIBLE, ok=False."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, disponible=False, stock_cantidad=10)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), cantidad=1, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    cambios_tipo = [c.tipo for c in response.cambios]
    assert "PRODUCTO_NO_DISPONIBLE" in cambios_tipo
    assert response.items[0].disponible is False


# ---------------------------------------------------------------------------
# Task 4.5 — STOCK_INSUFICIENTE con detalle correcto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_insuficiente_con_detalle():
    """Task 4.5: stock_cantidad < cantidad solicitada → STOCK_INSUFICIENTE, ok=False."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, stock_cantidad=3, disponible=True)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), cantidad=5, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    stock_cambios = [c for c in response.cambios if c.tipo == "STOCK_INSUFICIENTE"]
    assert len(stock_cambios) == 1
    assert stock_cambios[0].detalle["stock_disponible"] == 3
    assert stock_cambios[0].detalle["cantidad_solicitada"] == 5


# ---------------------------------------------------------------------------
# Task 4.6 — PRECIO_CAMBIADO como único cambio → ok=True (no bloqueante)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_precio_cambiado_unico_ok_true():
    """Task 4.6: Solo PRECIO_CAMBIADO → ok=True (cambio no bloqueante)."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, precio_base=100.01, stock_cantidad=5, disponible=True)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    # El cliente tiene precio 100.00, el producto actual es 100.01
    request = _make_request(_item(producto_id=str(pid), cantidad=1, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is True  # PRECIO_CAMBIADO no bloquea
    precio_cambios = [c for c in response.cambios if c.tipo == "PRECIO_CAMBIADO"]
    assert len(precio_cambios) == 1
    assert precio_cambios[0].detalle["precio_anterior"] == "100.00"
    assert precio_cambios[0].detalle["precio_actual"] == "100.01"


# ---------------------------------------------------------------------------
# Task 4.7 — PRECIO_CAMBIADO + STOCK_INSUFICIENTE → ok=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_precio_cambiado_mas_stock_insuficiente_ok_false():
    """Task 4.7: Precio cambiado + stock insuficiente → ok=False (cambio bloqueante presente)."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, precio_base=200.00, stock_cantidad=1, disponible=True)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    # Cliente tiene precio 100.00 (distinto) y quiere 5 unidades (solo hay 1)
    request = _make_request(_item(producto_id=str(pid), cantidad=5, precio="100.00"))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    tipos = {c.tipo for c in response.cambios}
    assert "PRECIO_CAMBIADO" in tipos
    assert "STOCK_INSUFICIENTE" in tipos


# ---------------------------------------------------------------------------
# Task 4.8 — PERSONALIZACION_INVALIDA: ingrediente inválido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personalizacion_invalida_ingrediente_no_removible():
    """Task 4.8: Ingrediente no removible en personalización → PERSONALIZACION_INVALIDA, ok=False."""
    pid = uuid.uuid4()
    ing_id = uuid.uuid4()

    producto = _make_producto(id=pid, stock_cantidad=5, disponible=True)
    repo = _make_productos_repo([producto])

    # Ingrediente existe pero es_removible=False
    pi = _make_pi(producto_id=pid, ingrediente_id=ing_id, es_removible=False)
    uow = _make_uow(repo, session_execute_result=[pi])

    request = _make_request(
        _item(
            producto_id=str(pid),
            cantidad=1,
            precio="100.00",
            personalizacion=[str(ing_id)],
        )
    )
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    pers_cambios = [c for c in response.cambios if c.tipo == "PERSONALIZACION_INVALIDA"]
    assert len(pers_cambios) == 1
    assert pers_cambios[0].detalle["ingrediente_id"] == str(ing_id)
    assert pers_cambios[0].detalle["razon"] == "no_es_removible"


# ---------------------------------------------------------------------------
# Task 4.9 — producto_id inexistente → PRODUCTO_NO_VIGENTE razon "no_encontrado"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_producto_inexistente_no_vigente_no_encontrado():
    """Task 4.9: producto_id que no existe en BD → PRODUCTO_NO_VIGENTE razon 'no_encontrado'."""
    pid = uuid.uuid4()
    repo = _make_productos_repo([])  # BD no tiene este producto
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid)))
    response = await validar_pre_checkout(uow, request)

    assert response.ok is False
    assert response.cambios[0].tipo == "PRODUCTO_NO_VIGENTE"
    assert response.cambios[0].detalle["razon"] == "no_encontrado"


# ---------------------------------------------------------------------------
# Task 4.10 — Anti-N+1: 1 sola query a productos para N ítems
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anti_n_plus_1_una_sola_query_para_n_items():
    """Task 4.10: El service ejecuta exactamente 1 query get_by_ids para N ítems distintos."""
    # Crear 3 productos distintos
    pid1, pid2, pid3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    p1 = _make_producto(id=pid1)
    p2 = _make_producto(id=pid2)
    p3 = _make_producto(id=pid3)

    repo = _make_productos_repo([p1, p2, p3])
    uow = _make_uow(repo)

    request = _make_request(
        _item(producto_id=str(pid1)),
        _item(producto_id=str(pid2)),
        _item(producto_id=str(pid3)),
    )
    await validar_pre_checkout(uow, request)

    # Verificar que get_by_ids fue llamado exactamente UNA VEZ (no 3 veces)
    assert repo.get_by_ids.call_count == 1

    # Verificar que la lista pasada contiene los 3 UUIDs (sin N+1)
    called_ids = set(str(i) for i in repo.get_by_ids.call_args[0][0])
    assert str(pid1) in called_ids
    assert str(pid2) in called_ids
    assert str(pid3) in called_ids


# ---------------------------------------------------------------------------
# Tests adicionales — Decimal cuantizado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_precio_identico_no_genera_cambio():
    """Precio idéntico después de cuantizar no genera PRECIO_CAMBIADO."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, precio_base=250.00)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), precio="250.00"))
    response = await validar_pre_checkout(uow, request)

    precio_cambios = [c for c in response.cambios if c.tipo == "PRECIO_CAMBIADO"]
    assert len(precio_cambios) == 0


@pytest.mark.asyncio
async def test_precio_diferente_en_un_centavo_genera_cambio():
    """Diferencia de 0.01 en precio genera PRECIO_CAMBIADO (tolerancia cero)."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid, precio_base=250.01)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid), precio="250.00"))
    response = await validar_pre_checkout(uow, request)

    precio_cambios = [c for c in response.cambios if c.tipo == "PRECIO_CAMBIADO"]
    assert len(precio_cambios) == 1


@pytest.mark.asyncio
async def test_dos_items_mismo_producto_una_sola_query():
    """Dos ítems con el mismo producto_id → se deduplica en la query batch."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid)
    repo = _make_productos_repo([producto])
    uow = _make_uow(repo)

    # Mismo producto_id, diferente personalización
    request = _make_request(
        _item(producto_id=str(pid), personalizacion=[]),
        _item(producto_id=str(pid), personalizacion=[str(uuid.uuid4())]),
    )
    await validar_pre_checkout(uow, request)

    # Solo 1 llamada a get_by_ids (deduplicación)
    assert repo.get_by_ids.call_count == 1

    # La lista tiene solo 1 UUID único (pid deduplicado)
    called_ids = list(repo.get_by_ids.call_args[0][0])
    assert len(called_ids) == 1
    assert called_ids[0] == pid


@pytest.mark.asyncio
async def test_items_response_same_length_as_request():
    """El response tiene exactamente un ItemValidadoRead por ítem del request."""
    pid1, pid2 = uuid.uuid4(), uuid.uuid4()
    p1 = _make_producto(id=pid1)
    p2 = _make_producto(id=pid2)
    repo = _make_productos_repo([p1, p2])
    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid1)), _item(producto_id=str(pid2)))
    response = await validar_pre_checkout(uow, request)

    assert len(response.items) == 2


@pytest.mark.asyncio
async def test_personalizacion_valida_no_genera_cambio():
    """Personalización con ingrediente es_removible=True no genera PERSONALIZACION_INVALIDA."""
    pid = uuid.uuid4()
    ing_id = uuid.uuid4()

    producto = _make_producto(id=pid, stock_cantidad=5)
    repo = _make_productos_repo([producto])

    pi = _make_pi(producto_id=pid, ingrediente_id=ing_id, es_removible=True)
    uow = _make_uow(repo, session_execute_result=[pi])

    request = _make_request(
        _item(
            producto_id=str(pid),
            cantidad=1,
            precio="100.00",
            personalizacion=[str(ing_id)],
        )
    )
    response = await validar_pre_checkout(uow, request)

    pers_cambios = [c for c in response.cambios if c.tipo == "PERSONALIZACION_INVALIDA"]
    assert len(pers_cambios) == 0


@pytest.mark.asyncio
async def test_service_no_llama_metodos_escritura():
    """El service no llama métodos de escritura del UoW (solo lectura)."""
    pid = uuid.uuid4()
    producto = _make_producto(id=pid)
    repo = _make_productos_repo([producto])

    # Agregar métodos de escritura como mocks que NO deben llamarse
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.soft_delete = AsyncMock()
    repo.decrement_stock = AsyncMock()

    uow = _make_uow(repo)

    request = _make_request(_item(producto_id=str(pid)))
    await validar_pre_checkout(uow, request)

    repo.create.assert_not_called()
    repo.update.assert_not_called()
    repo.soft_delete.assert_not_called()
    repo.decrement_stock.assert_not_called()
