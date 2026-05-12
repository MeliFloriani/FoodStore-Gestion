"""
Tests de migración Alembic — ciclo upgrade/downgrade/upgrade.

Estrategia (task 9.0, Opción B):
  - Usa alembic upgrade head + alembic downgrade base via subprocess.
  - Opera sobre foodstore_test (TEST_DATABASE_URL).
  - Fixture session-scoped garantiza la DB queda limpia al inicio de la suite.

Design:
  - Usa subprocess para invocar alembic CLI (evita conflictos de event loop).
  - TEST_DATABASE_URL se inyecta como variable de entorno DATABASE_URL
    para que get_settings() en env.py lo use.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from dotenv import load_dotenv

# Load .env so TEST_DATABASE_URL is available in os.environ
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic(args: list[str]) -> subprocess.CompletedProcess:
    """Corre un comando alembic apuntando a foodstore_test."""
    test_url = os.environ["TEST_DATABASE_URL"]
    env = {**os.environ, "DATABASE_URL": test_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic"] + args,
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    return result


@pytest.fixture(scope="session", autouse=True)
def clean_test_db_at_start():
    """Fixture session-scoped: garantiza la BD de test queda en estado limpio al inicio.

    Si la BD quedó sucia de una ejecución anterior (downgrade falló a mitad),
    este fixture ejecuta downgrade base antes de que empiecen los tests.
    Ignora errores (puede que ya esté limpia).

    Al finalizar: deja la BD en head para que test_seed.py pueda correr sin
    necesitar hacer upgrade separado.
    """
    _alembic(["downgrade", "base"])  # ignore errors — cleanup anterior run
    yield
    # Teardown: restaurar a head para que otros tests (test_seed) puedan funcionar
    _alembic(["upgrade", "head"])


class TestMigrationCycle:
    """Tests del ciclo completo upgrade/downgrade/upgrade sobre foodstore_test."""

    def test_upgrade_head(self):
        """upgrade head debe completar sin errores."""
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, (
            f"alembic upgrade head falló:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_downgrade_base(self):
        """downgrade base debe completar sin errores de FK."""
        result = _alembic(["downgrade", "base"])
        assert result.returncode == 0, (
            f"alembic downgrade base falló:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_upgrade_after_downgrade(self):
        """upgrade head después de downgrade base debe completar (schema reproducible)."""
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, (
            f"alembic upgrade head (post-downgrade) falló:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_upgrade_downgrade_upgrade_cycle(self):
        """Ciclo completo: upgrade → downgrade → upgrade debe completar sin errores."""
        # Downgrade
        r1 = _alembic(["downgrade", "base"])
        assert r1.returncode == 0, f"downgrade falló: {r1.stderr}"

        # Upgrade
        r2 = _alembic(["upgrade", "head"])
        assert r2.returncode == 0, f"upgrade (2do) falló: {r2.stderr}"
