import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class DiagnosticAttestation:
    signature: str
    signed_at: datetime
    content_hash: str


def attest_diagnostic(
    *,
    patient_id: UUID,
    doctor_id: UUID,
    doctor_subject: str,
    colegiado_id: str,
    dolencia: str,
    descripcion: str | None,
    history: str | None = None,
    symptoms: str | None = None,
    signed_at: datetime | None = None,
) -> DiagnosticAttestation:
    """Create ADR-0012 MVP attestation metadata for a diagnostic.

    This is not a qualified electronic signature. It records doctor identity,
    timestamp, and an immutable hash of the signed clinical content.
    """
    signed_at = signed_at or datetime.now(timezone.utc)
    content_hash = diagnostic_content_hash(
        patient_id=patient_id,
        doctor_id=doctor_id,
        dolencia=dolencia,
        descripcion=descripcion,
        history=history,
        symptoms=symptoms,
    )
    signature = "|".join(
        [
            "mvp-attestation:v1",
            f"sub={doctor_subject}",
            f"colegiado={colegiado_id}",
            f"signed_at={signed_at.isoformat()}",
            f"content_hash={content_hash}",
        ]
    )
    return DiagnosticAttestation(signature=signature, signed_at=signed_at, content_hash=content_hash)


def diagnostic_content_hash(
    *,
    patient_id: UUID,
    doctor_id: UUID,
    dolencia: str,
    descripcion: str | None,
    history: str | None = None,
    symptoms: str | None = None,
) -> str:
    payload = {
        "patient_id": str(patient_id),
        "doctor_id": str(doctor_id),
        "dolencia": dolencia,
        "descripcion": descripcion or "",
        "history": history or "",
        "symptoms": symptoms or "",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
