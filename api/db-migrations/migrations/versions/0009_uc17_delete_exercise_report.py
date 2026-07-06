"""grant medical specialist DELETE on exercise_report (UC-17)

Revision ID: 0009_uc17_delete_exercise_report
Revises: 0008_worker_metric_permissions
"""

from alembic import op

revision = "0009_uc17_delete_exercise_report"
down_revision = "0008_worker_metric_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        GRANT DELETE
        ON TABLE clinical.exercise_report
        TO ftm_medical_specialist;
        """
    )

    op.execute(
        """
        GRANT DELETE
        ON TABLE clinical.exercise_report
        TO ftm_gp;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE DELETE
        ON TABLE clinical.exercise_report
        FROM ftm_medical_specialist;

        REVOKE DELETE
        ON TABLE clinical.exercise_report
        FROM ftm_gp;
        """
    )
