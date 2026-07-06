"""Add RLS write policies and consent_text column to clinical.patient_consent (UC-05)

Revision ID: 0012_consent_rls_policy
Revises: 0011_seed_metric_norms
"""

from alembic import op

revision = "0012_consent_rls_policy"
down_revision = "0011_seed_metric_norms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the UNIQUE constraint so the table can hold multiple rows per patient+program
    #    (append-only consent audit trail — RGPD requires each grant/withdraw to be preserved)
    op.execute(
        """
        ALTER TABLE clinical.patient_consent
            DROP CONSTRAINT IF EXISTS patient_consent_patient_id_rehab_program_id_key;
        """
    )

    # 2. Add consent_text column (nullable at DB level; required at application level for new rows)
    op.execute(
        """
        ALTER TABLE clinical.patient_consent
            ADD COLUMN IF NOT EXISTS consent_text TEXT;
        """
    )

    # 3. RLS INSERT policy — patient may only insert rows for their own patient_id
    op.execute(
        """
        DROP POLICY IF EXISTS consent_patient_insert ON clinical.patient_consent;
        """
    )
    op.execute(
        """
        CREATE POLICY consent_patient_insert
            ON clinical.patient_consent
            FOR INSERT
            TO ftm_patient
            WITH CHECK (patient_id = clinical.current_patient_id());
        """
    )

    # 4. RLS UPDATE policy — patient may only update their own consent rows (withdraw)
    op.execute(
        """
        DROP POLICY IF EXISTS consent_patient_update ON clinical.patient_consent;
        """
    )
    op.execute(
        """
        CREATE POLICY consent_patient_update
            ON clinical.patient_consent
            FOR UPDATE
            TO ftm_patient
            USING (patient_id = clinical.current_patient_id());
        """
    )

    # 5. Grant INSERT and UPDATE to the patient role so the policies can take effect
    op.execute(
        """
        GRANT INSERT, UPDATE ON clinical.patient_consent TO ftm_patient;
        """
    )


def downgrade() -> None:
    # Reverse grant
    op.execute(
        """
        REVOKE INSERT, UPDATE ON clinical.patient_consent FROM ftm_patient;
        """
    )

    # Drop write policies
    op.execute(
        """
        DROP POLICY IF EXISTS consent_patient_insert ON clinical.patient_consent;
        """
    )
    op.execute(
        """
        DROP POLICY IF EXISTS consent_patient_update ON clinical.patient_consent;
        """
    )

    # Remove the consent_text column added in upgrade
    op.execute(
        """
        ALTER TABLE clinical.patient_consent
            DROP COLUMN IF EXISTS consent_text;
        """
    )

    # Restore the original UNIQUE constraint
    op.execute(
        """
        ALTER TABLE clinical.patient_consent
            ADD CONSTRAINT patient_consent_patient_id_rehab_program_id_key
            UNIQUE (patient_id, rehab_program_id);
        """
    )
