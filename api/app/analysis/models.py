import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db import Base


class AnalysisSetup(Base):
    __tablename__ = "analysis_setup"
    __table_args__ = {"schema": "analysis"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    function_name = Column(String, nullable=False)        # funcion registrada en el backend
    function_params = Column(JSONB, default=dict)
    llm_io_contract = Column(JSONB, default=dict)
    prompt = Column(Text)


class AiInsight(Base):
    __tablename__ = "ai_insight"
    __table_args__ = {"schema": "analysis"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_metrics_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    output = Column(JSONB)
    model = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)
