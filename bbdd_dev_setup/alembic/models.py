"""Modelo de datos FTM — Medical Rehab Follow-up Check-up Tool.

Modelos SQLAlchemy 2.0 (estilo Mapped) para PostgreSQL, derivados del SDD v1.3
y equivalentes a ftm_schema.sql. Organizado en 5 esquemas:

    clinical  -> espacio "Patient data"
    setup     -> espacio "Recording Analysis Setup"
    recording -> espacio "Exercise Recording"
    metrics   -> espacio "Exercise Recording metrics"
    audit     -> monitorizacion de eventos (FR-15 / UC-15)

Uso:
    pip install "sqlalchemy>=2.0" "psycopg[binary]"
    python models.py "postgresql+psycopg://user:pass@localhost/ftm"
"""

from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DDL, ForeignKey, Index, Integer,
    Text, UniqueConstraint, event, func, text,
)
from sqlalchemy.dialects.postgresql import (
    DOUBLE_PRECISION, ENUM, JSONB, TIMESTAMP, UUID,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tipos enumerados
# ---------------------------------------------------------------------------
class UserRole(enum.Enum):
    medical = "medical"
    patient = "patient"
    administrator = "administrator"
    technician = "technician"


class DoctorType(enum.Enum):
    gp = "gp"
    medical_specialist = "medical_specialist"
    medical_technical_specialist = "medical_technical_specialist"
    physiotherapist = "physiotherapist"


class ProgramStatus(enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class MediaKind(enum.Enum):
    audio = "audio"
    video = "video"


class MediaStatus(enum.Enum):
    available = "available"
    purged = "purged"
    corrupt = "corrupt"


class AuditAction(enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"


class MetricValueKind(enum.Enum):
    raw = "raw"
    derived = "derived"


class Sex(enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    unspecified = "unspecified"


class NormDirection(enum.Enum):
    higher_better = "higher_better"
    lower_better = "lower_better"
    in_range = "in_range"


class ResultStatus(enum.Enum):
    success = "success"
    error = "error"


_vals = lambda e: [m.value for m in e]  # noqa: E731 (usar los valores, no los nombres)

user_role_t = ENUM(UserRole, name="user_role", schema="clinical", values_callable=_vals, create_type=True)
doctor_type_t = ENUM(DoctorType, name="doctor_type", schema="clinical", values_callable=_vals, create_type=True)
program_status_t = ENUM(ProgramStatus, name="program_status", schema="clinical", values_callable=_vals, create_type=True)
media_kind_t = ENUM(MediaKind, name="media_kind", schema="recording", values_callable=_vals, create_type=True)
media_status_t = ENUM(MediaStatus, name="media_status", schema="recording", values_callable=_vals, create_type=True)
audit_action_t = ENUM(AuditAction, name="action", schema="audit", values_callable=_vals, create_type=True)
metric_value_kind_t = ENUM(MetricValueKind, name="metric_value_kind", schema="setup", values_callable=_vals, create_type=True)
sex_t = ENUM(Sex, name="sex", schema="clinical", values_callable=_vals, create_type=True)
norm_direction_t = ENUM(NormDirection, name="norm_direction", schema="reference", values_callable=_vals, create_type=True)
result_status_t = ENUM(ResultStatus, name="result_status", schema="metrics", values_callable=_vals, create_type=True)


# Atajos para columnas repetidas
def pk_uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def created() -> Mapped[datetime.datetime]:
    return mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


# ===========================================================================
# Esquema clinical (espacio "Patient data")
# ===========================================================================
class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"schema": "clinical"}

    identity_id: Mapped[uuid.UUID] = pk_uuid()
    role: Mapped[UserRole] = mapped_column(user_role_t, nullable=False)
    external_subject: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime.datetime] = created()

    patient: Mapped[Optional["Patient"]] = relationship(back_populates="user", uselist=False)
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="user", uselist=False)


class Patient(Base):
    __tablename__ = "patient"
    __table_args__ = {"schema": "clinical"}

    patient_id: Mapped[uuid.UUID] = pk_uuid()
    identity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.app_user.identity_id"), nullable=False, unique=True)
    national_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    sex: Mapped[Optional[Sex]] = mapped_column(sex_t)
    created_at: Mapped[datetime.datetime] = created()

    user: Mapped["AppUser"] = relationship(back_populates="patient")
    diagnostics: Mapped[list["Diagnostic"]] = relationship(back_populates="patient")
    consents: Mapped[list["PatientConsent"]] = relationship(back_populates="patient")
    followups: Mapped[list["FollowupCheckup"]] = relationship(back_populates="patient")
    pseudonym: Mapped[Optional["PseudonymMap"]] = relationship(
        back_populates="patient", uselist=False)


class PseudonymMap(Base):
    """Mapa paciente <-> pseudónimo. Vive en la zona identificada (clinical),
    protegido por RLS; el rol de IA NO tiene acceso. Es el ÚNICO punto donde
    existe el vínculo identidad<->pseudónimo. Borrar esta fila (derecho al olvido)
    deja las métricas de ese pseudónimo de facto anónimas (no relinkables)."""
    __tablename__ = "pseudonym_map"
    __table_args__ = {"schema": "clinical"}

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.patient.patient_id"), primary_key=True)
    pseudonym_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True,
        server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime.datetime] = created()

    patient: Mapped["Patient"] = relationship(back_populates="pseudonym")


