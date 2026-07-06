"""Alembic environment — estrategia SQL-first.

La revisión inicial ejecuta ftm_schema.sql (tablas, tipos, vista, roles, grants y RLS).
`target_metadata` apunta a models.Base.metadata para que el autogenerate de FUTURAS
migraciones pueda diffear las TABLAS (recuerda: vista/roles/grants/RLS no los ve el
autogenerate y se escriben a mano con op.execute).

La conexión NO se guarda en alembic.ini: se resuelve desde el entorno.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import engine_from_config, pool
from alembic import context

# Permitir importar models.py (en la raíz del proyecto, junto a alembic.ini)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import models  # noqa: E402

config = context.config


def _resolve_db_url() -> str | None:
    """Resuelve la URL de conexión SIN credenciales en alembic.ini.

    Prioridad:
      1. DATABASE_URL (cadena completa).
      2. Componentes POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
         (+ POSTGRES_HOST y POSTGRES_PORT opcionales).
    Devuelve None si no hay datos suficientes en el entorno.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("POSTGRES_USER")
    pwd = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    if user and pwd and db:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        # quote_plus por si la contraseña lleva caracteres especiales (@ : / ...)
        return (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}"
            f"@{host}:{port}/{db}"
        )
    return None


_db_url = _resolve_db_url()
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)
elif not config.get_main_option("sqlalchemy.url", None):
    raise RuntimeError(
        "No hay conexión a BD configurada. Define DATABASE_URL, o bien "
        "POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB en el entorno "
        "(por ejemplo: 'set -a; source .env; set +a'). "
        "alembic.ini ya no contiene credenciales."
    )

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
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
