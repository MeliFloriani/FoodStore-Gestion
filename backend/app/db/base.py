"""
Database naming convention configuration for SQLModel/SQLAlchemy.

Design decisions:
- D-12 / P-07: SQLModel.metadata.naming_convention MUST be set here, BEFORE models.
  This module must be imported before declaring any SQLModel table class.
  app/models/base.py imports this module first for that reason.
- This module does NOT import any models — it only configures metadata.
"""

from sqlmodel import SQLModel

# Naming convention for all constraints — applied to SQLAlchemy MetaData globally.
# This ensures consistent, predictable constraint names across all migrations.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Apply naming convention to the global SQLModel MetaData.
# Must happen before any model class with table=True is defined.
SQLModel.metadata.naming_convention = NAMING_CONVENTION
