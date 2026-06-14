import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base

SCHEMA = "clinical"


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"schema": SCHEMA}

    identity_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    role = Column(String, nullable=False)
    external_subject = Column(Text, unique=True)
    status = Column(Text, nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class Patient(Base):
    __tablename__ = "patient"
    __table_args__ = {"schema": SCHEMA}

    id = Column("patient_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.app_user.identity_id"), nullable=False)
    national_id = Column(Text, nullable=False)
    nombre = Column("first_name", Text, nullable=False)
    apellidos = Column("last_name", Text, nullable=False)
    birth_date = Column(DateTime, nullable=True)
    sex = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class Doctor(Base):
    __tablename__ = "doctor"
    __table_args__ = {"schema": SCHEMA}

    id = Column("doctor_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.app_user.identity_id"), nullable=False)
    colegiado_id = Column(Text, nullable=False)
    doctor_type = Column(String, nullable=False, default="gp")
    nombre = Column("first_name", Text, nullable=False)
    apellidos = Column("last_name", Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class CareAssignment(Base):
    """Legacy API-local relationship table.

    The SDD/ERD database does not have this table; new DB-backed code should
    authorize through clinical.app_user + clinical.doctor instead. This class is
    kept temporarily so older isolated unit tests and legacy router code import.
    """
    __tablename__ = "care_assignment"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_keycloak_id = Column(String, index=True, nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.patient_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Diagnostic(Base):
    __tablename__ = "diagnostic"
    __table_args__ = {"schema": SCHEMA}

    id = Column("diagnostic_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.patient_id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.doctor.doctor_id"), nullable=False)
    dolencia = Column(Text, nullable=False)
    descripcion = Column("description", Text)
    history = Column(Text)
    symptoms = Column(Text)
    signature = Column(Text, nullable=False)
    signed_at = Column(DateTime(timezone=True), server_default=text("now()"))
    content_hash = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))


class RehabProgram(Base):
    __tablename__ = "rehab_program"
    __table_args__ = {"schema": SCHEMA}

    id = Column("rehab_program_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.diagnostic.diagnostic_id"), nullable=False)
    physiotherapist_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.doctor.doctor_id"))
    name = Column(Text)
    estado = Column("status", String, nullable=False, default="active")
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))


class ProgramExercise(Base):
    __tablename__ = "program_exercise"
    __table_args__ = {"schema": SCHEMA}

    id = Column("program_exercise_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column("rehab_program_id", UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.rehab_program.rehab_program_id"), nullable=False)
    exercise_id = Column("rh_exercise_id", UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.rehab_exercise.rh_exercise_id"), nullable=False)
    pauta = Column("frequency", Text)
    estado = Column("status", String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class PseudonymMap(Base):
    """Mapeo pseudonimo<->paciente. Solo en 'clinical'. La IA nunca lo ve."""
    __tablename__ = "pseudonym_map"
    __table_args__ = {"schema": SCHEMA}

    patient_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.patient.patient_id"), primary_key=True)
    pseudonym_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
