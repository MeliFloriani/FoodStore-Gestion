"""
Schemas Pydantic para el endpoint POST /api/v1/pedidos (Change 17).

Modela el request y response de creación transaccional de pedidos.

Design decisions:
- D-09: Todos los campos monetarios (precio_snapshot, subtotal, costo_envio, total)
  se serializan como string decimal con 2 decimales, siguiendo el patrón de Change 11.
- D-09 / Nota R-01: exclusiones son list[UUID] — Ingrediente.id es UUID (no int).
  El cartStore.personalizacion almacena UUIDs como string[]; el frontend los pasa
  directamente sin conversión (NO parseInt — eso convertiría UUIDs a NaN).
- D-04: direccion_id = None → retiro en local (válido, costo_envio = 0.00).
- D-11: subtotal, costo_envio, total son calculados server-side. El frontend NO los envía.
- D-12: Naming — este módulo es pedidos.py (no pedidos_validar.py, que es de Change 16).

El campo HistorialEstadoPedidoRead.estado_hacia mapea a estado_hasta en el modelo ORM
(el campo DB se llama estado_hasta per Change 03; el response lo expone como estado_hacia
para alinearse con la terminología del diseño de negocio en la spec).

Change 20 additions (orders-visualization):
- PedidoListItem: compact schema for paginated listing (D-12).
- UsuarioBasic: nested user data for PedidoDetail (D-03).
- DireccionBasic: nested address data for PedidoDetail, best-effort (D-04 / OQ-01).
- PedidoDetail: full detail schema with items, historial, pago and user (D-12).

Aliases:
  HistorialRead = HistorialEstadoPedidoRead (used as type in PedidoDetail per spec).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ItemPedidoCreate(BaseModel):
    """Un ítem del carrito a incluir en el pedido.

    Attributes:
        producto_id: UUID del producto a pedir.
        cantidad: Cantidad solicitada (mínimo 1).
        exclusiones: UUIDs de ingredientes a excluir. Vacío si ninguno.
                     Estos son ingredientes con es_removible=True del producto.
    """

    producto_id: uuid.UUID
    cantidad: int = Field(ge=1)
    exclusiones: list[uuid.UUID] = Field(default_factory=list)


class PedidoEstadoUpdate(BaseModel):
    """Request body para actualizar el estado de un pedido.

    Change 18: usado por PATCH /{id}/estado (staff) y DELETE /{id} (cliente).

    Attributes:
        nuevo_estado: Código del nuevo estado destino (ej: "EN_PREP", "CANCELADO").
        motivo: Motivo obligatorio para transiciones a CANCELADO (RN-05).
    """

    nuevo_estado: str
    motivo: str | None = None


class PedidoCreate(BaseModel):
    """Request body para crear un pedido.

    Attributes:
        items: Lista de ítems del carrito. Mínimo 1 requerido.
        forma_pago_codigo: Código semántico del catálogo FormaPago
                           (ej: "MERCADOPAGO", "EFECTIVO", "TRANSFERENCIA").
        direccion_id: UUID de la dirección de entrega. None = retiro en local (válido).
        notas: Instrucciones adicionales opcionales (texto libre).
    """

    items: list[ItemPedidoCreate] = Field(min_length=1)
    forma_pago_codigo: str
    direccion_id: uuid.UUID | None = None
    notas: str | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DetallePedidoRead(BaseModel):
    """Línea de detalle del pedido con snapshots inmutables.

    Los campos nombre_snapshot y precio_snapshot son write-once al momento de
    creación — no se actualizan aunque el producto cambie (D-03).

    Attributes:
        id: UUID del detalle.
        producto_id: UUID del producto pedido.
        nombre_snapshot: Nombre del producto al momento de crear el pedido.
        precio_snapshot: Precio unitario del producto al momento de creación (string decimal).
        cantidad: Cantidad pedida.
        personalizacion: UUIDs de ingredientes excluidos (puede ser []).
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    producto_id: uuid.UUID
    nombre_snapshot: str
    precio_snapshot: Decimal
    cantidad: int
    personalizacion: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("personalizacion", mode="before")
    @classmethod
    def _normalize_personalizacion(cls, value: object) -> object:
        """Coerce DB NULL → [] for legacy rows where ARRAY column is NULL.

        The ORM column `DetallePedido.personalizacion` is nullable; pre-fix rows
        and rows created without exclusions may have NULL. The public API contract
        always returns a list, never null. `default_factory` does not cover this
        case because the attribute *exists* on the ORM object (just is None) —
        the default only kicks in when the field is missing entirely.
        """
        if value is None:
            return []
        return value

    @field_serializer("precio_snapshot")
    def serialize_precio_snapshot(self, value: Decimal) -> str:
        """Serializa precio_snapshot como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"


class HistorialEstadoPedidoRead(BaseModel):
    """Registro de transición de estado del pedido.

    El primer registro siempre tiene estado_desde=None y estado_hacia="PENDIENTE"
    (RN-02 del Integrador v5.0).

    Note: El campo ORM se llama 'estado_hasta' pero se expone como 'estado_hacia'
    en el response para alinearse con la terminología del diseño de negocio.

    Change 18: Agrega actor_user_id (alias de ORM.cambiado_por_id).
    NULL = creado por el sistema (Change 19 webhook) o transición inicial (Change 17).
    Non-NULL = transición manual por usuario autenticado (Change 18).

    Attributes:
        id: UUID del registro de historial.
        estado_desde: Estado anterior (None para la transición inicial).
        estado_hacia: Estado destino (mapeado desde ORM.estado_hasta).
        motivo: Descripción del motivo del cambio (opcional).
        actor_user_id: UUID del usuario que realizó la transición (mapeado desde ORM.cambiado_por_id).
                       None para transiciones del sistema (Change 19) o la inicial (Change 17).
        created_at: Timestamp de la transición.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    estado_desde: str | None = None
    estado_hacia: str = Field(validation_alias="estado_hasta")  # ORM column: estado_hasta
    motivo: str | None = None
    actor_user_id: uuid.UUID | None = Field(None, validation_alias="cambiado_por_id")
    created_at: datetime


