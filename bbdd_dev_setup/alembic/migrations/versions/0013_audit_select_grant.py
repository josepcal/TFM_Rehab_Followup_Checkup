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
    # entity_id was NOT NULL in the baseline DDL but the middleware cannot know the
    # entity UUID at interception time — only the route handler does. Make it nullable
    # so the middleware can write rows without entity_id; handlers can pass it explicitly.
    op.execute("ALTER TABLE audit.event_log ALTER COLUMN entity_id DROP NOT NULL;")

    # ftm_app is the pool login user that writes audit rows (no SET LOCAL ROLE).
    # It needs USAGE + INSERT to write to audit.event_log.
    op.execute("GRANT USAGE ON SCHEMA audit TO ftm_app;")
    op.execute("GRANT INSERT ON audit.event_log TO ftm_app;")

    # ftm_medical_specialist is the DB role mapped to the admin app role.
    # It needs USAGE + SELECT to serve GET /iam/audit-log.
    op.execute("GRANT USAGE ON SCHEMA audit TO ftm_medical_specialist;")
    op.execute("GRANT SELECT ON audit.event_log TO ftm_medical_specialist;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON audit.event_log FROM ftm_medical_specialist;")
    op.execute("REVOKE USAGE ON SCHEMA audit FROM ftm_medical_specialist;")
    op.execute("REVOKE INSERT ON audit.event_log FROM ftm_app;")
    op.execute("REVOKE USAGE ON SCHEMA audit FROM ftm_app;")
    op.execute("ALTER TABLE audit.event_log ALTER COLUMN entity_id SET NOT NULL;")
