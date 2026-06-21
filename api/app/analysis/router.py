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
    function_params: dict = {}
    llm_io_contract: dict = {}


@router.put("/exercises/{exercise_id}/analysis-setup")
def set_setup(exercise_id: uuid.UUID, body: SetupIn,
              _=Depends(require_role("medical", "technician")), db=Depends(get_db)):
    setup = db.scalar(select(AnalysisSetup).where(AnalysisSetup.exercise_id == exercise_id))
    if setup is None:
        setup = AnalysisSetup(exercise_id=exercise_id)
        db.add(setup)
    setup.metric_api_endpoint = body.function_name
    setup.prompt = body.prompt
    setup.function_params = body.function_params
    setup.llm_io_contract = body.llm_io_contract
    db.flush()
    return {"id": str(setup.id), "function_name": setup.metric_api_endpoint}
