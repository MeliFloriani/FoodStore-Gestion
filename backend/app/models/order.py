"""
Dominio Ventas y Pagos — modelos SQLModel.

Entidades: EstadoPedido, Pedido, DetallePedido, HistorialEstadoPedido, Pago.

Design decisions:
- D-17: Todos los modelos del dominio ventas en un único archivo.
- D-18: PK UUID v4. EstadoPedido.codigo = PK semántica (FK destino de D-28).
- D-19: DetallePedido.personalizacion = Column(ARRAY(Integer), nullable=True) explícito.
         SQLModel no genera ARRAY automáticamente desde list[int].
- D-21: Pedido.direccion_id nullable, ON DELETE SET NULL.
- D-23/D-31: HistorialEstadoPedido hereda Base completo; updated_at dormant.
- D-28: Pedido.forma_pago_codigo y estado_codigo son FK semánticas a codigo (no a id).
         HistorialEstadoPedido.estado_desde/hasta → estado_pedido.codigo.
- D-30: Todas las Relationship con back_populates, foreign_keys, lazy explícito.
         lazy="select" prohibido (MissingGreenlet en sesiones async).
- R-A-04: ARRAY(Integer) requiere import explícito de sqlalchemy.

NOTE: No 'from __future__ import annotations' — SQLModel 0.0.38 resuelve
los tipos de relationship en tiempo de ejecución.
"""

import uuid
from typing import List, Optional

from sqlalchemy import ARRAY, BIGINT, DECIMAL, CheckConstraint, Column, ForeignKey, Integer
from sqlmodel import Field, Relationship

from app.models.base import Base  # noqa: F401 — also imports app.db.base (naming_convention)


# ─────────────────────────────────────────────────────────────────────────────
# EstadoPedido
# ─────────────────────────────────────────────────────────────────────────────


