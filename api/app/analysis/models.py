import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID
from sqlalchemy.orm import relationship

from app.db import Base


class AnalysisSetup(Base):
    """SQL-first setup.analysis_setup mapping.

    The registered function name lives in ``metric_api_endpoint`` and is scoped
    to a concrete program exercise, matching ``bbdd_dev_setup``.
    """

    __tablename__ = "analysis_setup"
    __table_args__ = {"schema": "setup"}

    id = Column("analysis_setup_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_exercise_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical.program_exercise.program_exercise_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    description = Column(Text)
    type = Column(Text)
    metric_api_endpoint = Column(String, nullable=True)  # nombre registrado que resuelve el worker
    ai_model = Column(Text)
    ai_prompt = Column(Text)
    criteria = Column(Text)
    version = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))

    metric_definitions = relationship("MetricDefinition", back_populates="analysis_setup")


class MetricDefinition(Base):
    """SQL-first setup.metric_definition mapping used by worker/tests."""

    __tablename__ = "metric_definition"
    __table_args__ = {"schema": "setup"}

    metric_def_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_setup_id = Column(
        UUID(as_uuid=True),
        ForeignKey("setup.analysis_setup.analysis_setup_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path = Column(Text, nullable=False)
    label = Column(Text)
    section = Column(Text)
    value_kind = Column(Text, nullable=False, server_default=text("'raw'"))
    unit = Column(Text)
    data_type = Column(Text)
    nullable = Column(Boolean, nullable=False, server_default=text("false"))
    target_value = Column(DOUBLE_PRECISION)
    evaluation_criteria = Column(Text)
    display_order = Column(Integer)

    analysis_setup = relationship("AnalysisSetup", back_populates="metric_definitions")


class AiInsight(Base):
    __tablename__ = "ai_insight"
    __table_args__ = {"schema": "metrics"}
    id = Column("ai_insight_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("metrics.metric_result.result_id"), nullable=False)
    analysis_setup_id = Column(UUID(as_uuid=True), ForeignKey("setup.analysis_setup.analysis_setup_id"))
    model_used = Column(Text)
    prompt_used = Column(Text)
    insight_text = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow)
