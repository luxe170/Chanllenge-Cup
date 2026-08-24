from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.app.schemas import (
    ChangeEvidence,
    ChangeType,
    EmergingPositionItem,
    EvolutionChangeItem,
    PositionProfile,
    RequirementSnapshot,
    SkillRequirement,
    SourceSupport,
    WindowContinuity,
)


POSITION_ALIASES = {
    "pos_ai_agent_engineer": [
        "agent",
        "multi-agent",
        "多智能体",
        "tool use",
        "workflow",
        "langchain",
        "langgraph",
        "rag",
        "prompt",
        "llm",
        "大模型",
    ],
    "pos_llm_engineer": [
        "llm",
        "大模型",
        "rag",
        "检索增强",
        "评测",
        "prompt",
        "生成式",
        "模型训练",
    ],
    "pos_java_engineer": [
        "java",
        "spring",
        "springboot",
        "后端",
        "云原生",
        "kubernetes",
        "docker",
        "微服务",
    ],
    "pos_data_analyst": [
        "数据分析",
        "分析师",
        "sql",
        "excel",
        "报表",
        "数据挖掘",
    ],
    "pos_frontend_engineer": [
        "前端",
        "javascript",
        "typescript",
        "react",
        "vue",
        "web",
        "ai coding",
        "前端开发",
    ],
}

SKILL_ALIASES = {
    "skill_llm": ["llm", "大语言模型", "大模型", "foundation model"],
    "skill_rag": ["rag", "retrieval augmented", "检索增强", "向量检索"],
    "skill_python": ["python"],
    "skill_prompt": ["prompt", "提示词工程", "prompt engineering"],
    "skill_multi_agent": ["multi-agent", "多智能体", "agent workflow", "agent协同", "tool use"],
    "skill_rag_eval": ["rag评测", "评测", "benchmark", "eval", "模型评测"],
    "skill_java": ["java"],
    "skill_spring": ["spring", "springboot"],
    "skill_cloud_native": ["云原生", "kubernetes", "docker", "k8s"],
    "skill_sql": ["sql", "mysql", "hive"],
    "skill_excel": ["excel", "报表", "dashboard"],
    "skill_ai_codegen": ["ai coding", "ai编程", "代码生成", "copilot", "cursor"],
    "skill_frontend": ["前端", "javascript", "typescript", "react", "vue", "web"],
}

POSITION_NAME_MAP = {
    "pos_ai_agent_engineer": "AI Agent 研发工程师",
    "pos_llm_engineer": "大模型应用工程师",
    "pos_java_engineer": "Java 开发工程师",
    "pos_data_analyst": "数据分析师",
    "pos_frontend_engineer": "前端研发工程师",
}

SKILL_NAME_MAP = {
    "skill_llm": "大语言模型",
    "skill_rag": "RAG",
    "skill_python": "Python",
    "skill_prompt": "Prompt 工程",
    "skill_multi_agent": "多智能体协作",
    "skill_rag_eval": "RAG 评测",
    "skill_java": "Java",
    "skill_spring": "Spring 框架",
    "skill_cloud_native": "云原生",
    "skill_sql": "SQL",
    "skill_excel": "Excel / 报表",
    "skill_ai_codegen": "AI 辅助开发",
    "skill_frontend": "前端工程",
}


def _job_data_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "processed" / "relevant_jobs.jsonl"


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=None)
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=None)
    return parsed.astimezone().replace(tzinfo=None)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower()
    return text.replace("\u3000", " ")


def _match_aliases(text: str, aliases: Iterable[str]) -> bool:
    normalized = _normalize_text(text)
    for alias in aliases:
        if alias.lower() in normalized:
            return True
    return False


def _position_for_record(record: Dict[str, Any]) -> str:
    text = " ".join(
        [
            record.get("title", ""),
            record.get("description", ""),
            record.get("requirement", ""),
            record.get("category", ""),
        ]
    )
    best_position = "pos_ai_agent_engineer"
    best_score = -1
    for position_id, aliases in POSITION_ALIASES.items():
        score = sum(1 for alias in aliases if alias.lower() in text.lower())
        if score > best_score:
            best_score = score
            best_position = position_id
    return best_position


