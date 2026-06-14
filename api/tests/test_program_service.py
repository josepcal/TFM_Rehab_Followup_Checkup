from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.clinical.program_domain import ProgramExerciseRecord, ProgramRecord
from app.clinical.program_service import ProgramService
from app.clinical.schemas import ListQuery, ProgramExerciseIn, ProgramIn


@dataclass
class FakeProgramRepository:
    program: ProgramRecord
    assignment: ProgramExerciseRecord
    total: int = 1

    def __post_init__(self):
        self.calls = []

    def create_program(self, diagnostic_id: UUID, estado: str | None, doctor_subject: str) -> ProgramRecord:
        self.calls.append(("create_program", diagnostic_id, estado, doctor_subject))
        return self.program

    def list_programs(self, diagnostic_id: UUID, limit: int, offset: int, doctor_subject: str):
        self.calls.append(("list_programs", diagnostic_id, limit, offset, doctor_subject))
        return [self.program], self.total

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramRecord:
        self.calls.append(("get_program", program_id, doctor_subject))
        return self.program

    def assign_exercise(
        self,
        program_id: UUID,
        exercise_id: UUID,
        pauta: str | None,
        doctor_subject: str,
    ) -> ProgramExerciseRecord:
        self.calls.append(("assign_exercise", program_id, exercise_id, pauta, doctor_subject))
        return self.assignment


def make_service():
    program = ProgramRecord(
        id=uuid4(),
        diagnostic_id=uuid4(),
        estado="active",
        created_at=datetime.now(timezone.utc),
    )
    assignment = ProgramExerciseRecord(
        id=uuid4(),
        program_id=program.id,
        exercise_id=uuid4(),
        pauta="2 series",
        estado="active",
    )
    repo = FakeProgramRepository(program=program, assignment=assignment)
    return ProgramService(repo), repo


@pytest.mark.uc("UC-02")
@pytest.mark.ac("Program-C-02", "Program-C-03", "Program-C-05", "Program-C-06")
def test_create_program_delegates_to_repository_and_returns_schema():
    """
    GIVEN a ProgramService with a fake repository and a valid ProgramIn request
    WHEN create_program is called for a doctor subject
    THEN it delegates to the repository and maps the returned ProgramRecord to ProgramOut.
    """
    service, repo = make_service()

    response = service.create_program(ProgramIn(diagnostic_id=repo.program.diagnostic_id, estado="active"), "doctor-sub")

    assert response.id == repo.program.id
    assert response.diagnostic_id == repo.program.diagnostic_id
    assert response.estado == "active"
    assert repo.calls == [("create_program", repo.program.diagnostic_id, "active", "doctor-sub")]


@pytest.mark.uc("UC-02")
@pytest.mark.ac("Program-R-03", "Program-R-04", "Program-R-06")
def test_list_programs_applies_pagination_and_wraps_response():
    """
    GIVEN a ProgramService with a fake repository and a ListQuery dependency model
    WHEN list_programs is called
    THEN it applies pagination and wraps ProgramOut items in a PaginatedResponse.
    """
    service, repo = make_service()

    response = service.list_programs(repo.program.diagnostic_id, ListQuery(limit=10, offset=5), "doctor-sub")

    assert response.total == 1
    assert response.limit == 10
    assert response.offset == 5
    assert [item.id for item in response.data] == [repo.program.id]
    assert repo.calls == [("list_programs", repo.program.diagnostic_id, 10, 5, "doctor-sub")]


@pytest.mark.uc("UC-02")
@pytest.mark.ac("Program-G-02", "Program-G-03", "Program-G-04")
def test_get_program_delegates_and_returns_program_out():
    """
    GIVEN a ProgramService with a fake repository and an existing program id
    WHEN get_program is called
    THEN it delegates authorization/loading to the repository and returns ProgramOut.
    """
    service, repo = make_service()

    response = service.get_program(repo.program.id, "doctor-sub")

    assert response.id == repo.program.id
    assert response.estado == repo.program.estado
    assert repo.calls == [("get_program", repo.program.id, "doctor-sub")]


@pytest.mark.uc("UC-02")
@pytest.mark.ac("Exercise-A-02", "Exercise-A-03", "Exercise-A-05", "Exercise-A-06")
def test_assign_exercise_delegates_and_returns_assignment_out():
    """
    GIVEN a ProgramService with a fake repository and a valid ProgramExerciseIn request
    WHEN assign_exercise is called for a doctor subject
    THEN it delegates to the repository and maps ProgramExerciseRecord to ProgramExerciseOut.
    """
    service, repo = make_service()

    response = service.assign_exercise(
        repo.program.id,
        ProgramExerciseIn(exercise_id=repo.assignment.exercise_id, pauta="2 series"),
        "doctor-sub",
    )

    assert response.id == repo.assignment.id
    assert response.program_id == repo.program.id
    assert response.exercise_id == repo.assignment.exercise_id
    assert response.pauta == "2 series"
    assert response.estado == "active"
    assert repo.calls == [("assign_exercise", repo.program.id, repo.assignment.exercise_id, "2 series", "doctor-sub")]