class Doctor(Base):
    __tablename__ = "doctor"
    __table_args__ = {"schema": "clinical"}

    doctor_id: Mapped[uuid.UUID] = pk_uuid()
    identity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.app_user.identity_id"), nullable=False, unique=True)
    colegiado_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    doctor_type: Mapped[DoctorType] = mapped_column(doctor_type_t, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = created()

    user: Mapped["AppUser"] = relationship(back_populates="doctor")
    signed_diagnostics: Mapped[list["Diagnostic"]] = relationship(back_populates="doctor")


class Diagnostic(Base):
    __tablename__ = "diagnostic"
    __table_args__ = {"schema": "clinical"}

    diagnostic_id: Mapped[uuid.UUID] = pk_uuid()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.patient.patient_id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.doctor.doctor_id"), nullable=False, index=True)
    dolencia: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    history: Mapped[Optional[str]] = mapped_column(Text)
    symptoms: Mapped[Optional[str]] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime.datetime] = created()
    content_hash: Mapped[Optional[str]] = mapped_column(Text)  # hash inmutable del contenido firmado
    created_at: Mapped[datetime.datetime] = created()
    updated_at: Mapped[datetime.datetime] = created()

    patient: Mapped["Patient"] = relationship(back_populates="diagnostics")
    doctor: Mapped["Doctor"] = relationship(back_populates="signed_diagnostics")
    rehab_programs: Mapped[list["RehabProgram"]] = relationship(back_populates="diagnostic")


class RehabProgram(Base):
    __tablename__ = "rehab_program"
    __table_args__ = {"schema": "clinical"}

    rehab_program_id: Mapped[uuid.UUID] = pk_uuid()
    diagnostic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.diagnostic.diagnostic_id"), nullable=False, index=True)
    physiotherapist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clinical.doctor.doctor_id"))
    name: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ProgramStatus] = mapped_column(program_status_t, nullable=False, server_default=text("'active'"))
    start_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = created()
    updated_at: Mapped[datetime.datetime] = created()

    diagnostic: Mapped["Diagnostic"] = relationship(back_populates="rehab_programs")
    physiotherapist: Mapped[Optional["Doctor"]] = relationship(foreign_keys=[physiotherapist_id])
    program_exercises: Mapped[list["ProgramExercise"]] = relationship(back_populates="rehab_program")
    consents: Mapped[list["PatientConsent"]] = relationship(back_populates="rehab_program")
    reports: Mapped[list["ExerciseReport"]] = relationship(back_populates="rehab_program")
    followups: Mapped[list["FollowupCheckup"]] = relationship(back_populates="rehab_program")