def _load_job_records() -> List[Dict[str, Any]]:
    path = _job_data_path()
    if not path.exists():
        return []

    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not item.get("publish_time"):
                continue
            item["_position_id"] = _position_for_record(item)
            item["_parsed_time"] = _parse_datetime(item["publish_time"])
            records.append(item)
    return sorted(records, key=lambda r: r["_parsed_time"])


def _build_snapshot_windows() -> tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Dict[str, Any]]]]:
    records = _load_job_records()
    if not records:
        return ({}, {})

    midpoint = max(1, len(records) * 40 // 100)
    historical = records[:midpoint]
    current = records[midpoint:]

    def build_window(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        by_position: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        by_position_counts: Dict[str, int] = defaultdict(int)

        for record in items:
            position_id = record["_position_id"]
            by_position_counts[position_id] += 1

        for position_id, count in by_position_counts.items():
            skill_usage: Dict[str, int] = defaultdict(int)
            for record in items:
                if record["_position_id"] != position_id:
                    continue
                text = " ".join([record.get("title", ""), record.get("description", ""), record.get("requirement", "")])
                for skill_id, aliases in SKILL_ALIASES.items():
                    if _match_aliases(text, aliases):
                        skill_usage[skill_id] += 1

            for skill_id, usage in skill_usage.items():
                weight = round(min(1.0, usage / max(1, count)), 2)
                required = skill_id in {"skill_llm", "skill_rag", "skill_python", "skill_java", "skill_sql"}
                by_position[position_id][skill_id] = {
                    "requirementType": "required" if required else "preferred",
                    "weight": weight,
                }
        return dict(by_position)

    history_snapshot = build_window(historical)
    current_snapshot = build_window(current)

    if not current_snapshot:
        current_snapshot = history_snapshot

    return history_snapshot, current_snapshot


def _score_confidence(company_count: int, job_count: int, window_count: int, semantic_consistency: float) -> float:
    source_part = min(company_count / 5.0, 1.0)
    evidence_part = min(job_count / 100.0, 1.0)
    continuity_part = min(window_count / 4.0, 1.0)
    return round(
        0.35 * source_part + 0.25 * evidence_part + 0.2 * continuity_part + 0.2 * semantic_consistency,
        2,
    )


def _to_snapshot(payload: Optional[Dict[str, Any]]) -> Optional[RequirementSnapshot]:
    if payload is None:
        return None
    return RequirementSnapshot(
        requirementType=payload["requirementType"],
        weight=float(payload["weight"]),
    )


def _skill_meta(skill_id: str, position_id: str, record_hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    company_count = len({item.get("company") for item in record_hits if item.get("company")})
    job_count = len(record_hits)
    semantic = min(0.99, 0.72 + min(0.2, job_count / 150.0))
    return {
        "positionName": POSITION_NAME_MAP.get(position_id, position_id),
        "skillName": SKILL_NAME_MAP.get(skill_id, skill_id),
        "companyCount": company_count,
        "jobCount": job_count,
        "windowCount": 3,
        "semanticConsistency": round(semantic, 2),
        "evidenceIds": [f"jd_{idx + 1:04d}" for idx, _ in enumerate(record_hits[:5])],
    }


def _build_real_snapshot_data() -> tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Dict[str, Any]]]]:
    records = _load_job_records()
    if not records:
        return ({}, {}, {})

    now = datetime.utcnow()
    history_snapshot, current_snapshot = _build_snapshot_windows()
    evidence_store: Dict[str, Dict[str, Any]] = {}

    position_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        position_buckets[record["_position_id"]].append(record)

    for position_id, items in position_buckets.items():
        for skill_id, aliases in SKILL_ALIASES.items():
            hits = [record for record in items if _match_aliases(" ".join([record.get("title", ""), record.get("description", ""), record.get("requirement", "")]), aliases)]
            if not hits:
                continue
            evidence_store[f"{position_id}:{skill_id}"] = _skill_meta(skill_id, position_id, hits)

    return history_snapshot, current_snapshot, evidence_store


