from __future__ import annotations

import uuid

from backend.app.services.data_sources import processed_path, read_jsonl
from backend.app.services.resume_service import get_resume_task


_match_reports: dict[str, dict] = {}
LEVEL_SCORE = {"了解": 0.55, "熟悉": 0.7, "掌握": 0.85, "精通": 1.0}


def _position_requirements(position_id: str) -> tuple[dict, list[dict]]:
    nodes = [node for node in read_jsonl(processed_path("graph_nodes.jsonl")) if node.get("mode") == "panorama"]
    edges = [edge for edge in read_jsonl(processed_path("graph_edges.jsonl")) if edge.get("mode") == "panorama"]
    node_map = {node["id"]: node for node in nodes}
    position = node_map.get(position_id)
    if not position or position.get("type") != "position":
        raise KeyError(f"unknown position: {position_id}")
    requirements = []
    for edge in edges:
        if edge.get("source") != position_id or edge.get("relationship") != "REQUIRES":
            continue
        skill = node_map.get(edge.get("target"))
        if skill:
            requirements.append({"name": skill["name"], "type": edge.get("requirementType", "required"), "weight": float(edge.get("weight", skill.get("weight", 0.65)))})
    return position, requirements


def _learning_path(gaps: list[dict]) -> list[dict]:
    if not gaps:
        return [{"stage": 1, "title": "强化优势并形成作品", "duration": "1–2 周", "skills": ["项目复盘"], "goal": "将已有能力整理为可验证的项目证据"}]
    groups = [gaps[index:index + 2] for index in range(0, min(len(gaps), 6), 2)]
    titles = ["补齐高优先级基础", "完成岗位场景实践", "形成综合项目证据"]
    return [{"stage": index + 1, "title": titles[min(index, 2)], "duration": f"{index + 1}–{index + 2} 周", "skills": [gap["name"] for gap in group], "goal": f"掌握{'、'.join(gap['name'] for gap in group)}并完成可验证练习"} for index, group in enumerate(groups)]


