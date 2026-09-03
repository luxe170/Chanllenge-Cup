from __future__ import annotations

from typing import Literal
from datetime import datetime, timezone

from backend.app.demo_data import fresh
from backend.app.services.data_sources import processed_path, read_jsonl, write_jsonl
from backend.app.services.evolution_service import (
    SKILL_NAME_MAP,
    _load_job_records,
    compute_emerging_positions,
    compute_evolution_changes,
)


ReviewType = Literal["新岗位", "能力变更", "技能归一"]
ReviewStatus = Literal["pending", "approved", "rejected"]

_review_state: dict[str, dict[str, str]] = {}


def _load_review_state() -> None:
    for item in read_jsonl(processed_path("review_decisions.jsonl")):
        if item.get("id"):
            _review_state[item["id"]] = {"status": item.get("status", "pending"), "note": item.get("note", "")}


def _persist_review_state() -> None:
    rows = [{"id": review_id, **state} for review_id, state in sorted(_review_state.items())]
    write_jsonl(processed_path("review_decisions.jsonl"), rows)


def _state_for(review_id: str) -> dict[str, str]:
    _load_review_state()
    return _review_state.setdefault(review_id, {"status": "pending", "note": ""})


def _approve_position_into_graph(position_id: str) -> bool:
    from src.processing.build_graph_seed import merge_graph_data

    emerging = compute_emerging_positions(page=1, page_size=500)["items"]
    position = next((item for item in emerging if item.positionId == position_id), None)
    if position is None:
        return False

    records = [record for record in _load_job_records() if record.get("_position_id") == position_id]
    approved_id = f"approved_{position_id.removeprefix('candidate_')}"
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nodes = [
        {"mode": "panorama", "id": "approved_cluster_emerging", "name": "新兴技术岗位簇", "type": "cluster", "sampleCount": position.sampleCount, "confidence": position.confidence, "generatedAt": generated_at},
        {"mode": "panorama", "id": approved_id, "name": position.name, "type": "position", "trend": "new", "sampleCount": position.sampleCount, "firstSeen": position.firstSeen, "confidence": position.confidence, "generatedAt": generated_at},
        {"mode": "skill_reverse", "id": "approved_stack_emerging", "name": "新兴技术栈", "type": "stack", "sampleCount": position.sampleCount, "confidence": position.confidence, "generatedAt": generated_at},
        {"mode": "skill_reverse", "id": "approved_skill_cluster_emerging", "name": "新兴岗位核心技能簇", "type": "cluster", "sampleCount": position.sampleCount, "confidence": position.confidence, "generatedAt": generated_at},
        {"mode": "skill_reverse", "id": f"reverse_{approved_id}", "name": position.name, "type": "position", "trend": "new", "sampleCount": position.sampleCount, "firstSeen": position.firstSeen, "confidence": position.confidence, "generatedAt": generated_at},
    ]
    edges = [
        {"mode": "panorama", "source": approved_id, "target": "approved_cluster_emerging", "relationship": "BELONGS_TO", "generatedAt": generated_at},
        {"mode": "skill_reverse", "source": "approved_skill_cluster_emerging", "target": "approved_stack_emerging", "relationship": "BELONGS_TO", "generatedAt": generated_at},
    ]
    for index, skill in enumerate(position.skills):
        panorama_skill_id = f"approved_{skill.id}"
        reverse_skill_id = f"reverse_approved_{skill.id}"
        frequency = sum(SKILL_NAME_MAP.get(skill.id, skill.id) in f"{record.get('description', '')} {record.get('requirement', '')}" for record in records)
        weight = round(max(0.5, frequency / max(1, len(records))), 2)
        common = {"name": skill.name, "type": "skill", "trend": "new", "weight": weight, "sampleCount": max(1, frequency), "confidence": position.confidence, "generatedAt": generated_at}
        nodes.append({"mode": "panorama", "id": panorama_skill_id, **common})
        nodes.append({"mode": "skill_reverse", "id": reverse_skill_id, **common})
        requirement_type = "required" if index < 2 else "preferred"
        edges.append({"mode": "panorama", "source": approved_id, "target": panorama_skill_id, "relationship": "REQUIRES", "requirementType": requirement_type, "weight": weight, "confidence": position.confidence, "generatedAt": generated_at})
        edges.append({"mode": "skill_reverse", "source": reverse_skill_id, "target": "approved_skill_cluster_emerging", "relationship": "BELONGS_TO", "generatedAt": generated_at})
        edges.append({"mode": "skill_reverse", "source": f"reverse_{approved_id}", "target": reverse_skill_id, "relationship": "REQUIRES", "requirementType": requirement_type, "weight": weight, "confidence": position.confidence, "generatedAt": generated_at})

    node_path = processed_path("graph_nodes.jsonl")
    edge_path = processed_path("graph_edges.jsonl")
    merged_nodes, merged_edges = merge_graph_data(read_jsonl(node_path), read_jsonl(edge_path), nodes, edges)
    write_jsonl(node_path, merged_nodes)
    write_jsonl(edge_path, merged_edges)
    return True


