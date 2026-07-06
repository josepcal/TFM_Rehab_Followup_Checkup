"""create clinical.followup_checkup and clinical.followup_checkup_report (UC-09)

Revision ID: 0010_followup_checkup
Revises: 0009_uc17_delete_exercise_report
"""

from alembic import op

revision = "0010_followup_checkup"
down_revision = "0009_uc17_delete_exercise_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create clinical.followup_checkup
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical.followup_checkup (
            followup_checkup_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            rehab_program_id    uuid NOT NULL
                REFERENCES clinical.rehab_program(rehab_program_id),
            patient_id          uuid NOT NULL,
            period_start        date NOT NULL,
            period_end          date NOT NULL,
            summary             text,
            created_by          uuid
                REFERENCES clinical.doctor(doctor_id),
            created_at          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fchk_period CHECK (period_end >= period_start)
        );
        """
    )

    # 2. Create clinical.followup_checkup_report (link table)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical.followup_checkup_report (
            followup_checkup_id uuid NOT NULL
                REFERENCES clinical.followup_checkup(followup_checkup_id)
                ON DELETE CASCADE,
            exercise_report_id  uuid NOT NULL
                REFERENCES clinical.exercise_report(exercise_report_id),
            PRIMARY KEY (followup_checkup_id, exercise_report_id)
        );
        """
    )

    # 3. Indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_checkup_program
            ON clinical.followup_checkup(rehab_program_id);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_checkup_patient
            ON clinical.followup_checkup(patient_id);
        """
    )

    # 4. Row-level security — followup_checkup
    op.execute(
        """
        ALTER TABLE clinical.followup_checkup ENABLE ROW LEVEL SECURITY;
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS fchk_staff ON clinical.followup_checkup;
        CREATE POLICY fchk_staff
            ON clinical.followup_checkup
            FOR ALL
            TO ftm_gp, ftm_medical_specialist
            USING (true);
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS fchk_self ON clinical.followup_checkup;
        CREATE POLICY fchk_self
            ON clinical.followup_checkup
            FOR SELECT
            TO ftm_patient
            USING (patient_id = clinical.current_patient_id());
        """
    )

    # 5. Row-level security — followup_checkup_report
    op.execute(
        """
        ALTER TABLE clinical.followup_checkup_report ENABLE ROW LEVEL SECURITY;
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS fcr_staff ON clinical.followup_checkup_report;
        CREATE POLICY fcr_staff
            ON clinical.followup_checkup_report
            FOR ALL
            TO ftm_gp, ftm_medical_specialist
            USING (true);
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS fcr_self ON clinical.followup_checkup_report;
        CREATE POLICY fcr_self
            ON clinical.followup_checkup_report
            FOR SELECT
            TO ftm_patient
            USING (
                followup_checkup_id IN (
                    SELECT followup_checkup_id
                    FROM clinical.followup_checkup
                    WHERE patient_id = clinical.current_patient_id()
                )
            );
        """
    )

    # 6. Grant permissions to roles
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON TABLE clinical.followup_checkup
            TO ftm_gp, ftm_medical_specialist;

        GRANT SELECT
            ON TABLE clinical.followup_checkup
            TO ftm_patient;

        GRANT SELECT, INSERT, UPDATE, DELETE
            ON TABLE clinical.followup_checkup_report
            TO ftm_gp, ftm_medical_specialist;

        GRANT SELECT
            ON TABLE clinical.followup_checkup_report
            TO ftm_patient;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS clinical.followup_checkup_report CASCADE;
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS clinical.followup_checkup CASCADE;
        """
    )
