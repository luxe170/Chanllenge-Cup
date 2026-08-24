from __future__ import annotations

import uuid

from backend.app.demo_data import RESUME_TASK, fresh


_resume_tasks: dict[str, dict] = {}


def create_resume_task(filename: str = "") -> dict:
    task = fresh(RESUME_TASK)
    task["taskId"] = f"resume_{uuid.uuid4().hex[:10]}"
    task["status"] = "completed"
    task["progress"] = 100
    if filename:
        task["filename"] = filename
    _resume_tasks[task["taskId"]] = task
    return {"taskId": task["taskId"], "status": task["status"], "progress": task["progress"]}


def get_resume_task(task_id: str) -> dict:
    if task_id in _resume_tasks:
        return fresh(_resume_tasks[task_id])
    task = fresh(RESUME_TASK)
    task["taskId"] = task_id or task["taskId"]
    _resume_tasks[task["taskId"]] = task
    return fresh(task)


def update_resume_skills(task_id: str, skills: list[dict]) -> dict:
    task = get_resume_task(task_id)
    task.setdefault("result", {})
    task["result"]["skills"] = skills
    task["status"] = "completed"
    task["progress"] = 100
    _resume_tasks[task["taskId"]] = task
    return {"taskId": task["taskId"], "skills": fresh(skills)}
