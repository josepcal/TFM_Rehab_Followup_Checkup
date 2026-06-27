"""ORM models for follow-up check-ups (UC-09).

Maps to clinical.followup_checkup and clinical.followup_checkup_report.
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import PrimaryKeyConstraint

from app.db import Base

CLINICAL = "clinical"


class FollowupCheckup(Base):
    """ORM for clinical.followup_checkup (UC-09, FR-07, AC-14)."""

    __tablename__ = "followup_checkup"
    __table_args__ = {"schema": CLINICAL}

    followup_checkup_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rehab_program_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.rehab_program.rehab_program_id"),
        nullable=False,
    )
    # patient_id is derived server-side via RehabProgram → Diagnostic.patient_id
    # it is NEVER accepted from the request body
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    summary = Column(Text, nullable=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.doctor.doctor_id"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class FollowupCheckupReport(Base):
    """Junction table clinical.followup_checkup_report (N:N checkup <-> exercise_report)."""

    __tablename__ = "followup_checkup_report"
    __table_args__ = (
        PrimaryKeyConstraint("followup_checkup_id", "exercise_report_id"),
        {"schema": CLINICAL},
    )

    followup_checkup_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{CLINICAL}.followup_checkup.followup_checkup_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    exercise_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.exercise_report.exercise_report_id"),
        nullable=False,
    )
