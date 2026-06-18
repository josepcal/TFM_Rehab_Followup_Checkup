from uuid import uuid4

from app.clinical.models import Diagnostic
from app.clinical.schemas import DiagnosticIn, DiagnosticOut, DiagnosticPatchIn


def test_create_diagnostic_payload_and_response_shape():
    patient_id = uuid4()
    payload = DiagnosticIn(
        patient_id=patient_id,
        dolencia="Test Dolencia",
        descripcion="Descripcion",
        history="History",
        symptoms="Pain, stiffness",
    )

    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=payload.patient_id,
        dolencia=payload.dolencia,
        descripcion=payload.descripcion,
        history=payload.history,
        symptoms=payload.symptoms,
    )

    response = DiagnosticOut(
        id=diagnostic.id,
        patient_id=diagnostic.patient_id,
        dolencia=diagnostic.dolencia,
        descripcion=diagnostic.descripcion,
        history=diagnostic.history,
        symptoms=diagnostic.symptoms,
    )

    assert response.patient_id == patient_id
    assert response.dolencia == "Test Dolencia"
    assert response.descripcion == "Descripcion"
    assert response.history == "History"
    assert response.symptoms == "Pain, stiffness"


def test_patch_diagnostic_updates_only_supplied_fields():
    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=uuid4(),
        dolencia="Dolencia original",
        descripcion="Descripcion original",
    )
    patch = DiagnosticPatchIn(dolencia="Dolencia Actualizada", history="Updated history")

    if patch.dolencia is not None:
        diagnostic.dolencia = patch.dolencia
    if patch.descripcion is not None:
        diagnostic.descripcion = patch.descripcion
    if patch.history is not None:
        diagnostic.history = patch.history
    if patch.symptoms is not None:
        diagnostic.symptoms = patch.symptoms

    assert diagnostic.dolencia == "Dolencia Actualizada"
    assert diagnostic.descripcion == "Descripcion original"
    assert diagnostic.history == "Updated history"
