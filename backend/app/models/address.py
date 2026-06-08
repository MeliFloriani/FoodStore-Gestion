"""
Dominio Ventas — Dirección de Entrega.

Design decisions:
- D-17: DireccionEntrega en archivo propio para separar la entidad de dominio.
- Campo es_principal (NO es_predeterminada) — spec task 5.1, backend-data-model spec.
- D-30: Relationships con back_populates y lazy explícito donde aplica.
         Las relaciones inversas a Pedido no se declaran aquí para evitar circular
         import con order.py (excepción documentada de D-30).

Change 14 (delivery-addresses-management) corrections:
- FK uses ondelete="RESTRICT" (not CASCADE) — spec backend-migrations/spec.md
- ciudad and provincia are Optional[str] nullable (spec defines as NULL)
- codigo_postal max_length=10 (spec defines VARCHAR(10))
- referencia field added as Optional[str]

NOTE: No 'from __future__ import annotations' — SQLModel 0.0.38 resuelve
los tipos de relationship en tiempo de ejecución.
"""

import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey
from sqlmodel import Field

from app.models.base import Base  # noqa: F401 — also imports app.db.base (naming_convention)


class DireccionEntrega(Base, table=True):
    """Dirección de entrega asociada a un usuario.

    es_principal: campo correcto según spec (NO es_predeterminada).
    ON DELETE RESTRICT: la FK usa RESTRICT — no se puede eliminar un usuario
    con direcciones activas sin eliminar primero las direcciones.
    """

    __tablename__ = "direccion_entrega"

    usuario_id: uuid.UUID = Field(
        sa_column=Column(
            "usuario_id",
            ForeignKey("usuario.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    alias: Optional[str] = Field(default=None, max_length=50, nullable=True)
    linea1: str = Field(nullable=False)
    linea2: Optional[str] = Field(default=None, nullable=True)
    ciudad: Optional[str] = Field(default=None, max_length=100, nullable=True)
    provincia: Optional[str] = Field(default=None, max_length=100, nullable=True)
    codigo_postal: Optional[str] = Field(default=None, max_length=10, nullable=True)
    referencia: Optional[str] = Field(default=None, nullable=True)
    es_principal: bool = Field(default=False, nullable=False)

    # NOTE: DireccionEntrega.pedidos (inversa de Pedido.direccion) no se declara
    # aquí para evitar circular import con order.py.
    # D-30: excepción documentada — relación unidireccional desde Pedido.