class PedidoRead(BaseModel):
    """Response de creación de pedido.

    Incluye los detalles de línea con snapshots y el primer registro del historial
    para que el frontend pueda mostrar confirmación sin un GET adicional (OQ-02).

    Attributes:
        id: UUID del pedido.
        usuario_id: UUID del usuario que realizó el pedido (del JWT).
        estado_codigo: Estado actual — siempre "PENDIENTE" en creación.
        forma_pago_codigo: Código de la forma de pago elegida.
        direccion_id: UUID de la dirección (None si retiro en local).
        subtotal: Suma de precio_snapshot × cantidad para todos los ítems (string decimal).
        costo_envio: Costo de envío calculado server-side (string decimal).
        total: subtotal + costo_envio (string decimal).
        notas: Instrucciones adicionales (puede ser None).
        items: Lista de detalles de línea con snapshots inmutables.
        historial: Lista de registros de historial de estado (incluye el inicial).
        created_at: Timestamp de creación del pedido.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    usuario_id: uuid.UUID
    estado_codigo: str
    forma_pago_codigo: str
    direccion_id: uuid.UUID | None
    subtotal: Decimal
    costo_envio: Decimal
    total: Decimal
    notas: str | None
    items: list[DetallePedidoRead]
    historial: list[HistorialEstadoPedidoRead]
    created_at: datetime

    @field_serializer("subtotal")
    def serialize_subtotal(self, value: Decimal) -> str:
        """Serializa subtotal como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"

    @field_serializer("costo_envio")
    def serialize_costo_envio(self, value: Decimal) -> str:
        """Serializa costo_envio como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        """Serializa total como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Change 20 — orders-visualization: PedidoListItem, UsuarioBasic,
#             DireccionBasic, PedidoDetail  (tasks 1.1–1.5)
# ---------------------------------------------------------------------------


class PedidoListItem(BaseModel):
    """Schema compacto para el listado paginado de pedidos.

    Change 20 (D-12): usado por GET /api/v1/pedidos.
    usuario_nombre y usuario_email son null para respuestas CLIENT (D-15).
    total serializado como string decimal (D-09).

    Attributes:
        id: UUID del pedido.
        estado_codigo: Estado actual del pedido.
        total: Total del pedido serializado como string decimal.
        forma_pago_codigo: Código de la forma de pago.
        items_count: Cantidad de líneas DetallePedido en el pedido.
        created_at: Timestamp de creación del pedido.
        usuario_nombre: Nombre completo del usuario (null para respuestas CLIENT).
        usuario_email: Email del usuario (null para respuestas CLIENT).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado_codigo: str
    total: Decimal
    forma_pago_codigo: str
    items_count: int
    created_at: datetime
    usuario_nombre: str | None = None
    usuario_email: str | None = None

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        """Serializa total como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"


