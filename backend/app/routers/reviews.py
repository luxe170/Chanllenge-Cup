from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.responses import ok
from backend.app.services.review_service import decide_review, get_reviews

router = APIRouter(prefix="/api/v1", tags=["人工审核"])


class ReviewDecision(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = ""


@router.get("/reviews")
def reviews(
    status: Literal["pending", "approved", "rejected"] | None = Query(default=None),
    type: Literal["新岗位", "能力变更", "技能归一"] | None = Query(default=None),
    keyword: str = Query(default=""),
) -> dict:
    return ok(get_reviews(status=status, review_type=type, keyword=keyword))


@router.post("/reviews/{review_id}/decision")
def review_decision(review_id: str, decision: ReviewDecision) -> dict:
    try:
        return ok(decide_review(review_id, decision.status, decision.note))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/reviews/{review_id}/status")
def review_status(
    review_id: str,
    status: Literal["approved", "rejected"] = Query(),
) -> dict:
    try:
        return ok(decide_review(review_id, status))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
