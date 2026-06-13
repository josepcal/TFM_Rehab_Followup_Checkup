from uuid import uuid4

from app.clinical.models import Diagnostic
from app.clinical.schemas import DiagnosticIn, DiagnosticOut, DiagnosticPatchIn


def test_create_diagnostic_payload_and_response_shape():
    patient_id = uuid4()
    payload = DiagnosticIn(
        patient_id=patient_id,
        dolencia="Test Dolencia",
        descripcion="Descripcion",
    )

    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=payload.patient_id,
        dolencia=payload.dolencia,
        descripcion=payload.descripcion,
    )

    response = DiagnosticOut(
        id=diagnostic.id,
        patient_id=diagnostic.patient_id,
        dolencia=diagnostic.dolencia,
        descripcion=diagnostic.descripcion,
    )

    assert response.patient_id == patient_id
    assert response.dolencia == "Test Dolencia"
    assert response.descripcion == "Descripcion"


def test_patch_diagnostic_updates_only_supplied_fields():
    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=uuid4(),
        dolencia="Dolencia original",
        descripcion="Descripcion original",
    )
    patch = DiagnosticPatchIn(dolencia="Dolencia Actualizada")

    if patch.dolencia is not None:
        diagnostic.dolencia = patch.dolencia
    if patch.descripcion is not None:
        diagnostic.descripcion = patch.descripcion

    assert diagnostic.dolencia == "Dolencia Actualizada"
    assert diagnostic.descripcion == "Descripcion original"
