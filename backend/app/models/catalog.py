"""
Dominio Catálogo — modelos SQLModel.

Entidades: Categoria, FormaPago, Producto, Ingrediente, ProductoCategoria, ProductoIngrediente.

Design decisions:
- D-17: Todos los modelos del dominio catálogo en un único archivo.
- D-18: PK UUID v4 universal. codigo en FormaPago = PK semántica con unique=True.
- D-22: Categoria.parent_id — FK self-referencial nullable, ON DELETE SET NULL.
- D-28: FormaPago.codigo es la columna referenciada por Pedido.forma_pago_codigo (FK semántica).
- D-30: Relationships con back_populates, foreign_keys, lazy explícito. No lazy="select".
- D-31: deleted_at dormant en tablas pivot (ProductoCategoria, ProductoIngrediente).

NOTE: No 'from __future__ import annotations' — SQLModel 0.0.38 resuelve
los tipos de relationship en tiempo de ejecución. Generic types como List/Optional
en anotaciones de relaciones se resuelven como strings literales con __future__
y no pueden ser resueltos por SQLAlchemy.
"""

import uuid
from typing import List, Optional

from sqlalchemy import DECIMAL, CheckConstraint, Column, ForeignKey, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import Base  # noqa: F401 — also imports app.db.base (naming_convention)


# ─────────────────────────────────────────────────────────────────────────────
# Categoria
# ─────────────────────────────────────────────────────────────────────────────


class Categoria(Base, table=True):
    """Categoría de producto con soporte de árbol (self-ref).

    D-22: parent_id → categoria.id con ON DELETE SET NULL.
    Árbol recursivo (CTE) → Change 05 (catalog domain).
    """

    __tablename__ = "categoria"

    nombre: str = Field(max_length=100, nullable=False)
    descripcion: Optional[str] = Field(default=None, nullable=True)
    # FK self-referencial nullable — D-22
    parent_id: Optional[uuid.UUID] = Field(
        sa_column=Column(
            "parent_id",
            ForeignKey("categoria.id", ondelete="SET NULL"),
            nullable=True,
        )
    )

    # Relationships (D-30: self-ref requiere remote_side explícito)
    parent: Optional["Categoria"] = Relationship(
        back_populates="subcategorias",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "Categoria.parent_id",
            "remote_side": "Categoria.id",
        },
    )
    subcategorias: List["Categoria"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "Categoria.parent_id",
        },
    )
    producto_categorias: List["ProductoCategoria"] = Relationship(
        back_populates="categoria",
        sa_relationship_kwargs={"lazy": "noload"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# FormaPago
# ─────────────────────────────────────────────────────────────────────────────


class FormaPago(Base, table=True):
    """Forma de pago disponible en el sistema.

    D-18/D-28: codigo VARCHAR(20) unique — es la FK semántica referenciada por Pedido.
    """

    __tablename__ = "forma_pago"

    codigo: str = Field(max_length=20, nullable=False, unique=True)
    nombre: str = Field(max_length=100, nullable=False)
    habilitado: bool = Field(default=True, nullable=False)

    # NOTE: FormaPago.pedidos (inversa de Pedido.forma_pago) no se declara aquí
    # para evitar circular import con order.py. La relación Pedido→FormaPago es
    # unidireccional desde el lado de Pedido (FK dueña de la relación).
    # D-30: excepción documentada — circular import cross-domain impide bidireccionalidad.


# ─────────────────────────────────────────────────────────────────────────────
# Producto
# ─────────────────────────────────────────────────────────────────────────────


class Producto(Base, table=True):
    """Producto del catálogo con precio, stock y disponibilidad.

    CHECK constraints para precio y stock garantizan invariantes de negocio a nivel DB.
    """

    __tablename__ = "producto"
    __table_args__ = (
        # naming_convention expands to ck_producto_precio_base and ck_producto_stock_cantidad
        CheckConstraint("precio_base >= 0", name="precio_base"),
        CheckConstraint("stock_cantidad >= 0", name="stock_cantidad"),
    )

    nombre: str = Field(max_length=200, nullable=False)
    precio_base: float = Field(
        sa_column=Column("precio_base", DECIMAL(10, 2), nullable=False)
    )
    stock_cantidad: int = Field(default=0, nullable=False)
    disponible: bool = Field(default=True, nullable=False)
    descripcion: Optional[str] = Field(default=None, nullable=True)
    imagen_url: Optional[str] = Field(default=None, max_length=500, nullable=True)

    # Relationships (D-30)
    producto_categorias: List["ProductoCategoria"] = Relationship(
        back_populates="producto",
        sa_relationship_kwargs={"lazy": "noload"},
    )
    producto_ingredientes: List["ProductoIngrediente"] = Relationship(
        back_populates="producto",
        sa_relationship_kwargs={"lazy": "noload"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ingrediente
# ─────────────────────────────────────────────────────────────────────────────


class Ingrediente(Base, table=True):
    """Ingrediente con flag de alérgeno."""

    __tablename__ = "ingrediente"

    nombre: str = Field(max_length=100, nullable=False, unique=True)
    es_alergeno: bool = Field(default=False, nullable=False)

    # Relationships
    producto_ingredientes: List["ProductoIngrediente"] = Relationship(
        back_populates="ingrediente",
        sa_relationship_kwargs={"lazy": "noload"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ProductoCategoria  (pivot con Base completo — D-31)
# ─────────────────────────────────────────────────────────────────────────────


class ProductoCategoria(Base, table=True):
    """Relación muchos-a-muchos entre Producto y Categoria.

    D-31: deleted_at y updated_at dormant — la eliminación es hard delete.
    """

    __tablename__ = "producto_categoria"
    __table_args__ = (
        UniqueConstraint(
            "producto_id", "categoria_id",
            name="uq_producto_categoria_producto_id_categoria_id",
        ),
    )

    producto_id: uuid.UUID = Field(
        sa_column=Column(
            "producto_id",
            ForeignKey("producto.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    categoria_id: uuid.UUID = Field(
        sa_column=Column(
            "categoria_id",
            ForeignKey("categoria.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    es_principal: bool = Field(default=False, nullable=False)

    # Relationships
    producto: Optional["Producto"] = Relationship(
        back_populates="producto_categorias",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    categoria: Optional["Categoria"] = Relationship(
        back_populates="producto_categorias",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ProductoIngrediente  (pivot con Base completo — D-31)
# ─────────────────────────────────────────────────────────────────────────────


class ProductoIngrediente(Base, table=True):
    """Relación muchos-a-muchos entre Producto e Ingrediente.

    es_removible no tiene default — debe ser siempre explícito (spec task 4.6).
    D-31: deleted_at y updated_at dormant.
    """

    __tablename__ = "producto_ingrediente"
    __table_args__ = (
        UniqueConstraint(
            "producto_id", "ingrediente_id",
            name="uq_producto_ingrediente_producto_id_ingrediente_id",
        ),
    )

    producto_id: uuid.UUID = Field(
        sa_column=Column(
            "producto_id",
            ForeignKey("producto.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    ingrediente_id: uuid.UUID = Field(
        sa_column=Column(
            "ingrediente_id",
            ForeignKey("ingrediente.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    # Sin default — siempre debe ser explícito al insertar (task 4.6)
    es_removible: bool = Field(nullable=False)

    # Relationships
    producto: Optional["Producto"] = Relationship(
        back_populates="producto_ingredientes",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    ingrediente: Optional["Ingrediente"] = Relationship(
        back_populates="producto_ingredientes",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


