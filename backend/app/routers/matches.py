from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.responses import ok
from backend.app.services.match_service import create_match, get_learning_path

router = APIRouter(prefix="/api/v1", tags=["匹配诊断"])


class MatchRequest(BaseModel):
    resumeTaskId: str
    positionId: str


@router.post("/matches")
def matches(payload: MatchRequest) -> dict:
    try:
        return ok(create_match(payload.resumeTaskId, payload.positionId))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/matches/{match_id}/learning-path")
def learning_path(match_id: str) -> dict:
    try:
        return ok(get_learning_path(match_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
