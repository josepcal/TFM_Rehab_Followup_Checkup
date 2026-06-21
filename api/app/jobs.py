import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.db import Base


class AnalysisJob(Base):
    """Postgres-backed UC-06 analysis job queue row."""

    __tablename__ = "analysis_job"
    __table_args__ = {"schema": "metrics"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), nullable=False)
    function_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending | running | done | error
    attempts = Column(Integer, nullable=False, default=0)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def error(self) -> str | None:
        """Compatibility alias for the pre-Phase-2 worker."""
        return self.error_detail

    @error.setter
    def error(self, value: str | None) -> None:
        self.error_detail = value


def enqueue(session: Session, recording_id, function_name: str) -> AnalysisJob:
    """Enqueue a single pending analysis job without executing it inline."""
    job = AnalysisJob(recording_id=recording_id, function_name=function_name, status="pending")
    session.add(job)
    session.flush()
    return job


def claim_one(session: Session) -> AnalysisJob | None:
    """Claim one pending job using SELECT ... FOR UPDATE SKIP LOCKED.

    The caller must already be inside a transaction. The row is moved to
    ``running`` and locked until the caller commits/rolls back, allowing several
    worker processes to poll safely without processing the same job twice.
    """
    row = session.execute(
        text(
            """
            SELECT id
            FROM metrics.analysis_job
            WHERE status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
    ).first()
    if row is None:
        return None

    job = session.get(AnalysisJob, row[0])
    if job is None:
        return None

    job.status = "running"
    job.attempts = (job.attempts or 0) + 1
    job.locked_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    session.flush()
    return job
