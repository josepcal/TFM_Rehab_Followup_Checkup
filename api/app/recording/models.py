import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.db import Base


media_kind_t = ENUM("audio", "video", name="media_kind", schema="recording", create_type=False)
media_status_t = ENUM("available", "deleted", "quarantined", name="media_status", schema="recording", create_type=False)


class ExerciseRecording(Base):
    __tablename__ = "exercise_recording"
    __table_args__ = {"schema": "recording"}

    recording_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_exercise_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recorded_by = Column(UUID(as_uuid=True), nullable=True)
    media_kind = Column(media_kind_t, nullable=False)
    media_uri = Column(Text, nullable=True)  # key en el bucket/repositorio de media
    media_status = Column(media_status_t, nullable=False, default="available")
    recording_date = Column(Date, nullable=False, default=date.today)
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    @property
    def id(self):
        """Compatibilidad con código legado que esperaba `id`."""
        return self.recording_id

    @property
    def storage_uri(self):
        """Compatibilidad con la API/worker anterior: storage_uri == media_uri."""
        return self.media_uri

    @storage_uri.setter
    def storage_uri(self, value):
        self.media_uri = value