def compute_evolution_changes(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
    historical_snapshot, current_snapshot, evidence_store = _build_real_snapshot_data()
    items: List[EvolutionChangeItem] = []
    all_position_ids = set(historical_snapshot) | set(current_snapshot)
    if not all_position_ids:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    for position_id in sorted(all_position_ids):
        previous = historical_snapshot.get(position_id, {})
        current = current_snapshot.get(position_id, {})
        all_skill_ids = set(previous) | set(current)
        for skill_id in sorted(all_skill_ids):
            old_state = previous.get(skill_id)
            new_state = current.get(skill_id)
            if old_state is None and new_state is not None:
                change_type: ChangeType = "new"
            elif old_state is not None and new_state is not None:
                old_weight = float(old_state["weight"])
                new_weight = float(new_state["weight"])
                if new_weight > old_weight + 0.1:
                    change_type = "rising"
                elif new_weight < old_weight - 0.1:
                    change_type = "declining"
                else:
                    continue
            else:
                continue

            meta = evidence_store.get(f"{position_id}:{skill_id}", {})
            if not meta:
                meta = {
                    "positionName": POSITION_NAME_MAP.get(position_id, position_id),
                    "skillName": SKILL_NAME_MAP.get(skill_id, skill_id),
                    "companyCount": 1,
                    "jobCount": 1,
                    "windowCount": 1,
                    "semanticConsistency": 0.8,
                    "evidenceIds": [f"jd_{position_id}_{skill_id}_001"],
                }

            confidence = _score_confidence(
                int(meta.get("companyCount", 1)),
                int(meta.get("jobCount", 1)),
                int(meta.get("windowCount", 1)),
                float(meta.get("semanticConsistency", 0.8)),
            )

            item = EvolutionChangeItem(
                id=f"change_{len(items) + 1:03d}",
                positionId=position_id,
                positionName=meta.get("positionName", position_id),
                skillId=skill_id,
                skillName=meta.get("skillName", skill_id),
                changeType=change_type,
                before=_to_snapshot(old_state),
                after=RequirementSnapshot(
                    requirementType=new_state["requirementType"] if new_state else "preferred",
                    weight=float(new_state["weight"] if new_state else 0.0),
                ),
                evidenceCount=int(meta.get("jobCount", 1)),
                confidence=confidence,
                detectedAt=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            )

            if not keyword or keyword.lower() in item.positionName.lower() or keyword.lower() in item.skillName.lower():
                items.append(item)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def compute_change_evidence(change_id: str) -> dict:
    items = compute_evolution_changes(page=1, page_size=500)["items"]
    matched = next((item for item in items if item.id == change_id), None)
    if matched is None:
        raise KeyError(f"unknown changeId: {change_id}")

    position_id = matched.positionId
    skill_id = matched.skillId
    records = _load_job_records()
    hits = [
        (idx, record)
        for idx, record in enumerate(records)
        if record["_position_id"] == position_id
        and _match_aliases(" ".join([record.get("title", ""), record.get("description", ""), record.get("requirement", "")]), SKILL_ALIASES.get(skill_id, []))
    ]
    evidence_ids = [f"jd_{idx + 1:04d}" for idx, _ in hits[:5]]

    before = matched.before
    after = matched.after
    confidence = float(matched.confidence)
    source_count = max(1, len({record.get("company") for _, record in hits if record.get("company")}))
    job_count = len(hits)

    return ChangeEvidence(
        changeId=change_id,
        positionId=position_id,
        positionName=matched.positionName,
        skillId=skill_id,
        skillName=matched.skillName,
        before=_to_snapshot(before.model_dump() if hasattr(before, "model_dump") else before),
        after=RequirementSnapshot(
            requirementType=after.requirementType,
            weight=float(after.weight),
        ),
        confidence=confidence,
        sourceSupport=SourceSupport(companyCount=source_count, jobCount=job_count),
        windowContinuity=WindowContinuity(continuousWindowCount=3, passed=True),
        semanticConsistency=round(min(0.99, 0.7 + job_count / 150.0), 2),
        evidenceIds=evidence_ids,
    ).model_dump()


def compute_evidence_detail(evidence_id: str) -> dict:
    records = _load_job_records()
    if not records:
        raise KeyError(f"unknown evidenceId: {evidence_id}")

    match_index = None
    try:
        match_index = int(evidence_id.split("_")[-1]) - 1
    except ValueError:
        match_index = 0

    if match_index < 0 or match_index >= len(records):
        raise KeyError(f"unknown evidenceId: {evidence_id}")

    record = records[match_index]
    jd_text = "\n".join(
        [
            record.get("title", ""),
            record.get("description", ""),
            record.get("requirement", ""),
        ]
    ).strip()

    excerpt = jd_text[:800] if len(jd_text) > 800 else jd_text
    return {
        "evidenceId": evidence_id,
        "company": record.get("company", "未知公司"),
        "positionTitle": record.get("title", "未知岗位"),
        "sourcePlatform": record.get("source_platform", "unknown"),
        "publishedAt": record.get("publish_time", ""),
        "url": record.get("url", ""),
        "jdText": jd_text,
        "excerpt": excerpt,
        "matchedSkill": "AI Agent / 多智能体 / RAG",
    }


def compute_emerging_positions(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
    records = _load_job_records()
    if not records:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    historical_snapshot, current_snapshot, _ = _build_real_snapshot_data()
    position_counts: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for record in records:
        position_id = record["_position_id"]
        position_counts[position_id].setdefault("jobs", []).append(record)
        position_counts[position_id].setdefault("companies", set()).add(record.get("company"))

    candidates: List[Dict[str, Any]] = []
    for position_id, record_list in sorted(position_counts.items()):
        current_count = len(record_list["jobs"])
        if current_count < 3:
            continue
        cutoff = datetime(2025, 1, 1, tzinfo=None)
        history_count = len(
            [
                record
                for record in records
                if record["_position_id"] == position_id and record["_parsed_time"].replace(tzinfo=None) < cutoff
            ]
        )
        growth_rate = round((current_count / max(1, history_count)) - 1, 2) if history_count else 0.8
        if growth_rate <= 0.1:
            continue
        skill_ids = sorted((current_snapshot.get(position_id, {}) or {}).keys())[:3]
        if not skill_ids:
            skill_ids = sorted((historical_snapshot.get(position_id, {}) or {}).keys())[:3]
        skill_items = [{"id": skill_id, "name": SKILL_NAME_MAP.get(skill_id, skill_id)} for skill_id in skill_ids]
        confidence = min(0.99, 0.55 + growth_rate * 0.35)
        candidates.append(
            {
                "id": f"emerging_{len(candidates) + 1:03d}",
                "positionId": position_id,
                "name": POSITION_NAME_MAP.get(position_id, position_id),
                "description": "基于持续增长的岗位需求与技能组合，识别出具备上升趋势的岗位类型。",
                "growthRate": round(max(0.1, growth_rate), 2),
                "confidence": round(confidence, 2),
                "firstSeen": min(record["publish_time"] for record in record_list["jobs"] if record.get("publish_time"))[:10],
                "sourceCount": len(record_list["companies"]),
                "sampleCount": current_count,
                "skills": skill_items,
            }
        )

    filtered = []
    for item in candidates:
        haystack = f"{item['name']} {' '.join(skill['name'] for skill in item['skills'])}".lower()
        if not keyword or keyword.lower() in haystack:
            filtered.append(EmergingPositionItem(**item))

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": filtered[start:end],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def _record_text(record: Dict[str, Any]) -> str:
    return " ".join([record.get("title", ""), record.get("description", ""), record.get("requirement", "")])


def _split_numbered(text: Any) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?:\n|^)\s*\d+[、.)）]\s*", str(text))
    return [part.strip() for part in parts if len(part.strip()) > 4]