class RehabExercise(Base):
    __tablename__ = "rehab_exercise"
    __table_args__ = {"schema": "clinical"}

    rh_exercise_id: Mapped[uuid.UUID] = pk_uuid()
    type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("clinical.doctor.doctor_id"))
    created_at: Mapped[datetime.datetime] = created()

    program_exercises: Mapped[list["ProgramExercise"]] = relationship(back_populates="rehab_exercise")


class ProgramExercise(Base):
    __tablename__ = "program_exercise"
    __table_args__ = {"schema": "clinical"}

    program_exercise_id: Mapped[uuid.UUID] = pk_uuid()
    rehab_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.rehab_program.rehab_program_id"), nullable=False, index=True)
    rh_exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.rehab_exercise.rh_exercise_id"), nullable=False, index=True)
    frequency: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime.datetime] = created()

    rehab_program: Mapped["RehabProgram"] = relationship(back_populates="program_exercises")
    rehab_exercise: Mapped["RehabExercise"] = relationship(back_populates="program_exercises")
    analysis_setup: Mapped[Optional["AnalysisSetup"]] = relationship(back_populates="program_exercise", uselist=False)
    recordings: Mapped[list["ExerciseRecording"]] = relationship(back_populates="program_exercise")


class PatientConsent(Base):
    __tablename__ = "patient_consent"
    __table_args__ = (
        UniqueConstraint("patient_id", "rehab_program_id", name="uq_consent_patient_program"),
        {"schema": "clinical"},
    )

    consent_id: Mapped[uuid.UUID] = pk_uuid()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.patient.patient_id"), nullable=False)
    rehab_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.rehab_program.rehab_program_id"), nullable=False, index=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    granted_at: Mapped[datetime.datetime] = created()
    withdrawn_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True))

    patient: Mapped["Patient"] = relationship(back_populates="consents")
    rehab_program: Mapped["RehabProgram"] = relationship(back_populates="consents")


class ExerciseReport(Base):
    __tablename__ = "exercise_report"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_report_period"),
        {"schema": "clinical"},
    )

    exercise_report_id: Mapped[uuid.UUID] = pk_uuid()
    rehab_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.rehab_program.rehab_program_id"), nullable=False, index=True)
    program_exercise_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clinical.program_exercise.program_exercise_id"))
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("clinical.doctor.doctor_id"))
    attested_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True))
    attested_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("clinical.doctor.doctor_id"))
    content_hash: Mapped[Optional[str]] = mapped_column(Text)  # hash inmutable del informe atestado
    created_at: Mapped[datetime.datetime] = created()

    rehab_program: Mapped["RehabProgram"] = relationship(back_populates="reports")
    recording_links: Mapped[list["ExerciseReportRecording"]] = relationship(back_populates="report")


class FollowupCheckup(Base):
    __tablename__ = "followup_checkup"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_checkup_period"),
        {"schema": "clinical"},
    )

    followup_checkup_id: Mapped[uuid.UUID] = pk_uuid()
    rehab_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.rehab_program.rehab_program_id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.patient.patient_id"), nullable=False, index=True)
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("clinical.doctor.doctor_id"))
    created_at: Mapped[datetime.datetime] = created()

    rehab_program: Mapped["RehabProgram"] = relationship(back_populates="followups")
    patient: Mapped["Patient"] = relationship(back_populates="followups")
    report_links: Mapped[list["FollowupCheckupReport"]] = relationship(back_populates="checkup")


class FollowupCheckupReport(Base):
    """Union N:N follow-up <-> reportes agregados."""
    __tablename__ = "followup_checkup_report"
    __table_args__ = {"schema": "clinical"}

    followup_checkup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.followup_checkup.followup_checkup_id", ondelete="CASCADE"), primary_key=True)
    exercise_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.exercise_report.exercise_report_id"), primary_key=True)

    checkup: Mapped["FollowupCheckup"] = relationship(back_populates="report_links")
    report: Mapped["ExerciseReport"] = relationship()


