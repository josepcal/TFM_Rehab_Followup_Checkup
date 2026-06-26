import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.analysis.models import AnalysisSetup
from app.auth import require_role
from app.db import get_db

router = APIRouter(tags=["analysis"])


class SetupIn(BaseModel):
    function_name: str
    prompt: str | None = None
    description: str | None = None
    criteria: str | None = None
    ai_model: str | None = None


@router.put("/program-exercises/{program_exercise_id}/analysis-setup")
def set_setup(program_exercise_id: uuid.UUID, body: SetupIn,
              _=Depends(require_role("medical", "technician")), db=Depends(get_db)):
    setup = db.scalar(
        select(AnalysisSetup).where(AnalysisSetup.program_exercise_id == program_exercise_id)
    )
    if setup is None:
        setup = AnalysisSetup(program_exercise_id=program_exercise_id)
        db.add(setup)
    setup.metric_api_endpoint = body.function_name
    setup.ai_prompt = body.prompt
    setup.description = body.description
    setup.criteria = body.criteria
    setup.ai_model = body.ai_model
    db.flush()
    return {"id": str(setup.id), "function_name": setup.metric_api_endpoint}
