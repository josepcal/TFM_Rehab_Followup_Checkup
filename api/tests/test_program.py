from uuid import uuid4

from app.clinical.models import ProgramExercise, RehabProgram
from app.clinical.schemas import ProgramExerciseIn, ProgramExerciseOut, ProgramIn, ProgramOut


def test_create_program_payload_and_response_shape():
    diagnostic_id = uuid4()
    payload = ProgramIn(diagnostic_id=diagnostic_id, estado="activo")

    program = RehabProgram(id=uuid4(), diagnostic_id=payload.diagnostic_id, estado=payload.estado)
    response = ProgramOut(id=program.id, diagnostic_id=program.diagnostic_id, estado=program.estado)

    assert response.diagnostic_id == diagnostic_id
    assert response.estado == "activo"


def test_assign_exercise_payload_and_response_shape():
    program_id = uuid4()
    payload = ProgramExerciseIn(exercise_id=uuid4(), pauta="Pauta de prueba")

    assignment = ProgramExercise(
        id=uuid4(),
        program_id=program_id,
        exercise_id=payload.exercise_id,
        pauta=payload.pauta,
    )
    response = ProgramExerciseOut(
        id=assignment.id,
        program_id=assignment.program_id,
        exercise_id=assignment.exercise_id,
        pauta=assignment.pauta,
    )

    assert response.program_id == program_id
    assert response.exercise_id == payload.exercise_id
    assert response.pauta == "Pauta de prueba"
