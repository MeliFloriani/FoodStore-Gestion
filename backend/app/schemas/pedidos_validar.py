"""
Schemas Pydantic para validación pre-checkout.

Modela el request y response del endpoint POST /api/v1/pedidos/validar.
Este endpoint es stateless e idempotente — no crea pedidos ni modifica stock.

Tipos de cambio detectado (CambioRead.tipo):
  - PRODUCTO_NO_VIGENTE: producto eliminado (deleted_at no nulo) o no encontrado.
  - PRODUCTO_NO_DISPONIBLE: producto existe pero disponible=False.
  - STOCK_INSUFICIENTE: stock_cantidad < cantidad solicitada.
  - PRECIO_CAMBIADO: precio percibido difiere del precio_base actual (tolerancia cero).
  - PERSONALIZACION_INVALIDA: ingrediente no removible, inexistente o no pertenece al producto.

Decisión D-03: precio en wire format como string decimal (no float) para evitar pérdida
de precisión en JSON. Comparación Decimal con quantize(Decimal('0.01')).

Decisión D-05: response siempre 200 OK con ok: bool. Los cambios de negocio nunca
se modelan como 4xx — eso es para errores de protocolo (auth, schema).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ItemAValidar(BaseModel):
    """Un ítem del carrito del cliente a validar contra el estado actual de BD.

    Attributes:
        producto_id: UUID string del producto (as string — sin conversión a UUID).
        cantidad: Cantidad solicitada (mínimo 1).
        personalizacion: Lista de UUIDs de ingredientes removidos/seleccionados.
        precio: Precio percibido por el cliente en formato string decimal (ej: "250.00").
    """

    producto_id: str
    cantidad: int = Field(ge=1)
    personalizacion: list[str] = Field(default_factory=list)
    precio: str

    @field_validator("precio")
    @classmethod
    def precio_debe_ser_decimal(cls, v: str) -> str:
        """Valida que precio sea un string decimal parseable.

        Raises:
            ValueError: Si el valor no puede parsearse como Decimal.
        """
        try:
            parsed = Decimal(v)
            if parsed < 0:
                raise ValueError("El precio no puede ser negativo")
        except InvalidOperation:
            raise ValueError(
                f"El precio '{v}' no es un valor decimal válido (ej: '250.00')"
            )
        return v


class ValidarPreCheckoutRequest(BaseModel):
    """Request body para validar el carrito pre-checkout.

    Attributes:
        items: Lista de ítems del carrito. Mínimo 1 ítem requerido.
    """

    items: list[ItemAValidar] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ItemValidadoRead(BaseModel):
    """Resultado de validación para un ítem del carrito.

    Attributes:
        producto_id: UUID del producto validado.
        cantidad_solicitada: Cantidad que el cliente quiere comprar.
        stock_disponible: Stock actual en BD. None si el producto no existe o fue eliminado.
        precio_actual: precio_base actual como string decimal. None si producto no vigente.
        precio_percibido: Precio que el cliente tiene en su carrito (del request).
        vigente: True si el producto existe y deleted_at IS NULL.
        disponible: True si el producto está habilitado para la venta. None si no vigente.
    """

    producto_id: str
    cantidad_solicitada: int
    stock_disponible: int | None
    precio_actual: str | None
    precio_percibido: str
    vigente: bool
    disponible: bool | None


class CambioRead(BaseModel):
    """Un cambio detectado entre el carrito del cliente y el estado actual de BD.

    Attributes:
        producto_id: UUID del producto afectado.
        tipo: Tipo de cambio detectado (bloqueante excepto PRECIO_CAMBIADO).
        detalle: Datos adicionales según el tipo de cambio.
    """

    producto_id: str
    tipo: Literal[
        "PRODUCTO_NO_VIGENTE",
        "PRODUCTO_NO_DISPONIBLE",
        "STOCK_INSUFICIENTE",
        "PRECIO_CAMBIADO",
        "PERSONALIZACION_INVALIDA",
    ]
    detalle: dict  # type: ignore[type-arg]


class ValidarPreCheckoutResponse(BaseModel):
    """Response del endpoint POST /api/v1/pedidos/validar.

    Siempre devuelve HTTP 200 — los cambios de negocio no son errores HTTP.

    Attributes:
        ok: True si no hay cambios bloqueantes. PRECIO_CAMBIADO no es bloqueante.
            False si hay al menos un PRODUCTO_NO_VIGENTE, PRODUCTO_NO_DISPONIBLE,
            STOCK_INSUFICIENTE o PERSONALIZACION_INVALIDA.
        items: Un ItemValidadoRead por cada ítem del request (misma longitud).
        cambios: Lista de cambios detectados. Vacía si ok=True sin PRECIO_CAMBIADO.
    """

    ok: bool
    items: list[ItemValidadoRead]
    cambios: list[CambioRead]
