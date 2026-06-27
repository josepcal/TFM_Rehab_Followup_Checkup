from sqlalchemy import Column, Date, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import PrimaryKeyConstraint

from app.db import Base

# Re-export the canonical AiInsight ORM from analysis.models so consumers
# can import it from this module without creating a duplicate table definition.
from app.analysis.models import AiInsight  # noqa: F401

CLINICAL = "clinical"
METRICS = "metrics"


class ExerciseReport(Base):
    """ORM for clinical.exercise_report (UC-07 / UC-08, D14)."""

    __tablename__ = "exercise_report"
    __table_args__ = {"schema": CLINICAL}

    exercise_report_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rehab_program_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.rehab_program.rehab_program_id"),
        nullable=False,
    )
    program_exercise_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.program_exercise.program_exercise_id"),
        nullable=True,
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    summary = Column(Text, nullable=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.doctor.doctor_id"),
        nullable=True,
    )
    attested_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ExerciseReportRecording(Base):
    """Junction table clinical.exercise_report_recording (N:N report <-> recording)."""

    __tablename__ = "exercise_report_recording"
    __table_args__ = (
        PrimaryKeyConstraint("exercise_report_id", "recording_id"),
        {"schema": CLINICAL},
    )

    exercise_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CLINICAL}.exercise_report.exercise_report_id", ondelete="CASCADE"),
        nullable=False,
    )
    recording_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recording.exercise_recording.recording_id"),
        nullable=False,
    )


