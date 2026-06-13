import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ExerciseRecording(Base):
    __tablename__ = "exercise_recording"
    __table_args__ = {"schema": "recording"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_exercise_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    storage_uri = Column(String, nullable=False)        # key en el bucket
    content_type = Column(String, default="audio/wav")
    estado = Column(String, default="grabado")
    fecha = Column(DateTime, default=datetime.utcnow)
