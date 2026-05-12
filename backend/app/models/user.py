"""
Dominio Identidad y Acceso — modelos SQLModel.

Entidades: Rol, Usuario, UsuarioRol, RefreshToken.

Design decisions:
- D-17: Todos los modelos del dominio en un único archivo por cohesión.
- D-18: PK UUID v4 para todos (heredada de Base). codigo = PK semántica con unique=True.
- D-20: RefreshToken.token_hash es CHAR(64) con SHA-256 digest. Lógica de generación en Change 06.
- D-29: UsuarioRol hereda de Base completo (UUID PK + timestamps + deleted_at dormant).
- D-30: Todas las Relationship con back_populates, foreign_keys, lazy explícito.
         lazy="select" está prohibido (incompatible con sesiones async de SQLAlchemy 2.x).
- D-31: deleted_at en UsuarioRol queda dormant — eliminación es hard delete en Change 09.
"""

# NOTE: No 'from __future__ import annotations' — SQLModel 0.0.38 resuelve
# los tipos de relationship en tiempo de ejecución; las anotaciones de lista
# generadas por __future__ rompen la resolución de nombres en SQLAlchemy 2.x.

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import CHAR, Column, ForeignKey, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import Base  # noqa: F401 — also imports app.db.base (naming_convention)


# ─────────────────────────────────────────────────────────────────────────────
# Rol
# ─────────────────────────────────────────────────────────────────────────────


class Rol(Base, table=True):
    """Rol de acceso en el sistema RBAC (ADMIN, STOCK, PEDIDOS, CLIENT).

    D-18: UUID v4 como PK técnica. codigo = PK semántica única.
    """

    __tablename__ = "rol"

    codigo: str = Field(max_length=20, nullable=False, unique=True)
    nombre: str = Field(max_length=80, nullable=False)

    # Relationships (D-30: lazy explícito, no lazy="select")
    usuario_roles: List["UsuarioRol"] = Relationship(
        back_populates="rol",
        sa_relationship_kwargs={"lazy": "noload"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Usuario
# ─────────────────────────────────────────────────────────────────────────────


class Usuario(Base, table=True):
    """Usuario del sistema — clientes y staff.

    D-18: UUID v4 PK.
    password_hash: CHAR(60) almacena hash bcrypt (Change 06 genera el hash en auth service).
    """

    __tablename__ = "usuario"

    email: str = Field(max_length=254, nullable=False, unique=True)
    password_hash: str = Field(
        sa_column=Column("password_hash", CHAR(60), nullable=False)
    )
    nombre: str = Field(max_length=80, nullable=False)
    apellido: str = Field(max_length=80, nullable=False)

    # Relationships (D-30: lazy explícito, no lazy="select")
    usuario_roles: List["UsuarioRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "UsuarioRol.usuario_id",
        },
    )
    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "RefreshToken.usuario_id",
        },
    )
    asignaciones_hechas: List["UsuarioRol"] = Relationship(
        back_populates="asignado_por",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "UsuarioRol.asignado_por_id",
        },
    )
    # NOTE: Usuario.direcciones, Usuario.pedidos, Usuario.historial_cambios
    # (relaciones inversas hacia address.py/order.py) no se declaran aquí
    # para evitar circular import. D-30: excepción documentada — cross-domain.


# ─────────────────────────────────────────────────────────────────────────────
# UsuarioRol  (pivot con Base completo — D-29)
# ─────────────────────────────────────────────────────────────────────────────


class UsuarioRol(Base, table=True):
    """Asignación de rol a usuario.

    D-29: Hereda de Base completo (UUID PK + created_at + updated_at + deleted_at).
          NO composite PK.
    D-31: deleted_at dormant — la eliminación de asignaciones es hard delete (Change 09).
    D-30: foreign_keys explícitos para las dos FKs que apuntan a usuario (usuario_id,
          asignado_por_id). Evita AmbiguousForeignKeysError.
    task 8.4: asignado_por_id = NULL permitido para bootstrap system-generated.
    """

    __tablename__ = "usuario_rol"
    __table_args__ = (
        UniqueConstraint("usuario_id", "rol_id", name="uq_usuario_rol_usuario_id_rol_id"),
    )

    usuario_id: uuid.UUID = Field(
        sa_column=Column(
            "usuario_id",
            ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    rol_id: uuid.UUID = Field(
        sa_column=Column(
            "rol_id",
            ForeignKey("rol.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    # NULL permitido para bootstrap system-generated (task 8.4, D-29)
    asignado_por_id: Optional[uuid.UUID] = Field(
        sa_column=Column(
            "asignado_por_id",
            ForeignKey("usuario.id"),
            nullable=True,
        )
    )

    # Relationships (D-30: foreign_keys explícitos para evitar AmbiguousForeignKeysError)
    usuario: Optional["Usuario"] = Relationship(
        back_populates="usuario_roles",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "UsuarioRol.usuario_id",
        },
    )
    rol: Optional["Rol"] = Relationship(
        back_populates="usuario_roles",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    asignado_por: Optional["Usuario"] = Relationship(
        back_populates="asignaciones_hechas",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "UsuarioRol.asignado_por_id",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# RefreshToken
# ─────────────────────────────────────────────────────────────────────────────


class RefreshToken(Base, table=True):
    """Token de refresco JWT almacenado como SHA-256 hash.

    D-20: token_hash CHAR(64) almacena hashlib.sha256(token).hexdigest().
          El token en claro nunca se persiste.
          Lógica de generación y verificación → Change 06 (auth service).
    """

    __tablename__ = "refresh_token"

    token_hash: str = Field(
        sa_column=Column("token_hash", CHAR(64), unique=True, nullable=False)
    )
    usuario_id: uuid.UUID = Field(
        sa_column=Column(
            "usuario_id",
            ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
            index=True,  # FK no indexada automáticamente por PostgreSQL
        )
    )
    expires_at: datetime = Field(nullable=False)
    revoked_at: Optional[datetime] = Field(default=None, nullable=True)

    # Relationships
    usuario: Optional["Usuario"] = Relationship(
        back_populates="refresh_tokens",
        sa_relationship_kwargs={
            "lazy": "noload",
            "foreign_keys": "RefreshToken.usuario_id",
        },
    )
