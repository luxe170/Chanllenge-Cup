from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import (
    POSITION_NAME_MAP,
    SKILL_NAME_MAP,
    _load_job_records,
)
from src.processing.extract_jd_predictions import (
    extract_predictions,
)


POSITION_CLUSTER_MAP = {
    "pos_ai_agent_engineer": ("position_cluster_ai", "人工智能研发岗位簇"),
    "pos_llm_engineer": ("position_cluster_ai", "人工智能研发岗位簇"),
    "pos_algorithm_engineer": ("position_cluster_ai", "人工智能研发岗位簇"),
    "pos_java_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_backend_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_frontend_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_test_engineer": ("position_cluster_software", "软件研发岗位簇"),
    "pos_data_analyst": ("position_cluster_data", "数据技术岗位簇"),
    "pos_data_engineer": ("position_cluster_data", "数据技术岗位簇"),
    "pos_cloud_infra_engineer": ("position_cluster_cloud", "云计算与基础设施岗位簇"),
    "pos_security_engineer": ("position_cluster_cloud", "云计算与基础设施岗位簇"),
    "pos_storage_database_engineer": ("position_cluster_cloud", "云计算与基础设施岗位簇"),
    "pos_hardware_engineer": ("position_cluster_hardware", "硬件与智能系统岗位簇"),
    "pos_game_engineer": ("position_cluster_game", "游戏与图形技术岗位簇"),
}

SKILL_CLUSTER_MAP = {
    "skill_llm": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_rag": ("skill_cluster_knowledge", "知识检索与工程技能簇"),
    "skill_prompt": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_multi_agent": ("skill_cluster_llm_app", "大模型应用开发技能簇"),
    "skill_rag_eval": ("skill_cluster_knowledge", "知识检索与工程技能簇"),
    "skill_python": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_go": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_cpp": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_java": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_spring": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_cloud_native": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_distributed": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_frontend": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_ai_codegen": ("skill_cluster_engineering", "工程实现技能簇"),
    "skill_algorithm": ("skill_cluster_algorithm", "算法与机器学习技能簇"),
    "skill_nlp": ("skill_cluster_algorithm", "算法与机器学习技能簇"),
    "skill_multimodal": ("skill_cluster_algorithm", "算法与机器学习技能簇"),
    "skill_testing": ("skill_cluster_quality", "质量与测试技能簇"),
    "skill_security": ("skill_cluster_security", "安全与风控技能簇"),
    "skill_database": ("skill_cluster_data", "数据分析与处理技能簇"),
    "skill_sql": ("skill_cluster_data", "数据分析与处理技能簇"),
    "skill_excel": ("skill_cluster_data", "数据分析与处理技能簇"),
    "skill_hardware": ("skill_cluster_hardware", "硬件与系统技能簇"),
}


def _first_seen(records: list[dict[str, Any]]) -> str:
    values = [
        str(record.get("publish_time") or record.get("publishTime") or "")[:10]
        for record in records
        if record.get("publish_time") or record.get("publishTime")
    ]
    return min(values) if values else ""


def _prediction_position_id(prediction: dict[str, Any]) -> str:
    return str(
        prediction.get("positionId")
        or prediction.get("predictedPositionId")
        or (prediction.get("position") or {}).get("id")
        or ""
    )


def _prediction_skill_ids(prediction: dict[str, Any]) -> list[str]:
    skills = prediction.get("skills") or prediction.get("predictedSkills") or []
    if not isinstance(skills, list):
        return []
    result = []
    for skill in skills:
        if isinstance(skill, dict) and skill.get("id"):
            result.append(str(skill["id"]))
    return sorted(set(result))


def _split_for_path(input_path: Path | str | None) -> str:
    if input_path is None:
        return ""
    name = Path(input_path).name
    if name.startswith("graph_train"):
        return "graph_train"
    if name.startswith("jd_test"):
        return "jd_test"
    if name.startswith("jd_holdout"):
        return "holdout"
    return ""


