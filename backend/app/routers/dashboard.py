from fastapi import APIRouter

from backend.app.responses import ok
from backend.app.services.dashboard_service import get_dashboard_summary, get_evaluation_summary

router = APIRouter(prefix="/api/v1", tags=["工作台"])


@router.get("/dashboard")
def dashboard() -> dict:
    return ok(get_dashboard_summary())


@router.get("/dashboard/summary")
def dashboard_summary() -> dict:
    return ok(get_dashboard_summary())


@router.get("/evaluations/summary")
def evaluation_summary() -> dict:
    return ok(get_evaluation_summary())
