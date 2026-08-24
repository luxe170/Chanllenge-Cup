from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.demo_data import REVIEW_ITEMS, fresh
from backend.app.services.data_sources import write_jsonl
from backend.app.services.evolution_service import compute_emerging_positions, compute_evolution_changes


def build_review_candidates() -> list[dict]:
    items: list[dict] = []

    for position in compute_emerging_positions(page=1, page_size=100)["items"]:
        items.append(
            {
                "id": f"review_position_{position.positionId}",
                "type": "新岗位",
                "title": position.name,
                "description": position.description,
                "confidence": position.confidence,
                "sources": [f"{position.sourceCount} 个数据源", f"{position.sampleCount} 条样本"],
                "createdAt": position.firstSeen,
                "status": "pending",
                "targetId": position.positionId,
            }
        )

    for change in compute_evolution_changes(page=1, page_size=100)["items"]:
        items.append(
            {
                "id": f"review_change_{change.id}",
                "type": "能力变更",
                "title": f"{change.positionName} · {change.skillName}",
                "description": f"{change.skillName} 被识别为 {change.changeType}，由 {change.evidenceCount} 条 JD 证据支撑。",
                "confidence": change.confidence,
                "sources": [f"{change.evidenceCount} 条有效 JD", "岗位演化服务"],
                "createdAt": change.detectedAt,
                "status": "pending",
                "targetId": change.id,
            }
        )

    for item in fresh(REVIEW_ITEMS):
        if item["type"] == "技能归一":
            item["targetId"] = item.get("targetId", "skill_multi_agent")
            items.append(item)

    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rule-based review candidates from current backend computations.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    items = build_review_candidates()
    write_jsonl(args.output_dir / "review_candidates.jsonl", items)
    print(f"wrote {len(items)} review candidates")


if __name__ == "__main__":
    main()
