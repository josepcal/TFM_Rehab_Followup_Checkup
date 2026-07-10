"""Grant the worker read access to clinical.patient_consent (UC-05 / RGPD art. 7.3)

The analysis worker must re-check active consent before processing queued audio,
so a withdrawal that lands after enqueue still blocks processing. That requires
the ftm_worker role to SELECT patient_consent, plus an RLS policy allowing it.

Revision ID: 0015_worker_consent_read
Revises: 0014_encrypt_national_id
"""

from alembic import op

revision = "0015_worker_consent_read"
down_revision = "0014_encrypt_national_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON clinical.patient_consent TO ftm_worker;")
    op.execute(
        """
        DROP POLICY IF EXISTS consent_worker ON clinical.patient_consent;
        CREATE POLICY consent_worker
            ON clinical.patient_consent
            FOR SELECT
            TO ftm_worker
            USING (true);
        """
    )
    # Add 'skipped' as a first-class job status: analysis was intentionally not run
    # because consent was withdrawn (distinct from 'done' = analysed, 'error' = failed).
    op.execute(
        """
        ALTER TABLE metrics.analysis_job DROP CONSTRAINT IF EXISTS ck_analysis_job_status;
        ALTER TABLE metrics.analysis_job ADD CONSTRAINT ck_analysis_job_status
            CHECK (status IN ('pending', 'running', 'done', 'error', 'skipped'));
        """
    )


def downgrade() -> None:
    # 'skipped' rows (jobs the worker declined because consent was withdrawn) exist
    # in the DB the moment this migration has been live. Restoring the old CHECK
    # without first migrating them would fail with a check-constraint violation —
    # and since the DROP runs before the failed ADD, it would leave the table with
    # NO status constraint at all. Migrate them to 'error' first (error_detail still
    # carries CONSENT_WITHDRAWN, so the reason is preserved), then restore the CHECK.
    op.execute(
        """
        ALTER TABLE metrics.analysis_job DROP CONSTRAINT IF EXISTS ck_analysis_job_status;
        UPDATE metrics.analysis_job SET status = 'error' WHERE status = 'skipped';
        ALTER TABLE metrics.analysis_job ADD CONSTRAINT ck_analysis_job_status
            CHECK (status IN ('pending', 'running', 'done', 'error'));
        """
    )
    op.execute("DROP POLICY IF EXISTS consent_worker ON clinical.patient_consent;")
    op.execute("REVOKE SELECT ON clinical.patient_consent FROM ftm_worker;")