class EstadoPedido(Base, table=True):
    """Estado del pedido en la FSM.

    D-18/D-28: codigo VARCHAR(20) unique — FK semántica referenciada por Pedido
    y HistorialEstadoPedido.
    6 estados: PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO (terminal), CANCELADO (terminal).
    """

    __tablename__ = "estado_pedido"

    codigo: str = Field(max_length=20, nullable=False, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=200, nullable=True)
    es_terminal: bool = Field(default=False, nullable=False)
    orden: Optional[int] = Field(default=None, nullable=True)

    # Relationships (D-30: foreign_keys explícitos — múltiples FKs a estado_pedido desde historial)
    pedidos: List["Pedido"] = Relationship(
        back_populates="estado",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "Pedido.estado_codigo",
        },
    )
    historial_desde: List["HistorialEstadoPedido"] = Relationship(
        back_populates="estado_desde_rel",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.estado_desde",
        },
    )
    historial_hasta: List["HistorialEstadoPedido"] = Relationship(
        back_populates="estado_hasta_rel",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.estado_hasta",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pedido
# ─────────────────────────────────────────────────────────────────────────────


class Pedido(Base, table=True):
    """Pedido de un usuario con total, costo de envío y forma de pago.

    D-21: direccion_id nullable (retiro en local = None), ON DELETE SET NULL.
    D-28: estado_codigo y forma_pago_codigo son FK a columnas codigo (no a id).
    """

    __tablename__ = "pedido"
    __table_args__ = (
        # naming_convention expands to ck_pedido_total and ck_pedido_costo_envio
        CheckConstraint("total >= 0", name="total"),
        CheckConstraint("costo_envio >= 0", name="costo_envio"),
    )

    usuario_id: uuid.UUID = Field(
        sa_column=Column(
            "usuario_id",
            ForeignKey("usuario.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,  # Hot path: consultas por usuario
        )
    )
    # FK semántica → estado_pedido.codigo (D-28)
    estado_codigo: str = Field(
        sa_column=Column(
            "estado_codigo",
            ForeignKey("estado_pedido.codigo"),
            nullable=False,
            index=True,  # Hot path panel admin: filtro por estado (spec task 5.3)
        )
    )
    # FK semántica → forma_pago.codigo (D-28)
    forma_pago_codigo: str = Field(
        sa_column=Column(
            "forma_pago_codigo",
            ForeignKey("forma_pago.codigo"),
            nullable=False,
        )
    )
    # D-21: nullable, ON DELETE SET NULL (retiro en local = NULL)
    direccion_id: Optional[uuid.UUID] = Field(
        sa_column=Column(
            "direccion_id",
            ForeignKey("direccion_entrega.id", ondelete="SET NULL"),
            nullable=True,
        )
    )
    total: float = Field(
        sa_column=Column("total", DECIMAL(10, 2), nullable=False)
    )
    costo_envio: float = Field(
        sa_column=Column("costo_envio", DECIMAL(10, 2), nullable=False, server_default="50.00")
    )
    notas: Optional[str] = Field(default=None, nullable=True)

    # Relationships (D-30: foreign_keys explícitos)
    estado: Optional["EstadoPedido"] = Relationship(
        back_populates="pedidos",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "Pedido.estado_codigo",
        },
    )
    # forma_pago: unidireccional desde Pedido.
    # FormaPago.pedidos no se declara para evitar circular import con catalog.py.
    # D-30: excepción documentada — cross-domain unidireccional.
    forma_pago: Optional["FormaPago"] = Relationship(  # type: ignore[name-defined]
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "Pedido.forma_pago_codigo",
        },
    )
    # direccion: unidireccional desde Pedido.
    # DireccionEntrega.pedidos no se declara para evitar circular import con address.py.
    # D-30: excepción documentada — cross-domain unidireccional.
    direccion: Optional["DireccionEntrega"] = Relationship(  # type: ignore[name-defined]
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "Pedido.direccion_id",
        },
    )
    detalles: List["DetallePedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "DetallePedido.pedido_id",
        },
    )
    historial: List["HistorialEstadoPedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.pedido_id",
        },
    )
    pagos: List["Pago"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "Pago.pedido_id",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# DetallePedido
# ─────────────────────────────────────────────────────────────────────────────


class DetallePedido(Base, table=True):
    """Línea de detalle de un pedido con snapshot de nombre y precio.

    D-19: personalizacion = Column(ARRAY(Integer), nullable=True).
          SQLModel no genera ARRAY desde list[int] solo — requiere Column explícito.
          Los enteros son IDs de ingredientes removidos (snapshot, no FK real — Snapshot Pattern).
    """

    __tablename__ = "detalle_pedido"
    __table_args__ = (
        # naming_convention expands to ck_detalle_pedido_precio_snapshot and ck_detalle_pedido_cantidad
        CheckConstraint("precio_snapshot >= 0", name="precio_snapshot"),
        CheckConstraint("cantidad >= 1", name="cantidad"),
    )

    pedido_id: uuid.UUID = Field(
        sa_column=Column(
            "pedido_id",
            ForeignKey("pedido.id", ondelete="CASCADE"),
            nullable=False,
            index=True,  # Hot path: consultas de detalles por pedido
        )
    )
    producto_id: uuid.UUID = Field(
        sa_column=Column(
            "producto_id",
            ForeignKey("producto.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    nombre_snapshot: str = Field(max_length=200, nullable=False)
    precio_snapshot: float = Field(
        sa_column=Column("precio_snapshot", DECIMAL(10, 2), nullable=False)
    )
    cantidad: int = Field(nullable=False)
    # D-19: ARRAY(Integer) explícito — snapshot de IDs de ingredientes removidos
    personalizacion: Optional[List[int]] = Field(
        sa_column=Column("personalizacion", ARRAY(Integer), nullable=True)
    )

    # Relationships (D-30)
    pedido: Optional["Pedido"] = Relationship(
        back_populates="detalles",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "DetallePedido.pedido_id",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# HistorialEstadoPedido  (append-only — D-23/D-31)
# ─────────────────────────────────────────────────────────────────────────────


# APPEND-ONLY: never UPDATE or DELETE (RN-03)
class HistorialEstadoPedido(Base, table=True):
    """Registro de transiciones de estado de un pedido.

    D-23/D-31: hereda de Base completo; updated_at dormant (entidad append-only).
    D-28: estado_desde/hasta son FK a estado_pedido.codigo (no a id).
    D-30: dos FKs hacia estado_pedido → foreign_keys + primaryjoin explícitos en cada Relationship.
    RN-02: estado_desde puede ser NULL (transición inicial: el pedido nace en PENDIENTE).
    RN-03: esta tabla es APPEND-ONLY — nunca se hace UPDATE ni DELETE sobre sus filas.
           La guarda dura a nivel DB (trigger) se implementa en Change 18.
    """

    __tablename__ = "historial_estado_pedido"

    pedido_id: uuid.UUID = Field(
        sa_column=Column(
            "pedido_id",
            ForeignKey("pedido.id", ondelete="CASCADE"),
            nullable=False,
            index=True,  # Hot path: consultas de historial por pedido
        )
    )
    # NULL = transición inicial (RN-02)
    estado_desde: Optional[str] = Field(
        sa_column=Column(
            "estado_desde",
            ForeignKey("estado_pedido.codigo"),
            nullable=True,
        )
    )
    estado_hasta: str = Field(
        sa_column=Column(
            "estado_hasta",
            ForeignKey("estado_pedido.codigo"),
            nullable=False,
        )
    )
    cambiado_por_id: Optional[uuid.UUID] = Field(
        sa_column=Column(
            "cambiado_por_id",
            ForeignKey("usuario.id"),
            nullable=True,
        )
    )
    motivo: Optional[str] = Field(default=None, nullable=True)

    # Relationships (D-30 — dos FKs a estado_pedido → foreign_keys + primaryjoin obligatorios)
    pedido: Optional["Pedido"] = Relationship(
        back_populates="historial",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.pedido_id",
        },
    )
    estado_desde_rel: Optional["EstadoPedido"] = Relationship(
        back_populates="historial_desde",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.estado_desde",
            "primaryjoin": "HistorialEstadoPedido.estado_desde == EstadoPedido.codigo",
        },
    )
    estado_hasta_rel: Optional["EstadoPedido"] = Relationship(
        back_populates="historial_hasta",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "HistorialEstadoPedido.estado_hasta",
            "primaryjoin": "HistorialEstadoPedido.estado_hasta == EstadoPedido.codigo",
        },
    )
    # cambiado_por: unidireccional desde HistorialEstadoPedido.
    # Usuario.historial_cambios no se declara para evitar circular import con user.py.
    # D-30: excepción documentada — cross-domain FK sin bidireccionalidad.


# ─────────────────────────────────────────────────────────────────────────────
# Pago
# ─────────────────────────────────────────────────────────────────────────────


class Pago(Base, table=True):
    """Registro de pago MercadoPago con campos de idempotencia."""

    __tablename__ = "pago"

    pedido_id: uuid.UUID = Field(
        sa_column=Column(
            "pedido_id",
            ForeignKey("pedido.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,  # Hot path: consultas de pagos por pedido
        )
    )
    mp_payment_id: Optional[int] = Field(
        sa_column=Column("mp_payment_id", BIGINT, unique=True, nullable=True)
    )
    mp_status: str = Field(max_length=30, nullable=False)
    external_reference: str = Field(max_length=100, nullable=False, unique=True)
    idempotency_key: str = Field(max_length=100, nullable=False, unique=True)
    monto: Optional[float] = Field(
        sa_column=Column("monto", DECIMAL(10, 2), nullable=True)
    )

    # Relationships (D-30)
    pedido: Optional["Pedido"] = Relationship(
        back_populates="pagos",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "Pago.pedido_id",
        },
    )


