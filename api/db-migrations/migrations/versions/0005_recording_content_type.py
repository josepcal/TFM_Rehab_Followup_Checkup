"""persist the exact recording content type

Revision ID: 0005_recording_content_type
Revises: 0004_runtime_grants
"""

from alembic import op

revision = "0005_recording_content_type"
down_revision = "0004_runtime_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE recording.exercise_recording
          ADD COLUMN content_type text NOT NULL DEFAULT 'audio/wav';

        UPDATE recording.exercise_recording
        SET content_type = CASE media_kind
          WHEN 'video' THEN 'video/webm'
          ELSE 'audio/wav'
        END;

        ALTER TABLE recording.exercise_recording
          ADD CONSTRAINT ck_exercise_recording_content_type
            CHECK (content_type LIKE 'audio/%' OR content_type LIKE 'video/%');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE recording.exercise_recording
          DROP CONSTRAINT IF EXISTS ck_exercise_recording_content_type,
          DROP COLUMN IF EXISTS content_type;
        """
    )
