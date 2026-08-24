from __future__ import annotations

import uuid

from backend.app.demo_data import MATCH_REPORT, fresh
from backend.app.services.evolution_service import compute_position_profile
from backend.app.services.resume_service import get_resume_task


_match_reports: dict[str, dict] = {}


def _skill_names_from_resume(resume_task_id: str) -> set[str]:
    task = get_resume_task(resume_task_id or "demo_resume_task")
    result = task.get("result") or {}
    return {item.get("name", "") for item in result.get("skills", []) if item.get("name")}


def _skill_names_from_position(position_id: str) -> set[str]:
    try:
        profile = compute_position_profile(position_id)
    except KeyError:
        return set()
    return {item.get("name", "") for item in profile.get("requirements", []) if item.get("name")}


def create_match(resume_task_id: str, position_id: str) -> dict:
    report = fresh(MATCH_REPORT)
    report["matchId"] = f"match_{uuid.uuid4().hex[:10]}"
    report["resumeTaskId"] = resume_task_id or report["resumeTaskId"]
    report["positionId"] = position_id or report["positionId"]

    resume_skills = _skill_names_from_resume(report["resumeTaskId"])
    position_skills = _skill_names_from_position(report["positionId"])
    if resume_skills and position_skills:
        overlap = resume_skills & position_skills
        score = round(min(96, 58 + len(overlap) / max(1, len(position_skills)) * 38))
        report["overallScore"] = score
        report["level"] = "高度匹配" if score >= 80 else "中度匹配"
        report["fitLevel"] = report["level"]
        report["strengths"] = sorted(overlap)[:6] or report["strengths"]
        missing = [skill for skill in sorted(position_skills - resume_skills) if skill]
        if missing:
            report["gaps"] = [
                {
                    "name": skill,
                    "priority": "高" if index < 2 else "中",
                    "requirement": "岗位技能",
                    "current": "未识别",
                    "weight": max(58, 88 - index * 8),
                }
                for index, skill in enumerate(missing[:4])
            ]
        report["summary"] = f"识别到 {len(overlap)} 项岗位技能交集，仍需优先补齐 {len(report['gaps'])} 项关键能力。"

    _match_reports[report["matchId"]] = report
    return fresh(report)


def get_learning_path(match_id: str) -> dict:
    report = _match_reports.get(match_id, MATCH_REPORT)
    return {"matchId": match_id, "items": report["learningPath"]}
