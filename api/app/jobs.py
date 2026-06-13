import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_job"
    __table_args__ = {"schema": "metrics"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), nullable=False)
    function_name = Column(String, nullable=False)
    status = Column(String, default="pending")     # pending | running | done | error
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def enqueue(session, recording_id, function_name) -> AnalysisJob:
    job = AnalysisJob(recording_id=recording_id, function_name=function_name)
    session.add(job)
    session.flush()
    return job


def claim_one(session) -> AnalysisJob | None:
    """Toma un job pendiente con FOR UPDATE SKIP LOCKED (varios workers seguros)."""
    row = session.execute(text(
        """
        SELECT id FROM metrics.analysis_job
        WHERE status = 'pending'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """
    )).first()
    if not row:
        return None
    job = session.get(AnalysisJob, row[0])
    job.status = "running"
    session.flush()
    return job
