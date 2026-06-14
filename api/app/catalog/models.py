import uuid

from sqlalchemy import Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class RehabExercise(Base):
    __tablename__ = "rehab_exercise"
    __table_args__ = {"schema": "clinical"}

    id = Column("rh_exercise_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column("type", String, nullable=False)
    descripcion = Column("description", Text)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    @property
    def tipo(self):
        return self.nombre

    @tipo.setter
    def tipo(self, value):
        self.nombre = value
