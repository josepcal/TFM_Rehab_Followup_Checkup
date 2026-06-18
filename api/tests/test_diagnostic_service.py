from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.clinical.diagnostic_domain import DiagnosticRecord
from app.clinical.diagnostic_service import DiagnosticService
from app.clinical.schemas import DiagnosticIn, DiagnosticPatchIn, ListQuery


@dataclass
class FakeDiagnosticRepository:
    diagnostic: DiagnosticRecord
    total: int = 1

    def __post_init__(self):
        self.calls = []

    def create_diagnostic(
        self,
        patient_id: UUID,
        dolencia: str,
        descripcion: str | None,
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        self.calls.append(("create_diagnostic", patient_id, dolencia, descripcion, history, symptoms, doctor_subject))
        return self.diagnostic

    def list_diagnostics(self, limit: int, offset: int, doctor_subject: str):
        self.calls.append(("list_diagnostics", limit, offset, doctor_subject))
        return [self.diagnostic], self.total

    def get_diagnostic(self, diagnostic_id: UUID, doctor_subject: str) -> DiagnosticRecord:
        self.calls.append(("get_diagnostic", diagnostic_id, doctor_subject))
        return self.diagnostic

    def update_diagnostic(
        self,
        diagnostic_id: UUID,
        dolencia: str | None,
        descripcion: str | None,
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        self.calls.append(("update_diagnostic", diagnostic_id, dolencia, descripcion, history, symptoms, doctor_subject))
        return self.diagnostic


def make_service():
    diagnostic = DiagnosticRecord(
        id=uuid4(),
        patient_id=uuid4(),
        doctor_id=uuid4(),
        dolencia="Dolor cervical",
        descripcion="Descripcion",
        history="Clinical history",
        symptoms="Pain, stiffness",
        signature="mvp-attestation:v1|sub=doctor-sub",
        signed_at=datetime.now(timezone.utc),
        content_hash="a" * 64,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    repo = FakeDiagnosticRepository(diagnostic=diagnostic)
    return DiagnosticService(repo), repo


@pytest.mark.uc("UC-01")
@pytest.mark.ac("Diagnostic-C-01", "Diagnostic-C-04", "Diagnostic-C-07", "Diagnostic-C-09")
def test_create_diagnostic_delegates_to_repository_and_returns_schema():
    """
    GIVEN a DiagnosticService with a fake repository and a valid DiagnosticIn request
    WHEN create_diagnostic is called for a doctor subject
    THEN it delegates to the repository and maps DiagnosticRecord to DiagnosticOut.
    """
    service, repo = make_service()

    response = service.create_diagnostic(
        DiagnosticIn(
            patient_id=repo.diagnostic.patient_id,
            dolencia="Dolor cervical",
            descripcion="Descripcion",
            history="Clinical history",
            symptoms="Pain, stiffness",
        ),
        "doctor-sub",
    )

    assert response.id == repo.diagnostic.id
    assert response.patient_id == repo.diagnostic.patient_id
    assert response.signature == repo.diagnostic.signature
    assert response.content_hash == "a" * 64
    assert response.history == "Clinical history"
    assert response.symptoms == "Pain, stiffness"
    assert repo.calls == [(
        "create_diagnostic",
        repo.diagnostic.patient_id,
        "Dolor cervical",
        "Descripcion",
        "Clinical history",
        "Pain, stiffness",
        "doctor-sub",
    )]


@pytest.mark.uc("UC-01")
@pytest.mark.ac("Diagnostic-R-03", "Diagnostic-R-07")
def test_list_diagnostics_applies_pagination_and_wraps_response():
    """
    GIVEN a DiagnosticService with a fake repository and a ListQuery dependency model
    WHEN list_diagnostics is called
    THEN it applies pagination and wraps DiagnosticOut items in a PaginatedResponse.
    """
    service, repo = make_service()

    response = service.list_diagnostics(ListQuery(limit=7, offset=3), "doctor-sub")

    assert response.total == 1
    assert response.limit == 7
    assert response.offset == 3
    assert [item.id for item in response.data] == [repo.diagnostic.id]
    assert repo.calls == [("list_diagnostics", 7, 3, "doctor-sub")]


@pytest.mark.uc("UC-01")
@pytest.mark.ac("Diagnostic-G-02", "Diagnostic-G-03", "Diagnostic-G-04")
def test_get_diagnostic_delegates_and_returns_diagnostic_out():
    """
    GIVEN a DiagnosticService with a fake repository and an existing diagnostic id
    WHEN get_diagnostic is called
    THEN it delegates authorization/loading to the repository and returns DiagnosticOut.
    """
    service, repo = make_service()

    response = service.get_diagnostic(repo.diagnostic.id, "doctor-sub")

    assert response.id == repo.diagnostic.id
    assert response.dolencia == repo.diagnostic.dolencia
    assert response.content_hash == repo.diagnostic.content_hash
    assert repo.calls == [("get_diagnostic", repo.diagnostic.id, "doctor-sub")]


@pytest.mark.uc("UC-01")
@pytest.mark.ac("Diagnostic-U-02", "Diagnostic-U-03", "Diagnostic-U-04", "Diagnostic-U-07")
def test_update_diagnostic_delegates_patch_fields():
    """
    GIVEN a DiagnosticService with a fake repository and a partial DiagnosticPatchIn request
    WHEN update_diagnostic is called for a doctor subject
    THEN it passes only provided patch fields and maps the returned DiagnosticRecord.
    """
    service, repo = make_service()

    response = service.update_diagnostic(
        repo.diagnostic.id,
        DiagnosticPatchIn(dolencia="Dolor actualizado"),
        "doctor-sub",
    )

    assert response.id == repo.diagnostic.id
    assert response.signature == repo.diagnostic.signature
    assert repo.calls == [("update_diagnostic", repo.diagnostic.id, "Dolor actualizado", None, None, None, "doctor-sub")]
