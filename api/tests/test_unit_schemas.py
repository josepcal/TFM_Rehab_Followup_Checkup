import pytest
from pydantic import ValidationError
from uuid import UUID, uuid4
from app.clinical.schemas import DiagnosticIn, DiagnosticPatchIn

def test_diagnostic_in_valid():
    valid_data = {
        "patient_id": uuid4(),
        "dolencia": "A" * 10,
        "descripcion": "Desc"
    }
    diag = DiagnosticIn(**valid_data)
    assert diag.patient_id == valid_data["patient_id"]
    assert diag.dolencia == "A" * 10
    assert diag.descripcion == "Desc"

@pytest.mark.parametrize("dolencia", ["", "A" * 501])
def test_diagnostic_in_invalid_dolencia(dolencia):
    data = {
        "patient_id": uuid4(),
        "dolencia": dolencia
    }
    with pytest.raises(ValidationError):
        DiagnosticIn(**data)

@pytest.mark.parametrize("descripcion", ["A" * 5001])
def test_diagnostic_in_invalid_descripcion(descripcion):
    data = {
        "patient_id": uuid4(),
        "dolencia": "Valid",
        "descripcion": descripcion
    }
    with pytest.raises(ValidationError):
        DiagnosticIn(**data)

@pytest.mark.parametrize("dolencia", ["", "A" * 501])
def test_diagnostic_patch_in_invalid_dolencia(dolencia):
    data = {
        "dolencia": dolencia
    }
    with pytest.raises(ValidationError):
        DiagnosticPatchIn(**data)

@pytest.mark.parametrize("descripcion", ["A" * 5001])
def test_diagnostic_patch_in_invalid_descripcion(descripcion):
    data = {
        "descripcion": descripcion
    }
    with pytest.raises(ValidationError):
        DiagnosticPatchIn(**data)
