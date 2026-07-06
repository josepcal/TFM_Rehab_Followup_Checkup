"""Encrypt clinical.patient.national_id with application-layer Fernet encryption.

Changes:
- Adds national_id_enc (bytea) column
- Re-encrypts all existing plaintext national_id values using NATIONAL_ID_ENCRYPTION_KEY
- Drops the old national_id (text) column and renames national_id_enc -> national_id
- Removes the UNIQUE constraint (two Fernet ciphertexts of the same value differ;
  deduplication is enforced at application layer via national_id_hash if needed)

Requires NATIONAL_ID_ENCRYPTION_KEY env var to be set before running.

Revision ID: 0014_encrypt_national_id
Revises: 0013_audit_select_grant
"""

import os

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet

revision = "0014_encrypt_national_id"
down_revision = "0013_audit_select_grant"
branch_labels = None
depends_on = None


def _get_fernet() -> Fernet:
    key = os.environ.get("NATIONAL_ID_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "NATIONAL_ID_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def upgrade() -> None:
    fernet = _get_fernet()
    conn = op.get_bind()

    # 1. Add encrypted column alongside the existing plaintext column
    op.add_column(
        "patient",
        sa.Column("national_id_enc", sa.LargeBinary(), nullable=True),
        schema="clinical",
    )

    # 2. Re-encrypt each row in Python (never send plaintext to a SQL function)
    rows = conn.execute(
        sa.text("SELECT patient_id, national_id FROM clinical.patient")
    ).fetchall()

    for patient_id, plaintext in rows:
        if plaintext:
            ciphertext = fernet.encrypt(plaintext.encode())
            conn.execute(
                sa.text(
                    "UPDATE clinical.patient SET national_id_enc = :enc WHERE patient_id = :pid"
                ),
                {"enc": ciphertext, "pid": patient_id},
            )

    # 3. Make encrypted column NOT NULL now that all rows are populated
    op.alter_column("patient", "national_id_enc", nullable=False, schema="clinical")

    # 4. Drop the unique constraint on the old column (name from baseline DDL)
    op.drop_constraint("patient_national_id_key", "patient", schema="clinical")

    # 5. Drop old plaintext column and rename encrypted one
    op.drop_column("patient", "national_id", schema="clinical")
    op.alter_column(
        "patient", "national_id_enc",
        new_column_name="national_id",
        schema="clinical",
    )


def downgrade() -> None:
    fernet = _get_fernet()
    conn = op.get_bind()

    # Reverse: add text column, decrypt, swap back
    op.add_column(
        "patient",
        sa.Column("national_id_plain", sa.Text(), nullable=True),
        schema="clinical",
    )

    rows = conn.execute(
        sa.text("SELECT patient_id, national_id FROM clinical.patient")
    ).fetchall()

    for patient_id, ciphertext in rows:
        if ciphertext:
            plaintext = fernet.decrypt(bytes(ciphertext)).decode()
            conn.execute(
                sa.text(
                    "UPDATE clinical.patient SET national_id_plain = :plain WHERE patient_id = :pid"
                ),
                {"plain": plaintext, "pid": patient_id},
            )

    op.alter_column("patient", "national_id_plain", nullable=False, schema="clinical")
    op.drop_column("patient", "national_id", schema="clinical")
    op.alter_column(
        "patient", "national_id_plain",
        new_column_name="national_id",
        schema="clinical",
    )
    op.create_unique_constraint("patient_national_id_key", "patient", ["national_id"], schema="clinical")