class UsuarioBasic(BaseModel):
    """Datos básicos del usuario para incluir en PedidoDetail.

    Change 20 (D-03): expuesto tanto a PEDIDOS/ADMIN (gestión) como
    al propio CLIENT (es su propio dato).

    Attributes:
        id: UUID del usuario.
        nombre: Nombre del usuario.
        apellido: Apellido del usuario.
        email: Email del usuario.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    apellido: str
    email: str


class DireccionBasic(BaseModel):
    """Datos básicos de la dirección de entrega para incluir en PedidoDetail.

    Change 20 (D-04 / OQ-01): best-effort — si la dirección fue eliminada
    después del pedido, este campo será null aunque direccion_id sea no-null.

    Attributes:
        alias: Alias descriptivo de la dirección (nullable).
        linea1: Primera línea de la dirección (calle y número).
        linea2: Segunda línea (piso, depto, etc.) — nullable.
        ciudad: Ciudad / localidad — nullable.
        provincia: Provincia — nullable.
        codigo_postal: Código postal — nullable.
        referencia: Referencia adicional para el repartidor — nullable.
    """

    model_config = ConfigDict(from_attributes=True)

    alias: str | None = None
    linea1: str
    linea2: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    codigo_postal: str | None = None
    referencia: str | None = None


class PedidoDetail(BaseModel):
    """Schema de detalle completo del pedido.

    Change 20 (D-12): usado por GET /api/v1/pedidos/{id}.
    Incluye items con snapshots, historial, usuario y pago más reciente.
    subtotal/costo_envio/total serializados como string decimal (D-09).
    No incluye campo `descuento` — no existe en el modelo Pedido (D-14).

    Attributes:
        id: UUID del pedido.
        usuario_id: UUID del usuario propietario del pedido.
        usuario: Datos básicos del usuario (UsuarioBasic | None).
        estado_codigo: Estado actual del pedido.
        forma_pago_codigo: Código de la forma de pago.
        subtotal: Subtotal serializado como string decimal.
        costo_envio: Costo de envío serializado como string decimal.
        total: Total serializado como string decimal.
        notas: Instrucciones adicionales (puede ser None).
        direccion_id: UUID de la dirección de entrega (puede ser None).
        direccion: Datos básicos de la dirección (best-effort, puede ser None).
        items: Lista de detalles de línea con snapshots inmutables.
        historial: Lista de transiciones de estado ordenadas por created_at ASC.
        pago: Pago más reciente asociado al pedido (puede ser None).
        created_at: Timestamp de creación del pedido.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    usuario: UsuarioBasic | None = None
    estado_codigo: str
    forma_pago_codigo: str
    subtotal: Decimal
    costo_envio: Decimal
    total: Decimal
    notas: str | None = None
    direccion_id: uuid.UUID | None = None
    direccion: DireccionBasic | None = None
    items: list[DetallePedidoRead]
    historial: list[HistorialEstadoPedidoRead]
    pago: Optional[object] = None  # PagoResponse | None — resolved via model_rebuild below
    created_at: datetime

    @field_serializer("subtotal")
    def serialize_subtotal(self, value: Decimal) -> str:
        """Serializa subtotal como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"

    @field_serializer("costo_envio")
    def serialize_costo_envio(self, value: Decimal) -> str:
        """Serializa costo_envio como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        """Serializa total como string con 2 decimales (D-09 wire format)."""
        return f"{value:.2f}"


# Alias for spec compatibility (HistorialRead used in specs)
HistorialRead = HistorialEstadoPedidoRead

# Resolve forward reference for PedidoDetail.pago → PagoResponse
# This must run after PagoResponse is importable (no circular dependency — pagos/schemas.py
# does not import from schemas/pedidos.py).
def _rebuild_pedido_detail() -> None:
    """Resolve PagoResponse forward reference in PedidoDetail.pago field."""
    from app.pagos.schemas import PagoResponse  # noqa: PLC0415 — deferred import avoids top-level

    # Re-declare pago field with the real type
    PedidoDetail.model_fields["pago"].annotation = Optional[PagoResponse]  # type: ignore[assignment]
    PedidoDetail.model_rebuild(force=True)


# Attempt rebuild immediately — will succeed once pagos.schemas is importable
try:
    _rebuild_pedido_detail()
except Exception:
    # If pagos.schemas is not yet imported (rare edge case during test discovery),
    # the field remains as Optional[object] until first use triggers a rebuild.
    pass
