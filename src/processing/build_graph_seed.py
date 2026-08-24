from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import write_jsonl
from backend.app.services.evolution_service import (
    POSITION_NAME_MAP,
    SKILL_ALIASES,
    SKILL_NAME_MAP,
    _load_job_records,
    _match_aliases,
    _record_text,
)


POSITION_CLUSTER_MAP = {
    "pos_ai_agent_engineer": ("position_cluster_ai", "人工智能研发岗位簇"),
    "pos_llm_engineer": ("position_cluster_ai", "人工智能研发岗位簇"),
    "pos_java_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_frontend_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_data_analyst": ("position_cluster_data", "数据技术岗位簇"),
}

SKILL_CLUSTER_MAP = {
    "skill_llm": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_rag": ("skill_cluster_knowledge", "知识检索与工程技能簇"),
    "skill_prompt": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_multi_agent": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_rag_eval": ("skill_cluster_knowledge", "知识检索与工程技能簇"),
    "skill_python": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_java": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_spring": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_cloud_native": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_frontend": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_ai_codegen": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_sql": ("skill_cluster_data", "数据分析与处理技能簇"),
    "skill_excel": ("skill_cluster_data", "数据分析与处理技能簇"),
}


def _first_seen(records: list[dict[str, Any]]) -> str:
    values = [record.get("publish_time", "")[:10] for record in records if record.get("publish_time")]
    return min(values) if values else ""


def build_graph_seed() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = _load_job_records()
    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_position[record["_position_id"]].append(record)

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for position_id, position_records in by_position.items():
        cluster_id, cluster_name = POSITION_CLUSTER_MAP.get(position_id, ("position_cluster_other", "其他技术岗位簇"))
        nodes[cluster_id] = {
            "mode": "panorama",
            "id": cluster_id,
            "name": cluster_name,
            "type": "cluster",
            "sampleCount": nodes.get(cluster_id, {}).get("sampleCount", 0) + len(position_records),
            "confidence": 0.88,
        }
        nodes[position_id] = {
            "mode": "panorama",
            "id": position_id,
            "name": POSITION_NAME_MAP.get(position_id, position_id),
            "type": "position",
            "trend": "stable",
            "sampleCount": len(position_records),
            "firstSeen": _first_seen(position_records),
            "confidence": min(0.97, 0.62 + len(position_records) / 100),
        }
        edges[f"panorama:{position_id}->{cluster_id}"] = {
            "mode": "panorama",
            "source": position_id,
            "target": cluster_id,
            "relationship": "BELONGS_TO",
        }

        for skill_id, aliases in SKILL_ALIASES.items():
            hits = [record for record in position_records if _match_aliases(_record_text(record), aliases)]
            if not hits:
                continue
            weight = round(len(hits) / max(1, len(position_records)), 2)
            nodes[skill_id] = {
                "mode": "panorama",
                "id": skill_id,
                "name": SKILL_NAME_MAP.get(skill_id, skill_id),
                "type": "skill",
                "trend": "stable",
                "weight": weight,
                "sampleCount": len(hits),
                "firstSeen": _first_seen(hits),
                "confidence": min(0.97, 0.6 + weight * 0.35),
            }
            edges[f"panorama:{position_id}->{skill_id}"] = {
                "mode": "panorama",
                "source": position_id,
                "target": skill_id,
                "relationship": "REQUIRES",
                "requirementType": "required" if weight >= 0.55 else "preferred",
                "weight": weight,
                "confidence": min(0.97, 0.6 + weight * 0.35),
            }

            reverse_position_id = f"reverse_{position_id}"
            reverse_skill_id = f"reverse_{skill_id}"
            skill_cluster_id, skill_cluster_name = SKILL_CLUSTER_MAP.get(skill_id, ("skill_cluster_other", "通用技能簇"))
            reverse_cluster_id = f"reverse_{skill_cluster_id}"
            stack_id = "reverse_stack_next_it"

            nodes[stack_id] = {"mode": "skill_reverse", "id": stack_id, "name": "新一代信息技术栈", "type": "stack", "sampleCount": len(records), "confidence": 0.9}
            nodes[reverse_cluster_id] = {"mode": "skill_reverse", "id": reverse_cluster_id, "name": skill_cluster_name, "type": "cluster", "sampleCount": nodes.get(reverse_cluster_id, {}).get("sampleCount", 0) + len(hits), "confidence": 0.88}
            nodes[reverse_skill_id] = {"mode": "skill_reverse", "id": reverse_skill_id, "name": SKILL_NAME_MAP.get(skill_id, skill_id), "type": "skill", "trend": "stable", "weight": weight, "sampleCount": len(hits), "confidence": min(0.97, 0.6 + weight * 0.35)}
            nodes[reverse_position_id] = {"mode": "skill_reverse", "id": reverse_position_id, "name": POSITION_NAME_MAP.get(position_id, position_id), "type": "position", "trend": "stable", "weight": weight, "sampleCount": len(position_records), "confidence": min(0.97, 0.62 + len(position_records) / 100)}

            edges[f"skill_reverse:{reverse_cluster_id}->{stack_id}"] = {"mode": "skill_reverse", "source": reverse_cluster_id, "target": stack_id, "relationship": "BELONGS_TO"}
            edges[f"skill_reverse:{reverse_skill_id}->{reverse_cluster_id}"] = {"mode": "skill_reverse", "source": reverse_skill_id, "target": reverse_cluster_id, "relationship": "BELONGS_TO"}
            edges[f"skill_reverse:{reverse_position_id}->{reverse_skill_id}"] = {
                "mode": "skill_reverse",
                "source": reverse_position_id,
                "target": reverse_skill_id,
                "relationship": "REQUIRES",
                "requirementType": "required" if weight >= 0.55 else "preferred",
                "weight": weight,
                "confidence": min(0.97, 0.6 + weight * 0.35),
            }

    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for item in nodes.values():
        item["generatedAt"] = generated_at
    for item in edges.values():
        item["generatedAt"] = generated_at
    return list(nodes.values()), list(edges.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rule-based graph seed files from processed JD records.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    nodes, edges = build_graph_seed()
    write_jsonl(args.output_dir / "graph_nodes.jsonl", nodes)
    write_jsonl(args.output_dir / "graph_edges.jsonl", edges)
    print(f"wrote {len(nodes)} nodes and {len(edges)} edges")


if __name__ == "__main__":
    main()
