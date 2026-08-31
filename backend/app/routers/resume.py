from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.responses import ok
from backend.app.services.resume_service import create_resume_task, get_resume_task, patch_resume_skills, update_resume_skills

router = APIRouter(prefix="/api/v1", tags=["简历解析"])


class ResumeSkillsPatch(BaseModel):
    skills: list[dict] | None = None
    added: list[dict] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    updated: list[dict] = Field(default_factory=list)


@router.post("/resume-tasks")
async def resume_tasks(file: UploadFile | None = File(default=None)) -> dict:
    if file is None:
        return ok(create_resume_task())
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的简历为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="简历不能超过 10 MB")
    try:
        return ok(create_resume_task(filename=file.filename or "resume", content=content))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/resume-tasks/{task_id}")
def resume_task(task_id: str) -> dict:
    try:
        return ok(get_resume_task(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/resume-tasks/{task_id}/skills")
def resume_task_skills(task_id: str, payload: ResumeSkillsPatch) -> dict:
    try:
        if payload.skills is not None:
            return ok(update_resume_skills(task_id, payload.skills))
        return ok(patch_resume_skills(task_id, added=payload.added, removed=payload.removed, updated=payload.updated))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
