"""grant worker access to metric persistence tables

Revision ID: 0008_worker_metric_permissions
Revises: 0007_uc4_seed_metric_definition
"""

from alembic import op

revision = "0008_worker_metric_permissions"
down_revision = "0007_uc4_seed_metric_definition"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(
    """
    GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE metrics.metric_result
    TO ftm_worker;

    GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE metrics.recording_metric
    TO ftm_worker;
  """
    )

    op.execute("""
    DO $$
    BEGIN
        RAISE NOTICE 'ftm_worker exists = %',
            EXISTS (
                SELECT 1
                FROM pg_roles
                WHERE rolname = 'ftm_worker'
            );
    END $$;
    """)    

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'metrics'
              AND tablename = 'metric_result'
              AND policyname = 'metric_result_worker'
          ) THEN
            CREATE POLICY metric_result_worker
            ON metrics.metric_result
            FOR ALL
            TO ftm_worker
            USING (true)
            WITH CHECK (true);
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'metrics'
              AND tablename = 'recording_metric'
              AND policyname = 'recording_metric_worker'
          ) THEN
            CREATE POLICY recording_metric_worker
            ON metrics.recording_metric
            FOR ALL
            TO ftm_worker
            USING (true)
            WITH CHECK (true);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
    """
    DROP POLICY IF EXISTS recording_metric_worker
    ON metrics.recording_metric;

        DROP POLICY IF EXISTS metric_result_worker
        ON metrics.metric_result;
    """
    )

    op.execute(
        """
        REVOKE ALL PRIVILEGES
        ON TABLE metrics.recording_metric
        FROM ftm_worker;

        REVOKE ALL PRIVILEGES<
        ON TABLE metrics.metric_result
        FROM ftm_worker;
        """
    )