class ExerciseReportRecording(Base):
    """Union N:N (cruzada con recording) reporte <-> grabacion.

    El vinculo persiste aunque la grabacion se marque como borrada (UC-13).
    """
    __tablename__ = "exercise_report_recording"
    __table_args__ = {"schema": "clinical"}

    exercise_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.exercise_report.exercise_report_id", ondelete="CASCADE"), primary_key=True)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recording.exercise_recording.recording_id"), primary_key=True)

    report: Mapped["ExerciseReport"] = relationship(back_populates="recording_links")
    recording: Mapped["ExerciseRecording"] = relationship(back_populates="report_links")


# ===========================================================================
# Esquema setup (espacio "Recording Analysis Setup")
# ===========================================================================
class AnalysisSetup(Base):
    __tablename__ = "analysis_setup"
    __table_args__ = {"schema": "setup"}

    analysis_setup_id: Mapped[uuid.UUID] = pk_uuid()
    program_exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.program_exercise.program_exercise_id"), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[Optional[str]] = mapped_column(Text)
    metric_api_endpoint: Mapped[Optional[str]] = mapped_column(Text)
    ai_model: Mapped[Optional[str]] = mapped_column(Text)
    ai_prompt: Mapped[Optional[str]] = mapped_column(Text)
    criteria: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime.datetime] = created()
    updated_at: Mapped[datetime.datetime] = created()

    program_exercise: Mapped["ProgramExercise"] = relationship(back_populates="analysis_setup")
    metric_definitions: Mapped[list["MetricDefinition"]] = relationship(
        back_populates="analysis_setup", cascade="all, delete-orphan")
    results: Mapped[list["MetricResult"]] = relationship(back_populates="analysis_setup")
    insights: Mapped[list["AiInsight"]] = relationship(back_populates="analysis_setup")


class MetricDefinition(Base):
    __tablename__ = "metric_definition"
    __table_args__ = (
        UniqueConstraint("analysis_setup_id", "path", name="uq_metricdef_setup_path"),
        {"schema": "setup"},
    )

    metric_def_id: Mapped[uuid.UUID] = pk_uuid()
    analysis_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setup.analysis_setup.analysis_setup_id", ondelete="CASCADE"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)              # p.ej. 'domains.voice_stability'
    label: Mapped[Optional[str]] = mapped_column(Text)
    section: Mapped[Optional[str]] = mapped_column(Text)                 # 'domains' | 'raw' | ...
    value_kind: Mapped[MetricValueKind] = mapped_column(
        metric_value_kind_t, nullable=False, server_default=text("'raw'"))
    unit: Mapped[Optional[str]] = mapped_column(Text)
    data_type: Mapped[Optional[str]] = mapped_column(Text)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    target_value: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    evaluation_criteria: Mapped[Optional[str]] = mapped_column(Text)
    display_order: Mapped[Optional[int]] = mapped_column(Integer)

    analysis_setup: Mapped["AnalysisSetup"] = relationship(back_populates="metric_definitions")
    values: Mapped[list["RecordingMetric"]] = relationship(back_populates="definition")
    compositions: Mapped[list["MetricComposition"]] = relationship(
        back_populates="parent", foreign_keys="MetricComposition.parent_metric_def_id",
        cascade="all, delete-orphan")


class MetricComposition(Base):
    """Composicion ponderada: una metrica derivada se compone de otras (pesos).

    Materializa la "ponderacion de metricas" del objetivo del sistema:
    valor(derivada) = sum(weight_i * valor(hija_i)).
    """
    __tablename__ = "metric_composition"
    __table_args__ = (
        CheckConstraint("parent_metric_def_id <> child_metric_def_id", name="ck_composition_no_self"),
        {"schema": "setup"},
    )

    parent_metric_def_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setup.metric_definition.metric_def_id", ondelete="CASCADE"), primary_key=True)
    child_metric_def_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setup.metric_definition.metric_def_id"), primary_key=True)
    weight: Mapped[float] = mapped_column(DOUBLE_PRECISION, nullable=False)

    parent: Mapped["MetricDefinition"] = relationship(
        foreign_keys=[parent_metric_def_id], back_populates="compositions")
    child: Mapped["MetricDefinition"] = relationship(foreign_keys=[child_metric_def_id])


