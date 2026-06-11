import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base

SCHEMA = "clinical"


class Patient(Base):
    __tablename__ = "patient"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_id = Column(String, index=True, nullable=True)
    national_id = Column(String, nullable=True)   # cifrado a nivel de columna (TODO)
    nombre = Column(String)
    apellidos = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Doctor(Base):
    __tablename__ = "doctor"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_id = Column(String, index=True, nullable=False)
    colegiado_id = Column(String)
    nombre = Column(String)
    apellidos = Column(String)


class CareAssignment(Base):
    """Relacion terapeutica: la visibilidad RLS del medico se apoya en esto."""
    __tablename__ = "care_assignment"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_keycloak_id = Column(String, index=True, nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Diagnostic(Base):
    __tablename__ = "diagnostic"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.doctor.id"), nullable=False)
    dolencia = Column(String)
    descripcion = Column(Text)
    signature = Column(String, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RehabProgram(Base):
    __tablename__ = "rehab_program"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.diagnostic.id"), nullable=False)
    estado = Column(String, default="activo")
    created_at = Column(DateTime, default=datetime.utcnow)


class ProgramExercise(Base):
    __tablename__ = "program_exercise"
    __table_args__ = {"schema": SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.rehab_program.id"), nullable=False)
    exercise_id = Column(UUID(as_uuid=True), nullable=False)   # catalog.rehab_exercise.id
    pauta = Column(String)
    estado = Column(String, default="asignado")


class PseudonymMap(Base):
    """Mapeo pseudonimo<->paciente. Solo en 'clinical'. La IA nunca lo ve."""
    __tablename__ = "pseudonym_map"
    __table_args__ = {"schema": SCHEMA}
    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.id"), primary_key=True)
    pseudonym_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, index=True)
