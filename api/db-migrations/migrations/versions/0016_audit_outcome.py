"""Add outcome column to audit.event_log to record denied access (OWASP A09)

The audit middleware only records mutations that SUCCEEDED (2xx). That is correct
for attribution, but it dropped the trail of DENIED attempts — and the audit guide
requires alerting on repeated authorization failures (BOLA/BFLA probing). This adds
an explicit outcome so a success can be distinguished from a rejected attempt, and
indexes it for "denied attempts, recent, grouped" queries.

Revision ID: 0016_audit_outcome
Revises: 0015_worker_consent_read
"""

from alembic import op

revision = "0016_audit_outcome"
down_revision = "0015_worker_consent_read"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default 'success' keeps every existing row valid without a backfill: all rows
    # written so far were successful mutations (denied ones were never recorded).
    op.execute(
        """
        ALTER TABLE audit.event_log
            ADD COLUMN IF NOT EXISTS outcome text NOT NULL DEFAULT 'success';
        ALTER TABLE audit.event_log
            DROP CONSTRAINT IF EXISTS ck_event_log_outcome;
        ALTER TABLE audit.event_log
            ADD CONSTRAINT ck_event_log_outcome CHECK (outcome IN ('success', 'denied'));
        """
    )
    # Partial index: intrusion-detection queries only ever look at the denied rows,
    # which are a small minority — a partial index keeps it cheap.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_event_denied
            ON audit.event_log (occurred_at, actor_id)
            WHERE outcome = 'denied';
        """
    )
    # The audit role (medical specialist) already has SELECT on the table; the new
    # column is covered by that grant automatically.


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit.idx_event_denied;")
    op.execute("ALTER TABLE audit.event_log DROP CONSTRAINT IF EXISTS ck_event_log_outcome;")
    op.execute("ALTER TABLE audit.event_log DROP COLUMN IF EXISTS outcome;")