# ===========================================================================
# Esquema recording (espacio "Exercise Recording")
# ===========================================================================
class ExerciseRecording(Base):
    __tablename__ = "exercise_recording"
    __table_args__ = (
        Index("idx_recording_active", "program_exercise_id",
              postgresql_where=text("is_deleted = false")),
        {"schema": "recording"},
    )

    recording_id: Mapped[uuid.UUID] = pk_uuid()
    program_exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical.program_exercise.program_exercise_id"), nullable=False, index=True)
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clinical.app_user.identity_id"))
    media_kind: Mapped[MediaKind] = mapped_column(media_kind_t, nullable=False)
    media_uri: Mapped[Optional[str]] = mapped_column(Text)
    media_status: Mapped[MediaStatus] = mapped_column(
        media_status_t, nullable=False, server_default=text("'available'"))
    recording_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    sha256: Mapped[Optional[str]] = mapped_column(Text)  # integridad del fichero subido
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime.datetime] = created()

    program_exercise: Mapped["ProgramExercise"] = relationship(back_populates="recordings")
    recorded_by_user: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[recorded_by])
    result: Mapped[Optional["MetricResult"]] = relationship(back_populates="recording", uselist=False)
    report_links: Mapped[list["ExerciseReportRecording"]] = relationship(back_populates="recording")


# ===========================================================================
# Esquema metrics (espacio "Exercise Recording metrics")
# Doble almacenamiento: JSON integro (metric_result.raw_json) + valores
# aplanados de las metricas seguidas (recording_metric).
# ===========================================================================
class MetricResult(Base):
    """Una fila por ejecucion del analisis sobre una grabacion.

    Guarda el JSON completo de la API (fidelidad total, claves dinamicas como
    per_place) ademas de la fecha y la nota del resultado.
    """
    __tablename__ = "metric_result"
    __table_args__ = (
        Index("idx_metric_result_json", "raw_json", postgresql_using="gin"),
        CheckConstraint("status <> 'success' OR raw_json IS NOT NULL",
                        name="ck_metric_result_rawjson_present"),
        {"schema": "metrics"},
    )

    result_id: Mapped[uuid.UUID] = pk_uuid()
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recording.exercise_recording.recording_id"), nullable=False, unique=True)
    pseudonym_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True)  # sin FK: borrar el mapa -> métricas anónimas
    analysis_setup_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("setup.analysis_setup.analysis_setup_id"))
    result_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(Text)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB)  # nullable: en error puede no haber JSON
    function_name: Mapped[Optional[str]] = mapped_column(Text)     # función ejecutada (snapshot)
    function_version: Mapped[Optional[str]] = mapped_column(Text)  # versión semántica (p. ej. '1.0')
    code_sha: Mapped[Optional[str]] = mapped_column(Text)          # commit desplegado (cadena de custodia)
    status: Mapped[ResultStatus] = mapped_column(
        result_status_t, nullable=False, server_default=text("'success'"))
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    extracted_at: Mapped[datetime.datetime] = created()

    recording: Mapped["ExerciseRecording"] = relationship(back_populates="result")
    analysis_setup: Mapped[Optional["AnalysisSetup"]] = relationship(back_populates="results")
    metrics: Mapped[list["RecordingMetric"]] = relationship(
        back_populates="result", cascade="all, delete-orphan")
    ai_insight: Mapped[Optional["AiInsight"]] = relationship(
        back_populates="result", uselist=False, cascade="all, delete-orphan")


class RecordingMetric(Base):
    """Valor aplanado de una metrica seguida, direccionado por path.

    metric_path se guarda como snapshot para sobrevivir a cambios del setup;
    metric_def_id es nullable por el mismo motivo. is_null marca nulos legitimos.
    """
    __tablename__ = "recording_metric"
    __table_args__ = {"schema": "metrics"}

    recording_metric_id: Mapped[uuid.UUID] = pk_uuid()
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metrics.metric_result.result_id", ondelete="CASCADE"), nullable=False, index=True)
    metric_def_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("setup.metric_definition.metric_def_id"), index=True)
    metric_path: Mapped[str] = mapped_column(Text, nullable=False)
    value_num: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    is_null: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    result: Mapped["MetricResult"] = relationship(back_populates="metrics")
    definition: Mapped[Optional["MetricDefinition"]] = relationship(back_populates="values")


