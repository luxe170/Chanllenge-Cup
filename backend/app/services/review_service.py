from __future__ import annotations

from typing import Literal

from backend.app.demo_data import REVIEW_ITEMS, fresh
from backend.app.services.data_sources import processed_path, read_jsonl
from backend.app.services.evolution_service import compute_emerging_positions, compute_evolution_changes


ReviewType = Literal["新岗位", "能力变更", "技能归一"]
ReviewStatus = Literal["pending", "approved", "rejected"]

_review_state: dict[str, dict[str, str]] = {}


def _state_for(review_id: str) -> dict[str, str]:
    return _review_state.setdefault(review_id, {"status": "pending", "note": ""})


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


def _build_skill_normalization_reviews() -> list[dict]:
    items = []
    for item in fresh(REVIEW_ITEMS):
        if item["type"] != "技能归一":
            continue
        item["targetId"] = item.get("targetId", "skill_multi_agent")
        state = _state_for(item["id"])
        item["status"] = state["status"]
        item["note"] = state["note"]
        items.append(item)
    return items


def get_reviews(status: ReviewStatus | None = None, review_type: ReviewType | None = None, keyword: str = "") -> list[dict]:
    candidates = read_jsonl(processed_path("review_candidates.jsonl"))
    if candidates:
        items = []
        for item in candidates:
            state = _state_for(item["id"])
            item["status"] = state["status"]
            item["note"] = state["note"]
            items.append(item)
    else:
        items = _build_emerging_reviews() + _build_change_reviews() + _build_skill_normalization_reviews()
    lowered = keyword.strip().lower()
    filtered = []
    for item in items:
        if status and item["status"] != status:
            continue
        if review_type and item["type"] != review_type:
            continue
        if lowered and lowered not in f"{item['title']} {item['description']}".lower():
            continue
        filtered.append(item)
    return fresh(filtered)


def decide_review(review_id: str, status: ReviewStatus, note: str = "") -> dict:
    known_ids = {item["id"] for item in get_reviews()}
    if review_id not in known_ids:
        raise KeyError(f"unknown reviewId: {review_id}")
    _review_state[review_id] = {"status": status, "note": note}
    return fresh({"id": review_id, "status": status, "note": note})
