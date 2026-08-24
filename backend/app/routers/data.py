from fastapi import APIRouter

from backend.app.responses import ok
from backend.app.services.data_sources import data_source_status

router = APIRouter(prefix="/api/v1", tags=["数据与LLM边界"])


@router.get("/data-sources/status")
def data_sources_status() -> dict:
    return ok(data_source_status())
