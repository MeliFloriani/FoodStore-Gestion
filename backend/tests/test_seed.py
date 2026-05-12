"""
Tests de seed idempotente — verifica que seed.main() es idempotente y produce
exactamente los datos de catálogo esperados.

Estrategia (task 9.0, Opción A):
  - Cada test corre dentro de una sesión que hace ROLLBACK al final.
  - Requiere que foodstore_test tenga el schema creado (alembic upgrade head).
  - Los tests corren DESPUÉS de test_migrations.py (dependen del schema).

Fixtures:
  - `test_session`: AsyncSession contra foodstore_test con ROLLBACK al final.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from dotenv import load_dotenv

# Load .env so TEST_DATABASE_URL is available in os.environ
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.base  # noqa: F401
import app.models  # noqa: F401

from app.db.seed import (
    seed_admin,
    seed_estados_pedido,
    seed_formas_pago,
    seed_roles,
)
from app.models.catalog import FormaPago
from app.models.order import EstadoPedido
from app.models.user import Rol, Usuario, UsuarioRol


@pytest_asyncio.fixture
async def test_session():
    """AsyncSession contra foodstore_test con ROLLBACK automático al final."""
    test_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(test_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(test_session: AsyncSession):
    """Sesión con seed completo aplicado (no committed — se hace rollback al final)."""
    await seed_estados_pedido(test_session)
    await seed_formas_pago(test_session)
    await seed_roles(test_session)
    await seed_admin(test_session)
    # No commit — el rollback del test_session fixture deshace todo
    yield test_session


class TestSeedIdempotent:
    """Tests de idempotencia del seed."""

    async def test_seed_idempotent_double_run(self, test_session: AsyncSession):
        """Ejecutar seed dos veces no lanza excepciones ni crea duplicados."""
        # Primera ejecución
        await seed_estados_pedido(test_session)
        await seed_formas_pago(test_session)
        await seed_roles(test_session)
        await seed_admin(test_session)

        # Segunda ejecución — debe ser silenciosa (ON CONFLICT DO NOTHING)
        await seed_estados_pedido(test_session)
        await seed_formas_pago(test_session)
        await seed_roles(test_session)
        await seed_admin(test_session)

        # Verificar counts
        r = await test_session.execute(select(EstadoPedido))
        assert len(r.scalars().all()) == 6

        r = await test_session.execute(select(FormaPago))
        assert len(r.scalars().all()) == 3

        r = await test_session.execute(select(Rol))
        assert len(r.scalars().all()) == 4

        r = await test_session.execute(
            select(Usuario).where(Usuario.email == "admin@foodstore.com")
        )
        admins = r.scalars().all()
        assert len(admins) == 1

    async def test_seed_counts(self, seeded_session: AsyncSession):
        """6 EstadoPedido, 3 FormaPago, 4 Rol, 1 admin."""
        r = await seeded_session.execute(select(EstadoPedido))
        assert len(r.scalars().all()) == 6, "Deben existir exactamente 6 estados de pedido"

        r = await seeded_session.execute(select(FormaPago))
        assert len(r.scalars().all()) == 3, "Deben existir exactamente 3 formas de pago"

        r = await seeded_session.execute(select(Rol))
        assert len(r.scalars().all()) == 4, "Deben existir exactamente 4 roles"

        r = await seeded_session.execute(
            select(Usuario).where(Usuario.email == "admin@foodstore.com")
        )
        assert len(r.scalars().all()) == 1, "Debe existir exactamente 1 usuario admin"


class TestSeedEstadosTerminales:
    """Tests de los estados terminales de la FSM."""

    async def test_seed_estados_terminales(self, seeded_session: AsyncSession):
        """ENTREGADO y CANCELADO deben ser es_terminal=True; el resto False."""
        r = await seeded_session.execute(select(EstadoPedido))
        estados = {e.codigo: e.es_terminal for e in r.scalars().all()}

        # Estados terminales
        assert estados["ENTREGADO"] is True, "ENTREGADO debe ser es_terminal=True"
        assert estados["CANCELADO"] is True, "CANCELADO debe ser es_terminal=True"

        # Estados no terminales
        for codigo in ["PENDIENTE", "CONFIRMADO", "EN_PREP", "EN_CAMINO"]:
            assert estados[codigo] is False, f"{codigo} debe ser es_terminal=False"

    async def test_seed_estados_orden(self, seeded_session: AsyncSession):
        """Los estados deben tener el orden correcto (1..6)."""
        r = await seeded_session.execute(
            select(EstadoPedido).order_by(EstadoPedido.orden)
        )
        estados = r.scalars().all()
        codigos = [e.codigo for e in estados]
        expected = ["PENDIENTE", "CONFIRMADO", "EN_PREP", "EN_CAMINO", "ENTREGADO", "CANCELADO"]
        assert codigos == expected, f"Orden incorrecto: {codigos}"

    async def test_seed_formas_pago_habilitadas(self, seeded_session: AsyncSession):
        """Todas las formas de pago deben estar habilitadas."""
        r = await seeded_session.execute(select(FormaPago))
        formas = r.scalars().all()
        for forma in formas:
            assert forma.habilitado is True, f"{forma.codigo} debe tener habilitado=True"

    async def test_seed_admin_rol_asignado(self, seeded_session: AsyncSession):
        """El admin debe tener el rol ADMIN asignado con asignado_por_id=NULL."""
        r = await seeded_session.execute(
            select(Usuario).where(Usuario.email == "admin@foodstore.com")
        )
        admin = r.scalar_one()

        r = await seeded_session.execute(
            select(Rol).where(Rol.codigo == "ADMIN")
        )
        rol_admin = r.scalar_one()

        r = await seeded_session.execute(
            select(UsuarioRol).where(
                UsuarioRol.usuario_id == admin.id,
                UsuarioRol.rol_id == rol_admin.id,
            )
        )
        asignacion = r.scalar_one_or_none()
        assert asignacion is not None, "El admin debe tener el rol ADMIN asignado"
        assert asignacion.asignado_por_id is None, (
            "asignado_por_id debe ser NULL para bootstrap system-generated (D-29, task 8.4)"
        )

    async def test_seed_admin_password_hash(self, seeded_session: AsyncSession):
        """El hash de contraseña del admin debe ser bcrypt ($2b$12$...)."""
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)

        r = await seeded_session.execute(
            select(Usuario).where(Usuario.email == "admin@foodstore.com")
        )
        admin = r.scalar_one()

        assert admin.password_hash.startswith("$2b$12$"), (
            "El password_hash debe comenzar con $2b$12$ (bcrypt cost=12)"
        )
        assert ctx.verify("Admin1234!", admin.password_hash), (
            "La contraseña Admin1234! debe verificar contra el hash almacenado"
        )
        assert not ctx.verify("OtraContrasena", admin.password_hash), (
            "Una contraseña incorrecta no debe verificar"
        )

    async def test_seed_roles_codigos(self, seeded_session: AsyncSession):
        """Los 4 roles RBAC deben existir con sus códigos correctos."""
        r = await seeded_session.execute(select(Rol))
        roles = {rol.codigo for rol in r.scalars().all()}
        assert roles == {"ADMIN", "STOCK", "PEDIDOS", "CLIENT"}, (
            f"Roles incorrectos: {roles}"
        )
