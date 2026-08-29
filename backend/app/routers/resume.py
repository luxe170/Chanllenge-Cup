from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.responses import ok
from backend.app.services.resume_service import create_resume_task, get_resume_task, update_resume_skills

router = APIRouter(prefix="/api/v1", tags=["简历解析"])


class ResumeSkillsPatch(BaseModel):
    skills: list[dict]


@router.post("/resume-tasks")
async def resume_tasks(file: UploadFile = File(...)) -> dict:
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
    return ok(get_resume_task(task_id))


@router.patch("/resume-tasks/{task_id}/skills")
def resume_task_skills(task_id: str, payload: ResumeSkillsPatch) -> dict:
    return ok(update_resume_skills(task_id, payload.skills))
