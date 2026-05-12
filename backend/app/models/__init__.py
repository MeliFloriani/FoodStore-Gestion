"""
Models package — registro centralizado de todos los modelos de dominio.

D-25: Este módulo importa explícitamente todas las clases de dominio para que
SQLModel.metadata registre las 16 tablas antes de que Alembic las inspeccione.
Sin estas importaciones, autogenerate detecta 0 tablas.

Orden de importación:
  1. base (aplica naming_convention vía app.db.base)
  2. user, catalog, address, order (dominio a dominio)
"""

from app.models.base import Base

# Dominio Identidad y Acceso
from app.models.user import Usuario, Rol, UsuarioRol, RefreshToken

# Dominio Catálogo
from app.models.catalog import (
    Categoria,
    Producto,
    Ingrediente,
    ProductoCategoria,
    ProductoIngrediente,
    FormaPago,
)

# Dominio Ventas — Dirección
from app.models.address import DireccionEntrega

# Dominio Ventas y Pagos
from app.models.order import EstadoPedido, Pedido, DetallePedido, HistorialEstadoPedido, Pago

__all__ = [
    "Base",
    # Identidad
    "Usuario",
    "Rol",
    "UsuarioRol",
    "RefreshToken",
    # Catálogo
    "Categoria",
    "Producto",
    "Ingrediente",
    "ProductoCategoria",
    "ProductoIngrediente",
    "FormaPago",
    # Ventas - Dirección
    "DireccionEntrega",
    # Ventas y Pagos
    "EstadoPedido",
    "Pedido",
    "DetallePedido",
    "HistorialEstadoPedido",
    "Pago",
]
