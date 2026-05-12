"""
Script de seed idempotente para datos de catálogo obligatorios.

Inserta:
  - 6 EstadoPedido (FSM del Integrador v5.0)
  - 3 FormaPago (MERCADOPAGO, EFECTIVO, TRANSFERENCIA)
  - 4 Rol RBAC (ADMIN, STOCK, PEDIDOS, CLIENT)
  - 1 usuario administrador con hash bcrypt cost=12

Idempotencia: todos los inserts usan INSERT ... ON CONFLICT (codigo) DO NOTHING
o ON CONFLICT (email) DO NOTHING para no duplicar datos en ejecuciones repetidas.

D-26: passlib[bcrypt] con CryptContext(schemes=["bcrypt"], bcrypt__rounds=12).
D-29/task 8.4: asignado_por_id=None para bootstrap system-generated (no auto-asignación).
R-A-07: Warning si se usa contraseña default ADMIN_PASSWORD.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.base  # noqa: F401 — aplica naming_convention antes que los modelos
import app.models  # noqa: F401 — registra las 16 tablas en SQLModel.metadata

from app.db.session import get_session_factory
from app.models.order import EstadoPedido
from app.models.catalog import FormaPago
from app.models.user import Rol, Usuario, UsuarioRol

logger = logging.getLogger(__name__)

# bcrypt CryptContext — cost=12 (D-26)
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


# ─────────────────────────────────────────────────────────────────────────────
# Seed EstadoPedido — 6 estados FSM
# ─────────────────────────────────────────────────────────────────────────────


async def seed_estados_pedido(session: AsyncSession) -> None:
    """Inserta los 6 estados de pedido de la FSM.

    Códigos y flags según Integrador v5.0 y spec backend-seed-data.
    PENDIENTE/CONFIRMADO/EN_PREP/EN_CAMINO: es_terminal=False.
    ENTREGADO/CANCELADO: es_terminal=True.
    """
    estados = [
        {"codigo": "PENDIENTE",  "descripcion": "Pedido recibido, pendiente de confirmación", "es_terminal": False, "orden": 1},
        {"codigo": "CONFIRMADO", "descripcion": "Pedido confirmado, en espera de preparación", "es_terminal": False, "orden": 2},
        {"codigo": "EN_PREP",    "descripcion": "Pedido en preparación",                      "es_terminal": False, "orden": 3},
        {"codigo": "EN_CAMINO",  "descripcion": "Pedido en camino al cliente",                "es_terminal": False, "orden": 4},
        {"codigo": "ENTREGADO",  "descripcion": "Pedido entregado exitosamente",              "es_terminal": True,  "orden": 5},
        {"codigo": "CANCELADO",  "descripcion": "Pedido cancelado",                           "es_terminal": True,  "orden": 6},
    ]

    now = datetime.utcnow()
    rows = [
        {
            "id": uuid.uuid4(),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            **estado,
        }
        for estado in estados
    ]

    stmt = pg_insert(EstadoPedido).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
    await session.execute(stmt)
    print(f"[seed] EstadoPedido: {len(estados)} estados procesados (ON CONFLICT DO NOTHING)")


# ─────────────────────────────────────────────────────────────────────────────
# Seed FormaPago — 3 formas habilitadas
# ─────────────────────────────────────────────────────────────────────────────


async def seed_formas_pago(session: AsyncSession) -> None:
    """Inserta las 3 formas de pago habilitadas.

    MERCADOPAGO, EFECTIVO, TRANSFERENCIA — todas habilitado=True.
    """
    formas = [
        {"codigo": "MERCADOPAGO",   "nombre": "MercadoPago",      "habilitado": True},
        {"codigo": "EFECTIVO",      "nombre": "Efectivo",         "habilitado": True},
        {"codigo": "TRANSFERENCIA", "nombre": "Transferencia bancaria", "habilitado": True},
    ]

    now = datetime.utcnow()
    rows = [
        {
            "id": uuid.uuid4(),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            **forma,
        }
        for forma in formas
    ]

    stmt = pg_insert(FormaPago).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
    await session.execute(stmt)
    print(f"[seed] FormaPago: {len(formas)} formas procesadas (ON CONFLICT DO NOTHING)")


# ─────────────────────────────────────────────────────────────────────────────
# Seed Roles — 4 roles RBAC
# ─────────────────────────────────────────────────────────────────────────────


async def seed_roles(session: AsyncSession) -> None:
    """Inserta los 4 roles del sistema RBAC."""
    roles = [
        {"codigo": "ADMIN",   "nombre": "Administrador"},
        {"codigo": "STOCK",   "nombre": "Gestor de Stock"},
        {"codigo": "PEDIDOS", "nombre": "Gestor de Pedidos"},
        {"codigo": "CLIENT",  "nombre": "Cliente"},
    ]

    now = datetime.utcnow()
    rows = [
        {
            "id": uuid.uuid4(),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            **rol,
        }
        for rol in roles
    ]

    stmt = pg_insert(Rol).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
    await session.execute(stmt)
    print(f"[seed] Rol: {len(roles)} roles procesados (ON CONFLICT DO NOTHING)")


# ─────────────────────────────────────────────────────────────────────────────
# Seed Admin — usuario administrador con bcrypt cost=12
# ─────────────────────────────────────────────────────────────────────────────


async def seed_admin(session: AsyncSession) -> None:
    """Inserta el usuario administrador con rol ADMIN.

    D-26: hash bcrypt cost=12 via passlib.
    D-29/task 8.4: asignado_por_id=None — bootstrap system-generated, no auto-asignación.
    R-A-07: Warning si se usa ADMIN_PASSWORD default.
    """
    from sqlalchemy import select, text

    admin_email = os.getenv("ADMIN_EMAIL", "admin@foodstore.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if not admin_password:
        admin_password = "Admin1234!"
        print(
            "[seed] WARNING: ADMIN_PASSWORD no está configurada. "
            "Usando contraseña default 'Admin1234!'. "
            "CAMBIARLA en producción via variable de entorno ADMIN_PASSWORD.",
            file=sys.stderr,
        )

    password_hash = pwd_context.hash(admin_password)
    now = datetime.utcnow()

    # 1. Insertar usuario admin (ON CONFLICT (email) DO NOTHING)
    admin_id = uuid.uuid4()
    stmt = pg_insert(Usuario).values(
        id=admin_id,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        email=admin_email,
        password_hash=password_hash,
        nombre="Admin",
        apellido="FoodStore",
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["email"])
    await session.execute(stmt)

    # 2. Obtener el admin real (puede ser el recién insertado o el existente)
    result = await session.execute(
        select(Usuario).where(Usuario.email == admin_email)
    )
    admin = result.scalar_one()

    # 3. Obtener el rol ADMIN
    result = await session.execute(
        select(Rol).where(Rol.codigo == "ADMIN")
    )
    rol_admin = result.scalar_one()

    # 4. Asignar rol ADMIN al admin (ON CONFLICT (usuario_id, rol_id) DO NOTHING)
    # asignado_por_id=None — bootstrap system-generated (D-29, task 8.4)
    stmt = pg_insert(UsuarioRol).values(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        deleted_at=None,
        usuario_id=admin.id,
        rol_id=rol_admin.id,
        asignado_por_id=None,
    )
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_usuario_rol_usuario_id_rol_id"
    )
    await session.execute(stmt)

    print(f"[seed] Admin: usuario '{admin_email}' procesado (ON CONFLICT DO NOTHING)")


# ─────────────────────────────────────────────────────────────────────────────
# Main — ejecuta todos los seeds en orden
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    """Ejecuta el seed completo de catálogos y admin.

    Orden:
      1. EstadoPedido  (requerido antes que Pedido e HistorialEstadoPedido)
      2. FormaPago     (requerido antes que Pedido)
      3. Roles         (requerido antes que seed_admin)
      4. Admin         (depende de Rol.ADMIN existente)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await seed_estados_pedido(session)
            await seed_formas_pago(session)
            await seed_roles(session)
            await seed_admin(session)
            await session.commit()
            print("[seed] Seed completado exitosamente.")
        except Exception as exc:
            await session.rollback()
            print(f"[seed] ERROR: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
