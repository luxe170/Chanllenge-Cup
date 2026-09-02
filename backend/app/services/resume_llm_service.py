from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.services.evolution_service import SKILL_ALIASES, SKILL_NAME_MAP
from src.llm_client import JsonChatClient


PROMPT_VERSION = "resume-analysis-learning-v1"
ANALYZER_VERSION = f"llm-{PROMPT_VERSION}"
PROFICIENCY_LEVELS = ("了解", "熟悉", "掌握", "精通")


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _skill_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": skill_id,
            "name": name,
            "aliases": SKILL_ALIASES.get(skill_id, []),
        }
        for skill_id, name in sorted(SKILL_NAME_MAP.items())
    ]


def _system_prompt() -> str:
    return (
        "你是简历分析与学习建议助手。请只基于给定简历文本抽取事实，不要编造经历、学校、公司或技能。\n"
        "技能应尽量映射到 skills 中的标准技能 id；无法映射的技能可保留 name，但不要虚构 id。\n"
        "技能熟练度只能是 了解、熟悉、掌握、精通。熟练度必须基于上下文证据和个人贡献判断。\n"
        "学习建议必须对应简历中的能力缺口、项目证据缺口或目标岗位方向，不要输出泛泛资料清单。\n"
        "每个关键结论尽量提供 evidenceText。返回严格 JSON，格式为 {\"profile\": {...}}，不要 Markdown。\n"
        "profile 字段包括 candidateName、targetPosition、education、experienceYears、direction、summary、"
        "skills、experiences、abilityProfile、learningSuggestions、resumeOptimizationSuggestions、confidence。\n"
        f"skills={json.dumps(_skill_catalog(), ensure_ascii=False)}"
    )


def _user_payload(filename: str, text: str, fallback_profile: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "filename": filename,
        "resumeText": text[:6000],
        "ruleBaseline": _compact_fallback(fallback_profile or {}),
    }


def _compact_fallback(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidateName": profile.get("candidateName", ""),
        "targetPosition": profile.get("targetPosition", ""),
        "education": profile.get("education", ""),
        "experienceYears": profile.get("experienceYears", 0),
        "skills": [
            {"id": item.get("id"), "name": item.get("name"), "level": item.get("level")}
            for item in profile.get("skills", [])[:12]
            if isinstance(item, dict)
        ],
        "experiences": [
            {"title": item.get("title"), "description": item.get("description")}
            for item in profile.get("experiences", [])[:5]
            if isinstance(item, dict)
        ],
    }


def _clamp_confidence(value: Any, default: float = 0.0) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "") -> str:
    cleaned = str(value or "").strip()
    return cleaned if cleaned else default


def _skill_id_for(raw: dict[str, Any]) -> str:
    skill_id = str(raw.get("id") or raw.get("skillId") or "").strip()
    if skill_id in SKILL_NAME_MAP:
        return skill_id
    raw_name = str(raw.get("name") or "").casefold()
    for known_id, known_name in SKILL_NAME_MAP.items():
        if raw_name == known_name.casefold():
            return known_id
        aliases = [alias.casefold() for alias in SKILL_ALIASES.get(known_id, [])]
        if raw_name in aliases:
            return known_id
    return ""