def _position_growth(records_for_position: List[Dict[str, Any]]) -> float:
    current_count = len(records_for_position)
    cutoff = datetime(2025, 1, 1, tzinfo=None)
    history_count = len(
        [record for record in records_for_position if record["_parsed_time"].replace(tzinfo=None) < cutoff]
    )
    if history_count:
        return round((current_count / max(1, history_count)) - 1, 2)
    return 0.8


def compute_position_profile(position_id: str) -> dict:
    records = _load_job_records()
    position_records = [record for record in records if record["_position_id"] == position_id]
    if not position_records:
        raise KeyError(f"unknown positionId: {position_id}")

    historical_snapshot, current_snapshot, _ = _build_real_snapshot_data()
    skills_snapshot = current_snapshot.get(position_id) or historical_snapshot.get(position_id, {})

    requirements: List[SkillRequirement] = []
    for skill_id, snapshot in sorted(skills_snapshot.items()):
        hits = [record for record in position_records if _match_aliases(_record_text(record), SKILL_ALIASES.get(skill_id, []))]
        first_seen = min((record.get("publish_time", "") for record in hits if record.get("publish_time")), default="")[:10]
        requirements.append(
            SkillRequirement(
                id=f"{position_id}:{skill_id}",
                name=SKILL_NAME_MAP.get(skill_id, skill_id),
                type=snapshot["requirementType"],
                weight=float(snapshot["weight"]),
                frequency=len(hits),
                confidence=round(min(0.99, 0.6 + len(hits) / max(1, len(position_records)) * 0.35), 2),
                trend="stable",
                firstSeen=first_seen,
                evidenceCount=len(hits),
            )
        )

    responsibilities: List[str] = []
    seen_responsibilities: set[str] = set()
    for record in sorted(position_records, key=lambda r: r["_parsed_time"], reverse=True):
        for part in _split_numbered(record.get("description")):
            key = part[:24]
            if key in seen_responsibilities:
                continue
            seen_responsibilities.add(key)
            responsibilities.append(part)
        if len(responsibilities) >= 5:
            break

    scenarios: List[str] = []
    scenario_keywords = ("场景", "应用", "落地", "业务")
    for record in position_records:
        requirement = record.get("requirement", "")
        if any(keyword in requirement for keyword in scenario_keywords):
            for part in _split_numbered(requirement):
                if any(keyword in part for keyword in scenario_keywords) and part not in scenarios:
                    scenarios.append(part)
        if len(scenarios) >= 4:
            break
    if not scenarios:
        scenarios = [f"{requirement.name} 相关工程实践" for requirement in requirements[:3]]

    required_names = [requirement.name for requirement in requirements if requirement.type == "required"]
    preferred_names = [requirement.name for requirement in requirements if requirement.type == "preferred"]
    top_skill_names = [requirement.name for requirement in requirements[:3]]

    categories = [record.get("category") for record in position_records if record.get("category")]
    category = max(set(categories), key=categories.count) if categories else "未分类"

    sample_count = len(position_records)
    source_count = len({record.get("company") for record in position_records if record.get("company")})
    growth_rate = _position_growth(position_records)
    position_name = POSITION_NAME_MAP.get(position_id, position_id)

    description = (
        f"{position_name}：聚焦{category}方向，"
        f"核心能力围绕{'、'.join(top_skill_names) if top_skill_names else '核心技能'}展开"
        + (f"，必备技能包括{'、'.join(required_names)}" if required_names else "")
        + (f"，加分技能包括{'、'.join(preferred_names)}" if preferred_names else "")
        + f"。当前由 {sample_count} 条有效 JD、{source_count} 家企业共同支撑。"
    )

    first_seen = min((record.get("publish_time", "") for record in position_records if record.get("publish_time")), default="")[:10]
    last_seen = max((record.get("publish_time", "") for record in position_records if record.get("publish_time")), default="")[:10]

    return PositionProfile(
        id=position_id,
        name=position_name,
        category=category,
        techStack=" · ".join(top_skill_names) if top_skill_names else "通用",
        level="",
        status="emerging" if growth_rate > 0.1 else "existing",
        description=description,
        firstSeen=first_seen,
        lastSeen=last_seen,
        confidence=round(min(0.99, 0.55 + min(0.4, source_count / 10)), 2),
        sampleCount=sample_count,
        aliases=POSITION_ALIASES.get(position_id, []),
        responsibilities=responsibilities,
        scenarios=scenarios,
        requirements=[requirement.model_dump() for requirement in requirements],
    ).model_dump()