def _build_change_reviews() -> list[dict]:
    try:
        changes = compute_evolution_changes(page=1, page_size=8)["items"]
    except Exception:
        return []

    items = []
    for change in changes:
        review_id = f"review_change_{change.id}"
        state = _state_for(review_id)
        items.append(
            {
                "id": review_id,
                "type": "能力变更",
                "title": f"{change.positionName} · {change.skillName}",
                "description": f"{change.skillName} 被识别为 {change.changeType}，由 {change.evidenceCount} 条 JD 证据支撑。",
                "confidence": change.confidence,
                "sources": [f"{change.evidenceCount} 条有效 JD", "岗位演化服务"],
                "createdAt": change.detectedAt,
                "status": state["status"],
                "targetId": change.id,
                "note": state["note"],
            }
        )
    return items


def _build_emerging_reviews() -> list[dict]:
    try:
        emerging = compute_emerging_positions(page=1, page_size=5)["items"]
    except Exception:
        return []

    items = []
    for position in emerging:
        review_id = f"review_position_{position.positionId}"
        state = _state_for(review_id)
        items.append(
            {
                "id": review_id,
                "type": "新岗位",
                "title": position.name,
                "description": position.description,
                "confidence": position.confidence,
                "sources": [f"{position.sourceCount} 个数据源", f"{position.sampleCount} 条样本"],
                "createdAt": position.firstSeen,
                "status": state["status"],
                "targetId": position.positionId,
                "note": state["note"],
            }
        )
    return items


def get_reviews(status: ReviewStatus | None = None, review_type: ReviewType | None = None, keyword: str = "") -> list[dict]:
    from backend.app.services.pipeline_service import pipeline_reviews

    all_pipeline_items = pipeline_reviews()
    pipeline_items = pipeline_reviews(status=status) if status else all_pipeline_items
    if all_pipeline_items:
        lowered = keyword.strip().lower()
        return fresh([
            item for item in pipeline_items
            if (not review_type or item["type"] == review_type)
            and (not lowered or lowered in f"{item['title']} {item['description']}".lower())
        ])
    candidates = read_jsonl(processed_path("review_candidates.jsonl"))
    if candidates:
        items = []
        for item in candidates:
            state = _state_for(item["id"])
            item["status"] = state["status"]
            item["note"] = state["note"]
            items.append(item)
    else:
        items = _build_emerging_reviews() + _build_change_reviews()
    lowered = keyword.strip().lower()
    filtered = []
    for item in pipeline_items + items:
        if status and item["status"] != status:
            continue
        if review_type and item["type"] != review_type:
            continue
        if lowered and lowered not in f"{item['title']} {item['description']}".lower():
            continue
        filtered.append(item)
    return fresh(filtered)


def decide_review(review_id: str, status: ReviewStatus, note: str = "") -> dict:
    from backend.app.services.pipeline_service import decide_pipeline_review, pipeline_reviews

    if any(item["id"] == review_id for item in pipeline_reviews()):
        return fresh(decide_pipeline_review(review_id, status, note))
    known_items = {item["id"]: item for item in get_reviews()}
    if review_id not in known_items:
        raise KeyError(f"unknown reviewId: {review_id}")
    _review_state[review_id] = {"status": status, "note": note}
    _persist_review_state()
    graph_updated = False
    item = known_items[review_id]
    if status == "approved" and item.get("type") == "新岗位":
        graph_updated = _approve_position_into_graph(item.get("targetId", ""))
    return fresh({"id": review_id, "status": status, "note": note, "graphUpdated": graph_updated})
