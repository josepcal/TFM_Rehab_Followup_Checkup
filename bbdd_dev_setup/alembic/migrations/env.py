"""Alembic environment — estrategia SQL-first.

La revisión inicial ejecuta ftm_schema.sql (tablas, tipos, vista, roles, grants y RLS).
`target_metadata` apunta a models.Base.metadata para que el autogenerate de FUTURAS
migraciones pueda diffear las TABLAS (recuerda: vista/roles/grants/RLS no los ve el
autogenerate y se escriben a mano con op.execute).
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Permitir importar models.py (en la raíz del proyecto, junto a alembic.ini)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import models  # noqa: E402

config = context.config

# URL desde la variable de entorno DATABASE_URL si está; si no, la de alembic.ini.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url",os.environ.get("DATABASE_URL")),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,            # múltiples esquemas (clinical, metrics, ...)
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
