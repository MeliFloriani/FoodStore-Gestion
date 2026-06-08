"""
Service de validación pre-checkout.

Implementa la función stateless validar_pre_checkout que consulta el estado actual
de los productos del carrito del cliente y reporta discrepancias sin crear pedidos
ni modificar stock.

Decisión D-06: UoW de solo lectura — nunca llama métodos de escritura ni commit
de cambios. El commit final en UoW.__aexit__ es no-op porque no se modificaron entidades.

Decisión D-07: Anti-N+1 — todos los productos se obtienen con una sola query
SELECT WHERE id IN (...). Los ProductoIngrediente también se cargan en batch.

Decisión D-03: Precios como Decimal cuantizado a 2 decimales (tolerancia cero).

Decisión D-11: Naming — este módulo se llama pedidos_validar_service.py
(no pedidos_service.py) para dejar ese namespace a Change 17.

Flujo de evaluación por ítem (en orden):
  1. Vigencia (deleted_at IS NULL AND producto existe en BD)
  2. Disponibilidad (disponible=True)
  3. Stock (stock_cantidad >= cantidad)
  4. Precio (Decimal cuantizado 0.01)
  5. Personalización (es_removible=True y pertenece al producto)

ok = len([c for c in cambios if c.tipo != "PRECIO_CAMBIADO"]) == 0
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.core.uow import UnitOfWork
from app.models.catalog import ProductoIngrediente
from app.schemas.pedidos_validar import (
    CambioRead,
    ItemAValidar,
    ItemValidadoRead,
    ValidarPreCheckoutRequest,
    ValidarPreCheckoutResponse,
)

_QUANTIZE = Decimal("0.01")


def _cuantizar(valor: str | Decimal | float) -> Decimal:
    """Convierte un valor a Decimal cuantizado a 2 decimales (ROUND_HALF_UP)."""
    return Decimal(str(valor)).quantize(_QUANTIZE, rounding=ROUND_HALF_UP)


async def validar_pre_checkout(
    uow: UnitOfWork,
    request: ValidarPreCheckoutRequest,
) -> ValidarPreCheckoutResponse:
    """Valida los ítems del carrito contra el estado actual de la BD.

    Stateless e idempotente: no crea pedidos, no modifica stock, no persiste datos.
    Puede llamarse N veces con los mismos datos — cada llamada refleja el estado
    actual de la BD en ese instante.

    Args:
        uow: UnitOfWork en modo consulta (sin escrituras ni commit de cambios).
        request: ValidarPreCheckoutRequest con los ítems del carrito del cliente.

    Returns:
        ValidarPreCheckoutResponse con ok flag, lista de items validados y cambios
        detectados.
    """
    # -------------------------------------------------------------------------
    # PASO 1: Recopilar IDs únicos (deduplicar para el SELECT IN)
    # -------------------------------------------------------------------------
    ids_unicos: list[uuid.UUID] = list(
        {uuid.UUID(item.producto_id) for item in request.items}
    )

    # -------------------------------------------------------------------------
    # PASO 2: Consulta batch de productos (1 query — anti-N+1, D-07)
    # -------------------------------------------------------------------------
    productos_encontrados = await uow.productos.get_by_ids(ids_unicos)
    productos_por_id: dict[str, object] = {
        str(p.id): p for p in productos_encontrados  # type: ignore[attr-defined]
    }

    # -------------------------------------------------------------------------
    # PASO 3: Carga batch de ProductoIngrediente (solo para ítems con personalización)
    # Una sola query para todos los productos afectados.
    # -------------------------------------------------------------------------
    ids_con_personalizacion: list[uuid.UUID] = [
        uuid.UUID(item.producto_id)
        for item in request.items
        if item.personalizacion
    ]

    # Mapa: producto_id_str → list[ProductoIngrediente]
    ingredientes_por_producto: dict[str, list[ProductoIngrediente]] = {}

    if ids_con_personalizacion:
        ids_unicos_con_pers = list(set(ids_con_personalizacion))
        stmt = select(ProductoIngrediente).where(
            ProductoIngrediente.producto_id.in_(ids_unicos_con_pers)  # type: ignore[union-attr]
        )
        result = await uow.session.execute(stmt)
        for pi in result.scalars().all():
            key = str(pi.producto_id)
            ingredientes_por_producto.setdefault(key, []).append(pi)

    # -------------------------------------------------------------------------
    # PASO 4: Evaluar cada ítem del request en orden
    # -------------------------------------------------------------------------
    items_validados: list[ItemValidadoRead] = []
    cambios: list[CambioRead] = []

    for item in request.items:
        producto = productos_por_id.get(item.producto_id)
        item_validado, item_cambios = _evaluar_item(
            item=item,
            producto=producto,
            ingredientes=ingredientes_por_producto.get(item.producto_id, []),
        )
        items_validados.append(item_validado)
        cambios.extend(item_cambios)

    # -------------------------------------------------------------------------
    # PASO 5: ok = sin cambios bloqueantes (PRECIO_CAMBIADO no bloquea)
    # -------------------------------------------------------------------------
    ok = len([c for c in cambios if c.tipo != "PRECIO_CAMBIADO"]) == 0

    return ValidarPreCheckoutResponse(
        ok=ok,
        items=items_validados,
        cambios=cambios,
    )


def _evaluar_item(
    item: ItemAValidar,
    producto: object | None,
    ingredientes: list[ProductoIngrediente],
) -> tuple[ItemValidadoRead, list[CambioRead]]:
    """Evalúa un ítem del carrito y retorna (ItemValidadoRead, list[CambioRead]).

    Orden de evaluación:
      1. Vigencia → 2. Disponibilidad → 3. Stock → 4. Precio → 5. Personalización

    Si el producto no es vigente, se detiene (disponible/stock/precio son None).

    Args:
        item: Ítem del carrito con datos del cliente.
        producto: Objeto Producto ORM (None si no encontrado en BD).
        ingredientes: Lista de ProductoIngrediente del producto (puede estar vacía).

    Returns:
        Tuple de (ItemValidadoRead, lista de CambioRead para este ítem).
    """
    cambios: list[CambioRead] = []

    # -------------------------------------------------------------------------
    # Evaluación 1: Vigencia
    # -------------------------------------------------------------------------
    if producto is None:
        # Producto no encontrado en BD (ya filtrado por deleted_at IS NULL en get_by_ids)
        # o bien el producto_id no existe en absoluto
        cambios.append(
            CambioRead(
                producto_id=item.producto_id,
                tipo="PRODUCTO_NO_VIGENTE",
                detalle={"razon": "no_encontrado"},
            )
        )
        return (
            ItemValidadoRead(
                producto_id=item.producto_id,
                cantidad_solicitada=item.cantidad,
                stock_disponible=None,
                precio_actual=None,
                precio_percibido=item.precio,
                vigente=False,
                disponible=None,
            ),
            cambios,
        )

    # Producto encontrado — acceder atributos del ORM
    p = producto  # type: ignore[assignment]

    # Verificar si fue soft-deleted pero get_by_ids lo excluyó por deleted_at IS NULL.
    # Si llegamos aquí, producto existe y deleted_at IS NULL → vigente=True.
    vigente = True

    # -------------------------------------------------------------------------
    # Evaluación 2: Disponibilidad
    # -------------------------------------------------------------------------
    disponible: bool = bool(p.disponible)  # type: ignore[attr-defined]
    stock_disponible: int = int(p.stock_cantidad)  # type: ignore[attr-defined]
    precio_actual_decimal = _cuantizar(p.precio_base)  # type: ignore[attr-defined]
    precio_actual_str = str(precio_actual_decimal)

    if not disponible:
        cambios.append(
            CambioRead(
                producto_id=item.producto_id,
                tipo="PRODUCTO_NO_DISPONIBLE",
                detalle={"disponible": False},
            )
        )
        return (
            ItemValidadoRead(
                producto_id=item.producto_id,
                cantidad_solicitada=item.cantidad,
                stock_disponible=stock_disponible,
                precio_actual=precio_actual_str,
                precio_percibido=item.precio,
                vigente=vigente,
                disponible=False,
            ),
            cambios,
        )

    # -------------------------------------------------------------------------
    # Evaluación 3: Stock
    # -------------------------------------------------------------------------
    if stock_disponible < item.cantidad:
        cambios.append(
            CambioRead(
                producto_id=item.producto_id,
                tipo="STOCK_INSUFICIENTE",
                detalle={
                    "stock_disponible": stock_disponible,
                    "cantidad_solicitada": item.cantidad,
                },
            )
        )

    # -------------------------------------------------------------------------
    # Evaluación 4: Precio (tolerancia cero, Decimal cuantizado)
    # -------------------------------------------------------------------------
    precio_percibido_decimal = _cuantizar(item.precio)
    if precio_percibido_decimal != precio_actual_decimal:
        cambios.append(
            CambioRead(
                producto_id=item.producto_id,
                tipo="PRECIO_CAMBIADO",
                detalle={
                    "precio_anterior": str(precio_percibido_decimal),
                    "precio_actual": precio_actual_str,
                },
            )
        )

    # -------------------------------------------------------------------------
    # Evaluación 5: Personalización (solo si hay personalización en el ítem)
    # -------------------------------------------------------------------------
    if item.personalizacion:
        cambio_pers = _evaluar_personalizacion(
            item=item,
            ingredientes=ingredientes,
        )
        if cambio_pers:
            cambios.append(cambio_pers)

    return (
        ItemValidadoRead(
            producto_id=item.producto_id,
            cantidad_solicitada=item.cantidad,
            stock_disponible=stock_disponible,
            precio_actual=precio_actual_str,
            precio_percibido=item.precio,
            vigente=vigente,
            disponible=True,
        ),
        cambios,
    )


def _evaluar_personalizacion(
    item: ItemAValidar,
    ingredientes: list[ProductoIngrediente],
) -> CambioRead | None:
    """Evalúa la personalización del ítem contra los ingredientes removibles del producto.

    Verifica en memoria (sin consultas adicionales) que cada ingrediente_id en
    item.personalizacion:
      1. Existe en la lista de ingredientes del producto.
      2. Es es_removible=True.

    Retorna el primer cambio inválido encontrado, o None si todo es válido.

    Args:
        item: Ítem del carrito con la lista de personalización.
        ingredientes: Lista de ProductoIngrediente cargada en batch.

    Returns:
        CambioRead con tipo PERSONALIZACION_INVALIDA y el primer ingrediente inválido,
        o None si la personalización es completamente válida.
    """
    # Construir mapa: ingrediente_id_str → es_removible
    removibles: dict[str, bool] = {
        str(pi.ingrediente_id): bool(pi.es_removible)  # type: ignore[attr-defined]
        for pi in ingredientes
    }

    for ing_id in item.personalizacion:
        if ing_id not in removibles:
            # No existe o no pertenece al producto
            return CambioRead(
                producto_id=item.producto_id,
                tipo="PERSONALIZACION_INVALIDA",
                detalle={
                    "ingrediente_id": ing_id,
                    "razon": "no_pertenece_al_producto",
                },
            )
        if not removibles[ing_id]:
            return CambioRead(
                producto_id=item.producto_id,
                tipo="PERSONALIZACION_INVALIDA",
                detalle={
                    "ingrediente_id": ing_id,
                    "razon": "no_es_removible",
                },
            )

    return None
