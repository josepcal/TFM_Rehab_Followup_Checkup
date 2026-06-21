"""add UC-06 analysis queue foundation

Revision ID: 0006_analysis_worker
Revises: 0005_recording_content_type
"""

from alembic import op

revision = "0006_analysis_worker"
down_revision = "0005_recording_content_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # metric_result and recording_metric are owned by the SQL-first baseline.
    # Fail loudly if a non-canonical baseline is used rather than silently
    # creating incomplete patient-data tables without their RLS policies.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('metrics.metric_result') IS NULL THEN
            RAISE EXCEPTION 'missing baseline table metrics.metric_result';
          END IF;
          IF to_regclass('metrics.recording_metric') IS NULL THEN
            RAISE EXCEPTION 'missing baseline table metrics.recording_metric';
          END IF;
        END $$;
        """
    )

    # Give the success/raw-json invariant a stable name for Alembic/model drift
    # checks. The baseline's equivalent unnamed CHECK remains valid.
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'metrics.metric_result'::regclass
              AND conname = 'ck_metric_result_rawjson_present'
          ) THEN
            ALTER TABLE metrics.metric_result
              ADD CONSTRAINT ck_metric_result_rawjson_present
              CHECK (status <> 'success' OR raw_json IS NOT NULL);
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE metrics.analysis_job (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          recording_id  uuid NOT NULL
                        REFERENCES recording.exercise_recording(recording_id),
          function_name text NOT NULL,
          status        text NOT NULL DEFAULT 'pending',
          attempts      integer NOT NULL DEFAULT 0,
          error_detail  text,
          created_at    timestamptz NOT NULL DEFAULT now(),
          locked_at     timestamptz,
          updated_at    timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_analysis_job_status
            CHECK (status IN ('pending', 'running', 'done', 'error')),
          CONSTRAINT ck_analysis_job_attempts
            CHECK (attempts >= 0)
        );

        CREATE INDEX idx_analysis_job_pending
          ON metrics.analysis_job (created_at)
          WHERE status = 'pending';
        CREATE INDEX idx_analysis_job_recording
          ON metrics.analysis_job (recording_id);
        """
    )

    # Queue access follows the same recording visibility boundary as UC-05.
    # Technicians receive no grant; only patients/medical users enqueue, while
    # the worker owns state transitions and cleanup.
    op.execute(
        """
        GRANT SELECT, INSERT ON metrics.analysis_job
          TO ftm_gp, ftm_medical_specialist, ftm_patient;
        GRANT SELECT, INSERT, UPDATE, DELETE ON metrics.analysis_job
          TO ftm_worker;

        ALTER TABLE metrics.analysis_job ENABLE ROW LEVEL SECURITY;

        CREATE POLICY analysis_job_staff_select
          ON metrics.analysis_job FOR SELECT
          TO ftm_gp, ftm_medical_specialist
          USING (true);
        CREATE POLICY analysis_job_staff_insert
          ON metrics.analysis_job FOR INSERT
          TO ftm_gp, ftm_medical_specialist
          WITH CHECK (EXISTS (
            SELECT 1 FROM recording.exercise_recording r
            WHERE r.recording_id = analysis_job.recording_id
          ));

        CREATE POLICY analysis_job_patient_select
          ON metrics.analysis_job FOR SELECT
          TO ftm_patient
          USING (EXISTS (
            SELECT 1 FROM recording.exercise_recording r
            WHERE r.recording_id = analysis_job.recording_id
          ));
        CREATE POLICY analysis_job_patient_insert
          ON metrics.analysis_job FOR INSERT
          TO ftm_patient
          WITH CHECK (EXISTS (
            SELECT 1 FROM recording.exercise_recording r
            WHERE r.recording_id = analysis_job.recording_id
          ));

        CREATE POLICY analysis_job_worker
          ON metrics.analysis_job FOR ALL
          TO ftm_worker
          USING (true)
          WITH CHECK (true);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS metrics.analysis_job;")
    op.execute(
        """
        ALTER TABLE metrics.metric_result
          DROP CONSTRAINT IF EXISTS ck_metric_result_rawjson_present;
        """
    )
