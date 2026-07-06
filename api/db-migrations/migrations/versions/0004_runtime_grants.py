"""reassert runtime db-role grants for RLS role switching

Revision ID: 0004_runtime_grants
Revises: 0003_runtime_app_role
"""

from alembic import op

revision = "0004_runtime_grants"
down_revision = "0003_runtime_app_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ftm_app is only the LOGIN role. It must be able to SET LOCAL ROLE to the
    # effective RLS roles, which then need table privileges before policies run.
    op.execute("GRANT ftm_gp, ftm_medical_specialist, ftm_technician, ftm_patient, ftm_ai, ftm_worker TO ftm_app;")

    op.execute("GRANT USAGE ON SCHEMA clinical, recording, metrics TO ftm_gp;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical, recording TO ftm_gp;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_gp;")

    op.execute("GRANT USAGE ON SCHEMA clinical, recording, metrics, setup TO ftm_medical_specialist;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical, recording, setup TO ftm_medical_specialist;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_medical_specialist;")

    op.execute("GRANT USAGE ON SCHEMA setup, clinical TO ftm_technician;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA setup TO ftm_technician;")
    op.execute(
        """
        GRANT SELECT (program_exercise_id, rehab_program_id, rh_exercise_id)
        ON clinical.program_exercise TO ftm_technician;
        """
    )

    op.execute("GRANT USAGE ON SCHEMA clinical, recording, metrics TO ftm_patient;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA clinical TO ftm_patient;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON recording.exercise_recording TO ftm_patient;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_patient;")

    op.execute("GRANT USAGE ON SCHEMA setup, metrics TO ftm_ai;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA setup TO ftm_ai;")
    op.execute("GRANT SELECT ON metrics.v_ai_payload TO ftm_ai;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON metrics.ai_insight TO ftm_ai;")

    op.execute("GRANT USAGE ON SCHEMA clinical, recording, setup, metrics TO ftm_worker;")
    op.execute("GRANT SELECT ON recording.exercise_recording TO ftm_worker;")
    op.execute("GRANT SELECT ON clinical.pseudonym_map, clinical.program_exercise, clinical.rehab_program, clinical.diagnostic TO ftm_worker;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA setup TO ftm_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON metrics.metric_result, metrics.recording_metric TO ftm_worker;")

    op.execute("GRANT USAGE ON SCHEMA clinical TO ftm_app;")
    op.execute("GRANT EXECUTE ON FUNCTION clinical.identity_id_for_subject(text) TO ftm_app;")


def downgrade() -> None:
    # Do not revoke the role/table grants here: most were established by the
    # baseline and revoking them would leave older migrations in a broken state.
    pass
