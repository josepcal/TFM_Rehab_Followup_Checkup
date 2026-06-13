import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db import Base


class RecordingMetrics(Base):
    """Sin PII: referenciado por pseudonimo. Es lo unico que la IA puede leer."""
    __tablename__ = "recording_metrics"
    __table_args__ = {"schema": "metrics"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    pseudonym_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    function_name = Column(String, nullable=False)
    metrics = Column(JSONB, nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow)
