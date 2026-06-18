"""create runtime ftm_app role for API RLS

Revision ID: 0003_runtime_app_role
Revises: 0002_seed
"""

import os

from alembic import op

revision = "0003_runtime_app_role"
down_revision = "0002_seed"
branch_labels = None
depends_on = None


def _app_password_sql_literal() -> str:
    password = os.environ.get("FTM_APP_DB_PASSWORD")
    if not password:
        raise RuntimeError("Falta FTM_APP_DB_PASSWORD para crear/actualizar el login ftm_app")
    return password.replace("'", "''")


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ftm_app') THEN
                CREATE ROLE ftm_app LOGIN NOINHERIT PASSWORD '{_app_password_sql_literal()}';
            ELSE
                ALTER ROLE ftm_app LOGIN NOINHERIT PASSWORD '{_app_password_sql_literal()}';
            END IF;
        END $$;
        """
    )
    op.execute("GRANT ftm_gp, ftm_medical_specialist, ftm_technician, ftm_patient, ftm_ai, ftm_worker TO ftm_app;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION clinical.identity_id_for_subject(p_external_subject text) RETURNS uuid
          LANGUAGE sql STABLE SECURITY DEFINER SET search_path = clinical AS $$
          SELECT identity_id FROM clinical.app_user
          WHERE external_subject = p_external_subject $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA clinical TO ftm_app;")
    op.execute("GRANT EXECUTE ON FUNCTION clinical.identity_id_for_subject(text) TO ftm_app;")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION clinical.identity_id_for_subject(text) FROM ftm_app;")
    op.execute("DROP FUNCTION IF EXISTS clinical.identity_id_for_subject(text);")
    op.execute("REVOKE USAGE ON SCHEMA clinical FROM ftm_app;")
    op.execute("REVOKE ftm_gp, ftm_medical_specialist, ftm_technician, ftm_patient, ftm_ai, ftm_worker FROM ftm_app;")
    op.execute("DROP ROLE IF EXISTS ftm_app;")
