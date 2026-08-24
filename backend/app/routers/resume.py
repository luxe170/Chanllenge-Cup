from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.app.responses import ok
from backend.app.services.resume_service import create_resume_task, get_resume_task, update_resume_skills

router = APIRouter(prefix="/api/v1", tags=["简历解析"])


class ResumeSkillsPatch(BaseModel):
    skills: list[dict]


@router.post("/resume-tasks")
async def resume_tasks(request: Request) -> dict:
    filename = ""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            upload = form.get("file")
            filename = getattr(upload, "filename", "") or ""
        except Exception:
            filename = ""
    return ok(create_resume_task(filename=filename))


@router.get("/resume-tasks/{task_id}")
def resume_task(task_id: str) -> dict:
    return ok(get_resume_task(task_id))


@router.patch("/resume-tasks/{task_id}/skills")
def resume_task_skills(task_id: str, payload: ResumeSkillsPatch) -> dict:
    return ok(update_resume_skills(task_id, payload.skills))
