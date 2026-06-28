"""Grant SELECT on audit.event_log to ftm_medical_specialist (UC-15)

The audit schema and event_log table are created by 0001_baseline (ftm_schema.sql).
No app role has access to the audit schema by default — this migration adds the
minimum read grant so the admin role (mapped to ftm_medical_specialist) can query
the audit log via GET /iam/audit-log.

INSERT remains restricted to the pool login user (ftm_app) which owns the schema.
No UPDATE or DELETE grant is issued — the table is append-only by design (ADR-0021).

Revision ID: 0013_audit_select_grant
Revises: 0012_consent_rls_policy
"""

from alembic import op

revision = "0013_audit_select_grant"
down_revision = "0012_consent_rls_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA audit TO ftm_medical_specialist;")
    op.execute("GRANT SELECT ON audit.event_log TO ftm_medical_specialist;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON audit.event_log FROM ftm_medical_specialist;")
    op.execute("REVOKE USAGE ON SCHEMA audit FROM ftm_medical_specialist;")