class AiInsight(Base):
    """Interpretacion por IA de un metric_result (0..1 por resultado)."""
    __tablename__ = "ai_insight"
    __table_args__ = {"schema": "metrics"}

    ai_insight_id: Mapped[uuid.UUID] = pk_uuid()
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metrics.metric_result.result_id", ondelete="CASCADE"), nullable=False, unique=True)
    analysis_setup_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("setup.analysis_setup.analysis_setup_id"))
    model_used: Mapped[Optional[str]] = mapped_column(Text)
    prompt_used: Mapped[Optional[str]] = mapped_column(Text)
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime.datetime] = created()

    result: Mapped["MetricResult"] = relationship(back_populates="ai_insight")
    analysis_setup: Mapped[Optional["AnalysisSetup"]] = relationship(back_populates="insights")


# ===========================================================================
# Esquema audit (monitorizacion de eventos)
# ===========================================================================
class EventLog(Base):
    __tablename__ = "event_log"
    __table_args__ = (
        Index("idx_event_entity", "entity_type", "entity_id"),
        {"schema": "audit"},
    )

    event_id: Mapped[uuid.UUID] = pk_uuid()
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[AuditAction] = mapped_column(audit_action_t, nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clinical.app_user.identity_id"), index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime.datetime] = created()

    actor: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[actor_id])


# ===========================================================================
# Esquema reference (normas clinicas compartidas)
# ===========================================================================
class MetricNorm(Base):
    """Norma clinica por metrica, compartida entre pacientes (catalogo).

    Se enlaza por metric_code (= metric_definition.path), sin FK, porque es
    referencia independiente del setup. Estratificable por sexo/edad
    (NULL = comodin: aplica a cualquiera).
    """
    __tablename__ = "metric_norm"
    __table_args__ = (
        UniqueConstraint("metric_code", "sex", "age_min", "age_max", "version",
                         name="uq_metric_norm_strata"),
        CheckConstraint("age_min IS NULL OR age_max IS NULL OR age_min <= age_max",
                        name="ck_metric_norm_age"),
        Index("idx_metric_norm_code", "metric_code"),
        {"schema": "reference"},
    )

    norm_id: Mapped[uuid.UUID] = pk_uuid()
    metric_code: Mapped[str] = mapped_column(Text, nullable=False)   # = metric_definition.path
    label: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(Text)
    direction: Mapped[NormDirection] = mapped_column(norm_direction_t, nullable=False)
    sex: Mapped[Optional[Sex]] = mapped_column(sex_t)               # NULL = cualquier sexo
    age_min: Mapped[Optional[int]] = mapped_column(Integer)         # NULL = sin limite inferior
    age_max: Mapped[Optional[int]] = mapped_column(Integer)         # NULL = sin limite superior
    good_min: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)   # rango BUENO
    good_max: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    poor_min: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)   # rango POBRE
    poor_max: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    source: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime.datetime] = created()


# ---------------------------------------------------------------------------
# Creacion de extension y esquemas antes de las tablas
# ---------------------------------------------------------------------------
event.listen(Base.metadata, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
for _schema in ("clinical", "setup", "recording", "metrics", "audit", "reference"):
    event.listen(Base.metadata, "before_create", DDL(f"CREATE SCHEMA IF NOT EXISTS {_schema}"))


if __name__ == "__main__":
    import sys
    from sqlalchemy import create_engine

    url = sys.argv[1] if len(sys.argv) > 1 else "postgresql+psycopg://localhost/ftm"
    engine = create_engine(url, echo=True)
    Base.metadata.create_all(engine)
    print("Base de datos creada.")
