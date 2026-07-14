"""Add 'read' to the audit.action enum so sensitive GETs can be audited

The audit middleware only records mutations (create/update/delete). Read access
to clinical data — the vector for clinical snooping — left no trail. To audit a
GET honestly we need a matching action value; reusing 'create' would misrepresent
a read as a write and break compliance queries.

ADD VALUE cannot run inside a transaction block, and Alembic wraps each migration
in one, so we COMMIT first to leave it before altering the type.

Revision ID: 0017_audit_action_read
Revises: 0016_audit_outcome
"""

from alembic import op

revision = "0017_audit_action_read"
down_revision = "0016_audit_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Leave Alembic's transaction: ALTER TYPE ... ADD VALUE is not allowed inside one.
    op.execute("COMMIT")
    op.execute("ALTER TYPE audit.action ADD VALUE IF NOT EXISTS 'read'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value. A true rollback would recreate the
    # type without 'read', which requires rewriting every column that uses it — far
    # riskier than the additive change itself. The value is harmless if unused, so we
    # intentionally leave it in place.
    pass