def _resume_learning_path(profile: dict) -> list[dict]:
    path = []
    raw_items = profile.get("learningSuggestions", [])
    if not isinstance(raw_items, list):
        return path
    for index, item in enumerate(raw_items[:6]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        skills = [
            str(skill).strip()
            for skill in item.get("skills", [])
            if str(skill).strip()
        ][:6]
        actions = [
            str(action).strip()
            for action in item.get("actions", [])
            if str(action).strip()
        ][:3]
        goal = str(item.get("expectedOutcome") or item.get("goal") or item.get("reason") or "").strip()
        if actions:
            goal = f"{goal}；行动：{'、'.join(actions)}" if goal else f"行动：{'、'.join(actions)}"
        path.append(
            {
                "stage": int(item.get("stage") or index + 1),
                "title": title,
                "duration": str(item.get("duration") or "1–2 周"),
                "skills": skills,
                "goal": goal or "完成可验证练习并补充项目证据",
            }
        )
    return path


def _build_match_report(resume_task_id: str, profile: dict, position_id: str, persist: bool = True) -> dict:
    position, requirements = _position_requirements(position_id)
    resume_skills = {item.get("name", "").lower(): item for item in profile.get("skills", []) if item.get("name")}
    total_weight = sum(max(0.1, item["weight"]) for item in requirements) or 1.0
    covered_weight = required_total = required_covered = preferred_total = preferred_covered = 0.0
    strengths, gaps = [], []
    for item in sorted(requirements, key=lambda value: value["weight"], reverse=True):
        weight = max(0.1, item["weight"])
        resume_skill = resume_skills.get(item["name"].lower())
        required = item["type"] == "required"
        if required: required_total += weight
        else: preferred_total += weight
        if resume_skill:
            factor = LEVEL_SCORE.get(resume_skill.get("level", "熟悉"), 0.7)
            covered_weight += weight * factor
            strengths.append(item["name"])
            if required: required_covered += weight * factor
            else: preferred_covered += weight * factor
        else:
            importance = round(min(100, weight * 100))
            gaps.append({"name": item["name"], "priority": "高" if required or importance >= 80 else "中", "requirement": "必备技能" if required else "加分技能", "current": "未识别", "weight": importance})
    score = round(covered_weight / total_weight * 100) if requirements else 0
    required_score = round(required_covered / required_total * 100) if required_total else 100
    preferred_score = round(preferred_covered / preferred_total * 100) if preferred_total else 100
    experiences = profile.get("experiences", [])
    project_score = min(100, len(experiences) * 30 + len(strengths) * 8)
    skills = profile.get("skills", [])
    depth_score = round(sum(LEVEL_SCORE.get(item.get("level", "熟悉"), 0.7) for item in skills) / max(1, len(skills)) * 100)
    match_id = f"match_{uuid.uuid4().hex[:10]}"
    report = {
        "matchId": match_id, "resumeTaskId": resume_task_id, "positionId": position_id, "positionName": position["name"], "candidateName": profile.get("candidateName", "未识别姓名"),
        "overallScore": score, "fitLevel": "高度匹配" if score >= 80 else "中度匹配" if score >= 60 else "有待提升", "benchmarkRank": "暂无排名", "benchmarkSampleCount": 0,
        "summary": f"覆盖 {len(strengths)}/{len(requirements)} 项岗位技能，建议优先补齐 {len(gaps)} 项能力。",
        "matchedSkillCount": len(strengths), "totalRequirementCount": len(requirements), "gapCount": len(gaps),
        "dimensions": [{"name": "必备技能", "value": required_score, "color": "#6ee7f9"}, {"name": "加分技能", "value": preferred_score, "color": "#a78bfa"}, {"name": "项目经验", "value": project_score, "color": "#5ee7a8"}, {"name": "技能深度", "value": depth_score, "color": "#fbbf73"}],
        "strengths": strengths, "gaps": gaps[:8], "evidence": {"skillEvidenceCount": len(skills), "projectEvidenceCount": len(experiences), "jobSampleCount": int(position.get("sampleCount", 0))},
        "suggestions": [f"优先补齐{gap['name']}，该能力在目标岗位中的重要度为 {gap['weight']}%" for gap in gaps[:3]] or ["技能覆盖较完整，建议补充可量化的项目成果与岗位证据"],
        "learningPath": _resume_learning_path(profile) or _learning_path(gaps),
    }
    if persist:
        _match_reports[match_id] = report
    return report


def create_match(resume_task_id: str, position_id: str) -> dict:
    task = get_resume_task(resume_task_id)
    return _build_match_report(resume_task_id, task.get("result") or {}, position_id)


def rank_matches(resume_task_id: str, limit: int = 50) -> dict:
    task = get_resume_task(resume_task_id)
    profile = task.get("result") or {}
    positions = [
        node for node in read_jsonl(processed_path("graph_nodes.jsonl"))
        if node.get("mode") == "panorama" and node.get("type") == "position"
    ]
    reports = [_build_match_report(resume_task_id, profile, position["id"], persist=False) for position in positions]
    reports.sort(
        key=lambda report: (
            -report["overallScore"],
            -next((dimension["value"] for dimension in report["dimensions"] if dimension["name"] == "必备技能"), 0),
            report["positionName"],
        )
    )
    items = [
        {
            "positionId": report["positionId"],
            "positionName": report["positionName"],
            "score": report["overallScore"],
            "fitLevel": report["fitLevel"],
            "matchedSkillCount": report["matchedSkillCount"],
            "totalSkillCount": report["totalRequirementCount"],
            "strengths": report["strengths"][:3],
            "gapCount": report["gapCount"],
        }
        for report in reports[:max(1, min(limit, 100))]
    ]
    return {
        "resumeTaskId": resume_task_id,
        "bestPositionId": items[0]["positionId"] if items else "",
        "bestPositionName": items[0]["positionName"] if items else "暂无可匹配岗位",
        "bestScore": items[0]["score"] if items else 0,
        "items": items,
    }


def get_learning_path(match_id: str) -> dict:
    if match_id not in _match_reports:
        raise KeyError(f"unknown match: {match_id}")
    return {"matchId": match_id, "items": _match_reports[match_id]["learningPath"]}
