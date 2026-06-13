import uuid

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class RehabExercise(Base):
    __tablename__ = "rehab_exercise"
    __table_args__ = {"schema": "catalog"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    descripcion = Column(Text)
    tipo = Column(String)
