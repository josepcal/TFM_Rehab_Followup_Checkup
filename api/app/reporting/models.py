import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.db import Base


class ExerciseReport(Base):
    __tablename__ = "exercise_report"
    __table_args__ = {"schema": "reporting"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    metrics_id = Column(UUID(as_uuid=True), nullable=True)
    insight_id = Column(UUID(as_uuid=True), nullable=True)
    resumen = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class FollowupCheckup(Base):
    __tablename__ = "followup_checkup"
    __table_args__ = {"schema": "reporting"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    periodo = Column(String)
    report_ids = Column(ARRAY(UUID(as_uuid=True)))
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