def _normalize_skill(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = _text(raw.get("name"))
    skill_id = _skill_id_for(raw)
    if skill_id:
        name = SKILL_NAME_MAP[skill_id]
    if not name:
        return None
    level = _text(raw.get("level"), "掌握")
    if level not in PROFICIENCY_LEVELS:
        level = "掌握"
    source = _text(raw.get("source") or raw.get("evidenceText"), name)
    return {
        "id": skill_id or f"llm_custom_{abs(hash(name.casefold())) % 100000000:08d}",
        "name": name,
        "level": level,
        "source": source[:180],
        "confidence": _clamp_confidence(raw.get("confidence"), 0.7),
        "evidenceText": _text(raw.get("evidenceText") or source)[:240],
        "relatedExperience": _text(raw.get("relatedExperience"))[:120],
    }


def _normalize_skills(raw_value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_skills = raw_value if isinstance(raw_value, list) else []
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_skills:
        if not isinstance(raw, dict):
            continue
        skill = _normalize_skill(raw)
        if skill is None:
            continue
        key = str(skill.get("id") or skill.get("name")).casefold()
        if key in seen:
            continue
        skills.append(skill)
        seen.add(key)
    if skills:
        return skills[:20]
    return fallback


def _normalize_experiences(raw_value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_experiences = raw_value if isinstance(raw_value, list) else []
    experiences = []
    for raw in raw_experiences:
        if not isinstance(raw, dict):
            continue
        title = _text(raw.get("title") or raw.get("name"))
        description = _text(raw.get("description") or raw.get("detail"))
        if not title and not description:
            continue
        tags = [
            str(item).strip()
            for item in raw.get("skills", raw.get("tags", []))
            if str(item).strip()
        ][:8]
        experiences.append(
            {
                "period": _text(raw.get("period"), "简历原文")[:80],
                "title": (title or "未命名经历")[:100],
                "description": description[:320],
                "detail": description[:320],
                "role": _text(raw.get("role"))[:80],
                "contribution": _text(raw.get("contribution"))[:240],
                "outcome": _text(raw.get("outcome"))[:180],
                "skills": tags,
                "tags": tags,
                "evidenceText": _text(raw.get("evidenceText") or description)[:260],
                "confidence": _clamp_confidence(raw.get("confidence"), 0.65),
            }
        )
    if experiences:
        return experiences[:8]
    return fallback


def _string_list(raw_value: Any, limit: int = 8) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    values = []
    for raw in raw_value:
        text = _text(raw.get("text") if isinstance(raw, dict) else raw)
        if text and text not in values:
            values.append(text[:180])
        if len(values) >= limit:
            break
    return values


def _normalize_ability(raw_value: Any, profile: dict[str, Any]) -> dict[str, Any]:
    raw = raw_value if isinstance(raw_value, dict) else {}
    strengths = _string_list(raw.get("strengths"), 6)
    weaknesses = _string_list(raw.get("weaknesses") or raw.get("risks"), 6)
    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "projectEvidenceLevel": _text(raw.get("projectEvidenceLevel"), "待评估"),
        "engineeringMaturity": _text(raw.get("engineeringMaturity"), "待评估"),
        "targetRelevance": _text(raw.get("targetRelevance"), "待评估"),
        "riskNotes": _string_list(raw.get("riskNotes"), 6),
        "summary": _text(raw.get("summary"), profile.get("summary", ""))[:260],
    }


def _normalize_learning(raw_value: Any, fallback_profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = raw_value if isinstance(raw_value, list) else []
    items = []
    for index, raw in enumerate(raw_items[:9]):
        if not isinstance(raw, dict):
            continue
        title = _text(raw.get("title"))
        if not title:
            continue
        actions = _string_list(raw.get("actions") or raw.get("tasks"), 5)
        items.append(
            {
                "stage": _int_value(raw.get("stage"), index + 1),
                "category": _text(raw.get("category"), "短期补齐"),
                "priority": _text(raw.get("priority"), "中"),
                "title": title[:100],
                "reason": _text(raw.get("reason"))[:240],
                "duration": _text(raw.get("duration"), "1-2 周")[:60],
                "skills": _string_list(raw.get("skills"), 6),
                "actions": actions,
                "expectedOutcome": _text(raw.get("expectedOutcome") or raw.get("goal"))[:240],
                "projectIdea": _text(raw.get("projectIdea"))[:180],
                "evidenceGap": _text(raw.get("evidenceGap"))[:180],
            }
        )
    if items:
        return items
    return build_rule_learning_suggestions(fallback_profile)


def _normalize_profile(raw: dict[str, Any], fallback: dict[str, Any], *, model: str, generated_at: str) -> dict[str, Any]:
    raw_profile = raw.get("profile") if isinstance(raw.get("profile"), dict) else raw
    profile = {
        "candidateName": _text(raw_profile.get("candidateName"), fallback.get("candidateName", "未识别姓名")),
        "targetPosition": _text(raw_profile.get("targetPosition"), fallback.get("targetPosition", "待选择目标岗位")),
        "education": _text(raw_profile.get("education"), fallback.get("education", "未识别学历")),
        "experienceYears": _int_value(raw_profile.get("experienceYears"), int(fallback.get("experienceYears") or 0)),
        "direction": _text(raw_profile.get("direction"), fallback.get("direction", "软件与数据工程方向")),
        "summary": _text(raw_profile.get("summary"), fallback.get("summary", "")),
    }
    profile["name"] = profile["candidateName"]
    profile["intendedPosition"] = profile["targetPosition"]
    profile["skills"] = _normalize_skills(raw_profile.get("skills"), fallback.get("skills", []))
    profile["experiences"] = _normalize_experiences(raw_profile.get("experiences"), fallback.get("experiences", []))
    profile["abilityProfile"] = _normalize_ability(raw_profile.get("abilityProfile"), profile)
    profile["learningSuggestions"] = _normalize_learning(raw_profile.get("learningSuggestions"), profile)
    profile["resumeOptimizationSuggestions"] = _string_list(raw_profile.get("resumeOptimizationSuggestions"), 8)
    profile["confidence"] = _clamp_confidence(raw_profile.get("confidence"), 0.7)
    profile["analysisSource"] = "llm"
    profile["analyzerVersion"] = ANALYZER_VERSION
    profile["promptVersion"] = PROMPT_VERSION
    profile["model"] = model
    profile["generatedAt"] = generated_at
    profile["completeness"] = max(int(fallback.get("completeness", 0) or 0), _completeness(profile))
    return profile


def _completeness(profile: dict[str, Any]) -> int:
    score = 0
    if profile.get("candidateName") and profile["candidateName"] != "未识别姓名":
        score += 15
    if profile.get("targetPosition") and profile["targetPosition"] != "待选择目标岗位":
        score += 15
    if profile.get("education") and profile["education"] != "未识别学历":
        score += 15
    if profile.get("experienceYears"):
        score += 10
    score += min(20, len(profile.get("experiences", [])) * 10)
    score += min(25, len(profile.get("skills", [])) * 5)
    return min(100, max(35, score))


def build_rule_learning_suggestions(profile: dict[str, Any]) -> list[dict[str, Any]]:
    skill_names = {str(skill.get("name")) for skill in profile.get("skills", []) if isinstance(skill, dict)}
    target = str(profile.get("targetPosition") or "")
    suggestions = []
    if "AI" in target.upper() or skill_names & {"大语言模型", "RAG", "LangChain", "多智能体协作"}:
        missing = [name for name in ("RAG", "Prompt 工程", "多智能体协作", "FastAPI") if name not in skill_names]
        if missing:
            suggestions.append(
                {
                    "stage": 1,
                    "category": "短期补齐",
                    "priority": "高",
                    "title": "补齐 AI 应用工程核心技能",
                    "reason": f"目标方向需要能把模型能力落到可运行应用，当前简历中 {missing[0]} 等证据不足。",
                    "duration": "1-2 周",
                    "skills": missing[:3],
                    "actions": ["完成一个带检索、提示词和接口服务的最小项目", "为每个关键技能补充可验证的项目证据"],
                    "expectedOutcome": "形成一段可写入简历的 AI 应用项目经历",
                    "projectIdea": "企业知识库问答或岗位 JD 智能解析 Demo",
                    "evidenceGap": "缺少完整 AI 应用闭环项目证据",
                }
            )
    if not suggestions:
        suggestions.append(
            {
                "stage": 1,
                "category": "短期补齐",
                "priority": "中",
                "title": "强化项目证据表达",
                "reason": "当前简历需要把技能和项目贡献更明确地对应起来。",
                "duration": "1-2 周",
                "skills": list(skill_names)[:3],
                "actions": ["为核心项目补充个人贡献、技术难点和量化结果", "将技能列表中的关键词映射到具体经历"],
                "expectedOutcome": "提升简历可解释性和岗位匹配证据强度",
                "projectIdea": "",
                "evidenceGap": "技能与项目证据关联不足",
            }
        )
    suggestions.append(
        {
            "stage": 2,
            "category": "中期项目",
            "priority": "中",
            "title": "完成目标岗位相关作品",
            "reason": "中期作品能让匹配结果从技能命中提升到项目证据命中。",
            "duration": "2-6 周",
            "skills": list(skill_names)[:5],
            "actions": ["选择一个目标岗位高频场景完成端到端作品", "补充 README、架构图、评测指标和部署说明"],
            "expectedOutcome": "形成可演示、可复盘、可量化的项目材料",
            "projectIdea": "围绕目标岗位构建一个端到端工程项目",
            "evidenceGap": "缺少可展示作品或量化指标",
        }
    )
    return suggestions


def analyze_resume_with_llm(
    filename: str,
    text: str,
    client: JsonChatClient,
    *,
    fallback_profile: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or _generated_at()
    fallback = dict(fallback_profile or {})
    result = client.complete_json(_system_prompt(), _user_payload(filename, text, fallback))
    return _normalize_profile(result, fallback, model=client.model, generated_at=timestamp)

