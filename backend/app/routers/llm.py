from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.responses import ok
from src.llm_client import DEFAULT_BASE_URL, DEFAULT_MODEL, llm_config_status, write_llm_config


router = APIRouter(prefix="/api/v1", tags=["LLM配置"])


class LlmConfigRequest(BaseModel):
    apiKey: str = Field(min_length=1)
    model: str = DEFAULT_MODEL
    baseUrl: str = DEFAULT_BASE_URL
    resumeEnabled: bool = True


@router.get("/llm/config/status")
def llm_status() -> dict:
    return ok(llm_config_status())


@router.post("/llm/config")
def save_llm_config(payload: LlmConfigRequest) -> dict:
    config = write_llm_config(
        payload.apiKey,
        model=payload.model,
        base_url=payload.baseUrl,
        resume_enabled=payload.resumeEnabled,
    )
    return ok(
        {
            "configured": config.configured,
            "model": config.model,
            "baseUrl": config.base_url,
            "resumeEnabled": config.resume_enabled,
        }
    )
