"""baseline: esquema FTM completo desde ftm_schema.sql

Estrategia SQL-first: esta revisión inicial aplica el DDL íntegro
(esquemas, extensión, tipos, tablas, índices, vista v_ai_payload,
funciones de identidad, roles, grants y políticas RLS).

Las migraciones POSTERIORES no editan esta revisión: se crean nuevas
(con autogenerate para tablas + op.execute a mano para vista/roles/RLS).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-08
"""
from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# Snapshot del DDL que acompaña a esta migración (no depende de la raíz del repo).
SCHEMA_SQL = Path(__file__).resolve().parents[1] / "ftm_schema.sql"

# Esquemas creados por el DDL (para el downgrade).
SCHEMAS = ["clinical", "setup", "recording", "metrics", "audit", "reference"]
ROLES = ["ftm_gp", "ftm_medical_specialist", "ftm_technician",
         "ftm_patient", "ftm_ai", "ftm_worker"]


def upgrade() -> None:
    op.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    # CASCADE elimina tablas, vista, funciones, tipos y políticas de cada esquema.
    for schema in SCHEMAS:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE;")
    # Los roles no son objetos de esquema: se eliminan aparte.
    for role in ROLES:
        op.execute(f"DROP ROLE IF EXISTS {role};")
