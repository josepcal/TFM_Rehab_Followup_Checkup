import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, ENUM, JSONB, UUID

from app.db import Base


result_status_t = ENUM(
    "success",
    "error",
    name="result_status",
    schema="metrics",
    create_type=False,
)


class MetricResult(Base):
    """Current analysis result for one recording, stored under a pseudonym."""

    __tablename__ = "metric_result"
    __table_args__ = (
        CheckConstraint(
            "status <> 'success' OR raw_json IS NOT NULL",
            name="ck_metric_result_rawjson_present",
        ),
        {"schema": "metrics"},
    )

    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recording.exercise_recording.recording_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Deliberately no FK: deleting the identity map anonymizes retained metrics.
    pseudonym_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    analysis_setup_id = Column(
        UUID(as_uuid=True),
        ForeignKey("setup.analysis_setup.analysis_setup_id"),
        nullable=True,
    )
    result_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    raw_json = Column(JSONB, nullable=True)
    function_name = Column(Text, nullable=True)
    function_version = Column(Text, nullable=True)
    code_sha = Column(Text, nullable=True)
    status = Column(result_status_t, nullable=False, server_default=text("'success'"))
    error_detail = Column(Text, nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    @property
    def id(self) -> uuid.UUID | None:
        """Compatibility alias for the previous API-local model."""
        return self.result_id

    @property
    def metrics(self) -> dict[str, Any] | None:
        """Compatibility alias while the Phase 2 worker migrates to raw_json."""
        return self.raw_json

    @metrics.setter
    def metrics(self, value: dict[str, Any] | None) -> None:
        self.raw_json = value


class RecordingMetric(Base):
    """Flattened metric value retained alongside the verbatim result JSON."""

    __tablename__ = "recording_metric"
    __table_args__ = {"schema": "metrics"}

    recording_metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("metrics.metric_result.result_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_def_id = Column(
        UUID(as_uuid=True),
        ForeignKey("setup.metric_definition.metric_def_id"),
        nullable=True,
        index=True,
    )
    metric_path = Column(Text, nullable=False)
    value_num = Column(DOUBLE_PRECISION, nullable=True)
    value_text = Column(Text, nullable=True)
    is_null = Column(Boolean, nullable=False, server_default=text("false"))


# Temporary import compatibility for the legacy worker/router. Phase 2 will use
# MetricResult directly; both names map to the canonical SQL-first table.
RecordingMetrics = MetricResult
