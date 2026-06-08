"""
Script de seed idempotente para datos de catálogo obligatorios.

Inserta:
  - 6 EstadoPedido (FSM del Integrador v5.0)
  - 3 FormaPago (MERCADOPAGO, EFECTIVO, TRANSFERENCIA)
  - 4 Rol RBAC (ADMIN, STOCK, PEDIDOS, CLIENT)
  - 1 usuario administrador con hash bcrypt cost=12
  - Dev catalog data (smoke test): 3 categorías, 6 ingredientes (3 alérgenos),
    3 productos disponibles con stock, pivots y 1 usuario cliente CLIENT.

Idempotencia: catálogos por (codigo) usan ON CONFLICT DO NOTHING. Catálogo de
desarrollo (categoria/ingrediente/producto) usa SELECT-by-nombre + INSERT-if-missing
porque los unique indexes son parciales (WHERE deleted_at IS NULL) y no son
compatibles directamente con ON CONFLICT.

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
from decimal import Decimal

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.base  # noqa: F401 — aplica naming_convention antes que los modelos
import app.models  # noqa: F401 — registra las 16 tablas en SQLModel.metadata

from app.db.session import get_session_factory
from app.models.order import EstadoPedido
from app.models.catalog import (
    Categoria,
    FormaPago,
    Ingrediente,
    Producto,
    ProductoCategoria,
    ProductoIngrediente,
)
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
# Dev catalog seed — Categorias / Ingredientes / Productos / Cliente
# Habilita smoke test local del Change 19 (payments-mercadopago-integration).
# NO es lógica productiva: solo datos mínimos para que el frontend tenga catálogo
# y exista un usuario cliente con credenciales conocidas.
# ─────────────────────────────────────────────────────────────────────────────


async def _get_or_create_categoria_root(
    session: AsyncSession, nombre: str
) -> Categoria:
    """SELECT por nombre+parent_id IS NULL+deleted_at IS NULL; INSERT si falta.

    El partial unique index uq_categoria_nombre_root (migration 0003) garantiza
    unicidad entre categorías raíz activas. Evitamos pg_insert.on_conflict porque
    SQLAlchemy 2.x no soporta predicados WHERE en on_conflict.
    """
    result = await session.execute(
        select(Categoria).where(
            Categoria.nombre == nombre,
            Categoria.parent_id.is_(None),  # type: ignore[union-attr]
            Categoria.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    cat = Categoria(nombre=nombre, descripcion=f"Categoría {nombre}", parent_id=None)
    session.add(cat)
    await session.flush()  # asigna id sin commit
    return cat


async def _get_or_create_ingrediente(
    session: AsyncSession, nombre: str, es_alergeno: bool
) -> Ingrediente:
    """SELECT por nombre+deleted_at IS NULL (partial index ix_ingrediente_nombre_activo)."""
    result = await session.execute(
        select(Ingrediente).where(
            Ingrediente.nombre == nombre,
            Ingrediente.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    ing = Ingrediente(nombre=nombre, es_alergeno=es_alergeno)
    session.add(ing)
    await session.flush()
    return ing


async def _get_or_create_producto(
    session: AsyncSession,
    nombre: str,
    precio_base: Decimal,
    stock_cantidad: int,
    descripcion: str,
) -> Producto:
    """SELECT por nombre+deleted_at IS NULL; INSERT si falta.

    Producto no tiene unique en nombre — usamos nombre como key natural a nivel seed.
    """
    result = await session.execute(
        select(Producto).where(
            Producto.nombre == nombre,
            Producto.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    prod = Producto(
        nombre=nombre,
        precio_base=float(precio_base),
        stock_cantidad=stock_cantidad,
        disponible=True,
        descripcion=descripcion,
    )
    session.add(prod)
    await session.flush()
    return prod


async def _link_producto_categoria(
    session: AsyncSession, producto: Producto, categoria: Categoria, es_principal: bool
) -> None:
    """Idempotente vía uq_producto_categoria_producto_id_categoria_id."""
    stmt = pg_insert(ProductoCategoria).values(
        id=uuid.uuid4(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        deleted_at=None,
        producto_id=producto.id,
        categoria_id=categoria.id,
        es_principal=es_principal,
    )
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_producto_categoria_producto_id_categoria_id"
    )
    await session.execute(stmt)


async def _link_producto_ingrediente(
    session: AsyncSession, producto: Producto, ingrediente: Ingrediente, es_removible: bool
) -> None:
    """Idempotente vía uq_producto_ingrediente_producto_id_ingrediente_id."""
    stmt = pg_insert(ProductoIngrediente).values(
        id=uuid.uuid4(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        deleted_at=None,
        producto_id=producto.id,
        ingrediente_id=ingrediente.id,
        es_removible=es_removible,
    )
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_producto_ingrediente_producto_id_ingrediente_id"
    )
    await session.execute(stmt)


async def seed_dev_catalog(session: AsyncSession) -> None:
    """Datos mínimos de catálogo para habilitar smoke test local.

    NO ejecutar en producción: prefijo 'DEV' en nombres ayuda a identificarlos.
    """
    # 1. Categorías raíz (3)
    cat_pizzas = await _get_or_create_categoria_root(session, "DEV Pizzas")
    cat_burgers = await _get_or_create_categoria_root(session, "DEV Hamburguesas")
    cat_bebidas = await _get_or_create_categoria_root(session, "DEV Bebidas")

    # 2. Ingredientes (3 normales + 3 alérgenos)
    queso = await _get_or_create_ingrediente(session, "DEV Queso mozzarella", es_alergeno=True)  # lactosa
    harina = await _get_or_create_ingrediente(session, "DEV Harina de trigo", es_alergeno=True)  # gluten
    mani = await _get_or_create_ingrediente(session, "DEV Maní", es_alergeno=True)  # frutos secos
    tomate = await _get_or_create_ingrediente(session, "DEV Tomate", es_alergeno=False)
    albahaca = await _get_or_create_ingrediente(session, "DEV Albahaca", es_alergeno=False)
    agua = await _get_or_create_ingrediente(session, "DEV Agua mineral", es_alergeno=False)

    # 3. Productos disponibles con stock
    pizza = await _get_or_create_producto(
        session,
        nombre="DEV Pizza Margherita",
        precio_base=Decimal("3500.00"),
        stock_cantidad=20,
        descripcion="Pizza clásica con tomate, mozzarella y albahaca.",
    )
    burger = await _get_or_create_producto(
        session,
        nombre="DEV Hamburguesa Clásica",
        precio_base=Decimal("2800.00"),
        stock_cantidad=15,
        descripcion="Hamburguesa con queso y tomate.",
    )
    agua_prod = await _get_or_create_producto(
        session,
        nombre="DEV Agua mineral 500ml",
        precio_base=Decimal("800.00"),
        stock_cantidad=50,
        descripcion="Botella de agua mineral sin gas.",
    )

    # 4. Pivots producto ↔ categoria
    await _link_producto_categoria(session, pizza, cat_pizzas, es_principal=True)
    await _link_producto_categoria(session, burger, cat_burgers, es_principal=True)
    await _link_producto_categoria(session, agua_prod, cat_bebidas, es_principal=True)

    # 5. Pivots producto ↔ ingrediente
    await _link_producto_ingrediente(session, pizza, harina, es_removible=False)
    await _link_producto_ingrediente(session, pizza, queso, es_removible=True)
    await _link_producto_ingrediente(session, pizza, tomate, es_removible=False)
    await _link_producto_ingrediente(session, pizza, albahaca, es_removible=True)
    await _link_producto_ingrediente(session, burger, harina, es_removible=False)
    await _link_producto_ingrediente(session, burger, queso, es_removible=True)
    await _link_producto_ingrediente(session, burger, tomate, es_removible=True)
    await _link_producto_ingrediente(session, agua_prod, agua, es_removible=False)

    print(
        "[seed] DevCatalog: 3 categorías, 6 ingredientes (3 alérgenos), 3 productos "
        "y sus pivots procesados (idempotente)"
    )


async def seed_dev_cliente(session: AsyncSession) -> None:
    """Usuario cliente de prueba con rol CLIENT.

    Credenciales: cliente@foodstore.com / Cliente1234!
    Idempotente: ON CONFLICT (email) DO NOTHING en usuario y constraint en usuario_rol.
    """
    cliente_email = os.getenv("DEV_CLIENT_EMAIL", "cliente@foodstore.com")
    cliente_password = os.getenv("DEV_CLIENT_PASSWORD", "Cliente1234!")
    password_hash = pwd_context.hash(cliente_password)
    now = datetime.utcnow()

    # 1. Insertar usuario cliente
    cliente_id = uuid.uuid4()
    stmt = pg_insert(Usuario).values(
        id=cliente_id,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        email=cliente_email,
        password_hash=password_hash,
        nombre="Cliente",
        apellido="Test",
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["email"])
    await session.execute(stmt)

    # 2. Obtener el cliente real
    result = await session.execute(
        select(Usuario).where(Usuario.email == cliente_email)
    )
    cliente = result.scalar_one()

    # 3. Obtener rol CLIENT
    result = await session.execute(select(Rol).where(Rol.codigo == "CLIENT"))
    rol_client = result.scalar_one()

    # 4. Asignar rol CLIENT (idempotente por uq_usuario_rol_usuario_id_rol_id)
    stmt = pg_insert(UsuarioRol).values(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        deleted_at=None,
        usuario_id=cliente.id,
        rol_id=rol_client.id,
        asignado_por_id=None,
    )
    stmt = stmt.on_conflict_do_nothing(constraint="uq_usuario_rol_usuario_id_rol_id")
    await session.execute(stmt)

    print(f"[seed] DevCliente: usuario '{cliente_email}' procesado (ON CONFLICT DO NOTHING)")


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
      5. DevCatalog    (dev only — productos visibles para smoke test)
      6. DevCliente    (dev only — login cliente para smoke test, depende de Rol.CLIENT)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await seed_estados_pedido(session)
            await seed_formas_pago(session)
            await seed_roles(session)
            await seed_admin(session)
            await seed_dev_catalog(session)
            await seed_dev_cliente(session)
            await session.commit()
            print("[seed] Seed completado exitosamente.")
        except Exception as exc:
            await session.rollback()
            print(f"[seed] ERROR: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