def build_graph_seed(
    input_path: Path | str | None = None,
    *,
    predictions: list[dict[str, Any]] | None = None,
    split: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if predictions is None:
        records = _load_job_records(input_path)
        predictions = extract_predictions(records, split=split or _split_for_path(input_path))

    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prediction in predictions:
        position_id = _prediction_position_id(prediction)
        if position_id:
            by_position[position_id].append(prediction)

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for position_id, position_records in by_position.items():
        # New-position candidates enter the formal graph only after review and
        # registration in the standard position library.
        if position_id.startswith("candidate_"):
            continue
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

        skill_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for prediction in position_records:
            for skill_id in _prediction_skill_ids(prediction):
                skill_hits[skill_id].append(prediction)

        for skill_id, hits in sorted(skill_hits.items()):
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
            nodes[reverse_cluster_id] = {"mode": "skill_reverse", "id": reverse_cluster_id, "name": skill_cluster_name, "type": "cluster", "sampleCount": nodes.get(reverse_cluster_id, {}).get("sampleCount", 0) + len(hits), "confidence": 0.88}
            nodes[reverse_skill_id] = {"mode": "skill_reverse", "id": reverse_skill_id, "name": SKILL_NAME_MAP.get(skill_id, skill_id), "type": "skill", "trend": "stable", "weight": weight, "sampleCount": len(hits), "confidence": min(0.97, 0.6 + weight * 0.35)}
            nodes[reverse_position_id] = {"mode": "skill_reverse", "id": reverse_position_id, "name": POSITION_NAME_MAP.get(position_id, position_id), "type": "position", "trend": "stable", "weight": weight, "sampleCount": len(position_records), "confidence": min(0.97, 0.62 + len(position_records) / 100)}

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

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for item in nodes.values():
        item["generatedAt"] = generated_at
    for item in edges.values():
        item["generatedAt"] = generated_at
    return list(nodes.values()), list(edges.values())


def _identity_name(name: Any) -> str:
    normalized = "".join(str(name or "").lower().split())
    aliases = {
        "java后端工程师": "java开发工程师",
        "java后端开发工程师": "java开发工程师",
        "高级java开发工程师": "java开发工程师",
    }
    return aliases.get(normalized, normalized)


def merge_graph_data(
    existing_nodes: list[dict[str, Any]],
    existing_edges: list[dict[str, Any]],
    incoming_nodes: list[dict[str, Any]],
    incoming_edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Idempotently merge a generated batch into the currently served graph."""
    existing_nodes = [
        node for node in existing_nodes
        if not str(node.get("id", "")).startswith(("candidate_", "reverse_candidate_"))
    ]
    nodes_by_id = {(node.get("mode"), node.get("id")): dict(node) for node in existing_nodes}
    identity_to_id = {
        (node.get("mode"), node.get("type"), _identity_name(node.get("name"))): node.get("id")
        for node in existing_nodes
    }
    id_remap: dict[tuple[Any, Any], Any] = {}

    for node in incoming_nodes:
        mode = node.get("mode")
        incoming_id = node.get("id")
        identity = (mode, node.get("type"), _identity_name(node.get("name")))
        target_id = identity_to_id.get(identity, incoming_id)
        id_remap[(mode, incoming_id)] = target_id
        key = (mode, target_id)
        if key in nodes_by_id:
            current = nodes_by_id[key]
            merged = {**current, **node, "id": target_id}
            merged["firstSeen"] = min(filter(None, [current.get("firstSeen"), node.get("firstSeen")]), default="")
            merged["sampleCount"] = max(int(current.get("sampleCount", 0)), int(node.get("sampleCount", 0)))
            merged["dataKind"] = "mixed" if current.get("dataKind") == "demo" else node.get("dataKind", current.get("dataKind"))
            nodes_by_id[key] = merged
        else:
            inserted = dict(node)
            inserted["id"] = target_id
            nodes_by_id[key] = inserted
            identity_to_id[identity] = target_id

    edges_by_key = {
        (edge.get("mode"), edge.get("source"), edge.get("target"), edge.get("relationship")): dict(edge)
        for edge in existing_edges
    }
    for edge in incoming_edges:
        mode = edge.get("mode")
        merged = dict(edge)
        merged["source"] = id_remap.get((mode, edge.get("source")), edge.get("source"))
        merged["target"] = id_remap.get((mode, edge.get("target")), edge.get("target"))
        key = (mode, merged.get("source"), merged.get("target"), merged.get("relationship"))
        edges_by_key[key] = {**edges_by_key.get(key, {}), **merged}

    valid_ids = set(nodes_by_id)
    valid_edges = [
        edge for edge in edges_by_key.values()
        if (edge.get("mode"), edge.get("source")) in valid_ids
        and (edge.get("mode"), edge.get("target")) in valid_ids
    ]
    return list(nodes_by_id.values()), valid_edges


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rule-based graph seed files from processed JD records.")
    parser.add_argument("--input", type=Path, default=None, help="JSONL JD records used to build graph seed files.")
    parser.add_argument("--predictions-input", type=Path, default=None, help="Per-JD extraction predictions used to build the graph.")
    parser.add_argument("--split", default="graph_train", help="Split to read from --predictions-input.")
    parser.add_argument(
        "--extraction-output",
        type=Path,
        default=None,
        help="Optional path to write per-JD extraction predictions before graph aggregation.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--replace", action="store_true", help="Replace the existing graph instead of merging into it.")
    args = parser.parse_args()

    extraction_predictions: list[dict[str, Any]] | None = None
    if args.predictions_input is not None:
        extraction_predictions = [
            item for item in read_jsonl(args.predictions_input)
            if not args.split or item.get("split") == args.split
        ]
    elif args.extraction_output is not None:
        records = _load_job_records(args.input)
        extraction_predictions = extract_predictions(records, split=args.split or _split_for_path(args.input))
        write_jsonl(args.extraction_output, extraction_predictions)

    incoming_nodes, incoming_edges = build_graph_seed(args.input, predictions=extraction_predictions, split=args.split)
    node_path = args.output_dir / "graph_nodes.jsonl"
    edge_path = args.output_dir / "graph_edges.jsonl"
    if args.replace:
        nodes, edges = incoming_nodes, incoming_edges
        operation = "replaced"
    else:
        nodes, edges = merge_graph_data(read_jsonl(node_path), read_jsonl(edge_path), incoming_nodes, incoming_edges)
        operation = "merged"
    write_jsonl(node_path, nodes)
    write_jsonl(edge_path, edges)
    if args.extraction_output is not None and extraction_predictions is not None:
        print(f"wrote graph extraction predictions: {len(extraction_predictions)} records -> {args.extraction_output}")
    elif args.predictions_input is not None:
        print(f"read graph extraction predictions: {len(extraction_predictions or [])} records <- {args.predictions_input}")
    print(f"{operation} graph: {len(nodes)} nodes and {len(edges)} edges ({len(incoming_nodes)} incoming nodes)")


if __name__ == "__main__":
    main()
